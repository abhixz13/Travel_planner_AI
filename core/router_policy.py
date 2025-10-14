# core/routing_policy.py
"""
Routing Policy:
1. If clarification is incomplete → ask more questions.
2. If no destination is provided → run destination discovery.
3. Otherwise → proceed to trip planning.
"""

from typing import Literal
from core.state import GraphState

# Possible next steps in routing
Route = Literal["ask_more", "discover", "plan"]


def route_after_extract(state: GraphState) -> Route:
    """Determine what to do next based on current state."""

    # Step 1: Check if clarification is complete
    tools = state.get("tool_results") or {}
    clarification = tools.get("clarification") or {}
    if clarification.get("status") != "complete":
        return "ask_more"

    # Step 2: Check if destination info exists
    info = state.get("extracted_info", {})
    destination = (info.get("destination") or "").strip()
    print(f"DEBUG: extracted_info = {info}")
    print(f"DEBUG: destination = '{destination}'")

    # If no concrete destination is present, then discover
    if not destination:
        print("DEBUG: Routing to 'discover' (no destination)")
        return "discover"

    # Step 3: Ready to plan
    print("DEBUG: Routing to 'plan' (destination present)")
    return "plan"
