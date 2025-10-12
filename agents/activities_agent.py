# agents/activities_agent.py
from __future__ import annotations
import json, os, requests
from typing import Any, Dict, List
from core.state import GraphState
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

@tool
def serp_activities(query: str) -> str:
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

_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

_AGENT = create_react_agent(
    _LLM,
    tools=[serp_activities, tavily_activities],
    state_modifier=(
        "You are an activities-finder agent.\n"
        "- Create 1–3 focused queries from the trip context.\n"
        "- Prefer `serp_activities` for breadth; if thin/generic, also call `tavily_activities`.\n"
        "- Aggregate 5–8 strong, non-duplicated links.\n"
        "- End with a brief 1–2 sentence summary for the user.\n"
        "Always use the tools for links; do not invent URLs."
    ),
)

def find_activities(state: GraphState) -> GraphState:
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}
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

    prior: List[BaseMessage] = list(state.get("messages", []))
    result = _AGENT.invoke(
        {"messages": prior + [SystemMessage(content=context)]},
        config={"tags": ["agent:activities"], "metadata": {"node": "fetch_activities"}}
    )

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