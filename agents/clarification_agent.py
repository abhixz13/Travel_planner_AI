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


# Treat low-information strings (e.g., "null") as missing.
_SENTINEL_STRINGS = {"", "null", "none", "n/a", "na", "unknown", "tbd", "unsure"}


def _normalize_value(val: Any) -> Any:
    """Coerce loose sentinels to None and trim whitespace."""
    if isinstance(val, str):
        cleaned = val.strip()
        if cleaned.lower() in _SENTINEL_STRINGS:
            return None
        return cleaned
    return val


# --- main node ---------------------------------------------------------------

def _detect_hotel_refinement(user_msg: str) -> bool:
    """Detect if user is requesting different hotel options."""
    msg_lower = user_msg.lower()
    patterns = [
        "cheaper", "budget", "less expensive", "lower price",
        "different hotel", "other hotel", "more hotel",
        "downtown", "near beach", "close to", "closer to",
        "sub $", "under $", "less than $", "below $"
    ]
    return any(pattern in msg_lower for pattern in patterns)


def extract_travel_info(state: GraphState) -> GraphState:
    """Extract essentials, confirm once, and skip re-asking when unchanged."""
    latest_user = last_user_message(state)
    if not latest_user or not latest_user.strip():
        logger.debug("Clarification agent: no new user input; returning state.")
        return state
    logger.debug("Clarification agent processing user input: %s", latest_user.strip())

    # Warm greeting for first interaction (detect simple greetings)
    msgs = state.get("messages", [])
    is_first_message = len([m for m in msgs if isinstance(m, HumanMessage)]) == 1

    # Check if this is just a greeting without trip info
    simple_greeting_tokens = ["hi", "hello", "hey", "greetings"]
    user_msg_lower = latest_user.lower().strip()
    is_simple_greeting = (
        is_first_message and
        len(user_msg_lower.split()) <= 2 and
        any(token in user_msg_lower for token in simple_greeting_tokens)
    )

    if is_simple_greeting:
        greeting = """👋 Hi! I'm your AI travel planner.

I'll help you create the perfect trip in minutes. Just tell me where you want to go, when, and what you're looking for - I'll handle the rest.

**Ready to start?** Tell me about your dream trip!"""
        add_message(state, AIMessage(content=greeting))
        logger.info("Sent warm greeting for first-time user with simple hello")
        return state  # Return early - don't ask for details yet

    # Initialize shared refs FIRST (needed by hotel refinement check)
    info = state.setdefault("extracted_info", {})
    tools = state.setdefault("tool_results", {})
    clar = tools.get("clarification", {}) or {}

    # Check if this is a hotel refinement request
    if _detect_hotel_refinement(latest_user):
        # Set refinement criteria (datetime already imported at module level)
        state.setdefault("refinement_criteria", {})["accommodation"] = {
            "user_request": latest_user,
            "refined_at": datetime.now().isoformat()
        }
        # Clear current hotels to force re-search
        current_plan = state.get("current_plan", {})
        if current_plan and "stays" in current_plan:
            current_plan["stays"] = None
        logger.info(f"Hotel refinement detected: {latest_user[:100]}")

        # Mark clarification as complete to avoid re-asking for confirmation
        # The refinement should proceed directly to stays research
        tools.setdefault("clarification", {})["status"] = "complete"
        logger.info("Clarification marked complete for hotel refinement - skipping re-extraction")

        # Return early - don't re-extract trip info, user is just refining hotels
        return state

    # Destination selection is now handled by autonomous destination_discovery_agent
    # No rule-based matching needed here - the discovery agent uses LLM to interpret intent

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

    system_prompt = """You are a travel information extractor. Extract trip details from natural conversation.
- Return ONLY valid JSON matching the exact schema
- Extract only what is explicitly stated or strongly implied
- COMBINE information from ALL user messages in the conversation
- Don't invent or assume information
- Be concise - no additional commentary
- If information is unclear or missing, list it in the 'missing' array"""

    prompt = f"""Extract trip information from natural conversation.

        CRITICAL RULES:
        - COMBINE information from ALL user messages in the conversation - DO NOT ignore earlier messages
        - Each user message may contain different pieces of information - merge them together
        - If "Already extracted" shows some fields, PRESERVE them unless the user explicitly changed them
        - If a user message is just a number (1, 2, 3), it's likely a selection - keep all info from previous messages
        - Use JSON null (not string "null") for missing/unknown values
        - Only set "destination" if user explicitly names a specific place
        - If destination is vague/uncertain, leave it as null and set "destination_hint" instead
        - Examples of what NOT to set as destination: "somewhere", "anywhere", "beach", "mountains"
        - "near [city]" should be set as destination_hint, not destination

        CONSTRAINT CAPTURE (IMPORTANT):
        - Capture WHO is traveling with their characteristics in trip_purpose
        - Include age groups, mobility needs, preferences in trip_purpose description
        - Examples:
          * "family activities with toddler" NOT just "family activities"
          * "relaxing getaway with 70-year-old dad" NOT just "relaxing getaway"
          * "beach vacation with wheelchair user" NOT just "beach vacation"
        - This helps AI apply common sense when recommending travel options

        TODAY: {today.strftime("%A, %B %d, %Y")}

        Conversation (COMBINE info from ALL messages):
        {conversation}

        Already extracted: {json.dumps(info, indent=2)}

        Return ONLY valid JSON like:
        {{
        "origin": "city, state or null", // IMPORTANT: Extract CITY name, not just state. "Tracy, California" NOT "California"
        "destination": "city, state or null", // ONLY specific places; use null otherwise
        "destination_hint": "vague location or null", // only set if destination is vague/uncertain
        "departure_date": "YYYY-MM-DD",
        "return_date": "YYYY-MM-DD",
        "duration_days": 2,
        "trip_purpose": "activities/goals",
        "travel_pack": "solo|family|couple|friends|other",
        "constraints": {{}},
        "missing": []
        }}

        ORIGIN EXTRACTION RULES:
        - "from Tracy in California" → origin: "Tracy, California"
        - "from San Francisco" → origin: "San Francisco, California"
        - "from California" → origin: "California" (only if no city mentioned)
        - Always preserve the CITY name if one is mentioned

        REQUIRED FIELDS: origin, departure_date, return_date, trip_purpose, travel_pack
        - List required fields that are missing or null in the "missing" array
        - "destination" is optional - only include if explicitly mentioned
        - "duration_days" is optional - can be computed from dates
        - If travel_pack is implied (e.g., "family trip", "with toddler"), set travel_pack="family" and don't include in missing
        - If dates can be reasonably inferred (e.g., "this weekend"), calculate the actual YYYY-MM-DD dates and don't include in missing
        - For "this weekend": if today is Mon-Wed, use upcoming Sat-Sun; if Thu-Sun, use the current/coming weekend
        - For trip_purpose: infer from context (e.g., "family trip" → "family activities and relaxation")
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
        logger.info("Clarification agent extracted from LLM: %s", json.dumps(parsed, indent=2))
        logger.debug("Current state before merge: %s", json.dumps(info, indent=2))

        # Write back parsed fields (skip empties)
        hint = parsed.get("destination_hint")
        if hint not in (None, "", {}, []):
            info["destination_hint"] = hint

        for key in [
            "origin", "destination", "departure_date", "return_date",
            "duration_days", "trip_purpose", "travel_pack", "constraints"
        ]:
            val = _normalize_value(parsed.get(key))
            if val in (None, "", {}, []):
                if key in info:
                    info.pop(key, None)
                continue
            if key == "destination":
                # If LLM gave a fuzzy place, store as hint instead.
                text_val = str(val).strip()
                if text_val and _looks_like_hint(text_val):
                    info["destination_hint"] = text_val
                    info.pop("destination", None)
                    continue
            info[key] = val

        logger.info("Clarification agent state after merge: %s", json.dumps(info, indent=2))

        missing_raw = parsed.get("missing", []) or []
        missing: List[str] = []
        for item in missing_raw:
            text = str(item).strip()
            if text and text.lower() not in _SENTINEL_STRINGS:
                missing.append(text)

        required_fields = ["origin", "departure_date", "return_date", "trip_purpose", "travel_pack"]
        for field in required_fields:
            if not _normalize_value(info.get(field)):
                if field not in missing:
                    missing.append(field)

        complete = all([
            info.get("origin"),
            info.get("departure_date") and info.get("return_date"),
            info.get("trip_purpose"),
            info.get("travel_pack"),
        ])

        logger.debug(f"Missing fields: {missing if missing else 'None'}")
        logger.debug(f"Completeness: {'✓ Complete' if (complete and not missing) else '✗ Incomplete'}")

        # If complete, avoid re-asking if we've already confirmed this exact combo
        if complete and not missing:
            current_hash = _hash_required(info)
            if clar.get("status") == "complete" and clar.get("confirmed_hash") == current_hash:
                state.setdefault("ui_flags", {})["confirmed"] = True
                return state

            # Build structured confirmation card
            from_loc = info.get("origin", "")
            to_loc = info.get("destination") or info.get("destination_hint", "")

            # Format dates nicely
            date_str = ""
            if info.get("departure_date") and info.get("return_date"):
                dep = datetime.fromisoformat(info["departure_date"]).strftime("%b %d")
                ret = datetime.fromisoformat(info["return_date"]).strftime("%b %d, %Y")
                date_str = f"{dep}-{ret}"
                if info.get("duration_days"):
                    date_str += f" ({info['duration_days']} days)"

            # Build travelers string
            travelers_str = ""
            pack = info.get("travel_pack", "")
            if pack and pack != "solo":
                travelers_str = pack.capitalize()

            # Create visual card
            confirmation_msg = f"""Perfect! Here's what I have:

