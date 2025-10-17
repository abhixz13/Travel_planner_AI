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
    "You are an accommodation recommendation agent.\n"
    "WORKFLOW:\n"
    "1. Create 1-2 focused search queries based on trip context\n"
    "2. Use tavily_stays or serp_stays to find relevant articles\n"
    "3. Use fetch_page_content on the TOP 2-3 most relevant URLs to read actual content\n"
    "4. Synthesize the content into 2-3 SPECIFIC hotel/area recommendations with details:\n"
    "   - Name of property/area\n"
    "   - Why it's good for this family (proximity to attractions, amenities, etc.)\n"
    "   - Price range if available\n"
    "   - Family-friendly features\n"
    "5. End with your recommendations in clear prose, then list source URLs\n\n"
    "CRITICAL: Actually READ the content using fetch_page_content - don't just list links!"
)

_AGENT = None
_FALLBACK_MODE = False
_ACK_REPLIES = {
    "ok", "okay", "yes", "yep", "yeah", "sure", "sounds good", 
    "looks good", "thanks", "thank you",
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
        f"- dates: {dep} → {ret}\n"
        f"- party: adults={ex.get('num_adults','')} kids={ex.get('kids_ages','')}\n"
        f"- purpose: {ex.get('trip_purpose','')} | preferences: {ex.get('travel_pack','')}\n\n"
        "MANDATORY: Use fetch_page_content on AT LEAST 4 URLs (preferably 5-6).\n"
        "Focus on: hotels.com, booking.com, tripadvisor, local hotel sites.\n"
        "Extract REAL PRICES and SPECIFIC amenities from the content.\n"
        "Your recommendations must include exact prices or 'call for rates'.\n"
        "Each hotel description must be 4-6 sentences explaining WHY it's perfect."
    )
    
    logger.debug("Accommodation agent invoking ReAct for %s", dest)
    
    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=context)]},
            config={"tags": ["agent:accommodation"], "metadata": {"node": "fetch_accommodation"}},
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