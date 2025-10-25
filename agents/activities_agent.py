# agents/activities_agent.py
from __future__ import annotations
import json
import os
import re
import logging
import requests
from typing import Any, Dict, List, Optional
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

@tool
def serp_activities(query: str) -> str:
    """Google (SerpAPI) search for activities; returns JSON list of {title,url,snippet}."""
    api = os.getenv("SERPAPI_API_KEY")
    if not api: return "[]"
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"engine":"google","q":query,"hl":"en","gl":"us","api_key":api},
            timeout=12,
        )
        data = r.json() if r.ok else {}
        rows = data.get("organic_results", []) or []
        out = []
        for x in rows:
            url = (x.get("link") or "").strip()
            if url:
                out.append({
                    "title": x.get("title","") or "", 
                    "url": url, 
                    "snippet": x.get("snippet","") or ""
                })
            if len(out) >= 8: break
        return json.dumps(out)
    except Exception:
        return "[]"

@tool
def tavily_activities(query: str) -> str:
    """Tavily search for activity guides; returns JSON list of {title,url,snippet}."""
    api = os.getenv("TAVILY_API_KEY")
    if not api: return "[]"
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": api, "query": query, "max_results": 8, "search_depth": "basic"},
            timeout=12,
        )
        data = r.json() if r.ok else {}
        rows = data.get("results", []) or []
        out = [{
            "title": x.get("title","") or "", 
            "url": (x.get("url") or "").strip(), 
            "snippet": x.get("content","") or ""
        } for x in rows if (x.get("url") or "").strip()]
        return json.dumps(out[:8])
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

_PROMPT = (
    "You are an activities recommendation agent.\n"
    "WORKFLOW:\n"
    "1. Create 1-2 focused search queries for family/toddler activities\n"
    "2. Use serp_activities or tavily_activities to find guides\n"
    "3. Use fetch_page_content on TOP 3-5 URLs to read actual recommendations and extract specific details\n"
    "4. For EACH activity, extract structured information from the web pages:\n"
    "   **CRITICAL - EXTRACT THESE SPECIFIC DETAILS:**\n"
    "   - **Duration**: Look for phrases like 'visit takes', 'allow X hours', 'typical visit', 'plan for'\n"
    "     Examples: '2-3 hours typical', 'allow 90 minutes', 'half-day activity'\n"
    "   - **Cost**: Search for 'admission', 'price', 'entry fee', 'tickets', 'cost', '$'\n"
    "     Examples: '$25 per adult', 'free admission', '$15-20 per person', 'admission included'\n"
    "   - **Operating hours**: Look for 'hours', 'open', 'closes at'\n"
    "     Examples: '9am-5pm', 'open daily 10-6', 'seasonal hours'\n"
    "   - **Best time**: Look for recommendations about timing\n"
    "     Examples: 'arrive early to avoid crowds', 'mornings are best', 'skip weekends'\n"
    "5. Synthesize into 4-6 SPECIFIC activity recommendations with this structure:\n"
    "   \n"
    "   **Activity Name** (Type: indoor/outdoor/educational/etc.)\n"
    "   - Description: [1-2 sentences about what it is]\n"
    "   - Duration: [Extracted from research, e.g., '60-90 minutes' or '2-3 hours typical']\n"
    "   - Cost: [Extracted from research, e.g., '$15 per person' or 'free admission' or 'call for rates']\n"
    "   - Hours: [If found in research]\n"
    "   - Why perfect for [traveler type]: [specific reasons]\n"
    "   - Tips: [practical advice]\n"
    "   \n"
    "6. If duration/cost not found on web page, indicate 'check website' or 'typical [activity type] takes X'\n"
    "7. Provide recommendations in clear, structured prose with specific data points\n\n"
    "CRITICAL: Use fetch_page_content to READ actual content - extract real duration/cost data!"
)

_AGENT = None
_FALLBACK_MODE = False
_ACK_REPLIES = {
    "ok", "okay", "sure", "sounds good",
    "looks good", "thanks", "thank you",
    # NOTE: "yes", "yep", "yeah" removed - these are user confirmations, not acknowledgments
    # User saying "yes" to hotel means they want to proceed to activities research
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
            tools=[serp_activities, tavily_activities, fetch_page_content],
            state_modifier=_PROMPT,
        )
        _FALLBACK_MODE = False
    except TypeError:
        _AGENT = create_react_agent(llm, tools=[serp_activities, tavily_activities, fetch_page_content])
        _FALLBACK_MODE = True
    return _AGENT

def find_activities(state: GraphState) -> Optional[Dict[str, Any]]:
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}
    logger.debug("Activities agent input keys: %s", sorted(ex.keys()))

    if _is_brief_ack(last_user_message(state)):
        logger.debug("Activities agent: acknowledgement detected; returning None.")
        return None

    dest = (ex.get("destination") or "").strip()
    if not dest:
        logger.debug("Activities agent: destination missing; returning None.")
        return None

    context = (
        "TRIP CONTEXT:\n"
        f"- destination: {dest}\n"
        f"- purpose: {ex.get('trip_purpose','')}\n"
        f"- pack: {ex.get('travel_pack','')}\n"
        f"- dates: {ex.get('departure_date','')} → {ex.get('return_date','')}\n\n"
        "MANDATORY: Use fetch_page_content on AT LEAST 5 URLs.\n"
        "Find diverse sources: local blogs, tourism sites, family review sites.\n"
        "Extract REAL PRICES, HOURS, and TODDLER-SPECIFIC details.\n"
        "Provide 6-8 activities with full details (what, why, cost, duration, tips).\n"
        "Each activity needs 4-5 sentences of detail."
    )

    try:
        agent = _build_agent()
    except RuntimeError:
        logger.debug("Activities agent: OPENAI_API_KEY missing")
        payload = {
            "recommendations": "Cannot research activities: OPENAI_API_KEY is not set.",
            "sources": [],
        }
        state.setdefault("tool_results", {})["activities"] = payload
        return {"activities": payload}

    logger.debug("Activities agent invoking ReAct for %s", dest)
    
    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=context)]},
            config={"tags": ["agent:activities"], "metadata": {"node": "fetch_activities"}},
        )
    except Exception as exc:
        logger.exception("Activities agent invocation failed.")
        payload = {
            "recommendations": "Activities research failed: " + str(exc).split("\n")[0],
            "sources": [],
        }
        state.setdefault("tool_results", {})["activities"] = payload
        return {"activities": payload}

    messages = result.get("messages", []) if isinstance(result, dict) else []
    
    # Collect sources
    collected: List[Dict[str, Any]] = []
    for m in messages:
        if isinstance(m, ToolMessage) and m.name in ["serp_activities", "tavily_activities"]:
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
    
    logger.debug("Activities agent completed with %d sources", len(sources))
    state.setdefault("tool_results", {})["activities"] = payload
    return {"activities": payload}