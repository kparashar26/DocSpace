
from pathlib import PurePosixPath
from uuid import uuid4

from app.core.config import settings
from app.core.supabase import supabase


class StorageError(Exception):
    """Raised when a Supabase Storage operation fails."""


def _validate_storage_key(storage_key: str) -> None:
    """Validate a document storage path."""

    if not storage_key or "\\" in storage_key:
        raise ValueError("Invalid storage path.")

    parts = storage_key.split("/")
    path = PurePosixPath(storage_key)

    if (
        path.is_absolute()
        or len(parts) != 2
        or parts[0] != "uploads"
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("Invalid storage path.")


def save_document_file(
    file_bytes: bytes,
    extension: str,
    mime_type: str,
) -> str:
    """Upload a document to Supabase Storage."""

    storage_filename = f"{uuid4().hex}{extension.lower()}"
    storage_key = f"uploads/{storage_filename}"

    try:
        supabase.storage.from_(
            settings.SUPABASE_STORAGE_BUCKET
        ).upload(
            path=storage_key,
            file=file_bytes,
            file_options={
                "content-type": mime_type,
            },
        )

    except Exception as exc:
        raise StorageError(
            "Failed to upload the document to storage."
        ) from exc

    return storage_key


def download_document_file(storage_key: str) -> bytes:
    """Download a document from Supabase Storage."""

    _validate_storage_key(storage_key)

    try:
        return supabase.storage.from_(
            settings.SUPABASE_STORAGE_BUCKET
        ).download(storage_key)

    except Exception as exc:
        raise StorageError(
            "Failed to download the document from storage."
        ) from exc


def delete_document_file(storage_key: str) -> None:
    """Delete a document from Supabase Storage."""

    _validate_storage_key(storage_key)

    try:
        supabase.storage.from_(
            settings.SUPABASE_STORAGE_BUCKET
        ).remove([storage_key])

    except Exception as exc:
        raise StorageError(
            "Failed to delete the document from storage."
        ) from exc


def create_document_signed_url(
    storage_key: str,
    expires_in: int = 300,
) -> str:
    """Generate a temporary URL for a private document."""

    _validate_storage_key(storage_key)

    if expires_in <= 0:
        raise ValueError("URL expiration must be positive.")

    try:
        response = supabase.storage.from_(
            settings.SUPABASE_STORAGE_BUCKET
        ).create_signed_url(
            storage_key,
            expires_in,
        )

        signed_url = (
            response.get("signedURL")
            or response.get("signedUrl")
            or response.get("signed_url")
        )

        if not signed_url:
            raise StorageError(
                "Supabase did not return a signed URL."
            )

        return signed_url

    except StorageError:
        raise

    except Exception as exc:
        raise StorageError(
            "Failed to generate a document download URL."
        ) from exc
