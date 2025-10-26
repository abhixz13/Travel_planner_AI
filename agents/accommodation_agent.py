# agents/accommodation_agent.py
from __future__ import annotations

import json
import os
import re
import logging
from typing import Any, Dict, List, Optional

import requests
from core.conversation_manager import last_user_message
from core.state import GraphState
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
try:
    from langgraph.prebuilt import create_react_agent
except ImportError:
    create_react_agent = None

logger = logging.getLogger(__name__)

# ----------------------------- Tools ------------------------------------------

@tool
def tavily_stays(query: str) -> str:
    """Search web for hotels/areas; returns JSON list of {title,url,snippet}."""
    api = os.getenv("TAVILY_API_KEY")
    if not api:
        return "[]"
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": api, "query": query, "max_results": 8, "search_depth": "basic"},
            timeout=12,
        )
        data = r.json() if r.ok else {}
        rows = data.get("results", []) or []
        out = [
            {
                "title": x.get("title", "") or "",
                "url": (x.get("url") or "").strip(),
                "snippet": x.get("content", "") or "",
            }
            for x in rows
            if (x.get("url") or "").strip()
        ]
        return json.dumps(out[:8])
    except Exception:
        return "[]"

@tool
def serp_stays(query: str) -> str:
    """Google (SerpAPI) search for stays/areas; returns JSON list of {title,url,snippet}."""
    api = os.getenv("SERPAPI_API_KEY")
    if not api:
        return "[]"
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": query, "hl": "en", "gl": "us", "api_key": api},
            timeout=12,
        )
        data = r.json() if r.ok else {}
        rows = data.get("organic_results", []) or []
        out = []
        for x in rows:
            url = (x.get("link") or "").strip()
            if url:
                out.append({
                    "title": x.get("title", "") or "",
                    "url": url,
                    "snippet": x.get("snippet", "") or "",
                })
            if len(out) >= 8:
                break
        return json.dumps(out)
    except Exception:
        return "[]"

