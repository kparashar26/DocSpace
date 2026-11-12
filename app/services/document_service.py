
from pathlib import Path
from uuid import UUID

import pymupdf
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.workspace import Workspace
from app.models.user import User

from app.services.document_processing_service import (
    extract_document,
    chunk_extracted_segments,
)
from app.services.storage_service import save_document_file


def process_uploaded_document(
    db: Session,
    current_user: User,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    workspace_id: UUID | None = None,
) -> Document:

    # Verify the selected workspace exists.
    if workspace_id is not None:
        workspace = db.get(Workspace, workspace_id)

        if workspace is None:
            raise ValueError("Selected workspace does not exist.")

    extension = Path(filename).suffix.lower()

    # Save the original file.
    storage_key = save_document_file(file_bytes, extension)

    document = Document(
        user_id=current_user.id,
        workspace_id=workspace_id,
        filename=filename,
        source_type="upload",
        source_file_id=None,
        storage_key=storage_key,
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        status="processing",
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)

    except Exception:
        db.rollback()

        from app.services.storage_service import delete_document_file

        try:
            delete_document_file(storage_key)
        except Exception:
            pass

        raise

    try:
        # Extract document text and embedded-image OCR.
        segments = extract_document(file_bytes, filename)

        if not segments:
            raise ValueError(
                "No readable text was found in the document."
            )

        # Split extracted text into chunks.
        chunks = chunk_extracted_segments(segments)

        if not chunks:
            raise ValueError(
                "Document processing did not produce any text chunks."
            )

        # Determine PDF page count.
        page_count = None

        if extension == ".pdf":
            with pymupdf.open(
                stream=file_bytes,
                filetype="pdf",
            ) as pdf:
                page_count = pdf.page_count

        # Save chunks using the existing document_chunks table.
        db.add_all([
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                content=chunk.content,
            )
            for chunk in chunks
        ])

        document.page_count = page_count
        document.status = "ready"

        db.commit()
        db.refresh(document)

        return document

    except Exception as exc:
        db.rollback()

        # Keep the document record and mark processing as failed.
        try:
            failed_document = db.get(Document, document.id)

            if failed_document is not None:
                failed_document.status = "failed"
                db.commit()

        except Exception:
            db.rollback()

        if isinstance(exc, ValueError):
            raise

        raise ValueError(
            "An unexpected error occurred while processing the document."
        ) from exc
