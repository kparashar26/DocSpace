
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIRECTORY = PROJECT_ROOT / "uploads"


def save_document_file(file_bytes: bytes, extension: str) -> str:
    """Save a document using a generated filename."""

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

    storage_filename = f"{uuid4().hex}{extension.lower()}"
    file_path = UPLOAD_DIRECTORY / storage_filename

    file_path.write_bytes(file_bytes)

    # Store a relative path in the database.
    return f"uploads/{storage_filename}"


def delete_document_file(storage_key: str) -> None:
    """Delete a stored document safely."""

    relative_path = Path(storage_key)

    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("Invalid storage path.")

    file_path = (PROJECT_ROOT / relative_path).resolve()

    if not file_path.is_relative_to(UPLOAD_DIRECTORY.resolve()):
        raise ValueError("Invalid storage path.")

    if file_path.exists() and file_path.is_file():
        file_path.unlink()
