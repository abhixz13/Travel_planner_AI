# agents/refinement_agent.py
"""
Refinement Agent - Handles user selections and itinerary modifications
Allows users to select hotels, swap activities, and finalize their plan.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
import logging
import re
from core.state import GraphState, add_message
from core.component_registry import (
    get_component, find_component, update_component,
    list_components_by_type, get_component_path
)
from core.conversation_manager import last_user_message
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def detect_refinement_intent(user_message: str) -> Optional[Dict[str, Any]]:
    """
    Simplified intent detection - only for hotel selection.
    Other intents are handled by LLM router.

    Returns:
        Dict with intent details or None if no refinement detected
    """
    msg_lower = user_message.lower().strip()

    # Simple hotel selection patterns
    hotel_patterns = [
        r'^\s*(\d+)\s*$',  # Just "1", "2", "3"
        r'(?:hotel|option)\s+(\d+)',  # "hotel 2", "option 3"
    ]

    for pattern in hotel_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            hotel_num = int(match.group(1))
            if 1 <= hotel_num <= 3:
                return {
                    "action": "select_hotel",
                    "target": f"hotel_{hotel_num}",
                    "selection_index": hotel_num - 1
                }

    return None


def handle_hotel_selection(state: GraphState, selection_index: int) -> bool:
    """
    Switch the selected hotel with an alternative.

    Args:
        state: GraphState
        selection_index: Index of hotel to select (0-based: 0=hotel1, 1=hotel2, 2=hotel3)

    Returns:
        True if successful
    """
    components = state.get("itinerary_components", {})
    current_hotel = components.get("accommodation")

    if not current_hotel:
        logger.warning("No primary accommodation found to swap")
        return False

    alternatives = current_hotel.get("alternatives", [])

    # Total available options = 1 primary + N alternatives
    total_options = 1 + len(alternatives)

    if selection_index < 0 or selection_index >= total_options:
        logger.warning(f"Invalid hotel selection index: {selection_index} (available: 0-{total_options-1})")
        return False

    # If selecting option 0 (primary hotel), just mark it as selected
    if selection_index == 0:
        current_hotel["selected"] = True
        logger.info(f"✓ Hotel selection confirmed: {current_hotel.get('name')} (already primary)")
        return True

    # Otherwise, swap with alternative at index (selection_index - 1)
    alternative_index = selection_index - 1
    selected_hotel = alternatives[alternative_index]

    # Build new alternatives list (all hotels except selected)
    new_alternatives = [current_hotel] + alternatives[:alternative_index] + alternatives[alternative_index + 1:]

    # Remove component_id fields from alternatives
    for alt in new_alternatives:
        alt.pop("component_id", None)
        alt.pop("component_type", None)
        alt.pop("registered_at", None)

    # Update to new primary hotel
    from core.component_registry import register_component
    register_component(
        state,
        component_data={
            "name": selected_hotel.get("name", "Hotel"),
            "description": selected_hotel.get("description", ""),
            "price_range": selected_hotel.get("price", ""),
            "features": selected_hotel.get("features", []),
            "alternatives": new_alternatives,
            "selected": True  # Mark as explicitly selected by user
        },
        component_type="accommodation"
    )

    logger.info(f"✓ Hotel selection updated: {selected_hotel.get('name')}")
    return True


def handle_activity_swap(state: GraphState, activity_reference: str,
                         replacement_request: str) -> Tuple[bool, Optional[str]]:
    """
    Find and prepare activity for swapping.

    Args:
        state: GraphState
        activity_reference: Natural language reference to activity
        replacement_request: User's request for what to replace it with

    Returns:
        (success, component_id) tuple
    """
    # Use component registry to find the activity
    component_id, component_data = find_component(state, activity_reference)

    if not component_data:
        logger.warning(f"Could not find activity: {activity_reference}")
        return False, None

    # Mark as pending replacement
    update_component(state, component_id, {
        "status": "pending_replacement",
        "replacement_request": replacement_request
    })

    logger.info(f"✓ Marked activity for replacement: {component_data.get('name')}")
    return True, component_id


def finalize_selections(state: GraphState) -> str:
    """
    Generate final itinerary summary with user's selected components.

    Returns:
        Formatted summary of final selections
    """
    components = state.get("itinerary_components", {})

    summary = "# ✓ Your Finalized Trip Plan\n\n"

    # Selected hotel
    hotel = components.get("accommodation")
    if hotel and hotel.get("selected"):
        summary += f"## 🏨 Selected Accommodation\n"
        summary += f"**{hotel.get('name')}**\n"
        summary += f"- {hotel.get('description')}\n"
        summary += f"- Price: {hotel.get('price_range')}\n\n"

    # Activities by day
    days = components.get("days", {})
    if days:
        summary += "## 📅 Final Itinerary\n\n"
        for day_key in sorted(days.keys()):
            day_num = day_key.replace("day", "")
            summary += f"### Day {day_num}\n"

            day_data = days[day_key]
            for slot in ["morning", "afternoon", "evening"]:
                slot_key = f"{slot}_slot"
                slot_data = day_data.get(slot_key)

                if isinstance(slot_data, dict) and slot_data.get("status") != "pending_replacement":
                    summary += f"**{slot.title()}**: {slot_data.get('name')}\n"

            summary += "\n"

    return summary


def handle_hotel_refinement_request(state: GraphState, user_message: str) -> GraphState:
    """
    User wants different hotel options (cheaper, different location, etc.).
    Store refinement criteria and flag for re-search.
    """
    from datetime import datetime

    # Store refinement criteria
    state.setdefault("refinement_criteria", {})["accommodation"] = {
        "user_request": user_message,
        "refined_at": datetime.now().isoformat()
    }

    # Clear previous hotel options (will trigger re-search)
    components = state.get("itinerary_components", {})
    if "accommodation" in components:
        components.pop("accommodation")

    # Clear accommodation alternatives from current_plan to force re-search
    current_plan = state.get("current_plan", {})
    if "stays" in current_plan:
        # Keep fingerprint to force re-search by clearing it
        current_plan["stays"] = None

    logger.info(f"Hotel refinement requested: {user_message[:100]}")
    add_message(state, AIMessage(content="Got it! Let me find better options for you..."))

    return state


def refine_itinerary(state: GraphState) -> GraphState:
    """
    Main refinement agent - handles user selections and modifications.

    Simplified: Only handles direct hotel selection here.
    Hotel refinement requests are detected by LLM router and routed to "plan".
    """
    user_msg = last_user_message(state)
    if not user_msg:
        return state

    logger.debug(f"Refinement agent processing: {user_msg[:100]}")

    # Detect simple hotel selection (1, 2, 3)
    intent = detect_refinement_intent(user_msg)

    if intent and intent.get("action") == "select_hotel":
        selection_idx = intent.get("selection_index", 0)
        success = handle_hotel_selection(state, selection_idx)

        if success:
            components = state.get("itinerary_components", {})
            hotel = components.get("accommodation", {})
            hotel_name = hotel.get("name", "Hotel")

            response = f"Perfect! I've selected **{hotel_name}**. Confirming your selection..."
            add_message(state, AIMessage(content=response))

            # Mark that hotel is selected AND confirmed - triggers activities research
            ui_flags = state.setdefault("ui_flags", {})
            ui_flags["hotel_selected"] = True
            ui_flags["hotel_confirmed"] = True
            logger.info(f"✓ Hotel selected and confirmed: {hotel_name}. Ready for activities research.")
        else:
            add_message(state, AIMessage(content="Sorry, I couldn't find that hotel option. Could you specify hotel 1, 2, or 3?"))
    else:
        # No hotel selection detected - LLM router should handle other cases
        logger.debug("No simple hotel selection detected. LLM router should have handled this.")
        add_message(state, AIMessage(content="I'm not sure what you'd like to adjust. Could you clarify?"))

    return state


def check_ready_to_finalize(state: GraphState) -> bool:
    """
    Check if user has made all necessary selections and is ready to finalize.

    Returns:
        True if ready to finalize
    """
    ui_flags = state.get("ui_flags", {})

    # Check if user has explicitly confirmed or made selections
    if ui_flags.get("confirmed_final"):
        return True

    # Check for finalization keywords in last message
    user_msg = last_user_message(state).lower()
    finalize_keywords = [
        "looks good", "looks great", "perfect", "that's great",
        "let's book", "ready to book", "finalize", "confirm",
        "that works", "sounds good"
    ]

    return any(keyword in user_msg for keyword in finalize_keywords)
