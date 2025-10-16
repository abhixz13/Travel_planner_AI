# agents/plan_composer_agent.py
"""
AI-driven Plan Composer (no fallback, no normalization helper)
- Reads: state["current_plan"], state["tool_results"], state["extracted_info"]
- Invokes an LLM to compose a concise, human-friendly plan message in markdown.
- Must-haves kept:
  * Read trip facts from current_plan["summary"] (fallback to extracted_info)
  * Simple type guards on tool blocks
  * Use destination hint from extracted_info when destination absent
  * Single next-step question crafted by the LLM
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import logging
from core.state import GraphState
from core.conversation_manager import handle_ai_output
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


def _gather_trip_facts(state: GraphState) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Collect trip facts and raw sections (travel/stays/activities) with minimal guarding."""
    plan: Dict[str, Any] = state.get("current_plan", {}) or {}
    tools: Dict[str, Any] = state.get("tool_results", {}) or {}
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}

    plan_summary: Dict[str, Any] = plan.get("summary", {}) if isinstance(plan.get("summary"), dict) else {}

    # Dates can be stored either flat or nested under "dates"
    dates_block = plan_summary.get("dates") if isinstance(plan_summary.get("dates"), dict) else {}
    dep = dates_block.get("departure") if dates_block else None
    ret = dates_block.get("return") if dates_block else None
    dur = dates_block.get("duration_days") if dates_block else None

    facts = {
        "origin": plan_summary.get("origin") or ex.get("origin") or "",
        "destination": plan_summary.get("destination") or ex.get("destination") or "",
        "destination_hint": ex.get("destination_hint") or "",
        "duration_days": plan_summary.get("duration_days") or ex.get("duration_days") or dur or "",
        "purpose": plan_summary.get("purpose") or ex.get("trip_purpose") or "",
        "pack": plan_summary.get("pack") or ex.get("travel_pack") or "",
        "dates": {
            "departure": dep or ex.get("departure_date") or "",
            "return": ret or ex.get("return_date") or "",
        },
    }

    # Minimal guards: ensure dicts; keep results as-is but only pass list-of-dicts with a url
    def _section(name: str) -> Dict[str, Any]:
        blk = tools.get(name)
        if not isinstance(blk, dict):
            return {}
        res = blk.get("results")
        if isinstance(res, list):
            res = [r for r in res if isinstance(r, dict) and (r.get("url") or "").strip()]
            blk = {**blk, "results": res[:6]}  # light cap for prompt size
        else:
            blk = {**blk, "results": []}
        return {
            "summary": blk.get("summary") or "",
            "results": blk.get("results") or [],
            "follow_up": blk.get("follow_up") or "",
        }

    travel = _section("travel")
    stays = _section("stays")
    acts = _section("activities")

    logger.debug(
        "Composer gathered facts: destination=%s, travel_links=%d, stay_links=%d, activity_links=%d",
        facts.get("destination") or facts.get("destination_hint"),
        len(travel["results"]),
        len(stays["results"]),
        len(acts["results"]),
    )

    return facts, travel, stays, acts


def compose_itinerary(state: GraphState) -> GraphState:
    """Use an LLM to compose the itinerary response (no deterministic fallback)."""
    facts, travel, stays, acts = _gather_trip_facts(state)

    context = {
        "trip": facts,
        "sections": {
            "travel": {"summary": travel["summary"], "links": travel["results"][:6]},
            "stays":  {"summary": stays["summary"],  "links": stays["results"][:6], "follow_up": stays.get("follow_up", "")},
            "activities": {"summary": acts["summary"], "links": acts["results"][:6]},
        },
    }

    system_prompt = (
        "You are a concise, human-friendly AI travel planner. "
        "Compose a short markdown reply with:\n"
        "1) A **Plan** line (origin → destination, or destination hint if destination is missing, → duration).\n"
        "2) Up to three sections: **Travel**, **Stays**, **Activities**. "
        "For each, include one concise summary sentence and up to 3 bullet links using the provided links only.\n"
        "3) End with a single next-step question tailored to the context (use stays.follow_up if present).\n"
        "Rules: Keep it skimmable. Avoid fluff. Do not invent URLs. "
        "If a section has no links, include only the summary line. Use destination hint when destination is missing."
    )

    user_prompt = (
        "Compose using this JSON context. Use only fields provided. "
        "Do not echo the JSON. Output markdown only.\n\n"
        f"{context}"
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    logger.debug("Composer invoking LLM to generate itinerary response.")
    resp = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    content = (resp.content or "").strip()
    logger.debug("Composer produced response with %d characters.", len(content))

    handle_ai_output(state, content)
    return state
