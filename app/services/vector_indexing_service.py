
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk

from app.services.embedding_service import embedding_service
from app.services.qdrant_service import qdrant_service


class VectorIndexingService:
    """
    Index existing PostgreSQL document chunks into Qdrant.

    Generates both dense and sparse embeddings using BGE-M3.
    PostgreSQL remains the source of truth for document text.
    """

    def __init__(self):
        # Reuse the application's shared embedding and Qdrant services.
        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service

    def index_document(self, db: Session, document_id: UUID) -> int:
        # Fetch the requested document from PostgreSQL.
        document = db.get(Document, document_id)

        if document is None:
            raise ValueError("Document not found.")

        # Only index documents that have completed extraction and chunking.
        document_status = getattr(document.status, "value", document.status)

        if document_status != "ready":
            raise ValueError("Only ready documents can be indexed.")

        # Fetch the document's chunks in their original order.
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        )

        chunks = db.execute(statement).scalars().all()

        if not chunks:
            raise ValueError("No document chunks found.")

        # Extract the authoritative text from PostgreSQL.
        chunk_texts = [chunk.content for chunk in chunks]

        # Generate both dense and sparse representations in one model call.
        embeddings = self.embedding_service.embed_documents_with_sparse(
            chunk_texts
        )

        # Ensure every chunk has both embedding representations.
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "Embedding count does not match document chunk count."
            )

        # Ensure Qdrant supports dense and sparse vector storage.
        self.qdrant_service.ensure_collection()

        qdrant_points = []

        for chunk, embedding in zip(chunks, embeddings):
            # Build the same metadata structure used during new uploads.
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

            # Use the existing PostgreSQL UUID and both named vector inputs.
            qdrant_points.append(
                {
                    "chunk_id": str(chunk.id),
                    "dense_vector": embedding["dense"],
                    "sparse_vector": embedding["sparse"],
                    "payload": payload,
                }
            )

        # Upsert both vector types using the existing point IDs.
        # Repeating this operation updates the same points rather than
        # creating duplicate Qdrant records.
        self.qdrant_service.upsert_chunks(qdrant_points)

        # Return the number of successfully indexed chunks.
        return len(qdrant_points)


# Create one reusable vector indexing service.
vector_indexing_service = VectorIndexingService()
