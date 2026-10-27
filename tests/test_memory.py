import pytest
from app.core.memory import ConversationManager, estimate_tokens


def test_token_estimation():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") >= 2
    assert estimate_tokens("a" * 40) == 10


def test_session_creation_and_isolation():
    manager = ConversationManager()
    session1 = manager.get_or_create_session("sess-1")
    session2 = manager.get_or_create_session("sess-2")

    session1.add_message("user", "Hello from session 1")
    session2.add_message("user", "Hello from session 2")

    assert len(session1.history) == 1
    assert len(session2.history) == 1
    assert session1.history[0].content == "Hello from session 1"
    assert session2.history[0].content == "Hello from session 2"


def test_sliding_window_truncation():
    manager = ConversationManager()
    session = manager.get_or_create_session("sess-trunc", strategy="truncation", max_messages=4)

    # Add 6 messages
    for i in range(6):
        session.add_message("user" if i % 2 == 0 else "assistant", f"Message {i+1}")

    assert len(session.history) == 6

    context = manager.build_llm_context(session, system_prompt="System instructions")

    # Context should only have the last 4 messages
    assert context.active_context_count == 4
    assert context.total_history_count == 6
    assert context.pruned_count == 2
    assert context.messages[0]["content"] == "Message 3"
    assert context.messages[-1]["content"] == "Message 6"
    assert context.has_summary is False


def test_summarization_strategy_lifecycle():
    manager = ConversationManager()
    session = manager.get_or_create_session(
        "sess-sum",
        strategy="summarization",
        max_messages=4,
        summary_trigger_threshold=4
    )

    # Initially empty
    assert session.get_messages_for_summarization() == []

    # Add 6 messages
    for i in range(6):
        session.add_message("user" if i % 2 == 0 else "assistant", f"Message {i+1}")

    # Messages needing summarization (older messages outside active window)
    to_summarize = session.get_messages_for_summarization()
    assert len(to_summarize) == 4  # 6 total - 2 active keep = 4 to summarize

    # Simulate committing summary
    session.commit_summary("Prior summary: user talked about architecture", up_to_index=4)
    assert session.running_summary == "Prior summary: user talked about architecture"

    context = manager.build_llm_context(session, system_prompt="System instructions")
    assert context.has_summary is True
    assert context.summary == "Prior summary: user talked about architecture"
    assert context.pruned_count == 4


def test_session_reset_and_delete():
    manager = ConversationManager()
    session = manager.get_or_create_session("sess-del")
    session.add_message("user", "To be deleted")
    assert len(session.history) == 1

    session.clear()
    assert len(session.history) == 0
    assert session.running_summary == ""

    assert manager.delete_session("sess-del") is True
    assert manager.get_session("sess-del") is None
