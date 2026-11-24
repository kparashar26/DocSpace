
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.workspace import Workspace

from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service


@dataclass
class RetrievalResult:
    """Represents one relevant chunk retrieved from PostgreSQL."""

    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    page_start: int | None
    page_end: int | None
    text: str
    score: float


class RetrievalService:
    """
    Retrieves relevant document chunks using BGE-M3 hybrid search.

    Qdrant handles vector retrieval and ranking.
    PostgreSQL verifies ownership and supplies authoritative chunk text.
    """

    def __init__(self):
        # Reuse the application's shared embedding and Qdrant services.
        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service

    def retrieve(
        self,
        db: Session,
        question: str,
        user_id: UUID,
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        limit: int = 5,
    ) -> list[RetrievalResult]:

        # Validate the authenticated user's ID.
        if not isinstance(user_id, UUID):
            raise ValueError("A valid authenticated user ID is required.")

        # Reject empty questions before generating embeddings.
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question cannot be empty.")

        question = question.strip()

        # Keep the retrieval limit within a reasonable range.
        if not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("Retrieval limit must be between 1 and 20.")

        # Verify that an optional document belongs to the current user.
        if document_id is not None:
            selected_document = db.execute(
                select(Document.id).where(
                    Document.id == document_id,
                    Document.user_id == user_id,
                )
            ).scalar_one_or_none()

            if selected_document is None:
                raise ValueError("Document not found or access denied.")

        # Verify that an optional shared workspace exists.
        if workspace_id is not None:
            selected_workspace = db.get(Workspace, workspace_id)

            if selected_workspace is None:
                raise ValueError("Workspace not found.")

        # Generate dense and sparse embeddings for the question.
        query_embeddings = self.embedding_service.embed_query_with_sparse(
            question
        )

        # Retrieve a larger candidate set before final RRF ranking.
        candidate_limit = min(max(limit * 4, 20), 100)

        # Execute hybrid dense + sparse retrieval in Qdrant.
        points = self.qdrant_service.search_hybrid(
            dense_query_vector=query_embeddings["dense"],
            sparse_query_vector=query_embeddings["sparse"],
            user_id=user_id,
            document_id=document_id,
            workspace_id=workspace_id,
            limit=limit,
            candidate_limit=candidate_limit,
        )

        # Return an empty result when Qdrant finds no matching points.
        if not points:
            return []

        # Collect valid chunk IDs from Qdrant's ranked results.
        ranked_chunk_ids = []

        for point in points:
            payload = point.payload or {}

            # Check the user identifier before trusting the point.
            if payload.get("user_id") != str(user_id):
                continue

            try:
                chunk_id = UUID(str(payload["chunk_id"]))
                payload_document_id = UUID(str(payload["document_id"]))

            except (KeyError, ValueError, TypeError):
                # Ignore points with missing or malformed identifiers.
                continue

            # Preserve the point's claimed document ID for cross-checking.
            ranked_chunk_ids.append(
                (chunk_id, payload_document_id, float(point.score))
            )

        if not ranked_chunk_ids:
            return []

        # Fetch authoritative chunk and document records from PostgreSQL.
        chunk_ids = list({item[0] for item in ranked_chunk_ids})

        statement = (
            select(DocumentChunk, Document)
            .join(
                Document,
                Document.id == DocumentChunk.document_id,
            )
            .where(
                DocumentChunk.id.in_(chunk_ids),
                Document.user_id == user_id,
                Document.status == "ready",
            )
        )

        # Apply optional document-level filtering in PostgreSQL too.
        if document_id is not None:
            statement = statement.where(
                Document.id == document_id
            )

        # Apply optional workspace filtering in PostgreSQL too.
        if workspace_id is not None:
            statement = statement.where(
                Document.workspace_id == workspace_id
            )

        database_rows = db.execute(statement).all()

        # Index verified database records by their chunk IDs.
        verified_chunks = {
            chunk.id: (chunk, document)
            for chunk, document in database_rows
        }

        results = []

        # Preserve Qdrant's RRF ranking when constructing final results.
        for chunk_id, payload_document_id, score in ranked_chunk_ids:
            database_record = verified_chunks.get(chunk_id)

            if database_record is None:
                continue

            chunk, document = database_record

            # Ensure the Qdrant point refers to the same document
            # that PostgreSQL associates with this chunk.
            if chunk.document_id != payload_document_id:
                continue

            # Use PostgreSQL's actual chunk content, never Qdrant text.
            if not isinstance(chunk.content, str) or not chunk.content.strip():
                continue

            # Construct the final result for the RAG pipeline.
            results.append(
                RetrievalResult(
                    chunk_id=str(chunk.id),
                    document_id=str(document.id),
                    filename=document.filename,
                    chunk_index=chunk.chunk_index,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=chunk.content,
                    score=score,
                )
            )

        return results


# Create one reusable retrieval service instance.
retrieval_service = RetrievalService()
