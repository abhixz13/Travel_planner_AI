# core/conversation_manager.py (Updated with Phase 1 Integration)
from __future__ import annotations
from typing import List, Dict, Optional
import logging
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from core.state import GraphState, new_state, add_message
from core.context_tracker import initialize_context, update_context

logger = logging.getLogger(__name__)

# --- Lifecycle ---------------------------------------------------------------

def initiate_conversation(system_prompt: Optional[str] = None) -> GraphState:
    """Create a fresh state; optionally seed a system message."""
    state = new_state()
    
    # Initialize context tracking
    initialize_context(state)
    update_context(state, conversation_stage="initial")
    
    if system_prompt:
        add_message(state, SystemMessage(content=system_prompt))
        logger.debug("Initiated conversation with system prompt.")
    else:
        logger.debug("Initiated conversation without system prompt.")
    
    return state


def handle_user_input(state: GraphState, user_input: str) -> GraphState:
    """Append a user message (ignores empty/whitespace-only)."""
    if user_input and user_input.strip():
        add_message(state, HumanMessage(content=user_input.strip()))
        logger.debug("Captured user input: %s", user_input.strip())
        
        # Update context to track conversation flow
        from core.context_tracker import get_current_context
        ctx = get_current_context(state)
        
        # If we had a pending decision, note that we received a response
        if ctx.get("pending_decision"):
            logger.debug("User responded to pending decision")
    
    return state


def handle_ai_output(state: GraphState, text: str) -> GraphState:
    """Append an AI message; handy for nodes that directly speak to user."""
    if text and text.strip():
        add_message(state, AIMessage(content=text.strip()))
        logger.debug("Queued AI output: %s", text.strip()[:100] + "...")
    return state


# --- History utilities -------------------------------------------------------

def get_conversation_history(state: GraphState) -> List[Dict[str, str]]:
    """
    Return a simple [{role, content}] history for LLMs/UI.
    Preserves system/tool messages; callers can filter if needed.
    """
    out: List[Dict[str, str]] = []
    for msg in state.get("messages", []):
        role = (
            "user" if isinstance(msg, HumanMessage)
            else "assistant" if isinstance(msg, AIMessage)
            else "system" if isinstance(msg, SystemMessage)
            else "tool" if isinstance(msg, ToolMessage)
            else getattr(msg, "type", "assistant")
        )
        out.append({"role": role, "content": str(getattr(msg, "content", ""))})
    return out


def last_user_message(state: GraphState) -> str:
    """Return the most recent human message content (or empty)."""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


def trim_history(state: GraphState, max_messages: int = 30) -> GraphState:
    """Keep only the last N messages (simple, token-agnostic trim)."""
    msgs: List[BaseMessage] = state.get("messages", [])
    if len(msgs) > max_messages:
        state["messages"] = msgs[-max_messages:]
        logger.debug("Trimmed conversation history to last %d messages.", max_messages)
    return state


# --- Phase 1 Extensions -------------------------------------------------------

def get_conversation_stage(state: GraphState) -> str:
    """
    Get the current conversation stage.
    
    Returns:
        Stage string: "initial", "clarifying", "planning", "refining", "complete"
    """
    from core.context_tracker import get_current_context
    ctx = get_current_context(state)
    return ctx.get("conversation_stage", "initial")


def set_conversation_stage(state: GraphState, stage: str) -> None:
    """
    Update the conversation stage.
    
    Args:
        state: GraphState dictionary
        stage: New stage ("initial", "clarifying", "planning", "refining", "complete")
    """
    update_context(state, conversation_stage=stage)
    logger.debug(f"Conversation stage updated to: {stage}")