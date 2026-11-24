
import uuid

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Map to the existing PostgreSQL enum.
# create_type=False prevents SQLAlchemy from trying to create the enum.
message_role_enum = ENUM(
    "user",
    "assistant",
    name="message_role",
    create_type=False,
)


class ChatMessage(Base):
    # Map this model to the existing PostgreSQL table.
    __tablename__ = "chat_messages"

    # Generate message UUIDs in Python.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Identify the conversation to which this message belongs.
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("chat_conversations.id"),
        nullable=False,
    )

    # Identify whether the message came from the user or the AI.
    role: Mapped[str] = mapped_column(
        message_role_enum,
        nullable=False,
    )

    # Store the actual message content.
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Record when the message was created.
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
