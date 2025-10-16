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
except ImportError:  # Older langgraph releases
    create_react_agent = None  # type: ignore

# ----------------------------- Tools ------------------------------------------

logger = logging.getLogger(__name__)


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

# --------------------------- Agent (ReAct) -----------------------------------

_PROMPT = (
    "You are a travel-options agent.\n"
    "- Create 1–3 focused queries from the trip context to research: flights, driving time/route, nearby airports, and transfers.\n"
    "- Prefer `tavily_travel` for curated roundups/how-tos; if thin or generic, also call `serp_travel` for breadth.\n"
    "- Aggregate up to 12 useful, non-duplicated links.\n"
    "- End with a brief 1–2 sentence user-facing summary.\n"
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
            tools=[tavily_travel, serp_travel],
            state_modifier=_PROMPT,
        )
        _FALLBACK_MODE = False
    except TypeError:
        _AGENT = create_react_agent(llm, tools=[tavily_travel, serp_travel])
        _FALLBACK_MODE = True
    return _AGENT

# ------------------------------ Node -----------------------------------------

def find_travel_options(state: GraphState) -> Optional[Dict[str, Any]]:
    """Gather transport research (flights, drive time, airports, transfers)."""

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
        logger.debug("Travel agent: OPENAI_API_KEY missing; returning failure patch.")
        payload = {
            "summary": "Cannot research travel options: OPENAI_API_KEY is not set.",
            "results": [],
        }
        logger.debug("Travel agent collected %d links; returning patch.", 0)
        state.setdefault("tool_results", {})["travel"] = payload
        return {"travel": payload}

    context = (
        "TRIP CONTEXT:\n"
        f"- origin: {origin}\n"
        f"- destination: {dest}\n"
        f"- when: {when}\n"
        "Research flights, driving time/routes, nearby airports, and transfer options. "
        "Form 1–3 concise queries and call the tools. End with a brief summary."
    )
    logger.debug(
        "Travel agent invoking ReAct with origin=%s destination=%s when=%s",
        origin,
        dest,
        when,
    )

    try:
        result = agent.invoke(
            {"messages": [SystemMessage(content=context)]},
            config={"tags": ["agent:travel"], "metadata": {"node": "fetch_travel_options"}},
        )
    except Exception as exc:
        logger.exception("Travel agent invocation failed.")
        payload = {
            "summary": "Travel research failed: " + str(exc).split("\n")[0],
            "results": [],
        }
        logger.debug("Travel agent collected %d links; returning patch.", 0)
        state.setdefault("tool_results", {})["travel"] = payload
        return {"travel": payload}

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

    summary = "Transport research links (flights, drive time, transfers)."
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            candidate = (m.content or "").strip()
            if candidate:
                summary = candidate
                break

    results = _normalize_links(collected, limit=12)

    payload = {"summary": summary, "results": results}
    logger.debug("Travel agent collected %d links; returning %s.", len(results), "patch" if results or summary else "None")

    if not (summary.strip() or results):
        return None

    state.setdefault("tool_results", {})["travel"] = payload
    return {"travel": payload}
