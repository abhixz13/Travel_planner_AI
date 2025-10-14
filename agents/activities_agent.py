# agents/activities_agent.py
from __future__ import annotations
import json, os, requests
from typing import Any, Dict, List
from core.state import GraphState
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
try:
    from langgraph.prebuilt import create_react_agent
except ImportError:  # Older langgraph releases
    create_react_agent = None  # type: ignore

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

def find_activities(state: GraphState) -> GraphState:
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}
    if not ex.get("destination"):
        print("DEBUG: No destination, skipping activities research")
        return state

    # Upstream guarantees destination exists
    dest = ex.get("destination", "").strip()

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
        state.setdefault("tool_results", {})["activities"] = {
            "summary": "Cannot research activities: OPENAI_API_KEY is not set.",
            "suggested_queries": [],
            "results": [],
        }
        return state

    prior: List[BaseMessage] = list(state.get("messages", []))
    try:
        result = agent.invoke(
            {"messages": prior + [SystemMessage(content=context)]},
            config={"tags": ["agent:activities"], "metadata": {"node": "fetch_activities"}}
        )
    except Exception as exc:
        state.setdefault("tool_results", {})["activities"] = {
            "summary": "Activities research failed: " + str(exc).split("\n")[0],
            "suggested_queries": [],
            "results": [],
        }
        return state

    messages: List[BaseMessage] = result.get("messages", []) if isinstance(result, dict) else []
    links: List[Dict[str, str]] = []

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
                                    "title": it.get("title","") or "",
                                    "url": url,
                                    "snippet": it.get("snippet","") or "",
                                })
            except Exception:
                pass

    # Pick the last AI message (not a ToolMessage) as the human-facing summary
    summary = "Here are top activity links."
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            summary = (m.content or summary).strip() or summary
            break

    # Simple dedupe + cap
    seen, deduped = set(), []
    for it in links:
        u = it["url"]
        if u and u not in seen:
            seen.add(u)
            deduped.append(it)
        if len(deduped) >= 8:
            break

    state.setdefault("tool_results", {})["activities"] = {
        "summary": summary,
        "suggested_queries": [],  # agent internalizes the queries
        "results": deduped,
    }
    return state
