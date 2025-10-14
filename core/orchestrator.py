# core/orchestrator.py

from __future__ import annotations
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
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

def build_graph():
    """Wire LangGraph nodes & edges for the prototype."""
    g = StateGraph(GraphState)

    # Nodes
    g.add_node("extract_info", extract_travel_info)
    g.add_node("discover_destination", suggest_destinations)
    g.add_node("generate_plan", create_itinerary)
    g.add_node("fetch_travel", find_travel_options)
    g.add_node("fetch_stays", find_accommodation)
    g.add_node("fetch_activities", find_activities)
    g.add_node("compose_response", compose_itinerary)

    # Entry + routing
    g.set_entry_point("extract_info")
    g.add_conditional_edges(
        "extract_info",
        route_after_extract,
        {"ask_more": END, "discover": "discover_destination", "plan": "generate_plan"},
    )
    g.add_edge("discover_destination", "generate_plan")

    # Fan-out (parallel) after planning
    g.add_edge("generate_plan", "fetch_travel")
    g.add_edge("generate_plan", "fetch_stays")
    g.add_edge("generate_plan", "fetch_activities")

    # Join into composer
    g.add_edge("fetch_travel", "compose_response")
    g.add_edge("fetch_stays", "compose_response")
    g.add_edge("fetch_activities", "compose_response")
    g.add_edge("compose_response", END)

    return g.compile()

APP = build_graph()

def run_session(state: GraphState) -> GraphState:
    """Run one turn and return updated state (LangSmith tracing via env vars)."""
    return APP.invoke(state)
