
import logging

import numpy as np
from FlagEmbedding import BGEM3FlagModel


# Create a logger so model-loading and embedding errors can be diagnosed.
logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles BGE-M3 model loading and dense and sparse embedding generation.

    The model is loaded only when the first embedding is requested.
    Subsequent requests reuse the same loaded model.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "cpu",
        batch_size: int = 1,
        max_length: int = 512,
    ):
        # Store model configuration without loading the model immediately.
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.max_length = max_length

        # Keep the model reference empty until the first embedding request.
        self._model = None

        # BGE-M3 dense embeddings have 1024 dimensions.
        self.vector_size = 1024

    def _load_model(self) -> None:
        """Load BGE-M3 once and reuse it for future requests."""

        if self._model is not None:
            return

        try:
            logger.info("Loading embedding model: %s", self.model_name)

            # Use FP32 because this machine is configured for CPU inference.
            self._model = BGEM3FlagModel(
                self.model_name,
                use_fp16=False,
                devices=[self.device],
            )

            logger.info("Embedding model loaded successfully.")

        except Exception:
            logger.exception("Failed to load the BGE-M3 model.")
            raise

    def _validate_texts(self, texts: list[str]) -> None:
        """Validate input before passing text to the embedding model."""

        # Reject invalid or empty text values.
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Every input must be a non-empty string.")

    def _encode(
        self,
        texts: list[str],
        include_sparse: bool = False,
    ) -> tuple[list[list[float]], list[dict] | None]:
        """
        Generate dense embeddings and optionally sparse embeddings.

        Dense vectors represent semantic meaning.
        Sparse vectors represent weighted lexical terms.
        """

        # Avoid unnecessary model calls for empty input.
        if not texts:
            return [], [] if include_sparse else None

        # Validate all input texts.
        self._validate_texts(texts)

        # Ensure the model is available.
        self._load_model()

        try:
            # Generate dense vectors and optionally BGE-M3 sparse weights.
            result = self._model.encode(
                texts,
                batch_size=self.batch_size,
                max_length=self.max_length,
                return_dense=True,
                return_sparse=include_sparse,
                return_colbert_vecs=False,
            )

            # Convert dense vectors into a consistent NumPy array.
            dense_vectors = np.asarray(
                result["dense_vecs"],
                dtype=np.float32,
            )

            # Validate dense vector dimensions.
            if (
                dense_vectors.ndim != 2
                or dense_vectors.shape[1] != self.vector_size
            ):
                raise ValueError(
                    f"Expected dense embeddings with {self.vector_size} "
                    f"dimensions; received {dense_vectors.shape}."
                )

            # Reject invalid dense vector values.
            if not np.isfinite(dense_vectors).all():
                raise ValueError("Dense embeddings contain invalid values.")

            # Convert dense vectors into ordinary Python lists.
            dense_output = dense_vectors.tolist()

            # Return dense embeddings only when sparse output is not requested.
            if not include_sparse:
                return dense_output, None

            # Read BGE-M3 learned lexical weights.
            lexical_weights = result["lexical_weights"]

            # Ensure one sparse representation exists for every input text.
            if len(lexical_weights) != len(texts):
                raise ValueError(
                    "Sparse embedding count does not match input count."
                )

            sparse_output = []

            for weights in lexical_weights:
                # Convert token IDs and weights into Qdrant-compatible arrays.
                sorted_weights = sorted(
                    (
                        (int(token_id), float(weight))
                        for token_id, weight in weights.items()
                        if float(weight) != 0.0
                    ),
                    key=lambda item: item[0],
                )

                # Separate token IDs from their corresponding weights.
                indices = [item[0] for item in sorted_weights]
                values = [item[1] for item in sorted_weights]

                # Reject empty or invalid sparse representations.
                if not indices:
                    raise ValueError(
                        "BGE-M3 generated an empty sparse embedding."
                    )

                if not np.isfinite(values).all():
                    raise ValueError(
                        "Sparse embeddings contain invalid values."
                    )

                # Store sparse vectors in a simple serializable format.
                sparse_output.append(
                    {
                        "indices": indices,
                        "values": values,
                    }
                )

            return dense_output, sparse_output

        except Exception:
            logger.exception("Failed to generate BGE-M3 embeddings.")
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embeddings for document chunks."""

        dense_vectors, _ = self._encode(
            texts,
            include_sparse=False,
        )

        return dense_vectors

    def embed_query(self, text: str) -> list[float]:
        """Generate a dense embedding for a search question."""

        embeddings = self.embed_documents([text])

        return embeddings[0]

    def embed_documents_with_sparse(
        self,
        texts: list[str],
    ) -> list[dict]:
        """
        Generate dense and sparse embeddings for document chunks.

        Each returned item contains:
        - dense: 1024-dimensional dense vector.
        - sparse: token indices and their learned weights.
        """

        dense_vectors, sparse_vectors = self._encode(
            texts,
            include_sparse=True,
        )

        # Combine both representations for each corresponding text.
        return [
            {
                "dense": dense_vector,
                "sparse": sparse_vector,
            }
            for dense_vector, sparse_vector in zip(
                dense_vectors,
                sparse_vectors,
            )
        ]

    def embed_query_with_sparse(self, text: str) -> dict:
        """Generate both representations for a user's search question."""

        # Generate both vectors in a single model inference call.
        embeddings = self.embed_documents_with_sparse([text])

        return embeddings[0]


# Create one reusable service instance.
# The model remains unloaded until the first embedding request.
embedding_service = EmbeddingService()
