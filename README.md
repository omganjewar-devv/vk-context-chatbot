
# 🤖 Atlas: Context-Aware Multi-Turn LLM Chatbot

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-12%20passed-brightgreen.svg)]()

> A production-grade multi-turn conversational AI engine backed by real LLM APIs (**Google Gemini** & **OpenAI**) with active **Context Window Management**, **Sliding-Window Truncation**, **Running Summarization**, and a glassmorphic **Live Context Inspector**.

---

## 📋 Requirements & Features Matrix

| Requirement | Implementation Status | Architecture Component |
| :--- | :---: | :--- |
| **Backend LLM Endpoint** | ✅ Implemented | `POST /api/chat` with Google Gemini & OpenAI SDKs |
| **Multi-Turn Memory** | ✅ Implemented | Per-session isolation via `ConversationManager` and UUID session keys |
| **Context Window Management** | ✅ Implemented | **Two Strategies:** Sliding Window Truncation & Running Summarization |
| **Defined Persona & Purpose** | ✅ Implemented | **Atlas**: Senior Software Architect & Technical Mentor |
| **Graceful Error Handling** | ✅ Implemented | Structured `LLMException` handling 401, 429 rate limits, timeouts & fallbacks |
| **Zero API Key Leakage** | ✅ Implemented | `.env` tracked in `.gitignore` before first commit; `.env.example` provided |
| **Usable Frontend & CLI** | ✅ Implemented | Modern responsive Web Chat UI + Interactive Rich Terminal CLI (`cli.py`) |
| **5-Turn Conversation Proof** | ✅ Implemented | Automated verification suite (`test_5_turns.py`) testing factual recall |

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    UserClient[Web UI / Terminal CLI] -->|POST /api/chat {message, session_id}| Server[FastAPI Application]
    Server --> Manager[ConversationManager]
    
    subgraph MemoryLayer ["Multi-Turn Memory Engine"]
        Manager --> Session[ConversationSession]
        Session --> AuditHistory[(Complete Turn History)]
        
        Session --> StrategyCheck{Context Strategy}
        StrategyCheck -->|Truncation| SlidingWindow[Keep Last N Messages]
        StrategyCheck -->|Summarization| Summarizer[Fold Older Turns into Running Summary]
        
        SlidingWindow --> PayloadAssembler[Context Window Payload]
        Summarizer --> PayloadAssembler
        
        PayloadAssembler --> PersonaEngine[Inject Atlas System Persona]
    end
    
    MemoryLayer -->|Bounded Context + Persona| LLMClient[Unified LLM Client]
    
    subgraph CloudAPIs ["LLM Providers"]
        LLMClient -->|google-genai SDK| Gemini[Gemini 2.5 Flash]
        LLMClient -->|openai SDK| OpenAI[GPT-4o-mini]
        LLMClient -->|Zero Key Fallback| Mock[Offline Simulation Mode]
    end
    
    CloudAPIs -->|Generated Response| SafeHandler[Error Handling & Sanitizer]
    SafeHandler --> SessionUpdate[Store Assistant Reply & Context Metrics]
    SessionUpdate --> ResponsePayload[JSON Response + Live Metadata]
    ResponsePayload --> UserClient
```

---

## 🧠 Context Window Management Strategies

LLMs have finite context limits and bill on per-token consumption. Unbounded conversational history leads to exponential latency, $\mathcal{O}(N^2)$ self-attention cost, and eventual HTTP 400 context overflow crashes.

Atlas implements two complementary strategies:

### 1. Sliding Window Truncation (`truncation`)
- Maintains an active window of the last $N$ messages (configurable via `MAX_HISTORY_MESSAGES`, default: 6).
- Older messages are pruned from the immediate prompt payload sent to the LLM.
- **Latency overhead:** $0\text{ms}$ (instantaneous list slice).
- **Ideal for:** Rapid transactions, low turn depth, customer support triage.

### 2. Running Summarization (`summarization`)
- When total conversation messages exceed the threshold (default: 6), older messages outside the active window are compressed into a running factual summary.
- The running summary is prepended to the system prompt:
  ```
  ### Prior Conversation Context Summary:
  - User is Om, designing a distributed notification service with Kafka & Redis.
  - Throughput requirement: 50,000 events/sec with p99 < 20ms latency.
  ```
- **Semantic retention:** Retains foundational decisions and preferences even after 20+ turns without blowing out token budgets.
- **Ideal for:** Complex architectural reviews, coding sessions, and continuous advisory.

---

## 🚀 Quickstart Guide

### 1. Clone & Set Up Virtual Environment

```bash
# Clone the repository
git clone https://github.com/<your-github-username>/VK_internship.git
cd VK_internship

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` and configure your API key (Gemini is free and recommended):

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

*(Note: If you run without an API key, the system automatically runs in **Offline Simulation Mode**, allowing you to test the UI, memory engine, and CLI out of the box!)*

---

### 3. Step 2 Verification (Minimal Connection Test)

Verify your API key and connection with the single-message test:

```bash
python minimal_test.py
```

---

### 4. Run the Full Web Application

Start the FastAPI server:

```bash
python -m app.main
# Or: uvicorn app.main:app --reload --port 8000
```

Open your browser at:
👉 **`http://localhost:8000`**

