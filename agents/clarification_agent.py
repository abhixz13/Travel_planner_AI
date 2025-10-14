"""Simple clarification agent - extract trip info, ask what's missing."""

from datetime import datetime
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage

_HINT_TOKENS = {
    "any", "some", "somewhere", "anywhere", "open", "suggest", "kid",
    "kids", "family", "friendly", "outdoor", "outdoors", "nature", "near",
    "around", "close", "within", "drive", "options", "ideas", "recommend",
}


def _looks_like_hint(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(token in lower for token in _HINT_TOKENS)
from core.conversation_manager import last_user_message
from core.state import GraphState, add_message

def _is_confirmation(text: str) -> bool:
    """Check if user is confirming/agreeing."""
    text = text.lower().strip()
    positive = {"yes", "yep", "yeah", "correct", "right", "sure", "ok", "okay", 
                "good", "great", "perfect", "sounds good", "looks good", "confirmed"}
    negative = {"no", "nope", "not", "wrong", "incorrect", "change", "actually"}
    
    if any(neg in text.split() for neg in negative):
        return False
    return any(pos in text.split() for pos in positive)

def extract_travel_info(state: GraphState) -> GraphState:
    """Extract trip info from conversation. Ask for missing essentials."""
    
    # Only run when we have a new user message
    latest_user = last_user_message(state)
    if not latest_user or not latest_user.strip():
        return state
    
    info = state.setdefault("extracted_info", {})
    tools = state.setdefault("tool_results", {})
    
    # Handle confirmation flow
    clarification_status = tools.get("clarification", {})
    if clarification_status.get("status") == "awaiting_confirmation":
        if _is_confirmation(latest_user):
            tools["clarification"] = {"status": "complete"}
            add_message(state, AIMessage(content="Perfect! Let me find great options for you."))
            return state
        else:
            # User is correcting - re-extract
            tools["clarification"] = {"status": "incomplete"}
    
    # Prevent loops - max 3 attempts
    attempts = state.get("clarification_attempts", 0)
    if attempts >= 3:
        tools["clarification"] = {"status": "complete"}
        add_message(state, AIMessage(content="Let me work with what we have."))
        return state
    
    # Get recent USER messages only
    messages = state.get("messages", [])
    recent_user_messages = []
    for msg in reversed(messages[-10:]):
        if isinstance(msg, HumanMessage):
            recent_user_messages.append(msg.content)
            if len(recent_user_messages) >= 3:
                break
    
    conversation = "\n".join([f"User: {m}" for m in reversed(recent_user_messages)])
    
    # Get current date for LLM context
    today = datetime.now()
    
    # Single LLM call - trust it to understand dates semantically
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    prompt = f"""Extract trip information from natural conversation. Use semantic understanding.

TODAY: {today.strftime("%A, %B %d, %Y")} (it's a {today.strftime("%A")})

Conversation:
{conversation}

Already extracted: {json.dumps(info, indent=2)}

Return valid JSON:
{{
  "origin": "city",
  "destination": "city or null",
  "departure_date": "YYYY-MM-DD",
  "return_date": "YYYY-MM-DD",
  "duration_days": 2,
  "trip_purpose": "activities/goals",
  "travel_pack": "solo/family/couple/friends/etc",
  "constraints": {{}},
  "missing": []
}}

DATE INTERPRETATION (use common sense):
- "this weekend" = the upcoming Saturday-Sunday from today
- "next weekend" = the weekend after this weekend
- "coming weekend" = usually means this weekend
- "long weekend" = typically 3 days (Fri-Sun or Sat-Mon)
- "Oct 17" in October 2025 = 2025-10-17
- "2 days" starting Friday = Friday + Saturday (return Sunday)

SEMANTIC RULES:
- "weekend trip" = Saturday to Sunday (2 days, return Sunday evening)
- "week trip" = 7 days
- "with family" = travel_pack: "family"
- "kids-friendly" or "toddler" mentioned = note in trip_purpose or constraints

BUILD ON EXISTING:
- Don't erase good data
- Update if user corrects something
- Combine related info intelligently

REQUIRED: origin, (departure_date + return_date), trip_purpose, travel_pack
OPTIONAL: destination, destination_hint, constraints, duration_days

List ONLY missing required fields in "missing" array. If all required present, return empty array."""

    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        content = response.content.strip()
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON in response")
        
        result = json.loads(json_match.group(0))
        
        # Update info with extracted values (skip nulls/empties)
        hint = result.get("destination_hint")
        if hint not in [None, "", {}, []]:
            info["destination_hint"] = hint

        for key in [
            "origin",
            "destination",
            "departure_date",
            "return_date",
            "duration_days",
            "trip_purpose",
            "travel_pack",
            "constraints",
        ]:
            value = result.get(key)
            if value in [None, "", {}, []]:
                continue
            if key == "destination":
                text = str(value).strip()
                if text and _looks_like_hint(text):
                    info["destination_hint"] = text
                    info.pop("destination", None)
                    continue
            info[key] = value
        
        # Check completeness
        missing = result.get("missing", [])
        has_required = all([
            info.get("origin"),
            info.get("departure_date") and info.get("return_date"),
            info.get("trip_purpose"),
            info.get("travel_pack")
        ])
        
        if has_required and not missing:
            # Build human-readable summary
            parts = []
            
            if info.get('origin'):
                parts.append(f"from {info['origin']}")
            
            if info.get('departure_date') and info.get('return_date'):
                # Format dates nicely
                dep = datetime.fromisoformat(info['departure_date']).strftime("%B %d")
                ret = datetime.fromisoformat(info['return_date']).strftime("%B %d")
                parts.append(f"{dep} to {ret}")
            
            if info.get('destination'):
                parts.append(f"to {info['destination']}")
            elif info.get('destination_hint'):
                parts.append(f"near {info['destination_hint']}")
            
            if info.get('trip_purpose'):
                parts.append(f"for {info['trip_purpose']}")
            
            if info.get('travel_pack'):
                pack = info['travel_pack']
                if pack != "solo":
                    parts.append(f"with {pack}")
            
            summary = ", ".join(parts)
            
            # ALWAYS confirm before proceeding
            confirmation = f"Let me confirm your trip: {summary}. Does this look correct?"
            
            tools["clarification"] = {
                "status": "awaiting_confirmation",
                "summary": summary
            }
            add_message(state, AIMessage(content=confirmation))
            return state
        
        # Ask for missing info
        if missing:
            state["clarification_attempts"] = attempts + 1
            
            # Show what we have
            have_parts = []
            if info.get('origin'):
                have_parts.append(f"from {info['origin']}")
            if info.get('departure_date'):
                have_parts.append(f"on {info['departure_date']}")
            if info.get('trip_purpose'):
                have_parts.append(f"for {info['trip_purpose']}")
            
            field_labels = {
                "origin": "departure location",
                "timing": "travel dates",
                "departure_date": "departure date",
                "return_date": "return date",
                "trip_purpose": "what you'd like to do",
                "travel_pack": "who's traveling"
            }
            
            missing_friendly = [field_labels.get(f, f) for f in missing[:2]]
            
            if have_parts:
                question = f"Thanks! I have {', '.join(have_parts)}. "
            else:
                question = "I'd love to help! "
            
            question += f"Could you share your {' and '.join(missing_friendly)}?"
            
            tools["clarification"] = {"status": "incomplete", "missing": missing}
            add_message(state, AIMessage(content=question))
            return state
            
    except Exception as e:
        print(f"[clarifier error] {e}")
        state["clarification_attempts"] = attempts + 1
        tools["clarification"] = {"status": "incomplete"}
        add_message(state, AIMessage(content="Could you tell me where you're traveling from, when, and what you'd like to do?"))
    
    return state
