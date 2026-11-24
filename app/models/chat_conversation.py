
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatConversation(Base):
    # Map this model to the existing PostgreSQL table.
    __tablename__ = "chat_conversations"

    # Generate UUIDs in Python because the database has no UUID default.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Identify the user who owns this conversation.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # A NULL document_id means the conversation covers the entire library.
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=True,
    )

    # Store the conversation title.
    title: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    # Let PostgreSQL supply the creation timestamp.
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # PostgreSQL supplies the initial timestamp; SQLAlchemy updates it on edits.
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
