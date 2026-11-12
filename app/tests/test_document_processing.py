
from io import BytesIO
import re

import pymupdf
import pytest

from PIL import Image, ImageDraw, ImageFont
from docx import Document as WordDocument

from app.services.document_processing_service import (
    extract_document,
    chunk_extracted_segments,
)


def create_test_image():
    """Create an image containing text for OCR testing."""

    image = Image.new("RGB", (1800, 400), "white")
    draw = ImageDraw.Draw(image)

    font = ImageFont.load_default(size=80)

    draw.text(
        (80, 120),
        "DOCSPACE OCR TEST 12345",
        fill="black",
        font=font,
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def normalize(text):
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def test_txt_extraction():
    content = b"DocSpace TXT extraction test."

    segments = extract_document(content, "sample.txt")

    assert len(segments) == 1
    assert "DocSpace TXT extraction test." in segments[0].content
    assert segments[0].page_start is None


def test_pdf_embedded_image_ocr():
    image_bytes = create_test_image()

    pdf = pymupdf.open()
    page = pdf.new_page(width=600, height=300)

    page.insert_image(
        page.rect,
        stream=image_bytes,
    )

    pdf_bytes = pdf.tobytes()
    pdf.close()

    segments = extract_document(pdf_bytes, "sample.pdf")

    extracted_text = " ".join(
        segment.content for segment in segments
    )

    assert "Embedded image OCR" in extracted_text
    assert "DOCSPACEOCRTEST12345" in normalize(extracted_text)
    assert segments[0].page_start == 1


def test_docx_embedded_image_ocr():
    image_bytes = create_test_image()

    word_document = WordDocument()
    word_document.add_paragraph("DocSpace DOCX text test.")

    word_document.add_picture(BytesIO(image_bytes))

    buffer = BytesIO()
    word_document.save(buffer)

    segments = extract_document(
        buffer.getvalue(),
        "sample.docx",
    )

    extracted_text = " ".join(
        segment.content for segment in segments
    )

    assert "DocSpace DOCX text test." in extracted_text
    assert "Embedded image OCR" in extracted_text
    assert "DOCSPACEOCRTEST12345" in normalize(extracted_text)
    assert segments[0].page_start is None


def test_text_chunking():
    segments = extract_document(
        b"A " * 1500,
        "sample.txt",
    )

    chunks = chunk_extracted_segments(
        segments,
        chunk_size=1000,
        overlap=150,
    )

    assert len(chunks) > 1

    for index, chunk in enumerate(chunks):
        assert chunk.chunk_index == index
        assert chunk.content.strip()


def test_unsupported_file_type():
    with pytest.raises(ValueError):
        extract_document(b"test", "sample.png")
