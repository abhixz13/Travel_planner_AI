# core/routing_policy.py
"""
Routing Policy:
1. If clarification is incomplete → ask more questions.
2. If no destination is provided → run destination discovery.
3. Otherwise → proceed to trip planning.
"""

import logging
from typing import Literal
from core.state import GraphState

logger = logging.getLogger(__name__)

# Possible next steps in routing
Route = Literal["ask_more", "discover", "plan", "refine"]


def route_after_extract(state: GraphState) -> Route:
    """Determine what to do next based on current state."""

    # Check if itinerary already exists and user wants to refine it
    itinerary_components = state.get("itinerary_components", {})
    ui_flags = state.get("ui_flags", {})

    # If itinerary was generated and user has sent a new message
    if itinerary_components.get("days") and ui_flags.get("itinerary_presented"):
        from agents.refinement_agent import detect_refinement_intent
        from core.conversation_manager import last_user_message

        user_msg = last_user_message(state)
        intent = detect_refinement_intent(user_msg) if user_msg else None

        if intent:
            logger.info("Routing after extract → refine (refinement intent detected).")
            return "refine"

    tools = state.get("tool_results") or {}
    clarification = tools.get("clarification") or {}
    if clarification.get("status") != "complete":
        logger.info("Routing after extract → ask_more (clarification incomplete).")
        return "ask_more"

    discovery = tools.get("discovery") or {}
    if discovery.get("suggestions") and not discovery.get("resolved"):
        logger.info("Routing after extract → ask_more (awaiting destination pick).")
        return "ask_more"

    info = state.get("extracted_info", {})
    destination = (info.get("destination") or "").strip()

    if not destination:
        logger.info("Routing after extract → discover (destination missing).")
        return "discover"

    logger.info("Routing after extract → plan (destination present).")
    return "plan"
