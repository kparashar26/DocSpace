
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


# Configure logging for document ingestion and indexing.
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

    PostgreSQL stores the original extracted chunks.
    Supabase Storage stores the original document.
    Qdrant stores dense and sparse vectors with searchable metadata.
    """

    # Verify the selected workspace before uploading the document.
    if workspace_id is not None:
        workspace = db.get(Workspace, workspace_id)

        if workspace is None:
            raise ValueError("Selected workspace does not exist.")

    # Determine the document extension.
    extension = Path(filename).suffix.lower()

    # Upload the original file to private Supabase Storage.
    storage_key = save_document_file(
        file_bytes=file_bytes,
        extension=extension,
        mime_type=mime_type,
    )

    # Create the initial document record in PostgreSQL.
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
        # Save the document record and obtain its database-generated ID.
        db.add(document)
        db.commit()
        db.refresh(document)

    except Exception:
        # Roll back the database transaction if document creation fails.
        db.rollback()

        # Remove the uploaded file because its database record was not created.
        try:
            delete_document_file(storage_key)
        except Exception:
            logger.warning(
                "Could not clean up uploaded file: %s",
                storage_key,
                exc_info=True,
            )

        raise

    # Track whether Qdrant indexing was attempted.
    qdrant_upsert_attempted = False

    try:
        # Extract text and page information from the uploaded document.
        segments = extract_document(file_bytes, filename)

        if not segments:
            raise ValueError("No readable text was found in the document.")

        # Preserve the existing chunking implementation and configuration.
        chunks = chunk_extracted_segments(segments)

        if not chunks:
            raise ValueError("Document processing did not produce any text chunks.")

        # Determine the PDF page count when applicable.
        page_count = None

        if extension == ".pdf":
            with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
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

        # Save the original extracted text before generating embeddings.
        db.add_all(database_chunks)
        document.page_count = page_count
        db.commit()

        # Refresh records to obtain their database-generated UUIDs.
        db.refresh(document)

        for database_chunk in database_chunks:
            db.refresh(database_chunk)

        logger.info(
            "Saved %s chunks for document %s.",
            len(database_chunks),
            document.id,
        )

        # Extract the text that will be embedded by BGE-M3.
        chunk_texts = [
            database_chunk.content
            for database_chunk in database_chunks
        ]

        # Generate dense and sparse embeddings together.
        embeddings = embedding_service.embed_documents_with_sparse(
            chunk_texts
        )

        # Ensure each chunk has exactly one dense and sparse representation.
        if len(embeddings) != len(database_chunks):
            raise RuntimeError(
                "Embedding count does not match document chunk count."
            )

        # Ensure the Qdrant collection supports both vector types.
        qdrant_service.ensure_collection()

        qdrant_chunks = []

        for database_chunk, embedding in zip(database_chunks, embeddings):
            # Prepare metadata using existing PostgreSQL fields.
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

            # Include workspace metadata only when one is assigned.
            if document.workspace_id is not None:
                payload["workspace_id"] = str(document.workspace_id)

            # Use the exact vector structure expected by QdrantService.
            qdrant_chunks.append(
                {
                    "chunk_id": database_chunk.id,
                    "dense_vector": embedding["dense"],
                    "sparse_vector": embedding["sparse"],
                    "payload": payload,
                }
            )

        # Mark the operation before sending points to Qdrant.
        qdrant_upsert_attempted = True

        # Store both embeddings and the existing searchable payload.
        qdrant_service.upsert_chunks(qdrant_chunks)

        logger.info(
            "Indexed %s dense and sparse chunks for document %s.",
            len(qdrant_chunks),
            document.id,
        )

        # Mark the document ready only after successful hybrid indexing.
        document.status = "ready"
        db.commit()
        db.refresh(document)

        logger.info("Document %s is ready.", document.id)

        return document

    except Exception as exc:
        # Roll back any incomplete PostgreSQL transaction.
        db.rollback()

        # Delete partially indexed Qdrant points if indexing was attempted.
        if qdrant_upsert_attempted:
            try:
                qdrant_service.delete_document_chunks(document.id)
            except Exception:
                logger.exception(
                    "Could not clean up Qdrant points for document %s.",
                    document.id,
                )

        # Mark the document as failed while preserving its original file
        # and PostgreSQL chunks for diagnosis or future reprocessing.
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

        # Preserve validation errors for the API's existing HTTP 422 handling.
        if isinstance(exc, ValueError):
            raise

        # Log unexpected errors and return a controlled server error.
        logger.exception(
            "Document processing or hybrid indexing failed for %s.",
            document.id,
        )

        raise RuntimeError(
            "Document processing or vector indexing failed."
        ) from exc
