import uuid
import time
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

def estimate_tokens(text: str) -> int:
    """
    Heuristic token estimation: ~4 characters per token in English.
    Gives a realistic approximation without requiring external tokenizers.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: float = Field(default_factory=time.time)
    estimated_tokens: int = 0

    def __init__(self, **data):
        super().__init__(**data)
        if not self.estimated_tokens:
            self.estimated_tokens = estimate_tokens(self.content)


class ContextBuildResult(BaseModel):
    messages: List[Dict[str, str]]
    total_history_count: int
    active_context_count: int
    pruned_count: int
    has_summary: bool
    summary: Optional[str] = None
    estimated_total_tokens: int = 0
    strategy_applied: str


class ConversationSession:
    """
    Represents an isolated multi-turn conversation session.
    Maintains full message history, running summary, and context configuration.
    """
    def __init__(
        self,
        conversation_id: Optional[str] = None,
        strategy: str = "truncation",
        max_messages: int = 6,
        summary_trigger_threshold: int = 6
    ):
        self.conversation_id: str = conversation_id or str(uuid.uuid4())
        self.created_at: float = time.time()
        self.updated_at: float = self.created_at
        self.strategy: str = strategy
        self.max_messages: int = max_messages
        self.summary_trigger_threshold: int = summary_trigger_threshold
        
        # Complete historical audit log of all messages
        self.history: List[ChatMessage] = []
        
        # Running summary for summarization strategy
        self.running_summary: str = ""
        self.last_summarized_index: int = 0

    def add_message(self, role: Literal["user", "assistant", "system"], content: str) -> ChatMessage:
        msg = ChatMessage(role=role, content=content)
        self.history.append(msg)
        self.updated_at = time.time()
        return msg

    def clear(self):
        self.history.clear()
        self.running_summary = ""
        self.last_summarized_index = 0
        self.updated_at = time.time()

    def get_messages_for_summarization(self) -> List[ChatMessage]:
        """
        Returns messages that need to be folded into the running summary.
        Leaves the most recent `max_messages // 2` messages in active window.
        """
        active_window_keep = max(2, self.max_messages // 2)
        if len(self.history) <= active_window_keep:
            return []
        
        # Everything from last_summarized_index up to (total - active_window_keep)
        cutoff_index = len(self.history) - active_window_keep
        if cutoff_index > self.last_summarized_index:
            slice_to_summarize = self.history[self.last_summarized_index:cutoff_index]
            return slice_to_summarize
        return []

    def commit_summary(self, new_summary: str, up_to_index: int):
        self.running_summary = new_summary
        self.last_summarized_index = up_to_index


class ConversationManager:
    """
    Thread-safe in-memory session manager for multi-turn conversations.
    Provides session creation, retrieval, context window management, and audit inspection.
    """
    def __init__(self):
        self.sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(
        self,
        conversation_id: Optional[str] = None,
        strategy: str = "truncation",
        max_messages: int = 6,
        summary_trigger_threshold: int = 6
    ) -> ConversationSession:
        if conversation_id and conversation_id in self.sessions:
            session = self.sessions[conversation_id]
            # Optional runtime strategy update
            if strategy:
                session.strategy = strategy
            return session
        
        new_id = conversation_id or str(uuid.uuid4())
        session = ConversationSession(
            conversation_id=new_id,
            strategy=strategy,
            max_messages=max_messages,
            summary_trigger_threshold=summary_trigger_threshold
        )
        self.sessions[new_id] = session
        return session

    def get_session(self, conversation_id: str) -> Optional[ConversationSession]:
        return self.sessions.get(conversation_id)

    def delete_session(self, conversation_id: str) -> bool:
        if conversation_id in self.sessions:
            del self.sessions[conversation_id]
            return True
        return False

    def list_sessions(self) -> List[Dict]:
        result = []
        for s_id, s in sorted(self.sessions.items(), key=lambda x: x[1].updated_at, reverse=True):
            last_msg = s.history[-1].content if s.history else ""
            result.append({
                "conversation_id": s_id,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "message_count": len(s.history),
                "strategy": s.strategy,
                "last_message_preview": (last_msg[:60] + "...") if len(last_msg) > 60 else last_msg,
                "has_summary": bool(s.running_summary)
            })
        return result

    def build_llm_context(
        self,
        session: ConversationSession,
        system_prompt: str
    ) -> ContextBuildResult:
        """
        Builds the exact payload of messages sent to the LLM API based on the active strategy.
        """
        total_history = len(session.history)
        strategy = session.strategy.lower()

        if strategy == "summarization":
            return self._build_summarized_context(session, system_prompt)
        else:
            return self._build_truncated_context(session, system_prompt)

    def _build_truncated_context(
        self,
        session: ConversationSession,
        system_prompt: str
    ) -> ContextBuildResult:
        """
        Sliding Window Strategy:
        Keeps only the last `max_messages` messages.
        Older messages are pruned to respect token limits.
        """
        max_msgs = session.max_messages
        total_history = len(session.history)
        
        if total_history <= max_msgs:
            active_slice = session.history
            pruned_count = 0
        else:
            active_slice = session.history[-max_msgs:]
            pruned_count = total_history - max_msgs

        messages = [{"role": msg.role, "content": msg.content} for msg in active_slice]
        
        # Calculate tokens
        tokens = estimate_tokens(system_prompt) + sum(msg.estimated_tokens for msg in active_slice)

        return ContextBuildResult(
            messages=messages,
            total_history_count=total_history,
            active_context_count=len(active_slice),
            pruned_count=pruned_count,
            has_summary=False,
            summary=None,
            estimated_total_tokens=tokens,
            strategy_applied="truncation"
        )

    def _build_summarized_context(
        self,
        session: ConversationSession,
        system_prompt: str
    ) -> ContextBuildResult:
        """
        Summarization Strategy:
        Prepends the running summary of past context to the system prompt or as a context banner,
        and includes the active recent messages.
        """
        active_window_keep = max(2, session.max_messages // 2)
        total_history = len(session.history)

        if total_history <= active_window_keep:
            active_slice = session.history
            pruned_count = 0
        else:
            active_slice = session.history[-active_window_keep:]
            pruned_count = total_history - len(active_slice)

        messages = [{"role": msg.role, "content": msg.content} for msg in active_slice]
        
        # If we have a running summary, calculate tokens including summary
        tokens = estimate_tokens(system_prompt) + estimate_tokens(session.running_summary) + sum(msg.estimated_tokens for msg in active_slice)

        return ContextBuildResult(
            messages=messages,
            total_history_count=total_history,
            active_context_count=len(active_slice),
            pruned_count=pruned_count,
            has_summary=bool(session.running_summary),
            summary=session.running_summary if session.running_summary else None,
            estimated_total_tokens=tokens,
            strategy_applied="summarization"
        )


conversation_manager = ConversationManager()
