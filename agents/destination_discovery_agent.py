# agents/destination_discovery_agent.py
"""
Destination discovery (dynamic):
1) LLM candidate generation (JSON list)
2) Web validation via Tavily + SerpAPI
3) Scoring & filtering (family/toddler fit, distance heuristics for trip length, diversity)
- No mutation of extracted_info
- Early no-op if destination is already set OR discovery is resolved
- Suggestions live under state["tool_results"]["discovery"]
- CTA sent once
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import logging
import os
import re
import json
import requests

from langchain_openai import ChatOpenAI
from core.state import GraphState
from core.conversation_manager import handle_ai_output

logger = logging.getLogger(__name__)

# ---------------------------- Config knobs -----------------------------------

MAX_CANDIDATES_LLM = 8
TOP_N = 5                        # final number of suggestions (3–5)
MAX_LINKS_PER_DEST = 3
TAVILY_TIMEOUT = 12
SERP_TIMEOUT = 12

FAMILY_KEYWORDS = [
    "family", "kid", "toddler", "stroller", "playground", "gentle trail", "easy hike",
    "beach", "aquarium", "zoo", "park", "boardwalk", "picnic", "calm water"
]

def _long_drive_threshold(duration_days: float | int | str) -> float:
    """Return the max reasonable one-way drive hours based on trip length."""
    try:
        d = float(duration_days) if duration_days is not None else 0.0
    except Exception:
        d = 0.0
    if d <= 2:
        return 4.5
    if d <= 4:
        return 7.0
    return 9.0

# ---------------------------- LLM helpers ------------------------------------

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

def _llm_candidate_prompt(ex: Dict[str, Any]) -> str:
    origin = ex.get("origin", "")
    dur = ex.get("duration_days", "")
    return (
        "Generate up to 8 destination candidates for a short trip.\n"
        "Return pure JSON only: "
        '[{"name":"string","region":"string","state_or_country":"string","why":"string"}].\n'
        "Guidance:\n"
        f"- Prioritize places reasonably reachable from '{origin}' for a {dur}-day trip.\n"
        "- Prefer options within practical driving time; if driving is long, consider short/direct flights (≤ ~2 hours) from the nearest major airport.\n"
        "- Fit the purpose, group, and constraints; avoid duplicates and ensure varied vibes (coast, mountains, small town, city, park).\n"
        f"Origin: {origin}\n"
        f"Purpose: {ex.get('trip_purpose','')}\n"
        f"Pack: {ex.get('travel_pack','')}\n"
        f"Duration days: {dur}\n"
        f"Hint: {ex.get('destination_hint','')}\n"
        f"Constraints: {ex.get('constraints',{})}\n"
    )

def _llm_candidates(ex: Dict[str, Any]) -> List[Dict[str, str]]:
    llm = _get_llm()
    prompt = _llm_candidate_prompt(ex)
    try:
        resp = llm.invoke([
            {"role": "system", "content": "Return only JSON. No prose."},
            {"role": "user", "content": prompt}
        ])
        text = (resp.content or "").strip()
        # Extract first JSON array found
        m = re.search(r'\[\s*\{.*?\}\s*\]', text, flags=re.DOTALL)
        data = json.loads(m.group(0)) if m else json.loads(text)
        if not isinstance(data, list):
            return []
        # Normalize fields
        out: List[Dict[str, str]] = []
        seen = set()
        for it in data[:MAX_CANDIDATES_LLM]:
            if not isinstance(it, dict):
                continue
            name = (it.get("name") or "").strip()
            region = (it.get("region") or "").strip()
            state_or_country = (it.get("state_or_country") or it.get("state") or "").strip()
            why = (it.get("why") or "").strip()
            key = name.lower()
            if name and key not in seen:
                seen.add(key)
                out.append({
                    "name": name,
                    "region": region,
                    "state": state_or_country,
                    "why": why
                })
        return out
    except Exception as exc:
        logger.debug("candidate LLM failed: %s", exc)
        return []

# ---------------------------- Web validation ---------------------------------

def _tavily_search(query: str) -> List[Dict[str, str]]:
    api = os.getenv("TAVILY_API_KEY")
    if not api:
        return []
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": api, "query": query, "max_results": 8, "search_depth": "basic"},
            timeout=TAVILY_TIMEOUT,
        )
        data = r.json() if r.ok else {}
        rows = data.get("results", []) or []
        out = []
        for x in rows:
            url = (x.get("url") or "").strip()
            if url:
                out.append({
                    "title": (x.get("title") or "").strip(),
                    "url": url,
                    "snippet": (x.get("content") or "").strip(),
                })
            if len(out) >= MAX_LINKS_PER_DEST:
                break
        return out
    except Exception as exc:
        logger.debug("tavily error: %s", exc)
        return []

def _serp_search(query: str) -> List[Dict[str, str]]:
    api = os.getenv("SERPAPI_API_KEY")
    if not api:
        return []
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": query, "hl": "en", "gl": "us", "api_key": api},
            timeout=SERP_TIMEOUT,
        )
        data = r.json() if r.ok else {}
        rows = data.get("organic_results", []) or []
        out = []
        for x in rows:
            url = (x.get("link") or "").strip()
            if url:
                out.append({
                    "title": (x.get("title") or "").strip(),
                    "url": url,
                    "snippet": (x.get("snippet") or "").strip(),
                })
            if len(out) >= MAX_LINKS_PER_DEST:
                break
        return out
    except Exception as exc:
        logger.debug("serp error: %s", exc)
        return []

def _extract_drive_hours(text: str) -> float | None:
    """Best-effort parse like '2 hr', '2.5 hours', '3-hour drive' from snippets."""
    if not text:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*hours?', text, re.I)
    if m:
        try:
            return (float(m.group(1)) + float(m.group(2))) / 2.0
        except Exception:
            pass
    m2 = re.search(r'(\d+(?:\.\d+)?)\s*(?:hr|hrs|hour|hours)', text, re.I)
    if m2:
        try:
            return float(m2.group(1))
        except Exception:
            pass
    return None

def _validate_candidate(origin: str, cand: Dict[str, str]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], float | None]:
    """
    Returns (tavily_links, serp_links, approx_drive_hours)
    """
    name = cand.get("name", "")
    if not name:
        return [], [], None

    # Queries
    q_info = f"{name} family toddler things to do"
    q_time = f"driving time from {origin} to {name}"

    tav = _tavily_search(q_info)
    serp = _serp_search(q_info)

    # Try to infer drive time from either info query or explicit time query
    drive_candidates = tav + serp + _tavily_search(q_time) + _serp_search(q_time)
    drive_hours: float | None = None
    for row in drive_candidates:
        h = _extract_drive_hours(row.get("snippet", "") + " " + row.get("title", ""))
        if h:
            drive_hours = h
            break

    return tav, serp, drive_hours

# ---------------------------- Scoring ----------------------------------------

def _keyword_hits(text: str, keywords: List[str]) -> int:
    if not text:
        return 0
    low = text.lower()
    return sum(1 for k in keywords if k in low)

def _score_candidate(ex: Dict[str, Any], cand: Dict[str, str],
                     tav: List[Dict[str, str]], serp: List[Dict[str, str]],
                     drive_hours: float | None) -> float:
    """
    Heuristic score:
    - Base relevance: family/toddler keywords in evidence
    - Purpose match boost if candidate 'why' + snippets contain purpose tokens
    - Distance penalty (duration-aware)
    - Evidence strength: more valid links = higher
    """
    purpose = (ex.get("trip_purpose") or "").lower()
    duration_days = ex.get("duration_days")
    threshold = _long_drive_threshold(duration_days)

    evidence = " ".join([(x.get("title","") + " " + x.get("snippet","")) for x in (tav + serp)])
    family_score = _keyword_hits(evidence, FAMILY_KEYWORDS)

    purpose_tokens = [t.strip() for t in re.split(r'[,/| ]+', purpose) if t.strip()]
    purpose_hits = sum(1 for t in purpose_tokens if t and t in evidence.lower())
    why_hits = sum(1 for t in purpose_tokens if t and t in (cand.get("why","").lower()))

    links_count = min(len(tav) + len(serp), MAX_LINKS_PER_DEST * 2)

    score = 1.0 * family_score + 0.5 * purpose_hits + 0.5 * why_hits + 0.2 * links_count

    # Duration-aware distance penalty
    try:
        if drive_hours and drive_hours > threshold:
            score -= (drive_hours - threshold)  # linear penalty
    except Exception:
        pass

    # Small boost if we actually extracted a drive time (evidence of practicality)
    if drive_hours is not None:
        score += 0.3

    return float(score)

def _diversify(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure a bit of diversity by region/type if available."""
    seen_names = set()
    out: List[Dict[str, Any]] = []
    for p in picks:
        name = p.get("name","").lower()
        if name and name not in seen_names:
            seen_names.add(name)
            out.append(p)
        if len(out) >= TOP_N:
            break
    return out

