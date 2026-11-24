
import logging
from typing import Any
from uuid import UUID

from qdrant_client import models

from app.core.config import settings
from app.core.qdrant import qdrant_client


# Configure logging for Qdrant operations.
logger = logging.getLogger(__name__)


class QdrantService:
    """
    Manages vector storage and retrieval for DocSpace.

    PostgreSQL remains the source of truth for document chunks.
    Qdrant stores their embeddings and searchable metadata.
    """

    def __init__(self):
        # Reuse the shared Qdrant client and configured collection name.
        self.client = qdrant_client
        self.collection_name = settings.QDRANT_COLLECTION_NAME

        # BGE-M3 produces 1024-dimensional dense embeddings.
        self.vector_size = 1024

    def ensure_collection(self) -> None:
        """
        Create the collection if it does not already exist.
        Also create indexes used by retrieval filters.
        """

        # Avoid creating the collection again if it already exists.
        if not self.client.collection_exists(self.collection_name):
            logger.info("Creating Qdrant collection: %s", self.collection_name)

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

            logger.info("Qdrant collection created successfully.")

        # Index fields used for access control and filtering.
        self._create_payload_indexes()

    def _create_payload_indexes(self) -> None:
        """Create indexes for frequently filtered payload fields."""

        indexed_fields = [
            "user_id",
            "document_id",
            "workspace_id",
        ]

        for field_name in indexed_fields:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )

        logger.info("Qdrant payload indexes verified.")

    def upsert_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """
        Insert or update document chunk vectors.

        Each item must contain:
        - chunk_id: Existing PostgreSQL chunk UUID.
        - vector: BGE-M3 dense embedding.
        - payload: Chunk text and metadata.
        """

        if not chunks:
            return

        points = []

        for chunk in chunks:
            chunk_id = str(chunk["chunk_id"])
            vector = chunk["vector"]
            payload = chunk["payload"]

            # Validate vector dimensions before sending data to Qdrant.
            if len(vector) != self.vector_size:
                raise ValueError(
                    f"Chunk {chunk_id} has {len(vector)} dimensions; "
                    f"expected {self.vector_size}."
                )

            # Use the existing PostgreSQL chunk UUID as the Qdrant point ID.
            points.append(
                models.PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload=payload,
                )
            )

        # Upsert inserts new points or replaces existing points with the same IDs.
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

        logger.info("Upserted %s document chunks into Qdrant.", len(points))

    def delete_document_chunks(self, document_id: UUID) -> None:
        """Delete all Qdrant vectors belonging to a document."""

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

        logger.info("Deleted Qdrant vectors for document %s.", document_id)

    def search(
        self,
        query_vector: list[float],
        user_id: UUID,
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        limit: int = 5,
    ) -> list[models.ScoredPoint]:
        """
        Search for relevant chunks while enforcing user-level isolation.

        The authenticated user's ID must be supplied by the backend.
        A client must never be allowed to choose another user's ID.
        """

        # Validate the query vector before searching.
        if len(query_vector) != self.vector_size:
            raise ValueError(
                f"Query vector must contain {self.vector_size} dimensions."
            )

        if limit < 1:
            raise ValueError("Search limit must be at least 1.")

        # Every search must include the authenticated user's ID.
        conditions = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=str(user_id)),
            )
        ]

        # Restrict retrieval to one document when requested.
        if document_id is not None:
            conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document_id)),
                )
            )

        # Restrict retrieval to one workspace/category when requested.
        if workspace_id is not None:
            conditions.append(
                models.FieldCondition(
                    key="workspace_id",
                    match=models.MatchValue(value=str(workspace_id)),
                )
            )

        # Execute dense vector similarity search with mandatory access filtering.
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=models.Filter(must=conditions),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return response.points


# Create one reusable service instance.
# This does not contact the Qdrant server until a method is called.
qdrant_service = QdrantService()
