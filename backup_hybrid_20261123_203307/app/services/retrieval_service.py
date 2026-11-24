
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.workspace import Workspace

from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service


@dataclass
class RetrievalResult:
    """Represents one relevant document chunk returned by retrieval."""

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
    Retrieves relevant document chunks using BGE-M3 and Qdrant.

    PostgreSQL remains the source of truth for ownership and document status.
    """

    def __init__(self):
        # Reuse the existing embedding and Qdrant service instances.
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
        if not 1 <= limit <= 20:
            raise ValueError("Retrieval limit must be between 1 and 20.")

        # Verify that an explicitly selected document belongs to this user.
        if document_id is not None:
            selected_document = db.execute(
                select(Document.id).where(
                    Document.id == document_id,
                    Document.user_id == user_id,
                )
            ).scalar_one_or_none()

            if selected_document is None:
                raise ValueError("Document not found or access denied.")

        # Verify that an explicitly selected workspace exists.
        # Workspaces are shared categories in our current schema.
        if workspace_id is not None:
            selected_workspace = db.get(Workspace, workspace_id)

            if selected_workspace is None:
                raise ValueError("Workspace not found.")

        # Convert the user's question into a BGE-M3 dense vector.
        query_vector = self.embedding_service.embed_query(question)

        # Search Qdrant using mandatory user-level filtering.
        points = self.qdrant_service.search(
            query_vector=query_vector,
            user_id=user_id,
            document_id=document_id,
            workspace_id=workspace_id,
            limit=limit,
        )

        # Return immediately when Qdrant finds no matching chunks.
        if not points:
            return []

        # Collect document IDs from Qdrant payloads belonging to this user.
        document_ids = set()

        for point in points:
            payload = point.payload or {}

            # Never trust payload ownership without checking it.
            if payload.get("user_id") != str(user_id):
                continue

            try:
                document_ids.add(UUID(payload["document_id"]))
            except (KeyError, ValueError, TypeError):
                # Ignore points with missing or invalid document IDs.
                continue

        if not document_ids:
            return []

        # Verify ownership and retrieve document status from PostgreSQL.
        statement = select(Document).where(
            Document.id.in_(document_ids),
            Document.user_id == user_id,
        )

        documents = db.execute(statement).scalars().all()

        # Only documents with ready status can provide retrieval context.
        ready_document_ids = {
            document.id
            for document in documents
            if getattr(document.status, "value", document.status) == "ready"
        }

        results = []

        # Preserve Qdrant's relevance ranking when constructing results.
        for point in points:
            payload = point.payload or {}

            try:
                result_document_id = UUID(payload["document_id"])
            except (KeyError, ValueError, TypeError):
                continue

            # Exclude documents that failed ownership or readiness checks.
            if result_document_id not in ready_document_ids:
                continue

            # Verify the payload belongs to the requested workspace if selected.
            if workspace_id is not None:
                if payload.get("workspace_id") != str(workspace_id):
                    continue

            # Exclude points without usable chunk text.
            chunk_text = payload.get("text")

            if not isinstance(chunk_text, str) or not chunk_text.strip():
                continue

            # Build a structured retrieval result for later RAG processing.
            results.append(
                RetrievalResult(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    document_id=str(result_document_id),
                    filename=payload.get("filename", ""),
                    chunk_index=payload.get("chunk_index", 0),
                    page_start=payload.get("page_start"),
                    page_end=payload.get("page_end"),
                    text=chunk_text,
                    score=float(point.score),
                )
            )

        return results


# Create one reusable retrieval service instance.
retrieval_service = RetrievalService()
