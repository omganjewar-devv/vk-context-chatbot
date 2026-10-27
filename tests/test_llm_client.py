import pytest
from app.core.llm_client import MockLLMClient, LLMException, GeminiClient, OpenAIClient


def test_mock_llm_client_generation():
    client = MockLLMClient(persona_name="Atlas")
    messages = [
        {"role": "user", "content": "My project is named Apollo and uses Python."},
        {"role": "assistant", "content": "Acknowledged Apollo project."},
        {"role": "user", "content": "What is my project name?"}
    ]

    response = client.generate(messages, system_instruction="Persona instructions")
    assert "Atlas" in response
    assert "What is my project name?" in response


def test_mock_llm_client_summarization():
    client = MockLLMClient(persona_name="Atlas")
    messages = [
        {"role": "user", "content": "We need 10,000 requests per second."},
        {"role": "assistant", "content": "Understood, high throughput requirement."}
    ]

    summary = client.summarize(messages, existing_summary="")
    assert "User inquired" in summary
    assert "Atlas recommended" in summary


def test_llm_exception_properties():
    exc = LLMException(
        message="Rate limit reached",
        error_type="RATE_LIMIT_ERROR",
        status_code=429,
        details="Quota exceeded for 24h"
    )
    assert exc.status_code == 429
    assert exc.error_type == "RATE_LIMIT_ERROR"
    assert "Rate limit" in exc.message
    assert "Quota exceeded" in exc.details
