# core/orchestrator.py

from __future__ import annotations
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


def _run_research(state: GraphState) -> GraphState:
    """Run travel, stay, and activity research sequentially."""
    find_travel_options(state)
    find_accommodation(state)
    find_activities(state)
    return state

def route_after_discover(state: GraphState):
    """Determine next step after destination discovery."""
    ex = state.get("extracted_info", {}) or {}
    has_destination = bool(ex.get("destination"))
    has_dates = bool(ex.get("departure_date")) and bool(ex.get("return_date"))
    has_duration = bool(ex.get("duration_days"))
    ready_for_plan = has_destination and (has_dates or has_duration)
    return "generate_plan" if ready_for_plan else "end"

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

    return g.compile()

APP = build_graph()

def run_session(state: GraphState) -> GraphState:
    """Run one turn and return updated state (LangSmith tracing via env vars)."""
    return APP.invoke(state)
