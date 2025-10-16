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
except ImportError:  # Older langgraph releases
    create_react_agent = None  # type: ignore

logger = logging.getLogger(__name__)
@tool
def serp_activities(query: str) -> str:
    """Google (SerpAPI) search for activities at a destination; returns JSON list of {title,url,snippet}."""
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
                out.append({"title": x.get("title","") or "", "url": url, "snippet": x.get("snippet","") or ""})
            if len(out) >= 8: break
        return json.dumps(out)
    except Exception:
        return "[]"

@tool
def tavily_activities(query: str) -> str:
    """Tavily search for activity roundups/guides; returns JSON list of {title,url,snippet}."""
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
        out = [{"title": x.get("title","") or "", "url": (x.get("url") or "").strip(), "snippet": x.get("content","") or ""} 
               for x in rows if (x.get("url") or "").strip()]
        return json.dumps(out[:8])
    except Exception:
        return "[]"

_PROMPT = (
    "You are an activities-finder agent.\n"
    "- Create 1–3 focused queries from the trip context.\n"
    "- Prefer `serp_activities` for breadth; if thin/generic, also call `tavily_activities`.\n"
    "- Aggregate 5–8 strong, non-duplicated links.\n"
    "- End with a brief 1–2 sentence summary for the user.\n"
    "Always use the tools for links; do not invent URLs."
)

_AGENT = None
_FALLBACK_MODE = False
_ACK_REPLIES = {
    "ok",
    "okay",
    "yes",
    "yep",
    "yeah",
    "sure",
    "sounds good",
    "looks good",
    "thanks",
    "thank you",
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
        raise RuntimeError("LangGraph version lacks create_react_agent; please upgrade langgraph>=0.1.5")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    try:
        _AGENT = create_react_agent(
            llm,
            tools=[serp_activities, tavily_activities],
            state_modifier=_PROMPT,
        )
        _FALLBACK_MODE = False
    except TypeError:
        _AGENT = create_react_agent(llm, tools=[serp_activities, tavily_activities])
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
        f"- dates: {ex.get('departure_date','')} → {ex.get('return_date','')}\n"
        "Use this context to form queries and call the tools. End with a brief summary."
    )

    try:
        agent = _build_agent()
    except RuntimeError:
        logger.debug("Activities agent: OPENAI_API_KEY missing; returning failure patch.")
        payload = {
            "summary": "Cannot research activities: OPENAI_API_KEY is not set.",
            "results": [],
        }
        logger.debug("Activities agent collected %d links; returning patch.", 0)
        state.setdefault("tool_results", {})["activities"] = payload
        return {"activities": payload}

    logger.debug(
        "Activities agent invoking ReAct for destination=%s dates=%s→%s",
        dest,
        ex.get("departure_date", ""),
        ex.get("return_date", ""),
    )
    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=context)]},
            config={"tags": ["agent:activities"], "metadata": {"node": "fetch_activities"}},
        )
    except Exception as exc:
        logger.exception("Activities agent invocation failed.")
        payload = {
            "summary": "Activities research failed: " + str(exc).split("\n")[0],
            "results": [],
        }
        logger.debug("Activities agent collected %d links; returning patch.", 0)
        state.setdefault("tool_results", {})["activities"] = payload
        return {"activities": payload}

    messages = result.get("messages", []) if isinstance(result, dict) else []
    collected: List[Dict[str, Any]] = []

    for m in messages:
        if isinstance(m, ToolMessage):
            try:
                payload = json.loads(m.content or "[]")
            except Exception:
                payload = []
            if isinstance(payload, list):
                collected.extend([it for it in payload if isinstance(it, dict)])

    summary = "Here are top activity links."
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            candidate = (m.content or "").strip()
            if candidate:
                summary = candidate
                break

    results = _normalize_links(collected, limit=8)

    payload = {"summary": summary, "results": results}
    logger.debug(
        "Activities agent collected %d links; returning %s.",
        len(results),
        "patch" if results or summary else "None",
    )

    if not (summary.strip() or results):
        return None

    state.setdefault("tool_results", {})["activities"] = payload
    return {"activities": payload}