┌─────────────────────────────────────┐
│ 📍 **From:** {from_loc}
│ 📍 **To:** {to_loc}
│ 📅 **When:** {date_str}"""

            if travelers_str:
                confirmation_msg += f"\n│ 👥 **Who:** {travelers_str}"

            if info.get("trip_purpose"):
                confirmation_msg += f"\n│ 🎯 **Purpose:** {info['trip_purpose']}"

            confirmation_msg += "\n└─────────────────────────────────────┘\n\n**Does this look good?**"

            # Build simple summary for logging
            summary_parts = []
            if info.get("origin"): summary_parts.append(info['origin'])
            if info.get("destination"): summary_parts.append(f"→ {info['destination']}")
            elif info.get("destination_hint"): summary_parts.append(f"→ {info['destination_hint']}")
            if info.get("departure_date"): summary_parts.append(info['departure_date'])
            summary = " ".join(summary_parts) if summary_parts else "trip confirmation"

            tools["clarification"] = {
                "status": "awaiting_confirmation",
                "summary": summary,
                "confirmed_hash": current_hash,  # used to skip re-asking when unchanged
            }
            logger.info("Clarification seeking confirmation: %s", summary)
            add_message(state, AIMessage(content=confirmation_msg))
            return state

        # If incomplete, ask for the top 1–2 missing items with smart context
        if missing:
            labels = {
                "origin": "departure location",
                "departure_date": "departure date",
                "return_date": "return date",
                "trip_purpose": "what you'd like to do",
                "travel_pack": "who's traveling",
            }

            # Only ask for top missing item (cleaner UX)
            ask_for = labels.get(missing[0], missing[0])

            # Build smart context showing what we DO have
            context_parts = []
            if info.get("destination") or info.get("destination_hint"):
                dest = info.get("destination") or info.get("destination_hint")
                context_parts.append(f"trip to **{dest}**")
            if info.get("trip_purpose"):
                context_parts.append(f"for **{info['trip_purpose']}**")
            if info.get("travel_pack"):
                pack = info['travel_pack']
                context_parts.append(f"with **{pack}**" if pack != "solo" else "**solo**")

            # Create natural, conversational ask
            if context_parts:
                context = "Great! I'm planning a " + ", ".join(context_parts) + "."
                question = f"\n\nWhat's your **{ask_for}**?"
            else:
                question = f"What's your **{ask_for}**?"
                context = ""

            message = context + question

            logger.info("Clarification requesting: %s", ask_for)
            add_message(state, AIMessage(content=message))
            tools["clarification"] = {"status": "incomplete", "missing": missing}
            return state

    except Exception as e:
        # Fall back to a simple ask if parsing fails
        logger.error("Clarification agent extraction failed: %s", e, exc_info=True)
        logger.debug("Conversation context was: %s", conversation)
        tools["clarification"] = {"status": "incomplete"}
        add_message(state, AIMessage(content="Could you tell me where you're traveling from, your dates, and what you'd like to do?"))
        return state

    return state
