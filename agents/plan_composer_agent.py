# agents/plan_composer_agent.py
"""
AI-driven Plan Composer - Generates complete day-by-day itinerary
- Creates a full travel plan with schedule
- Incorporates AI recommendations from research agents
- Provides actionable itinerary, not just links
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import logging
from core.state import GraphState
from core.conversation_manager import handle_ai_output
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


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
        sources: List[Dict[str, str]] = []
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


def compose_itinerary(state: GraphState) -> GraphState:
    """Generate a complete day-by-day itinerary with AI recommendations."""
    facts, travel, stays, acts = _gather_trip_facts(state)

    context = {
        "trip": facts,
        "research": {
            "travel": travel,
            "stays": stays,
            "activities": acts,
        },
    }

    system_prompt = (
        "You are an expert travel planner creating a complete, actionable itinerary.\n\n"
        "STRUCTURE YOUR RESPONSE AS:\n\n"
        "# 🗺️ Your [Destination] Adventure\n"
        "[Brief enthusiastic intro]\n\n"
        "## 📍 Trip Overview\n"
        "- Origin → Destination\n"
        "- Dates & Duration\n"
        "- Travel party\n\n"
        "## 🚗 Getting There\n"
        "[Synthesize travel recommendations into actionable advice]\n"
        "- If driving: estimated time, route tips\n"
        "- If flying: airport recommendations, flight options\n"
        "Include 2-3 reference links\n\n"
        "## 🏨 Where to Stay\n"
        "[Provide 2-3 SPECIFIC hotel/area recommendations with WHY they're good]\n"
        "Format as: **Hotel Name** - Brief description, family features, location benefits\n"
        "Include 2-3 reference links\n\n"
        "## 📅 Day-by-Day Itinerary\n\n"
        "### Day 1 - [Theme]\n"
        "**Morning (9am-12pm)**\n"
        "- [Specific activity with details]\n"
        "- Practical tips\n\n"
        "**Afternoon (12pm-5pm)**\n"
        "- [Activity]\n"
        "- Tips\n\n"
        "**Evening (5pm+)**\n"
        "- [Dinner/activity recommendation]\n\n"
        "[Repeat for each day]\n\n"
        "## 💡 Pro Tips\n"
        "- [3-5 specific, actionable tips for this trip]\n\n"
        "## 🔗 Additional Resources\n"
        "[Activity reference links]\n\n"
        "---\n"
        "**Ready to refine your plan?** Tell me if you'd like to adjust the pace, swap activities, or focus on specific interests!\n\n"
        "CRITICAL RULES:\n"
        "- Create a COMPLETE schedule, don't leave days blank\n"
        "- Be SPECIFIC with activity names and locations\n"
        "- Include PRACTICAL details (timing, costs if known, tips)\n"
        "- Make it ACTIONABLE - a family could follow this plan\n"
        "- Don't just ask what they want - MAKE RECOMMENDATIONS first\n"
        "- Use the research to inform your suggestions\n"
        "- Keep it engaging and enthusiastic but practical\n"
    )

    import json
    user_prompt = (
        "Create a complete day-by-day itinerary using this research.\n"
        "Make specific recommendations - don't just list options.\n"
        "The family is looking for a plan they can follow.\n\n"
        f"{json.dumps(context, indent=2)}"
    )

    llm = ChatOpenAI(model="gpt-4o", temperature=0.4)  # Use GPT-4 for better itinerary generation
    logger.debug("Composer invoking LLM to generate complete itinerary.")
    
    try:
        resp = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        content = (resp.content or "").strip()
        logger.debug("Composer produced itinerary with %d characters.", len(content))

        # Ensure we have substantial content
        if len(content) < 500:
            logger.warning("Generated itinerary seems too short, using fallback.")
            content = _generate_fallback_itinerary(facts, travel, stays, acts)

    except Exception as exc:
        logger.exception("Composer LLM invocation failed.")
        content = _generate_fallback_itinerary(facts, travel, stays, acts)

    handle_ai_output(state, content)
    return state


def _generate_fallback_itinerary(facts, travel, stays, acts) -> str:
    """Generate a basic itinerary if LLM fails."""
    dest = facts.get("destination") or facts.get("destination_hint") or "your destination"
    duration = facts.get("duration_days", 2)
    
    output = f"# Your {dest} Trip Plan\n\n"
    output += f"## Overview\n"
    output += f"- From: {facts.get('origin', 'your location')}\n"
    output += f"- To: {dest}\n"
    output += f"- Duration: {duration} days\n\n"
    
    if travel.get("recommendations"):
        output += "## Getting There\n"
        output += travel["recommendations"][:500] + "\n\n"
        if travel.get("sources"):
            output += "**Resources:**\n"
            for src in travel["sources"][:3]:
                output += f"- [{src['title']}]({src['url']})\n"
            output += "\n"
    
    if stays.get("recommendations"):
        output += "## Accommodations\n"
        output += stays["recommendations"][:500] + "\n\n"
        if stays.get("sources"):
            output += "**Resources:**\n"
            for src in stays["sources"][:3]:
                output += f"- [{src['title']}]({src['url']})\n"
            output += "\n"
    
    if acts.get("recommendations"):
        output += "## Activities & Attractions\n"
        output += acts["recommendations"][:700] + "\n\n"
        if acts.get("sources"):
            output += "**Resources:**\n"
            for src in acts["sources"][:4]:
                output += f"- [{src['title']}]({src['url']})\n"
            output += "\n"
    
    output += "Let me know if you'd like me to adjust any part of this plan!"
    
    return output