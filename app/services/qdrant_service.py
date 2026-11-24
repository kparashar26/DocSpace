
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
    Manages dense and sparse vector storage and retrieval.

    PostgreSQL remains the source of truth for document chunks.
    Qdrant stores searchable vector representations and metadata.
    """

    def __init__(self):
        # Reuse the shared Qdrant client and configured collection.
        self.client = qdrant_client
        self.collection_name = settings.QDRANT_COLLECTION_NAME

        # BGE-M3 dense vectors have 1024 dimensions.
        self.vector_size = 1024

        # Keep a consistent name for the sparse vector.
        self.sparse_vector_name = "sparse"

    def ensure_collection(self) -> None:
        """
        Ensure the collection has dense and sparse vector support.

        If the existing collection is dense-only, add the sparse vector
        without deleting existing dense vectors or payload data.
        """

        # Create the collection with both vector types if it does not exist.
        if not self.client.collection_exists(self.collection_name):
            logger.info(
                "Creating hybrid Qdrant collection: %s",
                self.collection_name,
            )

            self.client.create_collection(
                collection_name=self.collection_name,

                # Keep the existing unnamed dense vector configuration.
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),

                # Configure a named sparse vector for BGE-M3 lexical weights.
                sparse_vectors_config={
                    self.sparse_vector_name: models.SparseVectorParams()
                },
            )

            logger.info("Hybrid Qdrant collection created.")

        else:
            # Inspect the existing collection configuration.
            collection_info = self.client.get_collection(
                self.collection_name
            )

            # Confirm that the existing dense vector has the expected size.
            dense_config = collection_info.config.params.vectors

            if (
                not isinstance(dense_config, models.VectorParams)
                or dense_config.size != self.vector_size
            ):
                raise RuntimeError(
                    "The existing Qdrant dense vector configuration "
                    "does not match the expected 1024-dimensional "
                    "unnamed vector."
                )

            # Check whether the sparse vector schema already exists.
            sparse_configs = (
                collection_info.config.params.sparse_vectors or {}
            )

            if self.sparse_vector_name not in sparse_configs:
                logger.info(
                    "Adding sparse vector '%s' to existing collection.",
                    self.sparse_vector_name,
                )

                # Add a named sparse vector without deleting existing points.
                self.client.create_vector_name(
                    collection_name=self.collection_name,
                    vector_name=self.sparse_vector_name,
                    vector_name_config=models.SparseVectorNameConfig(
                        sparse=models.SparseVectorConfig()
                    ),
                    wait=True,
                )

                logger.info("Sparse vector schema added successfully.")

        # Create or verify indexes used by mandatory retrieval filters.
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

    def _build_sparse_vector(
        self,
        sparse_data: dict[str, list],
    ) -> models.SparseVector:
        """Convert BGE-M3 sparse output into a Qdrant SparseVector."""

        # Read token indices and corresponding lexical weights.
        indices = sparse_data["indices"]
        values = sparse_data["values"]

        # Validate the sparse representation before sending it to Qdrant.
        if not indices or len(indices) != len(values):
            raise ValueError("Invalid sparse vector representation.")

        return models.SparseVector(
            indices=indices,
            values=values,
        )

    def upsert_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """
        Insert or update chunks with dense and sparse embeddings.

        Each item must contain:
        - chunk_id: Existing PostgreSQL chunk UUID.
        - dense_vector: BGE-M3 dense embedding.
        - sparse_vector: BGE-M3 sparse embedding.
        - payload: Chunk text and metadata.
        """

        # Avoid unnecessary requests when there is nothing to index.
        if not chunks:
            return

        points = []

        for chunk in chunks:
            # Use the PostgreSQL chunk UUID as the Qdrant point ID.
            chunk_id = str(chunk["chunk_id"])

            # Read the two embedding representations.
            dense_vector = chunk["dense_vector"]
            sparse_vector = self._build_sparse_vector(
                chunk["sparse_vector"]
            )

            # Read the searchable text and metadata.
            payload = chunk["payload"]

            # Validate dense vector dimensions.
            if len(dense_vector) != self.vector_size:
                raise ValueError(
                    f"Chunk {chunk_id} has {len(dense_vector)} dense "
                    f"dimensions; expected {self.vector_size}."
                )

            # Store the unnamed dense vector and named sparse vector together.
            points.append(
                models.PointStruct(
                    id=chunk_id,
                    vector={
                        "": dense_vector,
                        self.sparse_vector_name: sparse_vector,
                    },
                    payload=payload,
                )
            )

        # Upsert replaces existing vectors for the same point IDs.
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

        logger.info(
            "Upserted %s dense and sparse document chunks.",
            len(points),
        )

    def delete_document_chunks(self, document_id: UUID) -> None:
        """Delete all Qdrant vectors belonging to a document."""

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=str(document_id)
                            ),
                        )
                    ]
                )
            ),
            wait=True,
        )

        logger.info(
            "Deleted Qdrant vectors for document %s.",
            document_id,
        )

    def _build_access_filter(
        self,
        user_id: UUID,
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
    ) -> models.Filter:
        """Build the mandatory user-level and optional retrieval filters."""

        # Every search must be restricted to the authenticated user.
        conditions = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=str(user_id)),
            )
        ]

        # Add a document filter when one document is selected.
        if document_id is not None:
            conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document_id)),
                )
            )

        # Add a workspace/category filter when one is selected.
        if workspace_id is not None:
            conditions.append(
                models.FieldCondition(
                    key="workspace_id",
                    match=models.MatchValue(value=str(workspace_id)),
                )
            )

        return models.Filter(must=conditions)

    def search_dense(
        self,
        query_vector: list[float],
        user_id: UUID,
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        limit: int = 5,
    ) -> list[models.ScoredPoint]:
        """Perform dense-only semantic retrieval."""

        # Validate the dense query vector.
        if len(query_vector) != self.vector_size:
            raise ValueError("Invalid dense query vector dimensions.")

        if limit < 1:
            raise ValueError("Search limit must be at least 1.")

        # Build mandatory access filters.
        access_filter = self._build_access_filter(
            user_id=user_id,
            document_id=document_id,
            workspace_id=workspace_id,
        )

        # Search the existing unnamed dense vector.
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=access_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return response.points

    def search_sparse(
        self,
        sparse_vector: dict[str, list],
        user_id: UUID,
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        limit: int = 5,
    ) -> list[models.ScoredPoint]:
        """Perform sparse-only lexical retrieval."""

        if limit < 1:
            raise ValueError("Search limit must be at least 1.")

        # Convert BGE-M3 sparse output into Qdrant's vector format.
        query_sparse_vector = self._build_sparse_vector(sparse_vector)

        # Build mandatory access filters.
        access_filter = self._build_access_filter(
            user_id=user_id,
            document_id=document_id,
            workspace_id=workspace_id,
        )

        # Search the named sparse vector.
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_sparse_vector,
            using=self.sparse_vector_name,
            query_filter=access_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return response.points

    def search_hybrid(
        self,
        dense_query_vector: list[float],
        sparse_query_vector: dict[str, list],
        user_id: UUID,
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        limit: int = 5,
        candidate_limit: int = 20,
    ) -> list[models.ScoredPoint]:
        """
        Perform hybrid retrieval using dense and sparse prefetches.

        Qdrant uses Reciprocal Rank Fusion (RRF) to combine both rankings.
        """

        # Validate the dense query vector.
        if len(dense_query_vector) != self.vector_size:
            raise ValueError("Invalid dense query vector dimensions.")

        if limit < 1 or candidate_limit < limit:
            raise ValueError("Invalid hybrid search limits.")

        # Convert the sparse query representation.
        sparse_vector = self._build_sparse_vector(sparse_query_vector)

        # Apply the same access filter to both retrieval stages.
        access_filter = self._build_access_filter(
            user_id=user_id,
            document_id=document_id,
            workspace_id=workspace_id,
        )

        # Retrieve candidates independently from dense and sparse search.
        prefetch_queries = [
            models.Prefetch(
                query=dense_query_vector,
                limit=candidate_limit,
                filter=access_filter,
            ),
            models.Prefetch(
                query=sparse_vector,
                using=self.sparse_vector_name,
                limit=candidate_limit,
                filter=access_filter,
            ),
        ]

        # Fuse the two ranked candidate lists using RRF.
        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetch_queries,
            query=models.FusionQuery(
                fusion=models.Fusion.RRF
            ),
            query_filter=access_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return response.points

    def search(
        self,
        query_vector: list[float],
        user_id: UUID,
        document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        limit: int = 5,
    ) -> list[models.ScoredPoint]:
        """Preserve the original dense-search method for compatibility."""

        return self.search_dense(
            query_vector=query_vector,
            user_id=user_id,
            document_id=document_id,
            workspace_id=workspace_id,
            limit=limit,
        )


# Create one reusable Qdrant service instance.
qdrant_service = QdrantService()
