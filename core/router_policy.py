# core/routing_policy.py
"""
Routing Policy:
1. If clarification is incomplete → ask more questions.
2. If no destination is provided → run destination discovery.
3. Otherwise → proceed to trip planning.

Enhanced with LLM-based routing for complex decisions.
"""

import logging
import json
from typing import Literal, List, Optional, Dict, Any
from core.state import GraphState
from core.conversation_manager import last_user_message
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Possible next steps in routing
Route = Literal["ask_more", "discover", "plan", "refine", "research_travel", "research_stays", "research_activities"]


def _is_user_confirmation(user_msg: str) -> bool:
    """Detect if user is confirming/approving to proceed (not just acknowledging)."""
    msg_lower = user_msg.lower().strip()

    # Explicit confirmation patterns
    confirmation_patterns = [
        "yes", "yeah", "yep", "sure", "ok", "okay",
        "proceed", "continue", "go ahead", "next",
        "looks good", "sounds good", "perfect",
        "let's move", "let's continue", "show me",
        "find hotel", "find stay", "find accommodation",
        "create itinerary", "make itinerary"
    ]

    # Negative patterns (user wants to refine/change)
    negative_patterns = [
        "no", "not", "different", "other", "cheaper",
        "change", "modify", "instead", "rather",
        "show me other", "what about"
    ]

    # Check for negatives first
    if any(pattern in msg_lower for pattern in negative_patterns):
        return False

    # Check for confirmations
    return any(pattern in msg_lower for pattern in confirmation_patterns)


def _determine_workflow_stage(state: GraphState) -> str:
    """
    Determine what stage of the workflow we're at.

    Returns: "need_travel", "awaiting_travel_confirm", "need_stays",
             "awaiting_hotel_confirm", "need_activities", "complete"
    """
    ui_flags = state.get("ui_flags", {}) or {}
    plan = state.get("current_plan", {}) or {}

    # Check what's been completed
    has_travel = bool(plan.get("travel"))
    has_stays = bool(plan.get("stays"))
    has_activities = bool(plan.get("activities"))

    travel_confirmed = ui_flags.get("travel_confirmed", False)
    hotel_confirmed = ui_flags.get("hotel_confirmed", False)

    # DEBUG: Log current state
    logger.warning("="*60)
    logger.warning("🔍 WORKFLOW STAGE DETECTION")
    logger.warning(f"Research Status: Travel={has_travel}, Stays={has_stays}, Activities={has_activities}")
    logger.warning(f"Confirmation Flags: travel_confirmed={travel_confirmed}, hotel_confirmed={hotel_confirmed}")

    if not has_travel:
        stage = "need_travel"
    elif has_travel and not travel_confirmed:
        stage = "awaiting_travel_confirm"
    elif not has_stays:
        stage = "need_stays"
    elif has_stays and not hotel_confirmed:
        stage = "awaiting_hotel_confirm"
    elif not has_activities:
        stage = "need_activities"
    else:
        stage = "complete"

    logger.warning(f"→ Stage determined: {stage}")
    logger.warning("="*60)

    return stage


