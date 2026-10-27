import logging
from fastapi import APIRouter, HTTPException, status
from app.config import settings
from app.core.memory import conversation_manager
from app.core.system_prompt import get_default_system_prompt
from app.core.llm_client import get_llm_client, LLMException
from app.api.schemas import (
    ChatRequest,
    ChatResponse,
    ContextMetadata,
    ConversationDetailResponse,
    ConversationSummaryResponse,
    HealthResponse,
    MessageItem
)

router = APIRouter(prefix="/api", tags=["Chat & Conversations"])
logger = logging.getLogger("chatbot.api")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint:
    - Maintains multi-turn conversation history per conversation_id
    - Applies context window management (sliding window truncation or running summarization)
    - Enforces system persona
    - Performs robust error handling for API timeouts, rate limits, and network errors
    """
    try:
        # 1. Retrieve or initialize the conversation session
        strategy = request.strategy or settings.context_strategy
        session = conversation_manager.get_or_create_session(
            conversation_id=request.conversation_id,
            strategy=strategy,
            max_messages=settings.max_history_messages,
            summary_trigger_threshold=settings.summary_trigger_threshold
        )

        # 2. Add the user's incoming message to history
        session.add_message(role="user", content=request.message.strip())

        # 3. Retrieve LLM client
        llm = get_llm_client()

        # 4. Handle Running Summarization if strategy is active
        if session.strategy == "summarization":
            unsummarized = session.get_messages_for_summarization()
            if unsummarized and len(session.history) > session.summary_trigger_threshold:
                try:
                    slice_dicts = [{"role": m.role, "content": m.content} for m in unsummarized]
                    new_summary = llm.summarize(slice_dicts, existing_summary=session.running_summary)
                    cutoff_index = len(session.history) - max(2, session.max_messages // 2)
                    session.commit_summary(new_summary, cutoff_index)
                except Exception as sum_err:
                    logger.warning(f"Summarization attempt encountered warning: {sum_err}")
                    # Summarization failure doesn't halt the conversation; fallback continues

        # 5. Assemble system instruction
        base_system_prompt = request.system_prompt or get_default_system_prompt()
        if session.strategy == "summarization" and session.running_summary:
            effective_system_prompt = (
                f"{base_system_prompt}\n\n"
                f"### Prior Conversation Context Summary:\n{session.running_summary}"
            )
        else:
            effective_system_prompt = base_system_prompt

        # 6. Build the context window payload according to the strategy
        context_result = conversation_manager.build_llm_context(session, effective_system_prompt)

        # 7. Call LLM to generate response
        try:
            reply_text = llm.generate(
                messages=context_result.messages,
                system_instruction=effective_system_prompt
            )
        except LLMException as llm_err:
            # Handle structured LLM exceptions gracefully
            logger.error(f"LLMException caught: {llm_err.message} ({llm_err.error_type})")
            error_notice = f"⚠️ [System Alert: {llm_err.error_type}]\n{llm_err.message}"
            session.add_message(role="assistant", content=error_notice)
            
            meta = ContextMetadata(
                conversation_id=session.conversation_id,
                total_history_count=context_result.total_history_count,
                active_context_count=context_result.active_context_count,
                pruned_count=context_result.pruned_count,
                has_summary=context_result.has_summary,
                summary=context_result.summary,
                strategy=session.strategy,
                estimated_tokens=context_result.estimated_total_tokens,
                provider=settings.llm_provider,
                model=settings.gemini_model if settings.llm_provider == "gemini" else settings.openai_model,
                is_mock_mode=not settings.has_valid_api_key()
            )
            return ChatResponse(
                reply=error_notice,
                conversation_id=session.conversation_id,
                metadata=meta,
                error=llm_err.message
            )
        except Exception as unk_err:
            logger.error(f"Unexpected error during generation: {unk_err}")
            fallback_msg = f"⚠️ An unexpected system error occurred: {str(unk_err)}. Please try again."
            session.add_message(role="assistant", content=fallback_msg)
            
            meta = ContextMetadata(
                conversation_id=session.conversation_id,
                total_history_count=context_result.total_history_count,
                active_context_count=context_result.active_context_count,
                pruned_count=context_result.pruned_count,
                has_summary=context_result.has_summary,
                summary=context_result.summary,
                strategy=session.strategy,
                estimated_tokens=context_result.estimated_total_tokens,
                provider=settings.llm_provider,
                model=settings.gemini_model if settings.llm_provider == "gemini" else settings.openai_model,
                is_mock_mode=not settings.has_valid_api_key()
            )
            return ChatResponse(
                reply=fallback_msg,
                conversation_id=session.conversation_id,
                metadata=meta,
                error=str(unk_err)
            )

        # 8. Record assistant reply in conversation history
        session.add_message(role="assistant", content=reply_text)

        # 9. Return structured response with rich context metadata
        active_model = settings.gemini_model if settings.llm_provider == "gemini" else settings.openai_model
        meta = ContextMetadata(
            conversation_id=session.conversation_id,
            total_history_count=context_result.total_history_count + 1,
            active_context_count=context_result.active_context_count + 1,
            pruned_count=context_result.pruned_count,
            has_summary=context_result.has_summary,
            summary=context_result.summary,
            strategy=session.strategy,
            estimated_tokens=context_result.estimated_total_tokens,
            provider=settings.llm_provider,
            model=active_model,
            is_mock_mode=not settings.has_valid_api_key()
        )

        return ChatResponse(
            reply=reply_text,
            conversation_id=session.conversation_id,
            metadata=meta
        )

    except Exception as e:
        logger.exception("Critical error in chat_endpoint")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}"
        )


@router.get("/conversations", response_model=list[ConversationSummaryResponse])
async def list_conversations():
    """Returns a list of all active multi-turn conversations."""
    return conversation_manager.list_sessions()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str):
    """Retrieves full conversation details, history, and context state."""
    session = conversation_manager.get_session(conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Conversation session not found.")
    
    messages = [
        MessageItem(
            role=m.role,
            content=m.content,
            timestamp=m.timestamp,
            estimated_tokens=m.estimated_tokens
        )
        for m in session.history
    ]
    
    return ConversationDetailResponse(
        conversation_id=session.conversation_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        strategy=session.strategy,
        running_summary=session.running_summary,
        message_count=len(session.history),
        messages=messages
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Deletes a conversation session from memory."""
    deleted = conversation_manager.delete_session(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation session not found.")
    return {"status": "success", "message": f"Conversation {conversation_id} deleted."}


@router.post("/conversations/{conversation_id}/reset")
async def reset_conversation(conversation_id: str):
    """Clears history and context for a conversation while keeping the same session ID."""
    session = conversation_manager.get_session(conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Conversation session not found.")
    session.clear()
    return {"status": "success", "message": f"Conversation {conversation_id} reset."}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health status and configuration inspector."""
    active_model = settings.gemini_model if settings.llm_provider == "gemini" else settings.openai_model
    return HealthResponse(
        status="healthy",
        provider=settings.llm_provider,
        model=active_model,
        has_valid_key=settings.has_valid_api_key(),
        active_sessions_count=len(conversation_manager.sessions),
        bot_name=settings.bot_name,
        bot_role=settings.bot_role
    )
