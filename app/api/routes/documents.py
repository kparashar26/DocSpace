
from io import BytesIO
from pathlib import Path
from uuid import UUID
import zipfile

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.services.document_service import process_uploaded_document


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

MAX_FILE_SIZE = 25 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    ".txt": "text/plain",
}


def validate_file_content(
    file_bytes: bytes,
    extension: str,
) -> None:
    """Check that the file content matches its extension."""

    if extension == ".pdf":
        if b"%PDF-" not in file_bytes[:1024]:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid PDF.",
            )

    elif extension == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
                names = set(archive.namelist())

                if (
                    "[Content_Types].xml" not in names
                    or "word/document.xml" not in names
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="The uploaded file is not a valid DOCX.",
                    )

        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid DOCX.",
            )

    elif extension == ".txt":
        try:
            file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="TXT files must use UTF-8 encoding.",
            )


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    workspace_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission("documents.upload")
    ),
):
    # Validate the filename.
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A filename is required.",
        )

    # Remove any directory components from the supplied filename.
    filename = file.filename.replace("\\", "/").split("/")[-1].strip()

    if not filename or filename in {".", ".."}:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        )

    if len(filename) > 255:
        raise HTTPException(
            status_code=400,
            detail="Filename cannot exceed 255 characters.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, DOCX and TXT files are supported.",
        )

    # Read one byte beyond the limit to detect oversized files.
    file_bytes = await file.read(MAX_FILE_SIZE + 1)

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Maximum upload size is 25 MB.",
        )

    validate_file_content(file_bytes, extension)

    mime_type = ALLOWED_MIME_TYPES[extension]

    try:
        document = process_uploaded_document(
            db=db,
            current_user=current_user,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            workspace_id=workspace_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "message": "Document uploaded and processed successfully.",
        "document": {
            "id": str(document.id),
            "filename": document.filename,
            "workspace_id": (
                str(document.workspace_id)
                if document.workspace_id
                else None
            ),
            "source_type": document.source_type,
            "mime_type": document.mime_type,
            "file_size_bytes": document.file_size_bytes,
            "page_count": document.page_count,
            "status": document.status,
            "created_at": document.created_at,
        },
    }
