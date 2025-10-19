# core/state.py

from __future__ import annotations
from typing import Any, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage

class GraphState(TypedDict, total=False):
    messages: List[BaseMessage]
    extracted_info: Dict[str, Any]
    current_plan: Dict[str, Any]
    tool_results: Dict[str, Any]
    
    # ===== Phase 1 Additions =====
    itinerary_components: Dict[str, Any]  # Module 1.1: Component registry
    conversation_context: Dict[str, Any]  # Module 1.2: Context tracking

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
        "itinerary_components": {
            "metadata": {},
            "accommodation": None,
            "transport": None,
            "days": {}
        },
        "conversation_context": {
            "current_topic": None,
            "current_component_id": None,
            "last_modification": None,
            "pending_decision": None,
            "recent_components": [],
            "conversation_stage": "initial",
            "last_user_intent": None,
            "disambiguation_needed": False
        }
    }

def add_message(state: GraphState, msg: BaseMessage) -> GraphState:
    """Append a chat turn to history."""
    state.setdefault("messages", []).append(msg)
    return state