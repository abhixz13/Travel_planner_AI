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
from agents.refinement_agent import refine_itinerary, check_ready_to_finalize

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
            plan[key] = None
            logger.debug("Reset plan section '%s' to None due to unexpected type.", key)


def _should_merge(payload: Dict[str, Any]) -> bool:
    """
    Return True if the payload satisfies merge requirements.
    Updated to handle both old structure (summary/results) and new structure (recommendations/sources).
    """
    if not isinstance(payload, dict):
        return False
    
    # New structure: recommendations + sources
    recommendations = payload.get("recommendations")
    sources = payload.get("sources")
    has_recommendations = isinstance(recommendations, str) and recommendations.strip() != ""
    has_sources = isinstance(sources, list) and len(sources) > 0
    
    # Old structure: summary + results (for backwards compatibility)
    summary = payload.get("summary")
    results = payload.get("results")
    has_summary = isinstance(summary, str) and summary.strip() != ""
    has_results = isinstance(results, list) and len(results) > 0
    
    return (has_recommendations or has_sources) or (has_summary or has_results)


# -----------------------------
# Staged research runners
# -----------------------------
def _run_travel_research(state: GraphState) -> GraphState:
    """Run only travel research."""
    # print("\n" + "="*60)
    # print("🔍 TRAVEL RESEARCH AGENT")
    # print("="*60)

    _ensure_plan_initialized(state)
    plan = state["current_plan"]
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}

    # print(f"Input parameters:")
    # print(f"  Origin: {ex.get('origin', 'N/A')}")
    # print(f"  Destination: {ex.get('destination', 'N/A')}")
    # print(f"  Dates: {ex.get('departure_date', 'N/A')} to {ex.get('return_date', 'N/A')}")
    # print(f"  Purpose: {ex.get('trip_purpose', 'N/A')}")

    logger.info("Running travel research only...")

    # Only run travel agent
    from agents.travel_options_agent import find_travel_options
    patch = find_travel_options(state)

    if isinstance(patch, dict) and "travel" in patch:
        payload = patch["travel"]
        if _should_merge(payload):
            # Compute fingerprint and store
            fp = compute_fp(ex, ["origin", "destination", "departure_date", "return_date", "trip_purpose"])
            payload["_fp"] = fp
            plan["travel"] = payload
            logger.info("✓ Travel research completed and merged")
            # print(f"✓ Travel research successful")
            # print(f"   Fingerprint: {fp[:16]}...")
            # print("="*60 + "\n")
        else:
            logger.warning("✗ Travel research returned insufficient data")
            # print("✗ Travel research returned no results")
            # print("="*60 + "\n")
    else:
        # print("✗ Travel agent returned no data")
        # print("="*60 + "\n")
        pass

    return state


def _run_stays_research(state: GraphState) -> GraphState:
    """Run only stays research."""
    # print("\n" + "="*60)
    # print("🏨 ACCOMMODATION RESEARCH AGENT")
    # print("="*60)

    _ensure_plan_initialized(state)
    plan = state["current_plan"]
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}

    # Check for refinement criteria
    refinement = state.get("refinement_criteria", {}).get("accommodation")
    # if refinement:
    #     print(f"Refinement request: {refinement.get('user_request', 'N/A')}")

    # print(f"Input parameters:")
    # print(f"  Destination: {ex.get('destination', 'N/A')}")
    # print(f"  Dates: {ex.get('departure_date', 'N/A')} to {ex.get('return_date', 'N/A')}")
    # print(f"  Purpose: {ex.get('trip_purpose', 'N/A')}")

    logger.info("Running stays research only...")

    # Only run stays agent
    from agents.accommodation_agent import find_accommodation
    patch = find_accommodation(state)

    if isinstance(patch, dict) and "stays" in patch:
        payload = patch["stays"]
        if _should_merge(payload):
            fp = compute_fp(ex, ["destination", "departure_date", "return_date", "trip_purpose"])
            payload["_fp"] = fp
            plan["stays"] = payload
            logger.info("✓ Stays research completed and merged")
            # print(f"✓ Accommodation research successful")
            # print(f"   Fingerprint: {fp[:16]}...")
            # print("="*60 + "\n")
        else:
            logger.warning("✗ Stays research returned insufficient data")
            # print("✗ Stays research returned no results")
            # print("="*60 + "\n")
    else:
        # print("✗ Accommodation agent returned no data")
        # print("="*60 + "\n")
        pass

    return state


def _run_activities_research(state: GraphState) -> GraphState:
    """Run only activities research."""
    # print("\n" + "="*60)
    # print("🎯 ACTIVITIES RESEARCH AGENT")
    # print("="*60)

    _ensure_plan_initialized(state)
    plan = state["current_plan"]
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}

    # print(f"Input parameters:")
    # print(f"  Destination: {ex.get('destination', 'N/A')}")
    # print(f"  Purpose: {ex.get('trip_purpose', 'N/A')}")
    # print(f"  Duration: {ex.get('duration_days', 'N/A')} days")

    logger.info("Running activities research only...")

    # Only run activities agent
    from agents.activities_agent import find_activities
    patch = find_activities(state)

    if isinstance(patch, dict) and "activities" in patch:
        payload = patch["activities"]
        if _should_merge(payload):
            fp = compute_fp(ex, ["destination", "trip_purpose"])
            payload["_fp"] = fp
            plan["activities"] = payload
            logger.info("✓ Activities research completed and merged")
            # print(f"✓ Activities research successful")
            # print(f"   Fingerprint: {fp[:16]}...")
            # print("="*60 + "\n")
        else:
            logger.warning("✗ Activities research returned insufficient data")
            # print("✗ Activities research returned no results")
            # print("="*60 + "\n")
    else:
        # print("✗ Activities agent returned no data")
        # print("="*60 + "\n")
        pass

    return state


