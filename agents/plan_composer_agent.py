# agents/plan_composer_agent.py
"""
AI-driven Plan Composer - Generates structured itinerary components.
Uses Pydantic structured output for reliable, validated data.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple
import logging
import json
from pydantic import ValidationError

from core.state import GraphState
from core.conversation_manager import handle_ai_output
from core.component_registry import register_component
from core.context_tracker import update_context
from core.component_schemas import (
    StructuredItinerary,
    validate_itinerary,
    itinerary_to_dict
)
from core.itinerary_renderer import render_itinerary
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

MAX_RETRIES = 2  # Retry up to 2 times on validation errors


def _gather_trip_facts(state: GraphState) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Collect trip facts and research results."""
    plan: Dict[str, Any] = state.get("current_plan") or {}
    ex: Dict[str, Any] = state.get("extracted_info") or {}

    # Defensive: ensure plan is dict
    if not isinstance(plan, dict):
        plan = {}

    # Get summary safely
    summary_raw = plan.get("summary")
    plan_summary: Dict[str, Any] = summary_raw if isinstance(summary_raw, dict) else {}

    # Get dates safely
    dates_raw = plan_summary.get("dates")
    dates_block = dates_raw if isinstance(dates_raw, dict) else {}

    dep = dates_block.get("departure") if dates_block else None
    ret = dates_block.get("return") if dates_block else None
    dur = dates_block.get("duration_days") if dates_block else None

    facts = {
        "origin": plan_summary.get("origin") or ex.get("origin") or "",
        "destination": plan_summary.get("destination") or ex.get("destination") or "",
        "destination_hint": ex.get("destination_hint") or "",
        "duration_days": plan_summary.get("duration_days") or ex.get("duration_days") or dur or 2,
        "purpose": plan_summary.get("purpose") or ex.get("trip_purpose") or "",
        "pack": plan_summary.get("pack") or ex.get("travel_pack") or "",
        "dates": {
            "departure": dep or ex.get("departure_date") or "",
            "return": ret or ex.get("return_date") or "",
        },
    }

    def _extract_research(name: str) -> Dict[str, Any]:
        raw = plan.get(name)
        block = raw if isinstance(raw, dict) else {}
        recommendations = str(block.get("recommendations", "") or block.get("summary", "") or "").strip()
        sources_raw = block.get("sources") or block.get("results")
        sources = []
        if isinstance(sources_raw, list):
            for item in sources_raw:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url", "") or "").strip()
                if not url:
                    continue
                title = str(item.get("title", "") or "").strip() or "Link"
                sources.append({"title": title, "url": url})
                if len(sources) >= 4:
                    break
        return {"recommendations": recommendations, "sources": sources}

    travel = _extract_research("travel")
    stays = _extract_research("stays")
    acts = _extract_research("activities")

    logger.debug(
        "Composer gathered: destination=%s, duration=%s days, travel_sources=%d, stay_sources=%d, activity_sources=%d",
        facts.get("destination") or facts.get("destination_hint"),
        facts.get("duration_days"),
        len(travel["sources"]),
        len(stays["sources"]),
        len(acts["sources"]),
    )

    return facts, travel, stays, acts


