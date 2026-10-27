import os
import time
import logging
from typing import List, Dict, Tuple, Optional
from app.config import settings

logger = logging.getLogger("chatbot.llm_client")


class LLMException(Exception):
    """Custom exception providing user-facing explanations for LLM errors."""
    def __init__(self, message: str, error_type: str = "API_ERROR", status_code: int = 500, details: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code
        self.details = details or ""


class BaseLLMClient:
    """Abstract interface for LLM operations."""
    def generate(self, messages: List[Dict[str, str]], system_instruction: str) -> str:
        raise NotImplementedError

    def summarize(self, messages: List[Dict[str, str]], existing_summary: str = "") -> str:
        raise NotImplementedError


class GeminiClient(BaseLLMClient):
    """Google Gemini Client using the official google-genai SDK."""
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            raise LLMException(
                message=f"Failed to initialize Gemini Client: {str(e)}",
                error_type="INITIALIZATION_ERROR",
                status_code=500
            )

    def generate(self, messages: List[Dict[str, str]], system_instruction: str) -> str:
        from google.genai import types

        formatted_contents = []
        for msg in messages:
            # Gemini expects 'user' or 'model'
            role = "model" if msg["role"] == "assistant" else "user"
            formatted_contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=formatted_contents,
                config=config,
            )
            if not response or not response.text:
                raise LLMException(
                    message="The Gemini API returned an empty response. Please try rephrasing your prompt.",
                    error_type="EMPTY_RESPONSE",
                    status_code=502
                )
            return response.text

        except LLMException:
            raise
        except Exception as e:
            err_str = str(e).lower()
            if "api_key" in err_str or "unauthenticated" in err_str or "permission_denied" in err_str or "401" in err_str or "403" in err_str:
                raise LLMException(
                    message="Invalid or unauthorized Gemini API key. Please verify your GEMINI_API_KEY in .env.",
                    error_type="AUTHENTICATION_ERROR",
                    status_code=401,
                    details=str(e)
                )
            elif "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                raise LLMException(
                    message="Gemini API rate limit or quota exceeded. Please wait a moment before sending another message.",
                    error_type="RATE_LIMIT_ERROR",
                    status_code=429,
                    details=str(e)
                )
            elif "timeout" in err_str or "timed out" in err_str or "deadline_exceeded" in err_str:
                raise LLMException(
                    message="Request to Gemini API timed out. The server took too long to respond.",
                    error_type="TIMEOUT_ERROR",
                    status_code=504,
                    details=str(e)
                )
            elif "connection" in err_str or "network" in err_str or "dns" in err_str:
                raise LLMException(
                    message="Network error connecting to Gemini API. Please check your internet connection.",
                    error_type="NETWORK_ERROR",
                    status_code=503,
                    details=str(e)
                )
            else:
                raise LLMException(
                    message=f"Gemini API Error: {str(e)}",
                    error_type="API_ERROR",
                    status_code=500,
                    details=str(e)
                )

    def summarize(self, messages: List[Dict[str, str]], existing_summary: str = "") -> str:
        dialogue_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        summary_instruction = (
            "You are an expert conversation summarizer. Distill the dialogue into a concise running factual summary. "
            "Highlight key facts, decisions, user preferences, and goals in 2-4 concise bullet points. "
            "Do not include preamble."
        )
        prompt = f"Existing Summary:\n{existing_summary or 'None'}\n\nNew Dialogue to Incorporate:\n{dialogue_text}\n\nProvide the updated summary:"
        return self.generate(
            messages=[{"role": "user", "content": prompt}],
            system_instruction=summary_instruction
        )


class OpenAIClient(BaseLLMClient):
    """OpenAI Client using the official openai SDK."""
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model_name = model_name
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except Exception as e:
            raise LLMException(
                message=f"Failed to initialize OpenAI Client: {str(e)}",
                error_type="INITIALIZATION_ERROR",
                status_code=500
            )

    def generate(self, messages: List[Dict[str, str]], system_instruction: str) -> str:
        from openai import AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError, APIError

        payload = [{"role": "system", "content": system_instruction}] + messages

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=payload,
                temperature=0.7,
                timeout=30.0
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMException(
                    message="OpenAI returned an empty response. Please try rephrasing your prompt.",
                    error_type="EMPTY_RESPONSE",
                    status_code=502
                )
            return content

        except AuthenticationError as e:
            raise LLMException(
                message="Invalid or missing OpenAI API key. Please check your OPENAI_API_KEY in .env.",
                error_type="AUTHENTICATION_ERROR",
                status_code=401,
                details=str(e)
            )
        except RateLimitError as e:
            raise LLMException(
                message="OpenAI rate limit or credit quota exceeded. Please check your usage plan or wait a few seconds.",
                error_type="RATE_LIMIT_ERROR",
                status_code=429,
                details=str(e)
            )
        except APITimeoutError as e:
            raise LLMException(
                message="OpenAI request timed out. Please try again.",
                error_type="TIMEOUT_ERROR",
                status_code=504,
                details=str(e)
            )
        except APIConnectionError as e:
            raise LLMException(
                message="Unable to connect to OpenAI API. Please check your network connection.",
                error_type="NETWORK_ERROR",
                status_code=503,
                details=str(e)
            )
        except APIError as e:
            raise LLMException(
                message=f"OpenAI API Error: {e.message}",
                error_type="API_ERROR",
                status_code=e.status_code or 500,
                details=str(e)
            )
        except LLMException:
            raise
        except Exception as e:
            raise LLMException(
                message=f"Unexpected error: {str(e)}",
                error_type="UNEXPECTED_ERROR",
                status_code=500,
                details=str(e)
            )

    def summarize(self, messages: List[Dict[str, str]], existing_summary: str = "") -> str:
        dialogue_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
        summary_instruction = (
            "You are an expert conversation summarizer. Distill the dialogue into a concise running factual summary. "
            "Highlight key facts, decisions, user preferences, and goals in 2-4 concise bullet points. "
            "Do not include preamble."
        )
        prompt = f"Existing Summary:\n{existing_summary or 'None'}\n\nNew Dialogue to Incorporate:\n{dialogue_text}\n\nProvide the updated summary:"
        return self.generate(
            messages=[{"role": "user", "content": prompt}],
            system_instruction=summary_instruction
        )


