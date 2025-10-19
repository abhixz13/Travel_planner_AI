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
    plan: Dict[str, Any] = state.get("current_plan", {}) or {}
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}

    plan_summary: Dict[str, Any] = plan.get("summary", {}) if isinstance(plan.get("summary"), dict) else {}

    dates_block = plan_summary.get("dates") if isinstance(plan_summary.get("dates"), dict) else {}
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


def _build_structured_prompt(facts: Dict[str, Any], research: Dict[str, Any]) -> str:
    """Build the prompt for structured output generation."""
    dest = facts.get("destination") or facts.get("destination_hint") or "your destination"
    duration = facts.get("duration_days", 2)
    purpose = facts.get("purpose", "family activities")
    pack = facts.get("pack", "family")

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

**TRANSPORTATION - PROVIDE MULTIPLE OPTIONS:**
- Generate 1-3 transport options (e.g., flying, driving, train)
- Compare options based on research data and traveler needs
- Set recommended=true for the BEST option given who's traveling
- For each option, provide pros_cons summary
- Example for family with toddler:
  * Option 1 (recommended=true): Flying - "Pros: Much faster (3 hrs vs 19 hrs), easier with toddler. Cons: More expensive, need car rental"
  * Option 2: Driving - "Pros: Cheaper, flexible schedule. Cons: 19 hours is extremely challenging with toddler, requires overnight stops"
- Flag obviously impractical options in pros_cons

CRITICAL REQUIREMENTS:
1. Generate 1-3 transport options (recommended option first)
2. Generate EXACTLY 3 accommodation options with real names and prices
3. Create a complete schedule for each day with:
   - Morning slot (9am-12pm): One activity OR restaurant
   - Afternoon slot (12pm-5pm): One activity OR restaurant
   - Evening slot (5pm-9pm): One activity OR restaurant
4. All activities must have specific times, durations, and costs
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
- All costs must be specific dollar amounts where available
- **CRITICAL**: For transport costs, provide BOTH:
  - cost_per_person: Per adult price
  - total_cost_estimate: Total for the entire family/group
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
    Generate a complete structured itinerary with validated components.
    Uses Pydantic structured output - no fuzzy parsing needed.
    """
    facts, travel, stays, acts = _gather_trip_facts(state)

    research = {
        "trip": facts,
        "travel": travel,
        "stays": stays,
        "activities": acts,
    }

    # Build prompt
    prompt = _build_structured_prompt(facts, research)

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

        # Register all components
        _register_structured_components(state, itinerary)

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