def _register_structured_components(state: GraphState, itinerary: StructuredItinerary) -> None:
    """
    Register all components from the structured itinerary.
    No fuzzy parsing - direct registration from validated objects.
    """
    logger.debug("Registering structured components...")

    # Initialize component storage
    if "itinerary_components" not in state:
        state["itinerary_components"] = {
            "metadata": {},
            "accommodation": None,
            "transport": None,
            "days": {}
        }

    # Register metadata
    state["itinerary_components"]["metadata"] = itinerary_to_dict(itinerary.metadata)

    # Register transport options
    for idx, transport_opt in enumerate(itinerary.transport_options):
        register_component(
            state,
            component_data={
                **itinerary_to_dict(transport_opt),
                "option_index": idx,
                "is_primary": (idx == 0)  # First option is primary/recommended
            },
            component_type="transport"
        )
    logger.debug(f"Registered {len(itinerary.transport_options)} transport options")

    # Register accommodation options
    # First option becomes primary, rest are alternatives
    primary_hotel = itinerary.accommodation_options[0]
    alternatives = [itinerary_to_dict(h) for h in itinerary.accommodation_options[1:]]

    register_component(
        state,
        component_data={
            **itinerary_to_dict(primary_hotel),
            "alternatives": alternatives,
            "selected": False  # Not yet selected by user
        },
        component_type="accommodation"
    )
    logger.debug(f"Registered accommodation: {primary_hotel.name} (+ {len(alternatives)} alternatives)")

    # Register daily activities
    for day in itinerary.days:
        day_num = day.day_number

        # Register morning slot
        if day.morning.activity:
            register_component(
                state,
                component_data=itinerary_to_dict(day.morning.activity),
                component_type="activity",
                day_number=day_num,
                time_slot="morning"
            )
        elif day.morning.restaurant:
            register_component(
                state,
                component_data=itinerary_to_dict(day.morning.restaurant),
                component_type="restaurant",
                day_number=day_num,
                time_slot="morning"
            )

        # Register afternoon slot
        if day.afternoon.activity:
            register_component(
                state,
                component_data=itinerary_to_dict(day.afternoon.activity),
                component_type="activity",
                day_number=day_num,
                time_slot="afternoon"
            )
        elif day.afternoon.restaurant:
            register_component(
                state,
                component_data=itinerary_to_dict(day.afternoon.restaurant),
                component_type="restaurant",
                day_number=day_num,
                time_slot="afternoon"
            )

        # Register evening slot
        if day.evening.activity:
            register_component(
                state,
                component_data=itinerary_to_dict(day.evening.activity),
                component_type="activity",
                day_number=day_num,
                time_slot="evening"
            )
        elif day.evening.restaurant:
            register_component(
                state,
                component_data=itinerary_to_dict(day.evening.restaurant),
                component_type="restaurant",
                day_number=day_num,
                time_slot="evening"
            )

        logger.debug(f"Registered Day {day_num} - {day.theme}")

    logger.info(f"✓ Registered all components: {len(itinerary.accommodation_options)} hotels, {len(itinerary.days)} days")