# ---------------------------- Main node --------------------------------------

def suggest_destinations(state: GraphState) -> GraphState:
    ex: Dict[str, Any] = state.get("extracted_info", {}) or {}
    tools: Dict[str, Any] = state.setdefault("tool_results", {})
    discovery: Dict[str, Any] = tools.setdefault("discovery", {})

    # If we're already waiting on the user to pick from existing suggestions, bail early.
    if discovery.get("suggestions") and not discovery.get("resolved"):
        logger.debug("Discovery suggestions already issued; awaiting user choice.")
        return state

    # If destination is already chosen OR discovery flow already resolved, skip.
    if (ex.get("destination") or "").strip() or discovery.get("resolved"):
        logger.debug("Destination set or discovery resolved; skipping discovery.")
        return state

    origin = (ex.get("origin") or "").strip()
    if not origin:
        logger.debug("No origin found; proceeding without drive-time heuristics.")

    # 1) LLM candidate generation
    candidates = _llm_candidates(ex)
    logger.debug("Discovery candidate generation produced %d options.", len(candidates))
    if not candidates:
        discovery["suggestions"] = []
        logger.debug("No candidates returned; leaving discovery suggestions empty.")
        return state

    # 2) Web validation + 3) Scoring
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for cand in candidates:
        tav, serp, drive_hours = _validate_candidate(origin, cand)
        score = _score_candidate(ex, cand, tav, serp, drive_hours)
        links = (tav + serp)[:MAX_LINKS_PER_DEST]
        suggestion = {
            "name": cand.get("name",""),
            "region": cand.get("region",""),
            "state": cand.get("state",""),
            "why": cand.get("why",""),
            "score": score,
            "drive_hours_estimate": drive_hours,
            "links": links,
        }
        scored.append((score, suggestion))

    # Sort, diversify, cap
    picks = [s for _, s in sorted(scored, key=lambda x: x[0], reverse=True)]
    picks = _diversify(picks)

    discovery["suggestions"] = picks
    logger.debug("Stored %d discovery suggestions.", len(picks))

    # CTA once
    if not discovery.get("cta_sent") and picks:
        bullets = []
        for idx, s in enumerate(picks[:3], start=1):
            why = (s.get("why") or "").strip()
            bullets.append(f"{idx}) {s['name']} — {why}" if why else f"{idx}) {s['name']}")
        cta = (
            "Here are a few destination ideas:\n"
            + "\n".join(bullets)
            + "\n\nReply with **1–3** to pick a destination (or name one)."
        )
        handle_ai_output(state, cta)
        discovery["cta_sent"] = True
        logger.debug("Discovery CTA sent to user.")

    return state
