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
    Detect if user wants to refine/select components.

    Returns:
        Dict with intent details or None if no refinement detected
        {
            "action": "select_hotel" | "swap_activity" | "remove_component" | "modify_time",
            "target": component reference,
            "details": additional info
        }
    """
    msg_lower = user_message.lower()

    # Hotel selection patterns (more lenient matching)
    hotel_patterns = [
        r'(?:select|choose|pick|prefer|want|book)\s+(?:hotel\s+)?(?:option\s+)?(\d+)',
        r'(?:go with|let\'s do)\s+(?:hotel\s+)?(?:option\s+)?(\d+)',
        r'hotel\s+(?:option\s+)?(\d+)\s*(?:looks good|sounds good|is better|please)?',
        r'(?:i|we)\'d like\s+(?:hotel\s+)?(?:option\s+)?(\d+)',
        r'^\s*hotel\s+(\d+)\s*$',  # Simple "hotel 1" pattern
        r'option\s+(\d+)',  # Just "option 1"
        r'^\s*(\d+)\s*$',  # Just the number alone (e.g., "1", "2", "3")
    ]

    for pattern in hotel_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            hotel_num = int(match.group(1))
            # Only accept 1, 2, or 3
            if 1 <= hotel_num <= 3:
                return {
                    "action": "select_hotel",
                    "target": f"hotel_{hotel_num}",
                    "selection_index": hotel_num - 1
                }

    # Budget/price-based accommodation changes
    budget_patterns = [
        r'(?:cheaper|budget|less expensive|lower cost|affordable)\s+(?:place|hotel|accommodation|option)',
        r'(?:looking for|want|need)\s+(?:something\s+)?(?:cheaper|more affordable)',
        r'(?:show|find|suggest)\s+(?:me\s+)?(?:cheaper|budget)\s+(?:options|hotels)',
    ]

    for pattern in budget_patterns:
        if re.search(pattern, msg_lower):
            return {
                "action": "change_budget",
                "target": "accommodation",
                "preference": "cheaper"
            }

    # Activity swap patterns
    swap_patterns = [
        r'swap\s+(?:the\s+)?(.+?)\s+(?:activity|for)',
        r'replace\s+(?:the\s+)?(.+?)\s+with',
        r'change\s+(?:the\s+)?(.+?)\s+(?:to|activity)',
        r'(?:skip|remove)\s+(?:the\s+)?(.+)',
    ]

    for pattern in swap_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            return {
                "action": "swap_activity",
                "target": match.group(1).strip(),
                "details": user_message
            }

    # Time modification patterns
    if any(word in msg_lower for word in ["earlier", "later", "move", "reschedule"]):
        return {
            "action": "modify_time",
            "target": "schedule",
            "details": user_message
        }

    return None


def handle_hotel_selection(state: GraphState, selection_index: int) -> bool:
    """
    Switch the selected hotel with an alternative.

    Args:
        state: GraphState
        selection_index: Index of hotel to select (0-based)

    Returns:
        True if successful
    """
    components = state.get("itinerary_components", {})
    current_hotel = components.get("accommodation")

    if not current_hotel:
        logger.warning("No primary accommodation found to swap")
        return False

    alternatives = current_hotel.get("alternatives", [])

    if selection_index < 0 or selection_index >= len(alternatives):
        logger.warning(f"Invalid hotel selection index: {selection_index}")
        return False

    # Get the selected alternative
    selected_hotel = alternatives[selection_index]

    # Build new alternatives list (all hotels except selected)
    new_alternatives = [current_hotel] + alternatives[:selection_index] + alternatives[selection_index + 1:]

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


def refine_itinerary(state: GraphState) -> GraphState:
    """
    Main refinement agent - handles user selections and modifications.
    """
    user_msg = last_user_message(state)
    if not user_msg:
        return state

    logger.debug(f"Refinement agent processing: {user_msg[:100]}")

    # Detect refinement intent
    intent = detect_refinement_intent(user_msg)

    if not intent:
        # No refinement detected, let other agents handle
        logger.debug("No refinement intent detected")
        return state

    action = intent.get("action")

    # Handle hotel selection
    if action == "select_hotel":
        selection_idx = intent.get("selection_index", 0)
        success = handle_hotel_selection(state, selection_idx)

        if success:
            components = state.get("itinerary_components", {})
            hotel = components.get("accommodation", {})
            hotel_name = hotel.get("name", "Hotel")

            response = f"Perfect! I've updated your accommodation to **{hotel_name}**. "
            response += "Your itinerary has been updated. Would you like to adjust anything else?"
            add_message(state, AIMessage(content=response))

            # Mark that user has made selections
            state.setdefault("ui_flags", {})["has_selections"] = True
        else:
            add_message(state, AIMessage(content="Sorry, I couldn't find that hotel option. Could you specify hotel 1, 2, or 3?"))

    # Handle activity swap
    elif action == "swap_activity":
        target = intent.get("target", "")
        success, component_id = handle_activity_swap(state, target, user_msg)

        if success:
            response = f"Got it! I'll help you swap that activity. What would you like to do instead?"
            add_message(state, AIMessage(content=response))

            # Store pending swap for next agent to handle
            state.setdefault("pending_actions", []).append({
                "type": "activity_swap",
                "component_id": component_id,
                "user_request": user_msg
            })
        else:
            add_message(state, AIMessage(content=f"I couldn't find '{target}' in your itinerary. Could you be more specific?"))

    # Handle budget/price preference changes
    elif action == "change_budget":
        preference = intent.get("preference", "cheaper")
        components = state.get("itinerary_components", {})
        current_hotel = components.get("accommodation", {})
        alternatives = current_hotel.get("alternatives", [])

        if alternatives:
            # Find the cheapest alternative
            all_hotels = [current_hotel] + alternatives
            # Sort by price_per_night (handle both dict and object formats)
            try:
                sorted_hotels = sorted(
                    all_hotels,
                    key=lambda h: h.get("price_per_night", h.get("price", 999999))
                    if isinstance(h, dict)
                    else getattr(h, "price_per_night", 999999)
                )
                cheapest = sorted_hotels[0]
                cheapest_name = cheapest.get("name", "Hotel") if isinstance(cheapest, dict) else getattr(cheapest, "name", "Hotel")
                cheapest_price = cheapest.get("price_per_night", 0) if isinstance(cheapest, dict) else getattr(cheapest, "price_per_night", 0)

                # Update to cheapest option
                from core.component_registry import register_component

                # Prepare component data
                if isinstance(cheapest, dict):
                    cheapest_data = dict(cheapest)
                else:
                    cheapest_data = {
                        "name": cheapest.name,
                        "description": cheapest.description,
                        "price_per_night": cheapest.price_per_night,
                        "features": cheapest.features,
                        "location": cheapest.location,
                    }

                cheapest_data["alternatives"] = [h for h in sorted_hotels if h != cheapest]
                cheapest_data["selected"] = True

                register_component(
                    state,
                    component_data=cheapest_data,
                    component_type="accommodation"
                )

                response = f"I've updated your accommodation to **{cheapest_name}** (${cheapest_price}/night), which is the most budget-friendly option. Your itinerary has been updated!"
                add_message(state, AIMessage(content=response))
                state.setdefault("ui_flags", {})["has_selections"] = True
                logger.info(f"✓ Switched to cheaper accommodation: {cheapest_name}")
            except Exception as e:
                logger.error(f"Error sorting hotels by price: {e}")
                response = "I found your request for a cheaper option. Here are the accommodation options sorted by price - which would you prefer?"
                add_message(state, AIMessage(content=response))
        else:
            response = "I understand you're looking for a more budget-friendly option. Unfortunately, I don't have alternative accommodations loaded yet. Would you like me to search for different options?"
            add_message(state, AIMessage(content=response))

    # Handle time modifications
    elif action == "modify_time":
        response = "I can help adjust the timing. Which specific activity would you like to move, and to what time?"
        add_message(state, AIMessage(content=response))

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
