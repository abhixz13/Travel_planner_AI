# core/orchestrator.py

from __future__ import annotations
from typing import Any, Dict, Callable, Optional
import logging

from langgraph.graph import StateGraph, END
from core.state import GraphState
from core.router_policy import route_after_extract
from agents.plan_composer_agent import compose_itinerary
from core.fp import compute_fp

# Agents/nodes
from agents.clarification_agent import extract_travel_info
from agents.destination_discovery_agent import suggest_destinations
from agents.travel_planner_agent import create_itinerary
from agents.travel_options_agent import find_travel_options
from agents.accommodation_agent import find_accommodation
from agents.activities_agent import find_activities

logger = logging.getLogger(__name__)

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


def _should_merge(payload: Dict[str, Any]) -> bool:
    """Return True if the payload satisfies merge requirements."""
    if not isinstance(payload, dict):
        return False
    summary = payload.get("summary")
    results = payload.get("results")
    has_summary = isinstance(summary, str) and summary.strip() != ""
    has_results = isinstance(results, list) and len(results) > 0
    return has_summary or has_results


# -----------------------------
# Idempotent research runner
# -----------------------------
def _run_research(state: GraphState) -> GraphState:
    """Run research agents with fingerprint-based gating and strict merge rules."""

    SectionConfig = Dict[str, Any]

    def _clean_str(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _travel_ready(ex: Dict[str, Any]) -> bool:
        origin = _clean_str(ex.get("origin"))
        destination = _clean_str(ex.get("destination"))
        dep = _clean_str(ex.get("departure_date"))
        ret = _clean_str(ex.get("return_date"))
        return (
            bool(origin)
            and bool(destination)
            and (bool(dep) or bool(ret) or bool(ex.get("duration_days")))
        )

    def _stays_ready(ex: Dict[str, Any]) -> bool:
        destination = _clean_str(ex.get("destination"))
        dep = _clean_str(ex.get("departure_date"))
        ret = _clean_str(ex.get("return_date"))
        return bool(destination and dep and ret)

    def _activities_ready(ex: Dict[str, Any]) -> bool:
        destination = _clean_str(ex.get("destination"))
        return bool(destination)

    section_map: Dict[str, SectionConfig] = {
        "travel": {
            "agent": find_travel_options,
            "keys": ["origin", "destination", "departure_date", "return_date", "trip_purpose"],
            "ready": _travel_ready,
        },
        "stays": {
            "agent": find_accommodation,
            "keys": ["destination", "departure_date", "return_date", "trip_purpose"],
            "ready": _stays_ready,
        },
        "activities": {
            "agent": find_activities,
            "keys": ["destination", "trip_purpose"],
            "ready": _activities_ready,
        },
    }

    _ensure_plan_initialized(state)
    plan = state["current_plan"]
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}

    for section, cfg in section_map.items():
        agent: Callable[[GraphState], Optional[Dict[str, Any]]] = cfg["agent"]
        keys = cfg["keys"]
        ready_fn = cfg["ready"]

        current_fp = compute_fp(ex, keys)
        existing_value = plan.get(section)
        existing_block = existing_value if isinstance(existing_value, dict) else None
        prev_fp = existing_block.get("_fp") if isinstance(existing_block, dict) else None

        if prev_fp == current_fp:
            logger.debug(
                "Research gating: section=%s fp_prev=%s fp_curr=%s decision=skip merged=False",
                section,
                prev_fp,
                current_fp,
            )
            continue

        if not ready_fn(ex):
            logger.debug(
                "Research gating: section=%s fp_prev=%s fp_curr=%s decision=skip merged=False (inputs incomplete)",
                section,
                prev_fp,
                current_fp,
            )
            continue

        patch = agent(state)
        merged = False
        if isinstance(patch, dict) and section in patch:
            payload = patch[section]
            if _should_merge(payload):
                payload = dict(payload)
                payload["_fp"] = current_fp
                plan[section] = payload
                merged = True
        logger.debug(
            "Research gating: section=%s fp_prev=%s fp_curr=%s decision=run merged=%s",
            section,
            prev_fp,
            current_fp,
            merged,
        )

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
