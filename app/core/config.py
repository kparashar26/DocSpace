
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL database connection.
    DATABASE_URL: str

    # JWT authentication configuration.
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Supabase private document storage.
    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "docspace-documents"

    # Qdrant vector database configuration.
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "docspace_chunks"

    # Ollama local LLM configuration.
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:4b"
    OLLAMA_TIMEOUT_SECONDS: int = 180
    OLLAMA_NUM_CTX: int = 8192
    OLLAMA_TEMPERATURE: float = 0.2

    # Load configuration from the project's .env file.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Create one shared application settings instance.
settings = Settings()
