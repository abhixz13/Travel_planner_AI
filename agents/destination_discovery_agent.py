# agents/destination_discovery_agent.py
"""
Destination discovery: suggest 3–5 destinations if user hasn't picked one.
"""

from __future__ import annotations
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from core.state import GraphState
from core.conversation_manager import handle_ai_output

LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

def suggest_destinations(state: GraphState) -> GraphState:
    """Offer 3–5 destination ideas based on purpose/pack/duration."""
    ex: Dict[str, Any] = state.get("extracted_info", {})
    prompt = (
        "Suggest 3–5 destination ideas for this trip as short bullets with why it fits.\n"
        f"Origin: {ex.get('origin','')}\n"
        f"Purpose: {ex.get('trip_purpose','')}\n"
        f"Pack: {ex.get('travel_pack','')}\n"
        f"Duration days: {ex.get('duration_days','')}\n"
        f"Constraints: {ex.get('constraints',{})}\n"
        "Keep it concise and friendly."
    )
    resp = LLM.invoke([{"role":"system","content":"Be concise."},{"role":"user","content":prompt}])
    handle_ai_output(state, getattr(resp,"content","Here are a few ideas."))
    return state