@tool
def fetch_page_content(url: str) -> str:
    """Fetch and return main text content from a URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; TravelBot/1.0)'}
        r = requests.get(url, headers=headers, timeout=15)  # Increased timeout
        if not r.ok:
            return ""
        
        text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # CHANGE THIS: Increase from 3000 to 5000 for more context
        return text[:5000]  # Was 3000, now 5000
    except Exception as exc:
        logger.debug(f"Failed to fetch {url}: {exc}")
        return ""

# --------------------------- Agent (ReAct) -----------------------------------

_PROMPT = (
    "You are a family accommodation expert.\n"
    "WORKFLOW:\n"
    "1. Create 1-2 focused search queries based on trip context and traveler needs\n"
    "2. Use tavily_stays or serp_stays to find relevant hotel listing pages\n"
    "3. Use fetch_page_content on the TOP 3-5 most relevant URLs to extract actual pricing and details\n"
    "4. **EXTRACT SPECIFIC PRICING from web pages:**\n"
    "   - Look for: 'per night', 'nightly rate', 'from $', 'starting at', 'price', 'rate'\n"
    "   - Examples: '$129/night', 'from $99', 'average $150 per night', 'rates from $85'\n"
    "   - If no price found: indicate 'call for rates' or 'check availability'\n"
    "5. **APPLY COMMON SENSE based on who's traveling:**\n"
    "   - Toddlers/infants: Prioritize cribs, high chairs, kitchenettes, kid-safe rooms, pools\n"
    "   - Young children: Look for family suites, kids activities, child-friendly dining\n"
    "   - Seniors/elderly: Prioritize elevators, ground-floor rooms, accessibility, quiet locations\n"
    "   - Accessibility needs: Ensure wheelchair access, grab bars, accessible bathrooms\n"
    "6. Synthesize into 3 SPECIFIC hotel recommendations with this structure:\n"
    "   \n"
    "   **Hotel Name** — $X/night\n"
    "   [2-3 sentences about the property]\n"
    "   Location: [City, area]\n"
    "   Features:\n"
    "   - [Relevant amenity for THIS travel party]\n"
    "   - [Another relevant feature]\n"
    "   - [Third feature matching traveler needs]\n"
    "   [Website link]\n"
    "   \n"
    "7. CRITICAL: Extract real prices from web content - don't make up generic ranges\n"
    "8. Provide recommendations in clear prose with specific data points\n\n"
    "CRITICAL: Match amenities to actual traveler needs - use human judgment!"
)

_AGENT = None
_FALLBACK_MODE = False
_ACK_REPLIES = {
    "ok", "okay", "sure", "sounds good",
    "looks good", "thanks", "thank you",
    # NOTE: "yes", "yep", "yeah" removed - these are user confirmations, not acknowledgments
    # User saying "yes" to travel means they want to proceed to stays research
}

def _is_brief_ack(message: Optional[str]) -> bool:
    if not message:
        return False
    cleaned = re.sub(r"[^a-zA-Z\s]", "", message).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned in _ACK_REPLIES

def _normalize_links(links: List[Dict[str, Any]], limit: int) -> List[Dict[str, str]]:
    seen = set()
    normalized: List[Dict[str, str]] = []
    for entry in links:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url", "") or "").strip()
        if not url or url in seen:
            continue
        title = str(entry.get("title", "") or "").strip() or "Link"
        snippet = str(entry.get("snippet", "") or "")
        normalized.append({"title": title, "url": url, "snippet": snippet})
        seen.add(url)
        if len(normalized) >= limit:
            break
    return normalized

def _build_agent():
    global _AGENT, _FALLBACK_MODE
    if _AGENT is not None:
        return _AGENT

    if create_react_agent is None:
        raise RuntimeError("LangGraph version lacks create_react_agent")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
    max_tokens=2048  # Ensure detailed responses
    )
    try:
        _AGENT = create_react_agent(
            llm,
            tools=[tavily_stays, serp_stays, fetch_page_content],
            state_modifier=_PROMPT,
        )
        _FALLBACK_MODE = False
    except TypeError:
        _AGENT = create_react_agent(llm, tools=[tavily_stays, serp_stays, fetch_page_content])
        _FALLBACK_MODE = True
    return _AGENT

# ------------------------------ Node -----------------------------------------

def find_accommodation(state: GraphState) -> Optional[Dict[str, Any]]:
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}
    logger.debug("Accommodation agent input keys: %s", sorted(ex.keys()))

    if _is_brief_ack(last_user_message(state)):
        logger.debug("Accommodation agent: acknowledgement detected; returning None.")
        return None

    dest = (ex.get("destination") or "").strip()
    dep = (ex.get("departure_date") or "").strip()
    ret = (ex.get("return_date") or "").strip()

    if not (dest and dep and ret):
        logger.debug("Accommodation agent: inputs incomplete for research; returning None.")
        return None

    # Get additional context for geographic verification
    dest_hint = (ex.get("destination_hint") or "").strip()  # e.g., "near Seattle"
    origin = (ex.get("origin") or "").strip()

    logger.info(f"Accommodation search for destination: '{dest}', hint: '{dest_hint}', from: '{origin}'")

    # Check for refinement criteria
    refinement = state.get("refinement_criteria", {}).get("accommodation")
    user_refinement_request = ""
    if refinement:
        user_refinement_request = refinement.get("user_request", "")
        logger.info(f"Accommodation agent using refinement criteria: {user_refinement_request[:100]}")

    try:
        agent = _build_agent()
    except RuntimeError:
        logger.debug("Accommodation agent: OPENAI_API_KEY missing; returning failure patch.")
        payload = {
            "recommendations": "Cannot research stays: OPENAI_API_KEY is not set.",
            "sources": [],
        }
        state.setdefault("tool_results", {})["stays"] = payload
        return {"stays": payload}

    context_prefix = (_PROMPT + "\n\n") if _FALLBACK_MODE else ""
    context = (
        f"{context_prefix}TRIP CONTEXT:\n"
        f"- destination: {dest}\n"
        f"- regional context: {dest_hint if dest_hint else 'not specified'}\n"
        f"- dates: {dep} → {ret}\n"
        f"- party: adults={ex.get('num_adults','')} kids={ex.get('kids_ages','')}\n"
        f"- purpose: {ex.get('trip_purpose','')} | preferences: {ex.get('travel_pack','')}\n\n"
    )

    # Add refinement instructions if present
    if user_refinement_request:
        context += (
            f"**USER REFINEMENT REQUEST:**\n"
            f'The user said: "{user_refinement_request}"\n'
            f"IMPORTANT: Adjust your search to match this feedback.\n"
            f"- If they want 'cheaper': Focus on budget hotels, hostels, lower price ranges\n"
            f"- If they mention location (e.g., 'downtown', 'beach'): Prioritize that area\n"
            f"- If they want 'different options': Find completely new hotels, different areas\n\n"
        )

    # Build geographic verification instructions
    verification_instructions = ""
    if any(keyword in dest.lower() for keyword in ["park", "falls", "beach", "trail", "museum", "center", "monument", "attraction"]):
        verification_instructions = (
            f"**CRITICAL FIRST STEP - VERIFY LOCATION:**\n"
            f"1. Search for 'where is {dest}' or '{dest} location' to find the EXACT city/region\n"
            f"2. Verify this matches the regional context: {dest_hint if dest_hint else 'user traveling from ' + origin}\n"
            f"3. ONLY AFTER verification, search for hotels using the verified city name\n"
            f"4. Example: If '{dest}' is in Kirkland, WA → search 'hotels in Kirkland Washington near {dest}'\n"
            f"5. DO NOT assume location - VERIFY first using web search!\n\n"
        )
    else:
        verification_instructions = (
            f"The destination appears to be a city/region name.\n"
            f"Search for hotels in '{dest}'"
            f"{' (verify it is ' + dest_hint + ')' if dest_hint else ''}.\n\n"
        )

    context += (
        f"{verification_instructions}"
        f"MANDATORY STEPS:\n"
        f"1. Use tavily_stays or serp_stays to VERIFY the geographic location\n"
        f"2. Use fetch_page_content on AT LEAST 4-6 URLs (preferably 5-6)\n"
        f"3. Focus on: hotels.com, booking.com, tripadvisor, Google Hotels\n"
        f"4. Search using the VERIFIED location (city name + state/country)\n"
        f"5. Extract REAL PRICES and SPECIFIC amenities from the content\n"
        f"6. Your recommendations must include exact prices or 'call for rates'\n"
        f"7. Each hotel description must be 4-6 sentences explaining WHY it's perfect\n\n"
        f"Example good search query: 'hotels near [verified landmark] in [verified city, state]'\n"
        f"Example bad search query: 'hotels in [first word of landmark]' (DON'T DO THIS)"
    )

    logger.debug("Accommodation agent invoking ReAct for %s (context: %s)", dest, dest_hint or origin)
    
    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=context)]},
            config={
                "tags": ["agent:accommodation"],
                "metadata": {"node": "fetch_accommodation"},
                "recursion_limit": 50,  # Allow more steps for complex research
            },
        )
    except Exception as exc:
        logger.exception("Accommodation agent invocation failed.")
        payload = {
            "recommendations": "Stay research failed: " + str(exc).split("\n")[0],
            "sources": [],
        }
        state.setdefault("tool_results", {})["stays"] = payload
        return {"stays": payload}

    if not isinstance(result, dict):
        payload = {
            "recommendations": "Unable to generate recommendations at this time.",
            "sources": [],
        }
        state.setdefault("tool_results", {})["stays"] = payload
        return {"stays": payload}

    messages = result.get("messages", [])
    
    # Collect source links
    collected: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.name in ["tavily_stays", "serp_stays"]:
            try:
                payload = json.loads(m.content or "[]")
                if isinstance(payload, list):
                    collected.extend([it for it in payload if isinstance(it, dict)])
            except Exception:
                pass

    # Get AI recommendations
    recommendations = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            candidate = (m.content or "").strip()
            if candidate and len(candidate) > 100:  # Ensure substantial response
                recommendations = candidate
                break

    sources = _normalize_links(collected, limit=6)

    payload = {
        "recommendations": recommendations or "Unable to generate specific recommendations.",
        "sources": sources
    }
    
    logger.debug("Accommodation agent completed with %d sources", len(sources))
    state.setdefault("tool_results", {})["stays"] = payload
    return {"stays": payload}