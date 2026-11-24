
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage
from app.models.message_citation import MessageCitation
from app.services.llm_service import ollama_service
from app.services.retrieval_service import retrieval_service


logger = logging.getLogger(__name__)


class ChatService:
    """
    Coordinate document retrieval, AI response generation,
    and chat message persistence.
    """

    def send_message(
        self,
        db: Session,
        conversation: ChatConversation,
        user_id: UUID,
        question: str,
        workspace_id: UUID | None = None,
        limit: int = 5,
    ) -> tuple[ChatMessage, ChatMessage, list]:
        # Remove unnecessary whitespace from the question.
        question = question.strip()

        if not question:
            raise ValueError("Question cannot be empty.")

        # Prevent access to another user's conversation.
        if conversation.user_id != user_id:
            raise PermissionError("You cannot access this conversation.")

        # Retrieve relevant chunks using the existing hybrid retrieval service.
        retrieved_chunks = retrieval_service.retrieve(
            db=db,
            question=question,
            user_id=user_id,
            document_id=conversation.document_id,
            workspace_id=workspace_id,
            limit=limit,
        )

        # Generate a fixed response when no relevant document chunks are found.
        if not retrieved_chunks:
            answer = (
                "I couldn't find relevant information in your selected "
                "documents to answer that question."
            )

        else:
            # Build the system instructions for grounded document-based answers.
            system_prompt = """
You are DocSpace, an AI assistant that answers questions about documents.

Follow these rules strictly:

1. Answer using only the supplied document context.
2. Do not invent facts or use unsupported external knowledge.
3. Cite supporting sources using their reference numbers, such as [1] or [2].
4. Only cite reference numbers that appear in the supplied context.
5. If the context does not contain enough information, clearly say so.
6. Give clear, direct, and helpful answers.
7. Do not pretend that you have read documents that were not supplied.
"""

            # Prepare the retrieved PostgreSQL chunk content for the LLM.
            context_sections = []

            for index, chunk in enumerate(retrieved_chunks, start=1):
                # Include page information when it is available.
                page_info = ""

                if chunk.page_start is not None:
                    page_info = f" | Pages: {chunk.page_start}"

                    if (
                        chunk.page_end is not None
                        and chunk.page_end != chunk.page_start
                    ):
                        page_info += f"-{chunk.page_end}"

                # Give every retrieved chunk a reference number for citations.
                context_sections.append(
                    f"""
[Source {index}]
Filename: {chunk.filename}{page_info}
Content:
{chunk.text}
"""
                )

            # Combine all retrieved document chunks into one context.
            document_context = "\n".join(context_sections)

            # Include the user's question after the document context.
            user_prompt = f"""
Use the following document context to answer the question.

DOCUMENT CONTEXT:
{document_context}

USER QUESTION:
{question}

Remember to cite supporting information using the source numbers.
"""

            # Generate the answer using the configured Ollama model.
            answer = ollama_service.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

        # Prepare the two messages for database storage.
        user_message = ChatMessage(
            conversation_id=conversation.id,
            role="user",
            content=question,
        )

        assistant_message = ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
        )

        try:
            # Add both messages to the current database transaction.
            db.add(user_message)
            db.add(assistant_message)

            # Flush to generate message UUIDs before creating citations.
            db.flush()

            # Prevent duplicate citations for the same chunk.
            cited_chunk_ids = set()

            for chunk in retrieved_chunks:
                if chunk.chunk_id in cited_chunk_ids:
                    continue

                cited_chunk_ids.add(chunk.chunk_id)

                # Link the AI response to its supporting document chunk.
                citation = MessageCitation(
                    message_id=assistant_message.id,
                    chunk_id=chunk.chunk_id,
                )

                db.add(citation)

            # Update the conversation's last-modified timestamp.
            conversation.updated_at = datetime.now(timezone.utc)

            # Commit messages, citations, and conversation update together.
            db.commit()

            # Reload the saved messages from PostgreSQL.
            db.refresh(user_message)
            db.refresh(assistant_message)

            return user_message, assistant_message, retrieved_chunks

        except Exception:
            # Undo all pending database changes if persistence fails.
            db.rollback()

            logger.exception("Failed to save chat messages and citations.")
            raise


# Reuse one service instance throughout the application.
chat_service = ChatService()
