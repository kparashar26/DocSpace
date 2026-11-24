
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db

from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage
from app.models.message_citation import MessageCitation

from app.schemas.chat import (
    ConversationCreate,
    ConversationRename,
    ConversationResponse,
    MessageRequest,
    MessageResponse,
    CitationResponse,
    ChatResponse,
)

from app.services.chat_service import chat_service
from app.services.llm_service import LLMError


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


# --------------------------------------------------
# Helper: Verify conversation ownership
# --------------------------------------------------

def get_user_conversation(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
) -> ChatConversation:
    # Only return conversations owned by the authenticated user.
    conversation = (
        db.query(ChatConversation)
        .filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user_id,
        )
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conversation


# --------------------------------------------------
# Helper: Build a message response with citations
# --------------------------------------------------

def build_message_response(
    db: Session,
    message: ChatMessage,
    retrieved_chunks: list | None = None,
) -> MessageResponse:
    citations = []

    # User messages do not have document citations.
    if message.role == "assistant":

        if retrieved_chunks is not None:
            # Use the retrieval results for the immediate chat response.
            seen_chunk_ids = set()

            for chunk in retrieved_chunks:
                if chunk.chunk_id in seen_chunk_ids:
                    continue

                seen_chunk_ids.add(chunk.chunk_id)

                citations.append(
                    CitationResponse(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        filename=chunk.filename,
                        chunk_index=chunk.chunk_index,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        score=chunk.score,
                    )
                )

        else:
            # For older messages, reconstruct citations from PostgreSQL.
            citation_rows = (
                db.query(MessageCitation, DocumentChunk, Document)
                .join(
                    DocumentChunk,
                    MessageCitation.chunk_id == DocumentChunk.id,
                )
                .join(
                    Document,
                    DocumentChunk.document_id == Document.id,
                )
                .filter(MessageCitation.message_id == message.id)
                .all()
            )

            for citation, chunk, document in citation_rows:
                citations.append(
                    CitationResponse(
                        chunk_id=chunk.id,
                        document_id=document.id,
                        filename=document.filename,
                        chunk_index=chunk.chunk_index,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        # Retrieval scores are not stored in the database.
                        score=None,
                    )
                )

    # Convert the SQLAlchemy message into the API response schema.
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        citations=citations,
    )


# --------------------------------------------------
# 1. Create a conversation
# --------------------------------------------------

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat.use")),
):
    # If a document is selected, verify that it belongs to this user.
    if payload.document_id is not None:
        document = db.get(Document, payload.document_id)

        if document is None or document.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

    # Create a conversation for the authenticated user.
    conversation = ChatConversation(
        user_id=current_user.id,
        document_id=payload.document_id,
        title=payload.title,
    )

    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return conversation

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# 2. List the current user's conversations
# --------------------------------------------------

@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
)
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat.use")),
):
    # Never return conversations belonging to another user.
    conversations = (
        db.query(ChatConversation)
        .filter(ChatConversation.user_id == current_user.id)
        .order_by(ChatConversation.updated_at.desc())
        .all()
    )

    return conversations


# --------------------------------------------------
# 3. Get conversation details
# --------------------------------------------------

@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat.use")),
):
    # Verify ownership before returning conversation details.
    return get_user_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )


# --------------------------------------------------
# 4. Rename a conversation
# --------------------------------------------------

@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def rename_conversation(
    conversation_id: UUID,
    payload: ConversationRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat.use")),
):
    conversation = get_user_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    # Reject titles containing only whitespace.
    title = payload.title.strip()

    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Conversation title cannot be empty.",
        )

    try:
        conversation.title = title
        db.commit()
        db.refresh(conversation)

        return conversation

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# 5. Delete a conversation
# --------------------------------------------------

@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat.use")),
):
    conversation = get_user_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    try:
        # Get all message IDs belonging to this conversation.
        message_ids = [
            message_id
            for (message_id,) in (
                db.query(ChatMessage.id)
                .filter(
                    ChatMessage.conversation_id == conversation.id
                )
                .all()
            )
        ]

        # Delete citations before deleting their referenced messages.
        if message_ids:
            (
                db.query(MessageCitation)
                .filter(MessageCitation.message_id.in_(message_ids))
                .delete(synchronize_session=False)
            )

            # Delete the conversation's messages.
            (
                db.query(ChatMessage)
                .filter(ChatMessage.id.in_(message_ids))
                .delete(synchronize_session=False)
            )

        # Finally delete the conversation itself.
        db.delete(conversation)
        db.commit()

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception:
        db.rollback()
        raise


# --------------------------------------------------
# 6. Retrieve conversation message history
# --------------------------------------------------

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_message_history(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat.use")),
):
    conversation = get_user_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    # Retrieve messages in chronological order.
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    # Reconstruct saved citations for assistant messages.
    return [
        build_message_response(db, message)
        for message in messages
    ]


# --------------------------------------------------
# 7. Send a question and receive an AI response
# --------------------------------------------------

@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: UUID,
    payload: MessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("chat.use")),
):
    conversation = get_user_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    try:
        # Run retrieval, generate the answer, and save both messages.
        user_message, assistant_message, retrieved_chunks = (
            chat_service.send_message(
                db=db,
                conversation=conversation,
                user_id=current_user.id,
                question=payload.question,
                workspace_id=payload.workspace_id,
                limit=payload.limit,
            )
        )

        # Return both messages and the sources used for this answer.
        return ChatResponse(
            user_message=build_message_response(
                db,
                user_message,
            ),
            assistant_message=build_message_response(
                db,
                assistant_message,
                retrieved_chunks=retrieved_chunks,
            ),
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this conversation.",
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except LLMError:
        # Report an unavailable AI service without exposing internal details.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI service is currently unavailable.",
        )
