import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.memory import conversation_manager

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_sessions():
    """Clear in-memory sessions before each test."""
    conversation_manager.sessions.clear()


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "provider" in data
    assert "bot_name" in data


def test_chat_endpoint_multi_turn_flow():
    # Turn 1
    res1 = client.post("/api/chat", json={
        "message": "Hello! I am testing the chatbot API.",
        "strategy": "truncation"
    })
    assert res1.status_code == 200
    data1 = res1.json()
    assert "reply" in data1
    assert "conversation_id" in data1
    conv_id = data1["conversation_id"]
    assert data1["metadata"]["total_history_count"] == 2  # user + assistant

    # Turn 2 using the same conversation_id
    res2 = client.post("/api/chat", json={
        "message": "Can you recall my earlier test message?",
        "conversation_id": conv_id,
        "strategy": "truncation"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["conversation_id"] == conv_id
    assert data2["metadata"]["total_history_count"] == 4  # 2 turns = 4 messages


def test_conversations_crud_endpoints():
    # Create conversation through chat
    res = client.post("/api/chat", json={
        "message": "First message in CRUD test"
    })
    conv_id = res.json()["conversation_id"]

    # List conversations
    res_list = client.get("/api/conversations")
    assert res_list.status_code == 200
    sessions = res_list.json()
    assert any(s["conversation_id"] == conv_id for s in sessions)

    # Get conversation details
    res_detail = client.get(f"/api/conversations/{conv_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["conversation_id"] == conv_id
    assert len(detail["messages"]) == 2

    # Reset conversation
    res_reset = client.post(f"/api/conversations/{conv_id}/reset")
    assert res_reset.status_code == 200
    res_detail_after = client.get(f"/api/conversations/{conv_id}")
    assert len(res_detail_after.json()["messages"]) == 0

    # Delete conversation
    res_del = client.delete(f"/api/conversations/{conv_id}")
    assert res_del.status_code == 200
    res_detail_del = client.get(f"/api/conversations/{conv_id}")
    assert res_detail_del.status_code == 404


def test_error_handling_for_empty_message():
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 422  # Pydantic validation error
