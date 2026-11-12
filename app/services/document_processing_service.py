
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import os
import zipfile

import pymupdf
import pytesseract

from PIL import Image
from docx import Document as WordDocument


# Optional: use an explicitly configured Tesseract executable.
# Otherwise, pytesseract uses Tesseract from the system PATH.
tesseract_path = os.getenv("TESSERACT_CMD")

if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path


@dataclass
class ExtractedSegment:
    content: str
    page_start: int | None = None
    page_end: int | None = None


@dataclass
class TextChunk:
    chunk_index: int
    content: str
    page_start: int | None = None
    page_end: int | None = None


def _ocr_image(image_bytes: bytes) -> str:
    """Extract text from an image using Tesseract OCR."""

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image = image.convert("RGB")
            return pytesseract.image_to_string(
                image,
                lang="eng"
            ).strip()

    except Exception as exc:
        raise ValueError(
            f"Could not process an embedded image: {exc}"
        ) from exc


def extract_pdf(file_bytes: bytes) -> list[ExtractedSegment]:
    """Extract PDF text and OCR its embedded images."""

    segments = []

    try:
        with pymupdf.open(
            stream=file_bytes,
            filetype="pdf"
        ) as pdf:

            for page_number, page in enumerate(pdf, start=1):

                extracted_text = page.get_text("text").strip()
                image_texts = []

                processed_images = set()

                for image_info in page.get_images(full=True):
                    image_xref = image_info[0]

                    if image_xref in processed_images:
                        continue

                    processed_images.add(image_xref)

                    image_data = pdf.extract_image(image_xref)

                    if not image_data:
                        continue

                    ocr_text = _ocr_image(image_data["image"])

                    if ocr_text:
                        image_texts.append(ocr_text)

                # Fallback for scanned pages where image extraction
                # does not provide usable text.
                if not extracted_text and not image_texts:
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(2, 2),
                        alpha=False
                    )

                    rendered_image = pixmap.tobytes("png")
                    rendered_text = _ocr_image(rendered_image)

                    if rendered_text:
                        image_texts.append(rendered_text)

                page_content = extracted_text

                if image_texts:
                    page_content += (
                        "\n\n[Embedded image OCR]\n"
                        + "\n\n".join(image_texts)
                    )

                if page_content.strip():
                    segments.append(
                        ExtractedSegment(
                            content=page_content.strip(),
                            page_start=page_number,
                            page_end=page_number
                        )
                    )

    except Exception as exc:
        raise ValueError(
            f"Could not process PDF file: {exc}"
        ) from exc

    return segments


def extract_docx(file_bytes: bytes) -> list[ExtractedSegment]:
    """Extract DOCX paragraphs, tables and embedded image text."""

    try:
        if not zipfile.is_zipfile(BytesIO(file_bytes)):
            raise ValueError("Invalid DOCX file.")

        word_document = WordDocument(BytesIO(file_bytes))

        text_parts = []

        # Extract paragraphs.
        for paragraph in word_document.paragraphs:
            text = paragraph.text.strip()

            if text:
                text_parts.append(text)

        # Extract tables.
        for table in word_document.tables:
            for row in table.rows:
                cells = [
                    cell.text.strip()
                    for cell in row.cells
                    if cell.text.strip()
                ]

                if cells:
                    text_parts.append(" | ".join(cells))

        # Extract and OCR embedded images.
        image_texts = []
        processed_images = set()

        for relationship in word_document.part.rels.values():

            if not relationship.reltype.endswith("/image"):
                continue

            if relationship.is_external:
                continue

            image_part = relationship.target_part
            image_name = str(image_part.partname)

            if image_name in processed_images:
                continue

            processed_images.add(image_name)

            ocr_text = _ocr_image(image_part.blob)

            if ocr_text:
                image_texts.append(ocr_text)

        if image_texts:
            text_parts.append(
                "[Embedded image OCR]\n"
                + "\n\n".join(image_texts)
            )

        content = "\n\n".join(text_parts).strip()

        if not content:
            return []

        return [
            ExtractedSegment(
                content=content,
                page_start=None,
                page_end=None
            )
        ]

    except Exception as exc:
        raise ValueError(
            f"Could not process DOCX file: {exc}"
        ) from exc


def extract_txt(file_bytes: bytes) -> list[ExtractedSegment]:
    """Extract text from a UTF-8 TXT file."""

    try:
        content = file_bytes.decode("utf-8-sig").strip()

    except UnicodeDecodeError as exc:
        raise ValueError(
            "TXT file must use UTF-8 encoding."
        ) from exc

    if not content:
        return []

    return [
        ExtractedSegment(
            content=content,
            page_start=None,
            page_end=None
        )
    ]


def extract_document(
    file_bytes: bytes,
    filename: str
) -> list[ExtractedSegment]:
    """Choose the correct extraction method based on file extension."""

    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        return extract_pdf(file_bytes)

    if extension == ".docx":
        return extract_docx(file_bytes)

    if extension == ".txt":
        return extract_txt(file_bytes)

    raise ValueError(
        "Unsupported file type. Only PDF, DOCX and TXT are accepted."
    )


def chunk_extracted_segments(
    segments: list[ExtractedSegment],
    chunk_size: int = 1000,
    overlap: int = 150
) -> list[TextChunk]:
    """Split extracted text into overlapping chunks."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be non-negative and smaller than chunk_size."
        )

    chunks = []

    for segment in segments:
        text = segment.content.strip()

        if not text:
            continue

        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Prefer ending at a word boundary.
            if end < len(text):
                boundary = text.rfind(" ", start, end)

                if boundary > start:
                    end = boundary

            chunk_content = text[start:end].strip()

            if chunk_content:
                chunks.append(
                    TextChunk(
                        chunk_index=len(chunks),
                        content=chunk_content,
                        page_start=segment.page_start,
                        page_end=segment.page_end
                    )
                )

            if end >= len(text):
                break

            start = max(end - overlap, start + 1)

    return chunks
