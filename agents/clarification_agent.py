"""Extract trip info, confirm once, and avoid repeat confirmations."""

from __future__ import annotations
from datetime import datetime
import logging
import hashlib
import json as _json
import json
import re
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage

from core.conversation_manager import last_user_message
from core.state import GraphState, add_message

logger = logging.getLogger(__name__)

# --- tiny helpers ------------------------------------------------------------

_HINT_TOKENS = {
    "any", "some", "somewhere", "anywhere", "open", "suggest", "kid",
    "kids", "family", "friendly", "outdoor", "outdoors", "nature", "near",
    "around", "close", "within", "drive", "options", "ideas", "recommend",
}

def _looks_like_hint(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(t in lower for t in _HINT_TOKENS)

def _normalize_for_yesno(text: str) -> str:
    # lowercase and strip punctuation to make token checks robust (e.g., "okay," → "okay")
    t = (text or "").lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _is_confirmation(text: str) -> bool:
    t = _normalize_for_yesno(text)
    # Require a whole-word match to avoid false positives inside other words
    pos = r"\b(yes|yep|yeah|correct|right|sure|ok|okay|good|great|perfect|sounds good|looks good|confirmed)\b"
    neg = r"\b(no|nope|not|wrong|incorrect|change|actually)\b"
    if re.search(neg, t):
        return False
    return bool(re.search(pos, t))

def _hash_required(info: Dict[str, Any]) -> str:
    """Stable fingerprint of the fields we confirm."""
    key = {
        "origin": info.get("origin"),
        "departure_date": info.get("departure_date"),
        "return_date": info.get("return_date"),
        "trip_purpose": info.get("trip_purpose"),
        "travel_pack": info.get("travel_pack"),
        "destination": info.get("destination"),
    }
    return hashlib.sha1(_json.dumps(key, sort_keys=True).encode()).hexdigest()


# --- main node ---------------------------------------------------------------

def extract_travel_info(state: GraphState) -> GraphState:
    """Extract essentials, confirm once, and skip re-asking when unchanged."""
    latest_user = last_user_message(state)
    if not latest_user or not latest_user.strip():
        logger.debug("Clarification agent: no new user input; returning state.")
        return state
    logger.debug("Clarification agent processing user input: %s", latest_user.strip())

    # Initialize shared refs ONCE
    info = state.setdefault("extracted_info", {})
    tools = state.setdefault("tool_results", {})
    clar = tools.get("clarification", {}) or {}

    # --- handle destination choice from discovery (numeric or name) ----------
    discovery = tools.setdefault("discovery", {})
    suggestions = discovery.get("suggestions") or []
    if suggestions:
        logger.debug("Clarification agent sees %d pending suggestions.", len(suggestions))
        raw = latest_user.strip()
        picked_name = None

        # Try to extract the first 1–2 digit number as the user's choice
        m_num = re.search(r"\b(\d{1,2})\b", raw)
        if m_num:
            idx = int(m_num.group(1)) - 1
            if 0 <= idx < len(suggestions):
                picked_name = (suggestions[idx].get("name") or "").strip()
                logger.debug("Clarification agent parsed numeric selection -> %s.", picked_name)

        # Fallback: free-text fuzzy match against suggestion names
        if not picked_name:
            low = raw.lower()
            for s in suggestions:
                name = (s.get("name") or "").strip()
                if not name:
                    continue
                nlow = name.lower()
                if low == nlow or nlow.startswith(low) or low in nlow:
                    picked_name = name
                    break

        if picked_name:
            info["destination"] = picked_name
            # Mark discovery resolved and optionally clear suggestions to avoid re-matching later
            discovery["resolved"] = True
            discovery["suggestions"] = []
            # Mark clarification complete for this combo to avoid re-asking
            tools["clarification"] = {
                "status": "complete",
                "confirmed_hash": _hash_required(info),
            }
            logger.debug("Destination '%s' selected; discovery resolved.", picked_name)
            add_message(state, AIMessage(content=f"Got it — **{picked_name}**. I’ll plan around that."))
            return state
        else:
            logger.debug("Clarification agent awaiting valid selection matching suggestions.")

    # If we're waiting for a Yes/No, handle it first.
    if clar.get("status") == "awaiting_confirmation":
        if _is_confirmation(latest_user):
            tools["clarification"] = {
                "status": "complete",
                "confirmed_hash": _hash_required(info),
            }
            state.setdefault("ui_flags", {})["confirmed"] = True
            logger.debug("Clarification confirmation received; marking complete.")
            add_message(state, AIMessage(content="Perfect! Let me find great options for you."))
            return state
        else:
            tools["clarification"] = {"status": "incomplete"}
            logger.debug("Clarification confirmation not detected; marking incomplete.")

    # Build a compact conversation context (last 3 user messages)
    msgs: List[Any] = state.get("messages", [])
    recent_user_msgs: List[str] = []
    for m in reversed(msgs[-10:]):
        if isinstance(m, HumanMessage):
            recent_user_msgs.append(m.content)
            if len(recent_user_msgs) >= 3:
                break
    conversation = "\n".join(f"User: {m}" for m in reversed(recent_user_msgs))

    # Call LLM once to (re)parse essentials
    today = datetime.now()
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    system_prompt = f"""
        - You are a travel information extractor. Extract trip details from natural conversation\n
        - Return ONLY valid JSON matching the exact schema\n
        - Extract only what is explicitly stated or strongly implied\n
        - Don't invent or assume information\n
        - Be concise - no additional commentary\n
        - If information is unclear or missing, list it in the 'missing' array\n
    """

    prompt = f"""Extract trip information from natural conversation.

        CRITICAL RULES:
        - Use JSON null (not string "null") for missing/unknown values
        - Only set "destination" if user explicitly names a specific place
        - If destination is vague/uncertain, leave it as null and set "destination_hint" instead
        - Examples of what NOT to set as destination: "somewhere", "anywhere", "beach", "mountains"

        TODAY: {today.strftime("%A, %B %d, %Y")}

        Conversation:
        {conversation}

        Already extracted: {json.dumps(info, indent=2)}

        Return ONLY valid JSON like:
        {{
        "origin": "city name or null",
        "destination": "city name or null", // ONLY specific places; use null otherwise
        "destination_hint": "vague location or null", // only set if destination is vague/uncertain
        "departure_date": "YYYY-MM-DD",
        "return_date": "YYYY-MM-DD",
        "duration_days": 2,
        "trip_purpose": "activities/goals",
        "travel_pack": "solo|family|couple|friends|other",
        "constraints": {{}},
        "missing": []
        }}

        REQUIRED FIELDS: origin, departure_date, return_date, trip_purpose, travel_pack
        - List required fields that are missing or null in the "missing" array
        - "destination" is optional - only include if explicitly mentioned
        - "duration_days" is optional - can be computed from dates
        - If travel_pack is implied (e.g., "family trip"), set travel_pack="family" and don't include in missing
        - If dates can be reasonably inferred (e.g., "this weekend"), set the specific dates and don't include in missing
        """

    try:
        resp = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        text = (resp.content or "").strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise ValueError("No JSON in response")
        parsed = json.loads(m.group(0))
        logger.debug("Clarification agent parsed extraction payload: %s", parsed)

        # Write back parsed fields (skip empties)
        hint = parsed.get("destination_hint")
        if hint not in (None, "", {}, []):
            info["destination_hint"] = hint

        for key in [
            "origin", "destination", "departure_date", "return_date",
            "duration_days", "trip_purpose", "travel_pack", "constraints"
        ]:
            val = parsed.get(key)
            if val in (None, "", {}, []):
                continue
            if key == "destination":
                # If LLM gave a fuzzy place, store as hint instead.
                text_val = str(val).strip()
                if text_val and _looks_like_hint(text_val):
                    info["destination_hint"] = text_val
                    info.pop("destination", None)
                    continue
            info[key] = val

        missing = parsed.get("missing", []) or []
        complete = all([
            info.get("origin"),
            info.get("departure_date") and info.get("return_date"),
            info.get("trip_purpose"),
            info.get("travel_pack"),
        ])

        # If complete, avoid re-asking if we've already confirmed this exact combo
        if complete and not missing:
            current_hash = _hash_required(info)
            if clar.get("status") == "complete" and clar.get("confirmed_hash") == current_hash:
                state.setdefault("ui_flags", {})["confirmed"] = True
                return state

            # Build one-line human summary and ask once
            parts = []
            if info.get("origin"): parts.append(f"from {info['origin']}")
            if info.get("departure_date") and info.get("return_date"):
                dep = datetime.fromisoformat(info["departure_date"]).strftime("%B %d")
                ret = datetime.fromisoformat(info["return_date"]).strftime("%B %d")
                parts.append(f"{dep} to {ret}")
            if info.get("destination"):
                parts.append(f"to {info['destination']}")
            elif info.get("destination_hint"):
                parts.append(f"near {info['destination_hint']}")
            if info.get("trip_purpose"): parts.append(f"for {info['trip_purpose']}")
            if info.get("travel_pack") and info["travel_pack"] != "solo":
                parts.append(f"with {info['travel_pack']}")
            summary = ", ".join(parts) if parts else "your trip"

            tools["clarification"] = {
                "status": "awaiting_confirmation",
                "summary": summary,
                "confirmed_hash": current_hash,  # used to skip re-asking when unchanged
            }
            add_message(state, AIMessage(content=f"Let me confirm your trip: {summary}. Does this look correct?"))
            return state

        # If incomplete, ask for the top 1–2 missing items
        if missing:
            labels = {
                "origin": "departure location",
                "departure_date": "departure date",
                "return_date": "return date",
                "trip_purpose": "what you'd like to do",
                "travel_pack": "who's traveling",
            }
            ask = [labels.get(missing[0], missing[0])]
            if len(missing) > 1:
                ask.append(labels.get(missing[1], missing[1]))
            prefix_bits = []
            if info.get("origin"): prefix_bits.append(f"from {info['origin']}")
            if info.get("departure_date"): prefix_bits.append(f"on {info['departure_date']}")
            if info.get("trip_purpose"): prefix_bits.append(f"for {info['trip_purpose']}")
            prefix = f"Thanks! I have {', '.join(prefix_bits)}. " if prefix_bits else ""
            add_message(state, AIMessage(content=prefix + f"Could you share your {' and '.join(ask)}?"))
            tools["clarification"] = {"status": "incomplete", "missing": missing}
            return state

    except Exception:
        # Fall back to a simple ask if parsing fails
        tools["clarification"] = {"status": "incomplete"}
        add_message(state, AIMessage(content="Could you tell me where you're traveling from, your dates, and what you'd like to do?"))
        return state

    return state
