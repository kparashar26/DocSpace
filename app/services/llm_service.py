
import logging

import httpx

from app.core.config import settings


# Create a logger for diagnosing LLM communication problems.
logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the local LLM cannot generate a response."""


class OllamaService:
    """
    Communicate with the locally running Ollama server.

    Ollama handles model execution.
    This service handles HTTP communication and response validation.
    """

    def __init__(self):
        # Load the Ollama connection and model configuration.
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate a response using the configured Ollama model."""

        # Validate prompts before sending the request.
        if not system_prompt.strip() or not user_prompt.strip():
            raise ValueError("LLM prompts cannot be empty.")

        # Prepare the Ollama chat API request.
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],

            # Disable Qwen3 thinking mode to avoid unnecessary reasoning output.
            "think": False,

            # Return the complete response instead of streaming tokens.
            "stream": False,

            # Configure generation behaviour.
            "options": {
                "temperature": settings.OLLAMA_TEMPERATURE,

                # Keep the configured context window.
                "num_ctx": settings.OLLAMA_NUM_CTX,

                # Limit answer length to reduce CPU generation time.
                "num_predict": 256,
            },
        }

        try:
            # Send the request to the local Ollama server.
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )

                # Raise an error if Ollama returns an unsuccessful status.
                response.raise_for_status()

                result = response.json()

            # Extract the assistant's generated response.
            message = result.get("message", {})
            answer = message.get("content")

            # Validate the generated answer.
            if not isinstance(answer, str) or not answer.strip():
                raise LLMError(
                    "Ollama returned an empty or invalid response."
                )

            # Return the cleaned answer.
            return answer.strip()

        except LLMError:
            raise

        except httpx.TimeoutException as exc:
            logger.exception("Ollama request timed out.")

            raise LLMError(
                "The language model took too long to respond."
            ) from exc

        except httpx.HTTPStatusError as exc:
            logger.exception("Ollama returned an HTTP error.")

            raise LLMError(
                "Ollama could not process the generation request. "
                "Check that the configured model is available."
            ) from exc

        except httpx.HTTPError as exc:
            logger.exception("Could not connect to Ollama.")

            raise LLMError(
                "Could not connect to the Ollama server."
            ) from exc

        except (ValueError, KeyError, TypeError) as exc:
            logger.exception("Invalid Ollama response.")

            raise LLMError(
                "Ollama returned an invalid response."
            ) from exc


# Create one reusable Ollama service instance.
ollama_service = OllamaService()
