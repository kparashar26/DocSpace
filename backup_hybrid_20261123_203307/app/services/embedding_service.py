
import logging

import numpy as np
from FlagEmbedding import BGEM3FlagModel


# Create a logger so model-loading and embedding errors can be diagnosed.
logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles BGE-M3 model loading and dense embedding generation.

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

    def _load_model(self) -> None:
        """Load BGE-M3 once and reuse it for future requests."""

        if self._model is not None:
            return

        try:
            logger.info("Loading embedding model: %s", self.model_name)

            # FP32 is used because this machine is configured for CPU inference.
            self._model = BGEM3FlagModel(
                self.model_name,
                use_fp16=False,
                devices=[self.device],
            )

            logger.info("Embedding model loaded successfully.")

        except Exception:
            logger.exception("Failed to load the BGE-M3 model.")
            raise

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embeddings for a collection of texts."""

        # Reject empty input rather than making an unnecessary model call.
        if not texts:
            return []

        # Validate text values before passing them to the model.
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Every input must be a non-empty string.")

        # Ensure the model is available before generating embeddings.
        self._load_model()

        try:
            # Generate dense vectors only; sparse and ColBERT are later milestones.
            result = self._model.encode(
                texts,
                batch_size=self.batch_size,
                max_length=self.max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )

            # Convert the NumPy output into a consistent 2D array.
            vectors = np.asarray(result["dense_vecs"], dtype=np.float32)

            # BGE-M3 dense embeddings must contain 1024 dimensions.
            if vectors.ndim != 2 or vectors.shape[1] != 1024:
                raise ValueError(
                    f"Expected embeddings with 1024 dimensions; "
                    f"received shape {vectors.shape}."
                )

            # Reject invalid numerical values before sending vectors to Qdrant.
            if not np.isfinite(vectors).all():
                raise ValueError("Generated embeddings contain invalid values.")

            # Convert NumPy arrays into ordinary Python lists for API compatibility.
            return vectors.tolist()

        except Exception:
            logger.exception("Failed to generate text embeddings.")
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for document chunks."""

        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        """Generate an embedding for a user's search question."""

        # A query is one text, so reuse the same embedding implementation.
        embeddings = self._embed([text])

        return embeddings[0]


# Create one reusable service instance.
# Because loading is lazy, importing this module does not download or load the model.
embedding_service = EmbeddingService()
