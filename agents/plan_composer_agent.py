# agents/plan_composer_agent.py
"""
Plan Composer (prototype)
- Reads: state["current_plan"], state["tool_results"] (travel/stays/activities)
- Writes: one AIMessage with a concise, actionable summary + top links
- Goal: reduce cognitive load (clear plan + handful of high-signal links)
"""

from __future__ import annotations
from typing import Dict, Any, List
from core.state import GraphState
from core.conversation_manager import handle_ai_output


def _fmt_links(items: List[Dict[str, str]], limit: int = 3) -> List[str]:
    """Return markdown bullets for top-N links."""
    out: List[str] = []
    for it in items[:limit]:
        title = (it.get("title") or "Link").strip()
        url = (it.get("url") or "").strip()
        if url:
            out.append(f" • [{title}]({url})")
    return out


def compose_itinerary(state: GraphState) -> GraphState:
    """
    Compose one friendly message combining:
    - Base plan summary (origin, destination, duration)
    - Travel / Stays / Activities highlights
    - A single, clear next-step question
    """
    plan: Dict[str, Any] = state.get("current_plan", {})
    tools: Dict[str, Any] = state.get("tool_results", {})

    # Core plan bits
    summary = plan.get("summary", "Trip plan")
    origin = plan.get("origin", "")
    dest = plan.get("destination", "")
    days = plan.get("duration_days", "")
    plan_line_bits: List[str] = []
    if origin: plan_line_bits.append(f"from **{origin}**")
    if dest: plan_line_bits.append(f"to **{dest}**")
    if days: plan_line_bits.append(f"**{days} days**")

    # Branch payloads
    travel = tools.get("travel", {})        # {"summary", "results", "suggested_queries"}
    stays = tools.get("stays", {})          # {"summary", "results", "follow_up"}
    acts = tools.get("activities", {})      # {"summary", "results"}

    # Build the reply
    lines: List[str] = []
    lines.append(f"**Plan**: {summary}")
    if plan_line_bits:
        lines.append(" • " + ", ".join(plan_line_bits))

    # Travel
    if travel:
        lines.append("\n**Travel**")
        tr_sum = travel.get("summary", "Transport research links (flights, drive time, transfers).")
        lines.append(f" • {tr_sum}")
        tr_links = _fmt_links(travel.get("results", []), limit=3)
        if tr_links: lines.extend(tr_links)

    # Stays
    if stays:
        lines.append("\n**Stays**")
        st_sum = stays.get("summary", "Neighborhood/hotel research to get you started.")
        lines.append(f" • {st_sum}")
        st_links = _fmt_links(stays.get("results", []), limit=3)
        if st_links: lines.extend(st_links)

    # Activities
    if acts:
        lines.append("\n**Activities**")
        ac_sum = acts.get("summary", f"Top activity links for {dest or 'your destination'}.")
        lines.append(f" • {ac_sum}")
        ac_links = _fmt_links(acts.get("results", []), limit=3)
        if ac_links: lines.extend(ac_links)

    # One clear next step (prefer stays' follow-up if present)
    follow_up = stays.get("follow_up") if stays else None
    lines.append(
        "\n" + (follow_up or "Shall I shortlist hotels, compare neighborhoods, or look up flight options?")
    )

    handle_ai_output(state, "\n".join(lines))
    return state
