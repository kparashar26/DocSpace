
import logging

import httpx

from app.core.config import settings


# Create a logger for diagnosing LLM communication problems.
logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the local LLM cannot generate a response."""


class OllamaService:
    """
    Communicates with the locally running Ollama server.

    Ollama handles model execution.
    This service handles HTTP communication and response validation.
    """

    def __init__(self):
        # Read model configuration from application settings.
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS

    def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate a response using the configured Ollama model."""

        # Validate prompts before making an external request.
        if not system_prompt.strip() or not user_prompt.strip():
            raise ValueError("LLM prompts cannot be empty.")

        # Build the Ollama chat API request.
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
            "stream": False,
            "options": {
                "temperature": settings.OLLAMA_TEMPERATURE,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
        }

        try:
            # Use a bounded timeout for local model inference.
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )

                # Convert HTTP errors into a controlled application error.
                response.raise_for_status()

                result = response.json()

            # Extract the generated assistant response.
            answer = result.get("message", {}).get("content")

            if not isinstance(answer, str) or not answer.strip():
                raise LLMError(
                    "Ollama returned an empty or invalid response."
                )

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


# Create one reusable Ollama service.
ollama_service = OllamaService()
