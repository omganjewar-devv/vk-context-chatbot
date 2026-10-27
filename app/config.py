import os
from typing import Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv(override=True)

class Settings(BaseModel):
    # LLM Provider configuration
    llm_provider: Literal["gemini", "openai"] = Field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini").lower()
    )
    
    # Google Gemini Settings
    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip()
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    )
    
    # OpenAI Settings
    openai_api_key: str = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip()
    )
    openai_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    )
    
    # Context Management
    context_strategy: Literal["truncation", "summarization"] = Field(
        default_factory=lambda: os.getenv("CONTEXT_STRATEGY", "truncation").lower()
    )
    max_history_messages: int = Field(
        default_factory=lambda: int(os.getenv("MAX_HISTORY_MESSAGES", "6"))
    )
    summary_trigger_threshold: int = Field(
        default_factory=lambda: int(os.getenv("SUMMARY_TRIGGER_THRESHOLD", "6"))
    )
    
    # Bot Persona
    bot_name: str = Field(
        default_factory=lambda: os.getenv("BOT_NAME", "Atlas").strip()
    )
    bot_role: str = Field(
        default_factory=lambda: os.getenv("BOT_ROLE", "Senior Software Architect & Technical Career Mentor").strip()
    )
    
    # Server configuration
    host: str = Field(
        default_factory=lambda: os.getenv("HOST", "0.0.0.0")
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("PORT", "8000"))
    )

    def active_api_key(self) -> str:
        """Returns the API key for the selected provider."""
        if self.llm_provider == "gemini":
            return self.gemini_api_key
        return self.openai_api_key

    def has_valid_api_key(self) -> bool:
        """Checks if a non-placeholder API key is configured."""
        key = self.active_api_key()
        if not key:
            return False
        placeholders = ["your_gemini_api_key_here", "your_openai_api_key_here", "your_api_key_here", "test", "xxx"]
        return key not in placeholders and len(key) > 8

    def reload(self):
        """Reload configuration from disk / environment."""
        load_dotenv(override=True)
        self.__init__()


settings = Settings()
