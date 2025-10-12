# core/state.py

from __future__ import annotations
from typing import Any, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage

class GraphState(TypedDict, total=False):
    messages: List[BaseMessage]
    extracted_info: Dict[str, Any]
    current_plan: Dict[str, Any]
    tool_results: Dict[str, Any]

def new_state(
    *, messages: Optional[List[BaseMessage]] = None,
    extracted_info: Optional[Dict[str, Any]] = None,
    ) -> GraphState:
    
    """Create a new, clean state."""
    return {
        "messages": list(messages or []),
        "extracted_info": dict(extracted_info or {}),
        "current_plan": {},
        "tool_results": {},
    }

def add_message(state: GraphState, msg: BaseMessage) -> GraphState:
    """Append a chat turn to history."""
    state.setdefault("messages", []).append(msg)
    return state
