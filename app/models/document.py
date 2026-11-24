
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Map to the existing PostgreSQL document_source_type enum.
# create_type=False prevents SQLAlchemy from attempting to create it.
document_source_enum = ENUM(
    "upload",
    "google_drive",
    name="document_source_type",
    create_type=False,
)


# Map to the existing PostgreSQL document_status enum.
# This fixes the VARCHAR versus document_status comparison error.
document_status_enum = ENUM(
    "pending",
    "processing",
    "ready",
    "failed",
    name="document_status",
    create_type=False,
)


class Document(Base):
    # Map this model to the existing PostgreSQL documents table.
    __tablename__ = "documents"

    # Preserve the existing unique constraint.
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_file_id",
            name="uq_documents_source_type_source_file_id",
        ),
    )

    # Primary key: generate UUID in Python.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # User who owns the document.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional workspace/category assignment.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Original document filename.
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Document origin: upload or Google Drive.
    source_type: Mapped[str] = mapped_column(
        document_source_enum,
        nullable=False,
    )

    # Original source file identifier, when available.
    source_file_id: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Location/key of the original file in Supabase Storage.
    storage_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # MIME type of the uploaded document.
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Original document size in bytes.
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # Processing status using the existing PostgreSQL enum.
    status: Mapped[str] = mapped_column(
        document_status_enum,
        nullable=False,
        server_default="pending",
    )

    # Number of pages, when applicable.
    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Record creation timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Record last-update timestamp.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship with the document owner.
    user = relationship(
        "User",
        back_populates="documents",
    )

    # Relationship with the assigned workspace.
    workspace = relationship(
        "Workspace",
        back_populates="documents",
    )

    # Relationship with the document's extracted chunks.
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
