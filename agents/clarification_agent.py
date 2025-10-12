# agents/clarifying_agent.py
"""
Clarifier: parses latest user message into required slots and asks follow-ups.
Slots: origin, destination, departure_date/return_date or duration_days,
trip_purpose, travel_pack, constraints.
"""

from __future__ import annotations
from typing import Any, Dict, List
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from core.state import GraphState, add_message
from core.conversation_manager import last_user_message

LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

REQUIRED_FIELDS = {
    "origin": "your starting city",
    "destination": "your destination",
    "when": "either departure & return dates, or trip length in days",
    "trip_purpose": "trip purpose (e.g., relaxation, adventure, sightseeing)",
    "travel_pack": "who's traveling (e.g., solo, couple, family)",
    "constraints": "any special needs or constraints",
}

def _empty(v: Any) -> bool:
    if v is None: return True
    if isinstance(v, str): return v.strip() == ""
    if isinstance(v, (list, dict)): return len(v) == 0
    return False

def _missing(info: Dict[str, Any]) -> List[str]:
    miss = []
    if _empty(info.get("origin")): miss.append("origin")
    if _empty(info.get("destination")): miss.append("destination")
    has_dates = not _empty(info.get("departure_date")) and not _empty(info.get("return_date"))
    has_duration = not _empty(info.get("duration_days"))
    if not has_dates and not has_duration: miss.append("when")
    if _empty(info.get("trip_purpose")): miss.append("trip_purpose")
    if _empty(info.get("travel_pack")): miss.append("travel_pack")
    if _empty(info.get("constraints")): miss.append("constraints")
    return miss

def _prompt(info: Dict[str, Any], user: str) -> str:
    return f"""
Extract trip info from the user's message. Only extract what is explicit.

Return JSON:
{{
  "extracted_info": {{
    "origin": "", "destination": "",
    "departure_date": "", "return_date": "", "duration_days": null,
    "trip_purpose": "", "travel_pack": "", "constraints": {{}}
  }},
  "follow_up": ""
}}

Current info: {json.dumps(info, ensure_ascii=False)}
User: {json.dumps(user, ensure_ascii=False)}
""".strip()

def extract_travel_info(state: GraphState) -> GraphState:
    """Fill slots and ask a follow-up if fields are missing."""
    info = state.setdefault("extracted_info", {})
    tools = state.setdefault("tool_results", {})
    user = last_user_message(state)

    resp = LLM.invoke([
        {"role":"system","content":"Extract trip info JSON only. Don't invent."},
        {"role":"user","content":_prompt(info, user)},
    ])
    data = {}
    try: data = json.loads(getattr(resp,"content","{}"))
    except: data = {}

    ext = data.get("extracted_info", {})
    for k in ["origin","destination","departure_date","return_date",
              "duration_days","trip_purpose","travel_pack","constraints"]:
        if k in ext and not _empty(ext[k]): info[k] = ext[k]

    miss = _missing(info)
    if miss:
        nice = [REQUIRED_FIELDS.get(m, m) for m in miss]
        q = data.get("follow_up") or (
            f"To plan your trip, I need {', '.join(nice[:-1])}, and {nice[-1]} (e.g. "
            f"'5 days', 'March 20-25')."
            if len(nice) > 1 else f"To plan your trip, I need {nice[0]} (e.g. '5 days')."
        )
        tools["clarification"] = {"status":"incomplete","missing":miss,"question":q}
        add_message(state, AIMessage(content=q))
    else:
        tools["clarification"] = {"status":"complete"}

    return state