
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk

from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service


class VectorIndexingService:
    """
    Handles indexing of existing PostgreSQL document chunks into Qdrant.

    PostgreSQL remains the source of truth. Qdrant stores searchable
    vector representations and copies of chunk text as payload.
    """

    def __init__(self):
        # Reuse the existing BGE-M3 and Qdrant service instances.
        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service

    def index_document(self, db: Session, document_id: UUID) -> int:
        # Fetch the document from PostgreSQL.
        document = db.get(Document, document_id)

        if document is None:
            raise ValueError("Document not found.")

        # Only index documents that have completed processing.
        document_status = getattr(document.status, "value", document.status)

        if document_status != "ready":
            raise ValueError("Only ready documents can be indexed.")

        # Fetch all chunks belonging to this document in their original order.
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        )

        chunks = db.execute(statement).scalars().all()

        if not chunks:
            raise ValueError("No document chunks found.")

        # Extract the original chunk text from PostgreSQL.
        chunk_texts = [chunk.content for chunk in chunks]

        # Generate one dense BGE-M3 embedding for each chunk.
        vectors = self.embedding_service.embed_documents(chunk_texts)

        # Ensure every chunk has a corresponding embedding.
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding count does not match chunk count.")

        # Prepare the Qdrant collection before inserting points.
        self.qdrant_service.ensure_collection()

        qdrant_points = []

        for chunk, vector in zip(chunks, vectors):
            # Build metadata using existing PostgreSQL fields.
            payload = {
                "user_id": str(document.user_id),
                "document_id": str(document.id),
                "chunk_id": str(chunk.id),
                "filename": document.filename,
                "chunk_index": chunk.chunk_index,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "text": chunk.content,
            }

            # Include the workspace only when the document has one.
            if document.workspace_id is not None:
                payload["workspace_id"] = str(document.workspace_id)

            # Use the PostgreSQL chunk UUID as the Qdrant point ID.
            qdrant_points.append({
                "chunk_id": str(chunk.id),
                "vector": vector,
                "payload": payload,
            })

        # Upsert makes this operation safe to repeat with the same chunk IDs.
        self.qdrant_service.upsert_chunks(qdrant_points)

        # Return the number of successfully submitted chunks.
        return len(qdrant_points)


# Create one reusable indexing service for the application.
vector_indexing_service = VectorIndexingService()