class MockLLMClient(BaseLLMClient):
    """
    Intelligent simulated LLM Client used when no API key is yet configured,
    or for deterministic offline testing. It actively simulates multi-turn memory
    and persona responses to ensure the system is testable out-of-the-box.
    """
    def __init__(self, persona_name: str = "Atlas"):
        self.persona_name = persona_name

    def generate(self, messages: List[Dict[str, str]], system_instruction: str) -> str:
        last_message = messages[-1]["content"] if messages else ""
        turn_count = len(messages)

        # Detect if user asks about previous turns
        context_cues = []
        for i, m in enumerate(messages[:-1]):
            if m["role"] == "user":
                words = m["content"].lower().split()
                # Find prominent keywords
                keywords = [w for w in words if len(w) > 4 and w not in ["about", "would", "could", "should", "there"]]
                if keywords:
                    context_cues.append(f"Turn {i+1} topic: '{', '.join(keywords[:2])}'")

        simulated_response = (
            f"**[{self.persona_name} - Senior Architect Mode]**\n\n"
            f"I have received your message: *\"{last_message}\"*\n\n"
        )

        if "Prior Conversation Context Summary:" in system_instruction:
            summary_part = system_instruction.split("Prior Conversation Context Summary:")[1][:200]
            simulated_response += f"📌 **Active Running Summary Recalled:**\n> {summary_part.strip()}...\n\n"
        elif context_cues:
            simulated_response += f"🧠 **Retained Active Multi-Turn Memory ({turn_count} turns in sliding window):**\n"
            for cue in context_cues[-3:]:
                simulated_response += f"- Recalled context: {cue}\n"
            simulated_response += "\n"

        simulated_response += (
            f"From an architectural standpoint, maintaining context while bounding memory and token complexity is "
            f"the cornerstone of production conversational systems. Each turn feeds into our context manager "
            f"ensuring no memory leaks or prompt truncation overflows occur."
        )

        # If user has not configured API key, remind them gently
        if not settings.has_valid_api_key():
            simulated_response += (
                "\n\n> ℹ️ *Note: Currently running in **Offline Simulation Mode** because no `GEMINI_API_KEY` or `OPENAI_API_KEY` "
                "is set in `.env`. Add your API key to `.env` to enable live cloud model inference!*"
            )

        return simulated_response

    def summarize(self, messages: List[Dict[str, str]], existing_summary: str = "") -> str:
        summarized_items = []
        for m in messages:
            if m["role"] == "user":
                summarized_items.append(f"User inquired: {m['content'][:45]}...")
            elif m["role"] == "assistant":
                summarized_items.append(f"Atlas recommended: {m['content'][:45]}...")

        new_notes = "\n".join([f"- {item}" for item in summarized_items[:4]])
        if existing_summary:
            return f"{existing_summary}\n{new_notes}"
        return f"Summary of earlier turns:\n{new_notes}"


def get_llm_client() -> BaseLLMClient:
    """Factory to get the appropriate LLM client based on settings."""
    provider = settings.llm_provider.lower()
    
    if not settings.has_valid_api_key():
        logger.warning("No valid API key found. Defaulting to MockLLMClient for offline testing/demo.")
        return MockLLMClient(persona_name=settings.bot_name)

    try:
        if provider == "gemini":
            return GeminiClient(api_key=settings.gemini_api_key, model_name=settings.gemini_model)
        elif provider == "openai":
            return OpenAIClient(api_key=settings.openai_api_key, model_name=settings.openai_model)
        else:
            logger.warning(f"Unknown provider '{provider}', falling back to Gemini.")
            return GeminiClient(api_key=settings.gemini_api_key, model_name=settings.gemini_model)
    except Exception as e:
        logger.error(f"Error instantiating {provider} client: {e}. Falling back to MockLLMClient.")
        return MockLLMClient(persona_name=settings.bot_name)
