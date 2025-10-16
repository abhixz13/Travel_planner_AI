# core/orchestrator.py

from __future__ import annotations
from typing import Any, Dict
import logging

from langgraph.graph import StateGraph, END
from core.state import GraphState
from core.router_policy import route_after_extract
from agents.plan_composer_agent import compose_itinerary

# Agents/nodes
from agents.clarification_agent import extract_travel_info
from agents.destination_discovery_agent import suggest_destinations
from agents.travel_planner_agent import create_itinerary
from agents.travel_options_agent import find_travel_options
from agents.accommodation_agent import find_accommodation
from agents.activities_agent import find_activities

logger = logging.getLogger(__name__)

# -----------------------------
# MUST-HAVE helpers (minimal)
# -----------------------------
def _is_non_empty_mapping(value: Any) -> bool:
    """True iff value is a non-empty dict."""
    return isinstance(value, dict) and len(value) > 0


def _ensure_plan_initialized(state: GraphState) -> None:
    """
    Ensure state["current_plan"] exists and has the normalized shape:
      {
        "summary": dict (may be empty),
        "travel": None | dict,
        "stays": None | dict,
        "activities": None | dict
      }
    """
    plan = state.get("current_plan")
    if not isinstance(plan, dict):
        plan = {}
        state["current_plan"] = plan
        logger.debug("Initialized fresh current_plan container.")

    # Keep existing summary if present; otherwise default to {}
    if "summary" not in plan or not isinstance(plan.get("summary"), dict):
        plan["summary"] = plan.get("summary") if isinstance(plan.get("summary"), dict) else {}
        logger.debug("Ensured plan summary block exists.")

    # Normalize research sections to either None or dict
    for key in ("travel", "stays", "activities"):
        val = plan.get(key, None)
        if val is None or isinstance(val, dict):
            plan[key] = val  # OK: None or dict
        else:
            # Not part of the MUST-HAVES to coerce types, but the safest minimal fix
            # is to reset unexpected types to None so guarded calls can proceed.
            plan[key] = None
            logger.debug("Reset plan section '%s' to None due to unexpected type.", key)


def _merge_section(plan: Dict[str, Any], key: str, patch: Dict[str, Any]) -> None:
    """
    Strict merge gate:
    - Only merge if `patch` is a non-empty dict.
    - Section is replaced with `patch` (source of truth comes from the agent).
    """
    if _is_non_empty_mapping(patch):
        plan[key] = patch
        logger.debug("Merged %s research results into plan.", key)
    # else: ignore None, empty dict, or non-dicts (strict gate)


# -----------------------------
# Idempotent research runner
# -----------------------------
def _run_research(state: GraphState) -> GraphState:
    """
    Run travel, stays, and activities research with idempotence.

    MUST-HAVES implemented:
    1) Initialize normalized plan shape once.
    2) Guarded calls: only call an agent if the section is None.
    3) Strict merge gate: only merge when the agent returns a non-empty dict.
    4) Agents are expected to RETURN patches (do not mutate current_plan directly).
    """
    _ensure_plan_initialized(state)
    plan = state["current_plan"]

    pending_sections = [key for key in ("travel", "stays", "activities") if plan.get(key) is None]
    if pending_sections:
        logger.info("Research pending for sections: %s.", ", ".join(pending_sections))
    else:
        logger.info("All research sections already populated; skipping web calls.")
        return state

    # TRAVEL
    if plan.get("travel") is None:
        logger.debug("Running travel research.")
        travel_patch = find_travel_options(state)  # expected: dict or None
        if _is_non_empty_mapping(travel_patch):
            _merge_section(plan, "travel", travel_patch)
    else:
        logger.debug("Skipping travel research; results already present.")

    # STAYS
    if plan.get("stays") is None:
        logger.debug("Running accommodation research.")
        stays_patch = find_accommodation(state)  # expected: dict or None
        if _is_non_empty_mapping(stays_patch):
            _merge_section(plan, "stays", stays_patch)
    else:
        logger.debug("Skipping accommodation research; results already present.")

    # ACTIVITIES
    if plan.get("activities") is None:
        logger.debug("Running activities research.")
        activities_patch = find_activities(state)  # expected: dict or None
        if _is_non_empty_mapping(activities_patch):
            _merge_section(plan, "activities", activities_patch)
    else:
        logger.debug("Skipping activities research; results already present.")

    return state


# -----------------------------
# Routing and graph wiring
# -----------------------------
def route_after_discover(state: GraphState):
    """Determine next step after destination discovery."""
    ex = state.get("extracted_info", {}) or {}
    has_destination = bool(ex.get("destination"))
    has_dates = bool(ex.get("departure_date")) and bool(ex.get("return_date"))
    has_duration = bool(ex.get("duration_days"))
    ready_for_plan = has_destination and (has_dates or has_duration)
    if ready_for_plan:
        logger.info("Discovery complete with sufficient info; proceeding to plan.")
        return "generate_plan"
    logger.info("Discovery yielded insufficient info; ending branch.")
    return "end"


def build_graph():
    """Wire LangGraph nodes & edges for the prototype."""
    g = StateGraph(GraphState)

    # Nodes
    g.add_node("extract_info", extract_travel_info)
    g.add_node("discover_destination", suggest_destinations)
    g.add_node("generate_plan", create_itinerary)
    g.add_node("run_research", _run_research)
    g.add_node("compose_response", compose_itinerary)

    # Entry + routing
    g.set_entry_point("extract_info")
    g.add_conditional_edges(
        "extract_info",
        route_after_extract,
        {"ask_more": END, "discover": "discover_destination", "plan": "generate_plan"},
    )
    g.add_conditional_edges(
        "discover_destination",
        route_after_discover,
        {"generate_plan": "generate_plan", "end": END},
    )

    # Research fan-out handled inside run_research to guarantee completeness
    g.add_edge("generate_plan", "run_research")

    # Compose once all research is gathered
    g.add_edge("run_research", "compose_response")
    g.add_edge("compose_response", END)

    logger.debug("Compiling LangGraph.")
    return g.compile()

APP = build_graph()

def run_session(state: GraphState) -> GraphState:
    """Run one turn and return updated state (LangSmith tracing via env vars)."""
    logger.info("Starting run_session with %d messages.", len(state.get("messages", [])))
    new_state = APP.invoke(state)
    logger.info("Completed run_session; total messages now %d.", len(new_state.get("messages", [])))
    return new_state
