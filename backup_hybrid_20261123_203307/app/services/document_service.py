
import logging
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
from app.services.storage_service import (
    save_document_file,
    delete_document_file,
)
from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service


# Configure logging so ingestion and indexing failures can be diagnosed.
logger = logging.getLogger(__name__)


def process_uploaded_document(
    db: Session,
    current_user: User,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    workspace_id: UUID | None = None,
) -> Document:
    """
    Upload, process, embed and index a document.

    PostgreSQL stores the authoritative document chunks.
    Qdrant stores their embeddings and searchable payload.
    """

    # Verify that the selected workspace exists before uploading the file.
    if workspace_id is not None:
        workspace = db.get(Workspace, workspace_id)

        if workspace is None:
            raise ValueError("Selected workspace does not exist.")

    # Determine the file extension for storage and PDF-specific processing.
    extension = Path(filename).suffix.lower()

    # Upload the original document to private Supabase Storage.
    storage_key = save_document_file(
        file_bytes=file_bytes,
        extension=extension,
        mime_type=mime_type,
    )

    # Create the initial document record before starting processing.
    # Its status remains "processing" until vector indexing succeeds.
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
        # Persist the document record and obtain its database-generated ID.
        db.add(document)
        db.commit()
        db.refresh(document)

    except Exception:
        # Roll back the database transaction if document creation fails.
        db.rollback()

        # Remove the uploaded file because no document record was created.
        try:
            delete_document_file(storage_key)
        except Exception:
            logger.warning(
                "Could not clean up uploaded file: %s",
                storage_key,
                exc_info=True,
            )

        raise

    # Track whether Qdrant upsert was attempted so partial indexing
    # can be cleaned up if a later operation fails.
    qdrant_upsert_attempted = False

    try:
        # Extract text from the document, including embedded-image OCR.
        segments = extract_document(file_bytes, filename)

        if not segments:
            raise ValueError(
                "No readable text was found in the document."
            )

        # Split the extracted text into overlapping chunks.
        chunks = chunk_extracted_segments(segments)

        if not chunks:
            raise ValueError(
                "Document processing did not produce any text chunks."
            )

        # Determine the total page count for PDF documents.
        page_count = None

        if extension == ".pdf":
            with pymupdf.open(
                stream=file_bytes,
                filetype="pdf",
            ) as pdf:
                page_count = pdf.page_count

        # Create PostgreSQL chunk records using the existing schema.
        database_chunks = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                content=chunk.content,
            )
            for chunk in chunks
        ]

        # Save all chunks before generating embeddings.
        # PostgreSQL remains the source of truth for extracted text.
        db.add_all(database_chunks)
        document.page_count = page_count
        db.commit()

        # Refresh the document and chunk records after the database commit.
        # This ensures database-generated chunk UUIDs are available.
        db.refresh(document)

        for database_chunk in database_chunks:
            db.refresh(database_chunk)

        logger.info(
            "Saved %s chunks for document %s.",
            len(database_chunks),
            document.id,
        )

        # Generate one dense BGE-M3 embedding for each saved chunk.
        chunk_texts = [
            database_chunk.content
            for database_chunk in database_chunks
        ]

        embeddings = embedding_service.embed_documents(chunk_texts)

        # Make sure every chunk has exactly one corresponding embedding.
        if len(embeddings) != len(database_chunks):
            raise RuntimeError(
                "The number of generated embeddings does not match "
                "the number of document chunks."
            )

        # Create the Qdrant collection and its filtering indexes if needed.
        qdrant_service.ensure_collection()

        # Prepare Qdrant points using existing PostgreSQL chunk UUIDs.
        qdrant_chunks = []

        for database_chunk, vector in zip(
            database_chunks,
            embeddings,
        ):
            # Store identifiers as strings for consistent Qdrant filtering.
            payload = {
                "user_id": str(document.user_id),
                "document_id": str(document.id),
                "chunk_id": str(database_chunk.id),
                "filename": document.filename,
                "chunk_index": database_chunk.chunk_index,
                "page_start": database_chunk.page_start,
                "page_end": database_chunk.page_end,
                "text": database_chunk.content,
            }

            # Workspace is optional, so omit it when no workspace is assigned.
            if document.workspace_id is not None:
                payload["workspace_id"] = str(document.workspace_id)

            qdrant_chunks.append(
                {
                    "chunk_id": database_chunk.id,
                    "vector": vector,
                    "payload": payload,
                }
            )

        # Mark the operation as attempted before calling Qdrant.
        # If the request fails partially, cleanup will still be attempted.
        qdrant_upsert_attempted = True

        # Store vectors and their searchable text/metadata in Qdrant.
        qdrant_service.upsert_chunks(qdrant_chunks)

        logger.info(
            "Successfully indexed %s chunks for document %s.",
            len(qdrant_chunks),
            document.id,
        )

        # Mark the document ready only after Qdrant indexing succeeds.
        document.status = "ready"
        db.commit()
        db.refresh(document)

        logger.info(
            "Document %s is ready.",
            document.id,
        )

        return document

    except Exception as exc:
        # Roll back any incomplete PostgreSQL transaction.
        db.rollback()

        # Attempt to remove partially indexed Qdrant points.
        # PostgreSQL chunks and the original Supabase file are retained.
        if qdrant_upsert_attempted:
            try:
                qdrant_service.delete_document_chunks(document.id)

                logger.info(
                    "Cleaned up Qdrant points for failed document %s.",
                    document.id,
                )

            except Exception:
                logger.exception(
                    "Could not clean up Qdrant points for document %s.",
                    document.id,
                )

        # Keep the document record and mark processing/indexing as failed.
        try:
            failed_document = db.get(Document, document.id)

            if failed_document is not None:
                failed_document.status = "failed"
                db.commit()

        except Exception:
            db.rollback()

            logger.exception(
                "Could not mark document %s as failed.",
                document.id,
            )

        # Preserve validation errors so the API can return HTTP 422.
        if isinstance(exc, ValueError):
            raise

        # Log the original technical error without exposing its details
        # to the API client.
        logger.exception(
            "Document processing or vector indexing failed for %s.",
            document.id,
        )

        # Let FastAPI handle unexpected processing/infrastructure failures
        # as server errors rather than incorrectly reporting HTTP 422.
        raise RuntimeError(
            "Document processing or vector indexing failed."
        ) from exc
