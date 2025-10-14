# agents/travel_options_agent.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import requests
from core.state import GraphState
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
try:
    from langgraph.prebuilt import create_react_agent
except ImportError:  # Older langgraph releases
    create_react_agent = None  # type: ignore

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

def find_travel_options(state: GraphState) -> GraphState:
    """
    ReAct agent to gather transport research (flights, drive time, airports, transfers).

    Writes: state['tool_results']['travel'] = {
        "summary": str,
        "suggested_queries": [],                  # agent internalizes queries
        "results": List[{title,url,snippet}]      # up to 12
    }
    """
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}
    origin = (ex.get("origin") or "").strip()
    dest = (ex.get("destination") or "").strip()
    when = (ex.get("departure_date") or "").strip() or f"{ex.get('duration_days','')} days"

    # Build agent lazily; degrade gracefully if no key
    try:
        agent = _build_agent()
    except RuntimeError:
        state.setdefault("tool_results", {})["travel"] = {
            "summary": "Cannot research travel options: OPENAI_API_KEY is not set.",
            "suggested_queries": [],
            "results": [],
        }
        return state

    context_prefix = (_PROMPT + "\n\n") if _FALLBACK_MODE else ""

    context = (
        f"{context_prefix}TRIP CONTEXT:\n"
        f"- origin: {origin}\n"
        f"- destination: {dest}\n"
        f"- when: {when}\n"
        "Research flights, driving time/routes, nearby airports, and transfer options. "
        "Form 1–3 concise queries and call the tools. End with a brief summary."
    )

    prior: List[BaseMessage] = list(state.get("messages", []))
    if not dest:
        state.setdefault("tool_results", {})["travel"] = {
            "summary": "Once we lock a destination, I can pull travel options.",
            "suggested_queries": [],
            "results": [],
        }
        return state

    try:
        prior: List[BaseMessage] = list(state.get("messages", []))
        conversation = prior + [SystemMessage(content=context)]
        result = agent.invoke(
            conversation,
            config={"tags": ["agent:travel"], "metadata": {"node": "fetch_travel_options"}}
        )
    except Exception as exc:
        state.setdefault("tool_results", {})["travel"] = {
            "summary": "Travel research failed: " + str(exc).split("\n")[0],
            "suggested_queries": [],
            "results": [],
        }
        return state

    messages: List[BaseMessage] = result.get("messages", []) if isinstance(result, dict) else []
    links: List[Dict[str, str]] = []

    # Collect tool payloads (each tool returns a JSON list)
    for m in messages:
        if isinstance(m, ToolMessage):
            try:
                payload = json.loads(m.content or "[]")
                if isinstance(payload, list):
                    for it in payload:
                        if isinstance(it, dict):
                            url = (it.get("url") or "").strip()
                            if url:
                                links.append({
                                    "title": it.get("title", "") or "",
                                    "url": url,
                                    "snippet": it.get("snippet", "") or "",
                                })
            except Exception:
                pass

    # Last AI message (not a ToolMessage) is the human-facing summary
    summary = "Transport research links (flights, drive time, transfers)."
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            summary = (m.content or summary).strip() or summary
            break

    # Simple dedupe + cap at 12
    seen, deduped = set(), []
    for it in links:
        u = it["url"]
        if u and u not in seen:
            seen.add(u)
            deduped.append(it)
        if len(deduped) >= 12:
            break

    state.setdefault("tool_results", {})["travel"] = {
        "summary": summary,
        "suggested_queries": [],  # agent internalizes the queries
        "results": deduped,
    }
    return state