def _build_structured_prompt(facts: Dict[str, Any], research: Dict[str, Any], hotel_selected: bool = False) -> str:
    """Build the prompt for structured output generation."""
    dest = facts.get("destination") or facts.get("destination_hint") or "your destination"
    duration = facts.get("duration_days", 2)
    purpose = facts.get("purpose", "family activities")
    pack = facts.get("pack", "family")

    # Stage 1: Just options (no hotel selected yet)
    if not hotel_selected:
        prompt = f"""
Create transport options and accommodation choices for a {pack} trip to {dest}.

**IMPORTANT: Generate ONLY transport and hotel options. Do NOT create daily activities yet.**
The user needs to select a hotel first before we plan day-by-day activities.

**APPLY COMMON SENSE - THIS IS CRITICAL:**
Trip purpose: {purpose}
Travel party: {pack}

Use human judgment when creating recommendations:
- If traveling with toddlers/infants: Prioritize shorter travel times, avoid long car rides, include nap time considerations
- If traveling with young children: Consider entertainment needs, frequent breaks
- If traveling with seniors/elderly: Choose accessible options, moderate pace
- If purpose mentions accessibility needs: Ensure all options are wheelchair accessible
- Match recommendations to the travelers' actual capabilities and comfort

**TRANSPORTATION - MANDATORY: PROVIDE AT LEAST 2 OPTIONS:**

**YOU MUST GENERATE AT LEAST 2 TRANSPORT OPTIONS.** Compare flying vs driving (or train if applicable):

For trips > 5 hours driving distance:
1. **Option 1 (Flying)**: Include flight time, airports, typical cost, pros/cons for THIS travel party
2. **Option 2 (Driving)**: Include drive time, route, cost estimate, pros/cons for THIS travel party
3. Set recommended=true on the BETTER option based on trip_purpose and travel party needs

Example for "family with toddler" on 15+ hour drive route:
```
transport_options: [
  {{
    mode: "flying",
    recommended: true,
    duration_minutes: 180,
    cost_per_person: 450,
    total_cost_estimate: 900,
    cost_notes: "for 2 adults, 1 toddler under 3 flies free",
    pros_cons: "Pros: Much faster (3 hrs vs 30 hrs), toddler can nap on plane, less stressful. Cons: More expensive, need car rental at destination."
  }},
  {{
    mode: "driving",
    recommended: false,
    duration_minutes: 1800,
    total_cost_estimate: 320,
    cost_notes: "fuel and meals for 2 adults, 1 toddler",
    pros_cons: "Pros: Cheaper, flexible schedule, own car. Cons: 30 hours is EXTREMELY challenging with toddler, requires 2 overnight stops, many rest breaks, exhausting for parents."
  }}
]
```

**DO NOT generate only 1 transport option. Users need comparison to make informed decisions.**

CRITICAL REQUIREMENTS:
1. **Generate AT LEAST 2 transport options** (mark the recommended one with recommended=true)
2. Generate EXACTLY 3 accommodation options with real names and prices
3. **STOP HERE - DO NOT GENERATE DAILY ACTIVITIES**
   - Set days = [] (EMPTY ARRAY)
   - DO NOT create Day 1, Day 2, etc.
   - DO NOT include morning/afternoon/evening activities
   - DO NOT include restaurants or time slots
   - User must choose a hotel BEFORE we plan daily activities
4. Include 3-5 general pro tips about traveling to this destination (not activity-specific)

**VALIDATION CHECK:**
Before responding, verify:
- transport_options array has at least 2 items ✓
- accommodation_options array has exactly 3 items ✓
- days array is EMPTY [] ✓
- If days has any items, DELETE THEM ALL

TRIP DETAILS:
- Origin: {facts.get('origin', 'unspecified')}
- Destination: {dest}
- Duration: {duration} days
- Dates: {facts.get('dates', {}).get('departure')} to {facts.get('dates', {}).get('return')}
- Purpose: {purpose}
- Travel party: {pack}

RESEARCH DATA TO USE:
{json.dumps(research, indent=2)}

SPECIFIC REQUIREMENTS:
- Use actual hotel names, prices, and features from research
- **HANDLING COSTS:**
  - If exact cost found in research: Use it (e.g., "$129/night", "$450 per person")
  - If range in research: Use the range (e.g., "from $99", "$400-500")
  - If not in research: Use "Call for rates" or omit if no data available
  - DO NOT make up specific prices without research backing
- **CRITICAL**: For transport costs, provide BOTH:
  - cost_per_person: Per adult price (from research)
  - total_cost_estimate: Total for the entire family/group (from research)
  - cost_notes: Clear explanation (e.g., "for 2 adults, 1 toddler under 3")
- Make transport and hotel options actionable and well-researched
- Tailor recommendations to the specific travel party mentioned in purpose
"""
    else:
        # Stage 2: Full itinerary with daily activities
        prompt = f"""
Create a COMPLETE {duration}-day itinerary for a {pack} trip to {dest}.

**APPLY COMMON SENSE - THIS IS CRITICAL:**
Trip purpose: {purpose}
Travel party: {pack}

Use human judgment when creating recommendations:
- If traveling with toddlers/infants: Prioritize shorter activities (60-90 min max), avoid long car rides, include nap time considerations
- If traveling with young children: Include age-appropriate activities, family-friendly restaurants with kids menus
- If traveling with seniors/elderly: Choose accessible venues, moderate pace activities, comfortable accommodations with elevators
- If purpose mentions accessibility needs: Ensure all venues are wheelchair accessible
- Match activity intensity and duration to the travelers' actual capabilities

**TRANSPORTATION - USE EXACT OPTIONS FROM RESEARCH:**
- **CRITICAL**: Extract and use the EXACT transport options already presented in the research data
- DO NOT generate new transport modes or options
- The research already contains options that were presented to the user (e.g., Drive, Fly, Hybrid)
- Parse each option from the research recommendations and structure it
- Preserve the original option details: mode, duration, costs, pros/cons
- If research mentions "Drive", "Fly", "Hybrid" - use those exact modes
- DO NOT add "train", "bus", or other modes not mentioned in research
- Set recommended=true ONLY for the option the research recommended

CRITICAL REQUIREMENTS:
1. Extract and use the exact transport options from research (preserve the modes mentioned - typically Drive, Fly, Hybrid)
2. Generate EXACTLY 3 accommodation options with real names and prices
3. Create a complete schedule for each day with:
   - Morning slot (9am-12pm): One activity OR restaurant
   - Afternoon slot (12pm-5pm): One activity OR restaurant
   - Evening slot (5pm-9pm): One activity OR restaurant
4. For activities: Extract duration and cost from research if available; if not mentioned, provide reasonable estimates
5. All restaurants must have specific meal times and family-friendly features
6. Include 5-10 practical pro tips specific to the travel party

TRIP DETAILS:
- Origin: {facts.get('origin', 'unspecified')}
- Destination: {dest}
- Duration: {duration} days
- Dates: {facts.get('dates', {}).get('departure')} to {facts.get('dates', {}).get('return')}
- Purpose: {purpose}
- Travel party: {pack}

RESEARCH DATA TO USE:
{json.dumps(research, indent=2)}

SPECIFIC REQUIREMENTS:
- Use actual hotel names, prices, and features from research
- Use actual activity names, costs, and details from research
- All times must be specific (e.g., "09:30 AM", not "morning")
- **HANDLING COSTS AND DURATIONS:**
  - If exact cost found in research: Use it (e.g., "$25 per person", "$150/night")
  - If range in research: Use the range (e.g., "$15-20", "from $99")
  - If not in research: Use "Check website" or "Free" if clearly a free attraction
  - DO NOT make up specific prices (e.g., don't invent "$23" if research says nothing)
  - For duration: If research mentions it (e.g., "2-3 hours"), use it
  - If not mentioned: Provide typical estimate (e.g., "60-90 minutes for zoo visit")
- **CRITICAL**: For transport costs, provide BOTH:
  - cost_per_person: Per adult price (from research)
  - total_cost_estimate: Total for the entire family/group (from research)
  - cost_notes: Clear explanation (e.g., "for 2 adults, 1 toddler under 3")
- Make it actionable - travelers could follow this plan directly
- Tailor recommendations to the specific travel party mentioned in purpose
"""
    return prompt