# -----------------------------
# Idempotent research runner (legacy - for full workflow)
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
            # print(f"✓ {section} options unchanged (using cached results)")
            continue

        if not ready_fn(ex):
            logger.debug(
                "Research gating: section=%s fp_prev=%s fp_curr=%s decision=skip merged=False (inputs incomplete)",
                section,
                prev_fp,
                current_fp,
            )
            # print(f"⊘ Skipping {section} research (inputs incomplete)")
            continue

        # Run the agent
        # print(f"\n🔍 Searching for {section} options...")
        logger.info(f"Running {section} research agent...")
        patch = agent(state)
        # print(f"✓ {section} research completed")
        merged = False
        
        if isinstance(patch, dict) and section in patch:
            payload = patch[section]
            if _should_merge(payload):
                payload = dict(payload)
                payload["_fp"] = current_fp
                plan[section] = payload
                merged = True
                logger.info(f"✓ {section.capitalize()} research completed and merged")
            else:
                logger.warning(f"✗ {section.capitalize()} research returned insufficient data")
        
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


def route_after_compose(state: GraphState):
    """Determine if user wants to refine itinerary or finalize."""
    # Check if itinerary was just generated (first time)
    ui_flags = state.get("ui_flags", {})

    if not ui_flags.get("itinerary_presented"):
        # First time showing itinerary - wait for user input
        state.setdefault("ui_flags", {})["itinerary_presented"] = True
        return "refine"

    # Check if user is ready to finalize
    if check_ready_to_finalize(state):
        logger.info("User confirmed - finalizing itinerary")
        return "end"

    # User wants to continue refining
    logger.info("Allowing further refinements")
    return "refine"


def route_after_refine(state: GraphState):
    """After refinement, check if we need to re-compose with selected hotel."""
    ui_flags = state.get("ui_flags") or {}
    components = state.get("itinerary_components") or {}

    # Check if hotel was just selected
    if ui_flags.get("hotel_selected"):
        # Clear flag to avoid loop
        ui_flags["hotel_selected"] = False

        # Check if we have days already (full itinerary exists)
        if isinstance(components, dict) and components.get("days"):
            logger.info("Hotel selected but full itinerary already exists - going to END")
            return "end"
        else:
            logger.info("Hotel selected - re-composing with full itinerary")
            return "compose_full"

    # Normal refinement flow - go to END
    return "end"


def build_graph():
    """Wire LangGraph nodes & edges for staged workflow."""
    g = StateGraph(GraphState)

    # Nodes
    g.add_node("extract_info", extract_travel_info)
    g.add_node("discover_destination", suggest_destinations)

    # Staged research nodes
    g.add_node("research_travel", _run_travel_research)
    g.add_node("research_stays", _run_stays_research)
    g.add_node("research_activities", _run_activities_research)

    # Composition and refinement
    g.add_node("compose_response", compose_itinerary)
    g.add_node("refine_itinerary", refine_itinerary)

    # Entry + routing
    g.set_entry_point("extract_info")
    g.add_conditional_edges(
        "extract_info",
        route_after_extract,
        {
            "ask_more": END,
            "discover": "discover_destination",
            "research_travel": "research_travel",
            "research_stays": "research_stays",
            "research_activities": "research_activities",
            "refine": "refine_itinerary"
        },
    )

    g.add_conditional_edges(
        "discover_destination",
        route_after_discover,
        {"generate_plan": "research_travel", "end": END},  # After discovery, start with travel
    )

    # Each research stage → compose → END (waits for user)
    g.add_edge("research_travel", "compose_response")
    g.add_edge("research_stays", "compose_response")
    g.add_edge("research_activities", "compose_response")
    g.add_edge("compose_response", END)

    # Refinement loop - conditional based on hotel selection
    g.add_conditional_edges(
        "refine_itinerary",
        route_after_refine,
        {
            "compose_full": "compose_response",  # Re-compose with full itinerary
            "end": END
        }
    )

    logger.debug("Compiling LangGraph for staged workflow.")
    return g.compile()

APP = build_graph()

def run_session(state: GraphState) -> GraphState:
    """Run one turn and return updated state (LangSmith tracing via env vars)."""
    # print("\n" + "="*60)
    # print("🚀 STARTING SESSION")
    # print("="*60 + "\n")

    logger.info("=" * 60)
    logger.info("Starting run_session with %d messages.", len(state.get("messages", [])))
    logger.info("=" * 60)

    try:
        new_state = APP.invoke(state)
        # print("\n" + "="*60)
        # print("✅ SESSION COMPLETED")
        # print("="*60 + "\n")
        logger.info("✓ Completed run_session; total messages now %d.", len(new_state.get("messages", [])))
        return new_state
    except Exception as exc:
        # print(f"\n❌ SESSION FAILED: {exc}\n")
        logger.exception("✗ Session failed with error:")
        raise