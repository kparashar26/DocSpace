
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------
# Conversation schemas
# ------------------------------

class ConversationCreate(BaseModel):
    # Optional document ID.
    # None means the conversation covers the user's entire library.
    document_id: UUID | None = None

    # Allow the user to provide an initial conversation title.
    title: str | None = None


class ConversationRename(BaseModel):
    # Require a non-empty title when renaming a conversation.
    title: str = Field(min_length=1)


class ConversationResponse(BaseModel):
    # Return the conversation details from the database.
    id: UUID
    user_id: UUID
    document_id: UUID | None
    title: str | None
    created_at: datetime
    updated_at: datetime

    # Allow Pydantic to read values directly from SQLAlchemy objects.
    model_config = ConfigDict(from_attributes=True)


# ------------------------------
# Message request schema
# ------------------------------

class MessageRequest(BaseModel):
    # The question submitted by the user.
    question: str = Field(min_length=1)

    # Optional workspace filter.
    # None means search all accessible documents.
    workspace_id: UUID | None = None

    # Number of relevant document chunks to retrieve.
    limit: int = Field(default=5, ge=1, le=20)


# ------------------------------
# Citation response schema
# ------------------------------

class CitationResponse(BaseModel):
    # Identify the source chunk used by the AI.
    chunk_id: UUID

    # Identify the document containing that chunk.
    document_id: UUID

    # Provide useful source information to the frontend.
    filename: str
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None

    # Retrieval score is returned when available.
    # It is not stored in the database.
    score: float | None = None


# ------------------------------
# Message response schemas
# ------------------------------

class MessageResponse(BaseModel):
    # Return the stored message information.
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    # Include source citations for assistant messages.
    citations: list[CitationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ------------------------------
# Complete chat response
# ------------------------------

class ChatResponse(BaseModel):
    # Return both messages created during one chat request.
    user_message: MessageResponse
    assistant_message: MessageResponse