def _route_with_llm(
    state: GraphState,
    decision_point: str,
    options: List[str],
    extra_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    LLM-based routing decision for complex cases.

    Args:
        state: Current graph state
        decision_point: Where we are in the flow (e.g., "after_extract")
        options: Valid routing options (e.g., ["ask_more", "discover", "plan", "refine"])
        extra_context: Additional context to help LLM decide

    Returns:
        Routing decision (one of the options)
    """
    user_msg = last_user_message(state)
    extracted = state.get("extracted_info", {}) or {}
    components = state.get("itinerary_components", {}) or {}
    ui_flags = state.get("ui_flags", {}) or {}
    tools = state.get("tool_results", {}) or {}

    # Build state summary (defensive: handle None values)
    accommodation = components.get("accommodation") or {}
    discovery = tools.get("discovery") or {}

    state_summary = {
        "destination": extracted.get("destination"),
        "departure_date": extracted.get("departure_date"),
        "return_date": extracted.get("return_date"),
        "trip_purpose": extracted.get("trip_purpose"),
        "hotel_options_shown": bool(accommodation),
        "hotel_selected": accommodation.get("selected", False) if isinstance(accommodation, dict) else False,
        "full_itinerary_exists": bool(components.get("days")),
        "itinerary_presented": ui_flags.get("itinerary_presented", False),
        "destination_confirmed": bool(extracted.get("destination")),
        "discovery_in_progress": discovery.get("cycle_count", 0) > 0 and not extracted.get("destination")
    }

    if extra_context:
        state_summary.update(extra_context)

    prompt = f"""You are a travel planning conversation router. Based on context, decide the next action.

DECISION POINT: {decision_point}
AVAILABLE ROUTES: {json.dumps(options)}

CURRENT STATE:
{json.dumps(state_summary, indent=2)}

USER'S LAST MESSAGE: "{user_msg}"

ROUTING RULES:
- "ask_more": Need more information (missing destination, dates, or user wants to change core trip details)
- "discover": User needs destination suggestions (destination is vague or user asked for ideas)
- "plan": Start planning or re-run research (have enough info, or user requested refinement that needs new search)
- "refine": User wants to select/modify existing options (hotel selection, activity changes, etc.)

DECISION CRITERIA (PRIORITY ORDER):
1. If destination_confirmed is True → proceed with planning workflow
2. If discovery_in_progress is True → "discover" (let autonomous agent continue conversation)
3. If user is selecting a hotel (numeric "1"/"2"/"3") AND hotel_options_shown is True → "refine"
4. If user wants different hotel options (e.g., "cheaper", "near beach", "show more") → "plan" (re-search needed)
5. If user wants to change destination/dates → "ask_more" (update core info)
6. If user is modifying existing itinerary (swap activity, change time) → "refine"
7. If no destination yet → "discover" (autonomous agent will handle)
8. If have all info but no itinerary → "plan"

Think step-by-step, then return ONLY the route name (no explanation).
Route:"""

    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=10)
        response = llm.invoke(prompt)
        decision = response.content.strip().strip('"').lower()

        # Validate LLM response
        if decision not in options:
            logger.warning(f"LLM returned invalid route '{decision}', options were {options}. Defaulting to '{options[0]}'")
            return options[0]

        # Safety check: Don't route to "refine" if no hotels shown
        if decision == "refine" and not state_summary.get("hotel_options_shown"):
            logger.warning(f"LLM tried to route to 'refine' but no hotels shown. Changing to 'plan'.")
            return "plan"

        logger.info(f"LLM routing at {decision_point}: '{user_msg[:50]}...' → {decision}")
        return decision

    except Exception as e:
        logger.exception(f"LLM routing failed at {decision_point}: {e}")
        # Fallback to first safe option
        return options[0]


def route_after_extract(state: GraphState) -> Route:
    """
    Determine what to do next based on current state.
    Uses staged workflow with user confirmation at each step.
    """

    # Fast path 1: Clarification incomplete (obvious)
    tools = state.get("tool_results") or {}
    clarification = tools.get("clarification") or {}
    if clarification.get("status") != "complete":
        logger.info("Routing after extract → ask_more (clarification incomplete).")
        return "ask_more"

    # Fast path 2: Check if destination is missing - route to autonomous discovery agent
    # The discovery agent handles conversation iteratively (no need to check suggestions/resolved flags)
    ex = state.get("extracted_info", {}) or {}
    destination = (ex.get("destination") or "").strip()

    if not destination:
        # No destination - let autonomous discovery agent handle it
        logger.info("Routing after extract → discover (no destination, autonomous agent will handle conversation).")
        return "discover"

    # Determine workflow stage and route accordingly
    stage = _determine_workflow_stage(state)
    user_msg = last_user_message(state)
    user_confirmed = _is_user_confirmation(user_msg) if user_msg else False

    logger.warning("="*60)
    logger.warning("🧭 ROUTING DECISION")
    logger.warning(f"User message: '{user_msg[:100] if user_msg else '(none)'}'")
    logger.warning(f"User confirmed: {user_confirmed}")
    logger.warning(f"Current stage: {stage}")

    # Stage 1: Need to research travel options
    if stage == "need_travel":
        # Destination already validated above, proceed to travel research
        route = "research_travel"
        reason = "No travel options yet - need to research"
        logger.info(f"Routing after extract → {route} ({reason})")
        return route

    # Stage 2: Travel shown, waiting for user confirmation
    elif stage == "awaiting_travel_confirm":
        logger.warning(f"⚠️ Stage is awaiting_travel_confirm | user_msg='{user_msg}' | user_confirmed={user_confirmed}")

        # Check if user is asking for hotel refinement (not travel refinement)
        refinement_criteria = state.get("refinement_criteria", {})
        if refinement_criteria.get("accommodation"):
            # User is asking about hotels, not travel - proceed to stays research
            state.setdefault("ui_flags", {})["travel_confirmed"] = True
            route = "research_stays"
            reason = "User asking for hotel options (skipping travel confirmation)"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route

        if user_confirmed:
            # User confirmed travel options, move to stays
            logger.warning(f"✅ User confirmed=True, routing to research_stays")
            state.setdefault("ui_flags", {})["travel_confirmed"] = True
            route = "research_stays"
            reason = "User confirmed travel options - proceeding to stays"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route
        else:
            # User wants to refine travel options - mark for re-research
            logger.warning(f"❌ User confirmed=False, routing back to research_travel")
            plan = state.get("current_plan", {})
            if plan and "travel" in plan:
                plan["travel"] = None  # Clear to force re-research
            route = "research_travel"
            reason = "User wants to refine travel options"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route

    # Stage 3: Need to research stay options
    elif stage == "need_stays":
        # Verify we have destination before researching stays
        ex = state.get("extracted_info", {}) or {}
        destination = (ex.get("destination") or "").strip()

        if not destination:
            # Shouldn't happen, but route to discovery as safety
            route = "discover"
            reason = "Missing destination for stays research"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route

        route = "research_stays"
        reason = "No stay options yet - need to research"
        logger.info(f"Routing after extract → {route} ({reason})")
        return route

    # Stage 4: Stays shown, waiting for hotel selection/confirmation
    elif stage == "awaiting_hotel_confirm":
        # Check if user selected a specific hotel number
        if user_msg and user_msg.strip() in ["1", "2", "3"]:
            # Let refinement agent handle hotel selection
            state.setdefault("ui_flags", {})["hotel_selection_pending"] = True
            route = "refine"
            reason = f"User selected hotel #{user_msg.strip()}"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route
        elif user_confirmed:
            # User confirmed hotel selection, move to activities
            state.setdefault("ui_flags", {})["hotel_confirmed"] = True
            route = "research_activities"
            reason = "User confirmed hotel selection - proceeding to activities"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route
        else:
            # Check if there's a hotel refinement request
            refinement_criteria = state.get("refinement_criteria", {})
            if refinement_criteria.get("accommodation"):
                route = "research_stays"
                reason = "User wants different hotel options (refinement detected)"
                logger.info(f"Routing after extract → {route} ({reason})")
                return route

            # Default: user wants different hotel options
            route = "research_stays"
            reason = "User wants different hotel options"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route

    # Stage 5: Need to research activities and generate full itinerary
    elif stage == "need_activities":
        # Verify we have destination before researching activities
        ex = state.get("extracted_info", {}) or {}
        destination = (ex.get("destination") or "").strip()

        if not destination:
            # Shouldn't happen, but route to discovery as safety
            route = "discover"
            reason = "Missing destination for activities research"
            logger.info(f"Routing after extract → {route} ({reason})")
            return route

        route = "research_activities"
        reason = "All confirmations received - generating full itinerary"
        logger.info(f"Routing after extract → {route} ({reason})")
        return route

    # Stage 6: Complete - handle refinements
    else:
        route = "refine"
        reason = "Full itinerary exists - handling refinements"
        logger.info(f"Routing after extract → {route} ({reason})")
        return route
