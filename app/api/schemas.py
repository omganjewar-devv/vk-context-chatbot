from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message content")
    conversation_id: Optional[str] = Field(default=None, description="Unique conversation session ID")
    strategy: Optional[Literal["truncation", "summarization"]] = Field(
        default=None,
        description="Context strategy override for this turn"
    )
    system_prompt: Optional[str] = Field(default=None, description="Optional custom system prompt")


class ContextMetadata(BaseModel):
    conversation_id: str
    total_history_count: int
    active_context_count: int
    pruned_count: int
    has_summary: bool
    summary: Optional[str] = None
    strategy: str
    estimated_tokens: int
    provider: str
    model: str
    is_mock_mode: bool


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    metadata: ContextMetadata
    error: Optional[str] = None


class MessageItem(BaseModel):
    role: str
    content: str
    timestamp: float
    estimated_tokens: int


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    created_at: float
    updated_at: float
    strategy: str
    running_summary: str
    message_count: int
    messages: List[MessageItem]


class ConversationSummaryResponse(BaseModel):
    conversation_id: str
    created_at: float
    updated_at: float
    message_count: int
    strategy: str
    last_message_preview: str
    has_summary: bool


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    has_valid_key: bool
    active_sessions_count: int
    bot_name: str
    bot_role: str
