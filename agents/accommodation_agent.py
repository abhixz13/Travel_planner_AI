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
except ImportError:  # Older langgraph releases
    create_react_agent = None  # type: ignore

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

# --------------------------- Agent (ReAct) -----------------------------------

_PROMPT = (
    "You are an accommodation-finder agent.\n"
    "- Create 1–3 focused queries from the trip context (destination, dates, party, preferences).\n"
    "- Prefer `tavily_stays` for curated neighborhood/hotel roundups; if thin or generic, also call `serp_stays` for breadth.\n"
    "- Aggregate 3–8 useful, non-duplicated links.\n"
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
            tools=[tavily_stays, serp_stays],
            state_modifier=_PROMPT,
        )
        _FALLBACK_MODE = False
    except TypeError:
        _AGENT = create_react_agent(llm, tools=[tavily_stays, serp_stays])
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
            "summary": "Cannot research stays: OPENAI_API_KEY is not set.",
            "results": [],
        }
        logger.debug("Accommodation agent collected %d links; returning patch.", 0)
        state.setdefault("tool_results", {})["stays"] = payload
        return {"stays": payload}

    context_prefix = (_PROMPT + "\n\n") if _FALLBACK_MODE else ""
    context = (
        f"{context_prefix}TRIP CONTEXT:\n"
        f"- destination: {dest}\n"
        f"- dates: {dep} → {ret}\n"
        f"- party: adults={ex.get('num_adults','')} kids={ex.get('kids_ages','')}\n"
        f"- purpose/preferences: {ex.get('trip_purpose','')} | pack: {ex.get('travel_pack','')}\n"
        "Use this context to form queries and call the tools. End with a brief summary."
    )
    logger.debug(
        "Accommodation agent invoking ReAct for destination=%s dates=%s→%s",
        dest,
        dep,
        ret,
    )
    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=context)]},
            config={"tags": ["agent:accommodation"], "metadata": {"node": "fetch_accommodation"}},
        )
    except Exception as exc:
        logger.exception("Accommodation agent invocation failed.")
        payload = {
            "summary": "Stay research failed: " + str(exc).split("\n")[0],
            "results": [],
        }
        logger.debug("Accommodation agent collected %d links; returning patch.", 0)
        state.setdefault("tool_results", {})["stays"] = payload
        return {"stays": payload}

    if not isinstance(result, dict):
        payload = {
            "summary": "Stays research completed, but returned no structured results this time. I can try again or refine the query.",
            "results": [],
        }
        logger.debug("Accommodation agent collected %d links; returning patch.", 0)
        state.setdefault("tool_results", {})["stays"] = payload
        return {"stays": payload}

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

    summary = "Here are useful stay/area links."
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            candidate = (m.content or "").strip()
            if candidate:
                summary = candidate
                break

    results = _normalize_links(collected, limit=8)

    payload = {"summary": summary, "results": results}
    logger.debug(
        "Accommodation agent collected %d links; returning %s.",
        len(results),
        "patch" if results or summary else "None",
    )

    if not (summary.strip() or results):
        return None

    state.setdefault("tool_results", {})["stays"] = payload
    return {"stays": payload}
