
from qdrant_client import QdrantClient

from app.core.config import settings


# Create one reusable Qdrant client for the entire application.
# The client is configured here but does not connect until an operation is performed.
qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
    timeout=30,
)
