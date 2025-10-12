# core/orchestrator.py

from __future__ import annotations
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
from core.state import GraphState
from core.routing_policy import route_after_extract
from core.conversation_manager import handle_ai_output

# Agents/nodes
from agents.clarifying_agent import extract_travel_info
from agents.destination_discovery_agent import suggest_destinations
from agents.travel_planner_agent import create_itinerary
from agents.travel_options_agent import find_travel_options
from agents.accommodation_agent import find_accommodation
from agents.activities_agent import find_activities

def compose_response(state: GraphState) -> GraphState:
    """Compose one friendly message from plan + branch outputs."""
    plan: Dict[str, Any] = state.get("current_plan", {})
    tools: Dict[str, Any] = state.get("tool_results", {})
    summary = plan.get("summary", "Trip plan")
    bits: List[str] = []
    if plan.get("origin"): bits.append(f"from **{plan['origin']}**")
    if plan.get("destination"): bits.append(f"to **{plan['destination']}**")
    if plan.get("duration_days"): bits.append(f"**{plan['duration_days']} days**")

    travel = tools.get("travel", {})
    stays  = tools.get("stays", {})
    acts   = tools.get("activities", {})

    out: List[str] = []
    out.append(f"**Plan**: {summary}")
    if bits: out.append(" • " + ", ".join(bits))

    if travel.get("suggested_queries"):
        out.append("\n**Travel — quick checks**")
        out += [f" • {q}" for q in travel["suggested_queries"][:4]]

    out.append("\n**Stays — summary**")
    out.append(f" • {stays.get('summary','I gathered helpful hotel/neighborhood links.')}")

    if acts.get("suggested_queries"):
        out.append("\n**Activities — ideas**")
        out += [f" • {q}" for q in acts["suggested_queries"][:4]]

    out.append("\nWant me to shortlist hotels, compare neighborhoods, or look up flights?")

    handle_ai_output(state, "\n".join(out))
    return state

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
    g.add_node("compose_response", compose_response)

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