def _generate_with_retries(llm: ChatOpenAI, prompt: str, max_retries: int = MAX_RETRIES) -> StructuredItinerary:
    """
    Generate structured itinerary with retry logic on validation errors.

    Args:
        llm: LLM instance
        prompt: Generation prompt
        max_retries: Maximum retry attempts

    Returns:
        Validated StructuredItinerary

    Raises:
        ValidationError: If all retries fail
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"Generation attempt {attempt + 1}/{max_retries + 1}")

            # Use structured output with Pydantic model
            structured_llm = llm.with_structured_output(StructuredItinerary)
            result = structured_llm.invoke(prompt)

            # Validate the result
            if isinstance(result, StructuredItinerary):
                logger.info(f"✓ Successfully generated structured itinerary on attempt {attempt + 1}")
                return result
            else:
                # Shouldn't happen with with_structured_output, but handle it
                validated = validate_itinerary(result)
                logger.info(f"✓ Successfully generated and validated itinerary on attempt {attempt + 1}")
                return validated

        except ValidationError as e:
            last_error = e
            logger.warning(f"Validation failed on attempt {attempt + 1}: {e}")

            if attempt < max_retries:
                # Add error feedback to prompt for retry
                error_msg = str(e)
                prompt += f"\n\nPREVIOUS ATTEMPT FAILED - Fix these validation errors:\n{error_msg}"
                logger.debug("Retrying with error feedback...")
            else:
                logger.error("All generation attempts failed")
                raise

        except Exception as e:
            logger.exception(f"Unexpected error on attempt {attempt + 1}")
            last_error = e
            if attempt >= max_retries:
                raise

    # Should not reach here
    raise last_error if last_error else RuntimeError("Generation failed")


def compose_itinerary(state: GraphState) -> GraphState:
    """
    Generate staged itinerary output based on what research has been completed.

    Stage 1: Travel only → Show travel options + ask for confirmation
    Stage 2: Travel + Stays → Show travel + hotels + ask for hotel selection
    Stage 3: All research → Generate full itinerary with daily activities
    """
    # Determine what research has been completed
    plan = state.get("current_plan", {}) or {}
    has_travel = bool(plan.get("travel"))
    has_stays = bool(plan.get("stays"))
    has_activities = bool(plan.get("activities"))

    logger.info(f"Composer stage check: travel={has_travel}, stays={has_stays}, activities={has_activities}")

    # Safety check: If no research at all, don't try to compose
    if not has_travel and not has_stays and not has_activities:
        logger.warning("Composer called with no research data - skipping")
        return state

    try:
        facts, travel, stays, acts = _gather_trip_facts(state)
    except Exception as e:
        logger.exception("Error in _gather_trip_facts")
        raise Exception(f"Failed in _gather_trip_facts: {str(e)}") from e

    try:
        research = {
            "trip": facts,
            "travel": travel,
            "stays": stays,
            "activities": acts,
        }
    except Exception as e:
        logger.exception("Error building research dict")
        raise Exception(f"Failed building research dict: {str(e)}") from e

    # Special handling for travel-only stage
    if has_travel and not has_stays and not has_activities:
        # Check if travel was already confirmed - if so, we tried stays and it failed
        ui_flags = state.get("ui_flags", {}) or {}
        travel_confirmed = ui_flags.get("travel_confirmed", False)

        if travel_confirmed:
            # Travel is confirmed but stays failed - this is an error state, not normal flow
            logger.warning("Composer: Stays research failed after travel confirmation - prompting user")

            error_msg = (
                "I'm having trouble finding accommodation options for this destination. "
                "This might be because the destination is very specific (like a park or attraction).\n\n"
                "Would you like me to:\n"
                "1. Search for hotels in the nearby city/area\n"
                "2. Skip hotel selection and proceed to activity planning\n"
                "3. Try a different destination\n\n"
                "Please let me know how you'd like to proceed!"
            )

            handle_ai_output(state, error_msg)
            return state

        logger.info("Composer: Travel-only stage - showing travel options and requesting confirmation")

        # Extract travel recommendations
        travel_text = travel.get("recommendations", "") if isinstance(travel, dict) else ""

        confirmation_msg = (
            f"## 🚗 Travel Options\n\n"
            f"{travel_text}\n\n"
            f"---\n\n"
            f"**Does this look good?**\n\n"
            f"Reply '**yes**' to proceed to accommodation search, or let me know if you'd like different travel options."
        )

        handle_ai_output(state, confirmation_msg)
        return state

    # Check if hotel has been selected
    try:
        components = state.get("itinerary_components") or {}
        if not isinstance(components, dict):
            components = {}
        hotel = components.get("accommodation") if isinstance(components, dict) else None
        if hotel is None or not isinstance(hotel, dict):
            hotel = {}
        hotel_selected = hotel.get("selected", False) if isinstance(hotel, dict) else False
        logger.debug(f"Composer stage check: hotel_selected={hotel_selected}, components type={type(components)}, hotel type={type(hotel)}")
    except Exception as e:
        logger.exception("Error checking hotel selection")
        raise Exception(f"Failed checking hotel selection: {str(e)}") from e

    # Build prompt based on stage
    try:
        if hotel_selected:
            logger.info("Composition stage: FULL ITINERARY - Generating complete day-by-day itinerary")
        else:
            logger.info("Composition stage: TRAVEL + HOTELS - Generating travel options + hotel choices")
            # IMPORTANT: When showing hotels, travel is implicitly confirmed
            # User has moved past travel and is now choosing hotels
            state.setdefault("ui_flags", {})["travel_confirmed"] = True
            logger.info("Set travel_confirmed=True (user is now choosing hotels)")

        prompt = _build_structured_prompt(facts, research, hotel_selected=hotel_selected)
    except Exception as e:
        logger.exception("Error building prompt")
        raise Exception(f"Failed building prompt: {str(e)}") from e

    # Initialize LLM with structured output support
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
        request_timeout=60
    )

    logger.info("Composer generating structured itinerary...")

    try:
        # Generate with retry logic
        itinerary = _generate_with_retries(llm, prompt, max_retries=MAX_RETRIES)

        # SAFETY CHECK: If hotel not selected, force days to be empty
        if not hotel_selected and itinerary.days:
            logger.warning(f"LLM generated {len(itinerary.days)} days despite hotel not being selected. Forcing days to empty.")
            # Properly recreate the model with empty days
            itinerary_dict = itinerary.model_dump()
            itinerary_dict['days'] = []
            itinerary = StructuredItinerary.model_validate(itinerary_dict)

        # REORDER HOTELS: If hotel was selected, put the selected one first
        if hotel_selected and hotel and isinstance(hotel, dict):
            selected_hotel_name = hotel.get("name", "").strip()
            if selected_hotel_name and itinerary.accommodation_options:
                # Find the selected hotel in the accommodation_options
                selected_index = None
                for idx, h in enumerate(itinerary.accommodation_options):
                    if h.name.strip() == selected_hotel_name:
                        selected_index = idx
                        break

                # Reorder: move selected hotel to first position
                if selected_index is not None and selected_index > 0:
                    itinerary_dict = itinerary.model_dump()
                    hotel_list = itinerary_dict['accommodation_options']
                    selected = hotel_list.pop(selected_index)
                    hotel_list.insert(0, selected)
                    itinerary = StructuredItinerary.model_validate(itinerary_dict)
                    logger.info(f"Reordered hotels: moved '{selected_hotel_name}' to first position")

        # Register all components
        _register_structured_components(state, itinerary)

        # IMPORTANT: Mark travel/stays as complete in current_plan when generated by composer
        # This is needed for stage detection to work correctly
        plan = state.setdefault("current_plan", {})

        # Mark travel as complete if generated
        if itinerary.transport_options and not plan.get("travel"):
            plan["travel"] = {
                "recommendations": f"Generated {len(itinerary.transport_options)} transport options",
                "sources": [],
                "_generated_by_composer": True
            }
            logger.info(f"Marked travel as complete in current_plan ({len(itinerary.transport_options)} options)")

        # Mark stays as complete if generated (but only when not hotel_selected)
        if not hotel_selected and itinerary.accommodation_options and not plan.get("stays"):
            plan["stays"] = {
                "recommendations": f"Generated {len(itinerary.accommodation_options)} hotel options",
                "sources": [],
                "_generated_by_composer": True
            }
            logger.info(f"Marked stays as complete in current_plan ({len(itinerary.accommodation_options)} hotels)")

        # Render to user-friendly markdown
        markdown_output = render_itinerary(itinerary)

        # Update context
        update_context(
            state,
            conversation_stage="plan_generated",
            current_topic="itinerary_review"
        )

        # Mark that itinerary has been presented
        state.setdefault("ui_flags", {})["itinerary_presented"] = True

        logger.info(f"✓ Itinerary generated and rendered: {len(markdown_output)} characters")

        # Show user the rendered markdown
        handle_ai_output(state, markdown_output)

    except ValidationError:
        logger.exception("Failed to generate valid itinerary after retries")
        error_msg = "I encountered an issue generating your itinerary. Let me try a simpler approach..."
        handle_ai_output(state, error_msg)

    except Exception:
        logger.exception("Unexpected error generating itinerary")
        error_msg = "I ran into an unexpected issue. Could you provide a bit more detail about what you're looking for?"
        handle_ai_output(state, error_msg)

    return state
