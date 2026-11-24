
# Test the existing DocSpace LLM service with the local Qwen3 model.

from app.services.llm_service import ollama_service, LLMError


def test_ollama_connection():
    """Verify that DocSpace can send a prompt to Ollama and receive a response."""

    system_prompt = (
        "You are DocSpace, an AI assistant that answers clearly and accurately."
    )

    user_prompt = (
        "Reply with exactly this sentence: "
        "DocSpace Ollama connection successful."
    )

    try:
        # Send the prompt through our existing LLM service.
        response = ollama_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Display the response returned by Qwen3.
        print("\nQWEN3 RESPONSE:")
        print(response)

        # Confirm that the model returned a non-empty response.
        assert response and response.strip(), "Qwen3 returned an empty response."

        print("\nOLLAMA INTEGRATION TEST PASSED.")

    except LLMError as error:
        # Display errors raised by our existing LLM service.
        print("\nOLLAMA INTEGRATION TEST FAILED:")
        print(error)
        raise


if __name__ == "__main__":
    test_ollama_connection()
