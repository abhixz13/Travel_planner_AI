# agents/travel_planner_agent.py
"""
Planner: builds a tiny base itinerary from extracted_info.
"""

from __future__ import annotations
from typing import Dict, Any, List
from core.state import GraphState

def _days(ex: Dict[str, Any]) -> int:
    try: return int(ex.get("duration_days") or 2)
    except: return 2

def _outline(days: int, purpose: str) -> List[Dict[str, Any]]:
    theme = (purpose or "").lower()
    plan = []
    for i in range(1, days+1):
        if "adventure" in theme: t = "outdoor/adventure"
        elif "relax" in theme or "chill" in theme: t = "relaxation"
        elif "sight" in theme: t = "sightseeing"
        else: t = "balanced"
        plan.append({"day": i, "theme": t, "notes": []})
    return plan

def create_itinerary(state: GraphState) -> GraphState:
    """Write current_plan with summary + outline."""
    ex: Dict[str, Any] = state.setdefault("extracted_info", {})
    d = _days(ex)
    state["current_plan"] = {
        "summary": f"{d}-day {(ex.get('trip_purpose') or 'trip')} for {(ex.get('travel_pack') or 'traveler(s)')}",
        "origin": ex.get("origin",""),
        "destination": ex.get("destination",""),
        "start_date": ex.get("departure_date",""),
        "end_date": ex.get("return_date",""),
        "duration_days": d,
        "trip_purpose": ex.get("trip_purpose",""),
        "travel_pack": ex.get("travel_pack",""),
        "constraints": ex.get("constraints",{}),
        "daily_outline": _outline(d, ex.get("trip_purpose","")),
    }
    return state
