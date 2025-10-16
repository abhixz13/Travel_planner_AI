# agents/travel_planner_agent.py
"""
Planner stub: builds a tiny base itinerary from extracted_info.

Writes:
state["current_plan"] = {
  "summary": {origin, destination, dates{departure, return, duration_days}, purpose, pack},
  "travel": None, "stays": None, "activities": None
}
"""

from __future__ import annotations
from typing import Dict, Any
import logging
from datetime import datetime
from core.state import GraphState

logger = logging.getLogger(__name__)


def _duration_days(ex: Dict[str, Any]) -> int:
    """Best-effort duration: prefer explicit duration_days; else compute from dates; else 2."""
    # Explicit field wins if valid
    try:
        d = int(ex.get("duration_days")) if ex.get("duration_days") is not None else None
        if d and d > 0:
            return d
    except Exception:
        pass

    # Try to compute from ISO dates
    dep = (ex.get("departure_date") or "").strip()
    ret = (ex.get("return_date") or "").strip()
    try:
        if dep and ret:
            delta = (datetime.fromisoformat(ret) - datetime.fromisoformat(dep)).days
            if delta > 0:
                return delta
    except Exception:
        pass

    # Fallback
    return 2


def create_itinerary(state: GraphState) -> GraphState:
    """Minimal planner: write summary + empty sections."""
    ex: Dict[str, Any] = state.setdefault("extracted_info", {}) or {}

    summary = {
        "origin": ex.get("origin", "") or "",
        "destination": ex.get("destination", "") or "",
        "dates": {
            "departure": ex.get("departure_date", "") or "",
            "return": ex.get("return_date", "") or "",
            "duration_days": _duration_days(ex),
        },
        "purpose": ex.get("trip_purpose", "") or "",
        "pack": ex.get("travel_pack", "") or "",
    }

    state["current_plan"] = {
        "summary": summary,
        "travel": None,
        "stays": None,
        "activities": None,
    }
    logger.debug(
        "Planner seeded current_plan summary: origin=%s destination=%s duration=%s",
        summary["origin"],
        summary["destination"],
        summary["dates"]["duration_days"],
    )
    return state
