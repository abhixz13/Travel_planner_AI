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
Route = Literal["ask_more", "discover", "plan"]


def route_after_extract(state: GraphState) -> Route:
    """Determine what to do next based on current state."""

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