- **Interactive Swagger Documentation:** `http://localhost:8000/docs`
- **Context Inspector:** Click the **"Context Inspector"** button in the top right to watch turns, tokens, pruned messages, and summaries update live.

---

### 5. Run the Interactive Terminal CLI

Prefer the command line? Run the rich terminal interface:

```bash
python cli.py
```

**Commands inside CLI:**
- `/context`: Inspect the active context window, token consumption, and running summary.
- `/strategy summarization`: Switch context strategy on the fly.
- `/strategy truncation`: Switch to sliding window.
- `/new`: Start a new conversation session.
- `/clear`: Clear history of current session.
- `/exit`: Quit CLI.

---

### 6. Run the Automated 5-Turn Verification

Verify multi-turn memory persistence and recall across 5 continuous dialogue turns:

```bash
# Run with sliding window truncation
python test_5_turns.py --strategy truncation

# Run with running summarization
python test_5_turns.py --strategy summarization
```

---

### 7. Run Automated Test Suite

```bash
pytest -v
```

All 12 unit and integration tests will execute and pass:
```
tests/test_api.py::test_health_endpoint PASSED
tests/test_api.py::test_chat_endpoint_multi_turn_flow PASSED
tests/test_api.py::test_conversations_crud_endpoints PASSED
tests/test_api.py::test_error_handling_for_empty_message PASSED
tests/test_llm_client.py::test_mock_llm_client_generation PASSED
tests/test_llm_client.py::test_mock_llm_client_summarization PASSED
tests/test_llm_client.py::test_llm_exception_properties PASSED
tests/test_memory.py::test_token_estimation PASSED
tests/test_memory.py::test_session_creation_and_isolation PASSED
tests/test_memory.py::test_sliding_window_truncation PASSED
tests/test_memory.py::test_summarization_strategy_lifecycle PASSED
tests/test_memory.py::test_session_reset_and_delete PASSED
```

---

## 📡 REST API Reference

### `POST /api/chat`
Sends a message to the LLM and maintains conversational state.

**Request Body:**
```json
{
  "message": "Hi, my project is a distributed notification engine.",
  "conversation_id": "optional-uuid-here",
  "strategy": "truncation"
}
```

**Response Body (HTTP 200):**
```json
{
  "reply": "Acknowledged. Let's design the ingestion queue and worker pool...",
  "conversation_id": "4b92ec7b-3b3b-4ce1-85e3-4752b04f74eb",
  "metadata": {
    "conversation_id": "4b92ec7b-3b3b-4ce1-85e3-4752b04f74eb",
    "total_history_count": 2,
    "active_context_count": 2,
    "pruned_count": 0,
    "has_summary": false,
    "summary": null,
    "strategy": "truncation",
    "estimated_tokens": 420,
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "is_mock_mode": false
  },
  "error": null
}
```

### Additional Endpoints:
- `GET /api/conversations`: List all active sessions with message counts & previews.
- `GET /api/conversations/{id}`: Inspect full transcript, context state, and running summary.
- `DELETE /api/conversations/{id}`: Delete a session from memory.
- `POST /api/conversations/{id}/reset`: Reset history while keeping the session ID.
- `GET /api/health`: Health status, active sessions count, model, and API key validation.

---

## 📁 Repository Structure

```
VK_internship/
├── .env.example              # Environment variables template (committed)
├── .gitignore                # Ensures .env, venv, and secrets are NEVER committed
├── requirements.txt          # Python dependencies
├── minimal_test.py           # Step 2: Minimal connection verification script
├── cli.py                    # Interactive Rich Terminal CLI
├── test_5_turns.py           # Automated 5-turn multi-turn verification runner
├── INTERVIEW_PREP.md         # Complete Technical Interview Q&A Guide
├── README.md                 # Project documentation
├── pytest.ini                # Pytest test configuration
├── app/
│   ├── __init__.py
│   ├── config.py             # Pydantic Settings & environment loader
│   ├── main.py               # FastAPI application entrypoint
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py         # REST API endpoints (/api/chat, /api/conversations)
│   │   └── schemas.py        # Pydantic request & response schemas
│   ├── core/
│   │   ├── __init__.py
│   │   ├── system_prompt.py  # Atlas Senior Architect persona instructions
│   │   ├── memory.py         # ConversationManager, SlidingWindow & Summarization
│   │   └── llm_client.py     # Gemini & OpenAI client wrapper + Error handling
│   └── static/
│       ├── index.html        # Modern Glassmorphic Chat UI
│       ├── app.js            # Frontend state, chat stream, inspector updates
│       └── style.css         # Styling, custom scrollbars, typography
└── tests/
    ├── __init__.py
    ├── test_api.py           # FastAPI integration tests
    ├── test_llm_client.py    # LLM client & error handling tests
    └── test_memory.py        # Context window & session isolation tests
```

---

## 🛡️ Security & Git Best Practices

- **Never Commit Secrets:** `.env` is listed in `.gitignore` prior to git initialization.
- **Input Validation:** All input payloads are strictly sanitized and validated via Pydantic models with minimum and maximum length bounds.
- **Fail-Safe UI:** In case of API rate limits or network issues, the system returns clear inline messages rather than unhandled exceptions or blank screens.

---


## 👨‍💻 Author
Prepared for **VK Internship Submission & Technical Evaluation**.

