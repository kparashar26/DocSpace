
import uuid

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MessageCitation(Base):
    # Map this model to the existing PostgreSQL table.
    __tablename__ = "message_citations"

    # Keep the existing unique constraint on message_id and chunk_id.
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "chunk_id",
            name="uq_message_chunk",
        ),
    )

    # Generate citation UUIDs in Python.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Identify the AI message that contains this citation.
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("chat_messages.id"),
        nullable=False,
    )

    # Identify the document chunk used as a source.
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_chunks.id"),
        nullable=False,
    )
