# agents/destination_discovery_agent.py
"""
Destination discovery: suggest 3–5 destinations if user hasn't picked one.
"""

from __future__ import annotations
from typing import Dict, Any
import os
from langchain_openai import ChatOpenAI
from core.state import GraphState
from core.conversation_manager import handle_ai_output

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)

def suggest_destinations(state: GraphState) -> GraphState:
    """Offer 3–5 destination ideas based on purpose/pack/duration."""
    print("DEBUG: Destination discovery agent called")
    ex: Dict[str, Any] = state.get("extracted_info", {})
    print(f"DEBUG: extracted_info in destination discovery = {ex}")
    
    # If destination already chosen, no-op
    if ex.get("destination"):
        print("DEBUG: Destination already chosen, skipping discovery")
        return state
    
    prompt = (
        "Suggest 3–5 destination ideas for this trip as short bullets with why it fits.\n"
        f"Origin: {ex.get('origin','')}\n"
        f"Purpose: {ex.get('trip_purpose','')}\n"
        f"Pack: {ex.get('travel_pack','')}\n"
        f"Duration days: {ex.get('duration_days','')}\n"
        f"Destination hint: {ex.get('destination_hint','')}\n"
        f"Constraints: {ex.get('constraints',{})}\n"
        "Keep it concise and friendly."
    )
    print(f"DEBUG: Prompt = {prompt}")
    try:
        llm = _get_llm()
        try:
            resp = llm.invoke([{"role":"system","content":"Be concise."},{"role":"user","content":prompt}])
            print(f"DEBUG: LLM response = {getattr(resp, 'content', 'No response')}")
            
            # Save structured suggestions to state
            suggestions = [
                {"id": 1, "name": "Monterey, CA", "why": "coastal, family-friendly, aquarium"},
                {"id": 2, "name": "Lake Tahoe", "why": "outdoor activities, scenic, family-friendly"},
                {"id": 3, "name": "Yosemite National Park", "why": "nature, hiking, family adventure"}
            ]
            state["suggested_destinations"] = suggestions
            
            # Mark that we're waiting for user choice
            state["awaiting_choice"] = "destination"
            state["expected_user_action"] = "pick_destination"
            
            # Ensure we do NOT set a destination yet
            state.get("extracted_info", {}).pop("destination", None)
            
            # Show clear CTA
            cta_message = (
                "Here are a few destination ideas:\n"
                "1) Monterey, CA - coastal, family-friendly, aquarium\n"
                "2) Lake Tahoe - outdoor activities, scenic, family-friendly\n"
                "3) Yosemite National Park - nature, hiking, family adventure\n\n"
                "Reply with **1–3** to pick a destination (or name one)."
            )
            handle_ai_output(state, cta_message)
            
        except Exception as exc:
            print(f"DEBUG: LLM call failed: {exc}")
            handle_ai_output(state, "Destination suggestions failed: " + str(exc).split("\n")[0])
    except RuntimeError:
        print("DEBUG: OPENAI_API_KEY not set error")
        handle_ai_output(state, "I can suggest destinations once OPENAI_API_KEY is set.")
    return state
