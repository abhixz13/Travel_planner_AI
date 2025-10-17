# agents/travel_options_agent.py
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
def tavily_travel(query: str) -> str:
    """Search web for transport options; returns JSON list of {title,url,snippet}."""
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
def serp_travel(query: str) -> str:
    """Google (SerpAPI) search for transport options; returns JSON list of {title,url,snippet}."""
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
    "You are a travel logistics expert.\n"
    "WORKFLOW:\n"
    "1. Create 1-2 focused queries for transport research (flights, driving, airports)\n"
    "2. Use tavily_travel or serp_travel to find information\n"
    "3. Use fetch_page_content on TOP 2-3 URLs to get detailed info\n"
    "4. Synthesize into actionable travel advice:\n"
    "   - Best transport method (drive vs fly) with reasoning\n"
    "   - If driving: distance, time, route highlights\n"
    "   - If flying: recommended airports, typical flight duration, airlines\n"
    "   - Cost estimates if available\n"
    "   - Practical tips (booking windows, traffic times, etc.)\n"
    "5. Provide clear recommendations in prose, then list sources\n\n"
    "CRITICAL: READ content with fetch_page_content to give informed advice!"
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
        normalized.append({"title": title, "url": url})
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
            tools=[tavily_travel, serp_travel, fetch_page_content],
            state_modifier=_PROMPT,
        )
        _FALLBACK_MODE = False
    except TypeError:
        _AGENT = create_react_agent(llm, tools=[tavily_travel, serp_travel, fetch_page_content])
        _FALLBACK_MODE = True
    return _AGENT

# ------------------------------ Node -----------------------------------------

def find_travel_options(state: GraphState) -> Optional[Dict[str, Any]]:
    """Gather transport research and recommendations."""

    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}
    logger.debug("Travel agent input keys: %s", sorted(ex.keys()))

    if _is_brief_ack(last_user_message(state)):
        logger.debug("Travel agent: acknowledgement detected; returning None.")
        return None

    origin = (ex.get("origin") or "").strip()
    dest = (ex.get("destination") or "").strip()
    dep = (ex.get("departure_date") or "").strip()
    ret = (ex.get("return_date") or "").strip()
    duration = ex.get("duration_days")

    if not (origin and dest and (dep or ret or duration)):
        logger.debug("Travel agent: inputs incomplete for research; returning None.")
        return None

    when = dep or ret or (f"{duration} days" if duration else "")

    try:
        agent = _build_agent()
    except RuntimeError:
        logger.debug("Travel agent: OPENAI_API_KEY missing")
        payload = {
            "recommendations": "Cannot research travel options: OPENAI_API_KEY is not set.",
            "sources": [],
        }
        state.setdefault("tool_results", {})["travel"] = payload
        return {"travel": payload}

    context = (
        "TRIP CONTEXT:\n"
        f"- origin: {origin}\n"
        f"- destination: {dest}\n"
        f"- when: {when}\n"
        f"- purpose: {ex.get('trip_purpose', '')}\n\n"
        "MANDATORY: Use fetch_page_content on AT LEAST 4 URLs.\n"
        "Find EXACT drive times, distances, routes from Google Maps or similar.\n"
        "If flying is an option, research REAL flight prices and airports.\n"
        "Make a CLEAR recommendation (drive vs fly) with 3-4 specific reasons.\n"
        "Include toddler-specific travel tips (rest stops, timing, entertainment)."
    )
    
    logger.debug("Travel agent invoking ReAct: %s → %s", origin, dest)

    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=context)]},
            config={"tags": ["agent:travel"], "metadata": {"node": "fetch_travel_options"}},
        )
    except Exception as exc:
        logger.exception("Travel agent invocation failed.")
        payload = {
            "recommendations": "Travel research failed: " + str(exc).split("\n")[0],
            "sources": [],
        }
        state.setdefault("tool_results", {})["travel"] = payload
        return {"travel": payload}

    messages = result.get("messages", []) if isinstance(result, dict) else []
    
    # Collect sources
    collected: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.name in ["tavily_travel", "serp_travel"]:
            try:
                payload = json.loads(m.content or "[]")
                if isinstance(payload, list):
                    collected.extend([it for it in payload if isinstance(it, dict)])
            except Exception:
                pass

    # Get recommendations
    recommendations = ""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            candidate = (m.content or "").strip()
            if candidate and len(candidate) > 100:
                recommendations = candidate
                break

    sources = _normalize_links(collected, limit=6)

    payload = {
        "recommendations": recommendations or "Unable to generate specific recommendations.",
        "sources": sources
    }
    
    logger.debug("Travel agent completed with %d sources", len(sources))
    state.setdefault("tool_results", {})["travel"] = payload
    return {"travel": payload}