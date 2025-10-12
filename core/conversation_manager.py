# core/conversation_manager.py
from __future__ import annotations
from typing import List, Dict, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from core.state import GraphState, new_state, add_message

# --- Lifecycle ---------------------------------------------------------------

def initiate_conversation(system_prompt: Optional[str] = None) -> GraphState:
    """Create a fresh state; optionally seed a system message."""
    state = new_state()
    if system_prompt:
        add_message(state, SystemMessage(content=system_prompt))
    return state

def handle_user_input(state: GraphState, user_input: str) -> GraphState:
    """Append a user message (ignores empty/whitespace-only)."""
    if user_input and user_input.strip():
        add_message(state, HumanMessage(content=user_input.strip()))
    return state

def handle_ai_output(state: GraphState, text: str) -> GraphState:
    """Append an AI message; handy for nodes that directly speak to user."""
    if text and text.strip():
        add_message(state, AIMessage(content=text.strip()))
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
    return state
