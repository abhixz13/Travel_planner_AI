# agents/destination_discovery_agent.py
"""
Autonomous Destination Discovery Agent

This agent handles destination discovery through conversational interaction:
- Reads full conversation history for context
- Uses web search tools (TAVILY, SERPAPI) to find destinations
- Interprets user responses semantically (no rule-based matching)
- Handles "show me more" requests by searching for different options
- Tracks iterations (max 3 cycles)
- Patches state with confirmed destination

Architecture:
- LLM decides action based on conversation
- Tools: web search for fresh destination options
- Memory: tracks shown destinations across cycles
- Output: state patch with destination or options to present
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import logging
import os
import re
import json
import requests

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from core.state import GraphState, add_message
from core.conversation_manager import last_user_message

logger = logging.getLogger(__name__)

# ---------------------------- Config --------------------------------------------

MAX_CYCLES = 3
SEARCH_TIMEOUT = 12
MAX_RESULTS_PER_SEARCH = 5

# ---------------------------- Web Search Tools ----------------------------------

def _search_destinations(query: str, trip_info: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Search for destination options using TAVILY and SERPAPI.

    Args:
        query: Search query (e.g., "family-friendly beach towns near Seattle")
        trip_info: Trip details for context filtering

    Returns:
        List of destination options with descriptions
    """
    results = []

    # Try TAVILY first
    tavily_results = _tavily_search(query)
    results.extend(tavily_results)

    # Supplement with SERPAPI if needed
    if len(results) < 3:
        serp_results = _serp_search(query)
        results.extend(serp_results)

    # Deduplicate and format
    seen_names = set()
    unique_results = []
    for r in results:
        name = r.get("name", "").strip()
        if name and name.lower() not in seen_names:
            seen_names.add(name.lower())
            unique_results.append(r)
            if len(unique_results) >= MAX_RESULTS_PER_SEARCH:
                break

    logger.info(f"Web search for '{query}' returned {len(unique_results)} destinations")
    return unique_results


def _tavily_search(query: str) -> List[Dict[str, str]]:
    """Search using TAVILY API."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.debug("TAVILY_API_KEY not set, skipping Tavily search")
        return []

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query + " tourist destination travel guide",
                "max_results": 8,
                "search_depth": "basic"
            },
            timeout=SEARCH_TIMEOUT
        )

        if not response.ok:
            logger.debug(f"Tavily API error: {response.status_code}")
            return []

        data = response.json()
        results = data.get("results", [])

        # Extract destination names from results
        destinations = []
        for result in results:
            title = result.get("title", "")
            snippet = result.get("content", "")

            # Try to extract destination name from title
            name = _extract_destination_name(title, snippet)
            if name:
                destinations.append({
                    "name": name,
                    "description": snippet[:200],
                    "source": "tavily"
                })

        return destinations

    except Exception as e:
        logger.debug(f"Tavily search error: {e}")
        return []


def _serp_search(query: str) -> List[Dict[str, str]]:
    """Search using SERPAPI."""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        logger.debug("SERPAPI_API_KEY not set, skipping SERP search")
        return []

    try:
        response = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google",
                "q": query + " travel destination",
                "hl": "en",
                "gl": "us",
                "api_key": api_key
            },
            timeout=SEARCH_TIMEOUT
        )

        if not response.ok:
            logger.debug(f"SERPAPI error: {response.status_code}")
            return []

        data = response.json()
        results = data.get("organic_results", [])

        destinations = []
        for result in results:
            title = result.get("title", "")
            snippet = result.get("snippet", "")

            name = _extract_destination_name(title, snippet)
            if name:
                destinations.append({
                    "name": name,
                    "description": snippet[:200],
                    "source": "serpapi"
                })

        return destinations

    except Exception as e:
        logger.debug(f"SERPAPI search error: {e}")
        return []


def _extract_destination_name(title: str, snippet: str) -> Optional[str]:
    """
    Extract destination name from search result.
    Uses LLM for robust extraction.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = f"""Extract the destination name from this search result.

Title: {title}
Snippet: {snippet}

Return ONLY the destination name (city, park, region, etc.) or "none" if unclear.
Examples: "Seattle", "Olympic National Park", "Big Sur", "Napa Valley"
"""

    try:
        response = llm.invoke(prompt)
        name = response.content.strip().strip('"\'')

        if name.lower() == "none" or len(name) > 50:
            return None

        return name

    except Exception as e:
        logger.debug(f"Destination name extraction error: {e}")
        return None


# ---------------------------- Autonomous Agent Logic ----------------------------

def _get_conversation_summary(state: GraphState) -> str:
    """Format conversation history for agent context."""
    messages = state.get("messages", [])

    # Get last 6 messages for context
    recent = messages[-6:] if len(messages) > 6 else messages

    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Assistant: {msg.content}")

    return "\n".join(lines)


def _get_shown_destinations(state: GraphState) -> List[str]:
    """Get list of destination names already shown to user."""
    tools = state.get("tool_results", {}) or {}
    discovery = tools.get("discovery", {}) or {}
    shown = discovery.get("shown_destinations", [])
    return shown if isinstance(shown, list) else []


def _interpret_user_intent(state: GraphState) -> Dict[str, Any]:
    """
    Use LLM to interpret user's intent regarding destination selection.

    Returns:
        {
            "action": "destination_confirmed" | "needs_options" | "wants_more" | "unclear",
            "destination": str or None,
            "search_refinement": str or None (e.g., "beach towns", "cheaper options")
        }
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    conversation = _get_conversation_summary(state)
    shown_destinations = _get_shown_destinations(state)
    last_msg = last_user_message(state)
    extracted_info = state.get("extracted_info", {}) or {}

    prompt = f"""You are analyzing a travel planning conversation to understand the user's destination intent.

Conversation history:
{conversation}

Previously shown destinations: {shown_destinations if shown_destinations else "None"}

User's latest message: "{last_msg}"

Current extracted info: {json.dumps(extracted_info, indent=2)}

Analyze the user's intent and return JSON with your interpretation:

{{
  "action": "destination_confirmed" | "needs_options" | "wants_more" | "unclear",
  "destination": "exact destination name" or null,
  "search_refinement": "what user wants to see" or null,
  "reasoning": "brief explanation"
}}

Action definitions:
- "destination_confirmed": User has clearly indicated/confirmed a specific destination
- "needs_options": User needs destination suggestions (no destination yet)
- "wants_more": User rejected current options and wants different/more suggestions
- "unclear": User's intent is ambiguous

Examples:
- "I want to go to Seattle" → {{"action": "destination_confirmed", "destination": "Seattle", ...}}
- "Show me beach towns" → {{"action": "needs_options", "search_refinement": "beach towns", ...}}
- "I don't like these, show me something different" → {{"action": "wants_more", "search_refinement": "different destinations", ...}}
- "Olympic National Park sounds perfect!" → {{"action": "destination_confirmed", "destination": "Olympic National Park", ...}}

Return ONLY valid JSON.
"""

    try:
        response = llm.invoke(prompt)
        text = response.content.strip()

        # Extract JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            logger.info(f"User intent interpreted: {result.get('action')} - {result.get('reasoning')}")
            return result
        else:
            logger.warning("Failed to parse intent JSON")
            return {"action": "unclear", "destination": None, "search_refinement": None}

    except Exception as e:
        logger.exception(f"Error interpreting user intent: {e}")
        return {"action": "unclear", "destination": None, "search_refinement": None}


def _build_search_query(state: GraphState, refinement: Optional[str] = None) -> str:
    """Build search query based on trip info and user refinement."""
    extracted_info = state.get("extracted_info", {}) or {}

    origin = extracted_info.get("origin", "")
    duration = extracted_info.get("duration_days", "")
    purpose = extracted_info.get("trip_purpose", "")
    pack = extracted_info.get("travel_pack", "")
    hint = extracted_info.get("destination_hint", "")

    # Start with base query
    parts = []

    if refinement:
        parts.append(refinement)
    elif hint:
        parts.append(hint)

    if purpose:
        parts.append(purpose)

    if pack and pack != "solo":
        parts.append(pack)

    if origin and duration:
        parts.append(f"near {origin} for {duration} days")

    query = " ".join(parts) if parts else "weekend destinations"

    logger.info(f"Built search query: '{query}'")
    return query


# ---------------------------- Main Agent Function --------------------------------

def suggest_destinations(state: GraphState) -> GraphState:
    """
    Autonomous destination discovery agent.

    Uses LLM to interpret conversation and decide actions:
    - Confirm destination if user has selected one
    - Search and present options if user needs suggestions
    - Search for different options if user wants more
    - Handle up to 3 cycles of iteration
    """

    # Get state components
    extracted_info = state.get("extracted_info", {}) or {}
    tools = state.setdefault("tool_results", {})
    discovery = tools.setdefault("discovery", {})

    # Check if destination already confirmed
    if extracted_info.get("destination"):
        logger.info(f"Destination already set: {extracted_info['destination']}")
        discovery["resolved"] = True
        return state

    # Check cycle count
    cycle_count = discovery.get("cycle_count", 0)
    if cycle_count >= MAX_CYCLES:
        logger.info(f"Reached max cycles ({MAX_CYCLES}), asking user to be more specific")
        add_message(state, AIMessage(content=(
            "I'm having trouble finding the perfect destination. Could you be more specific about:\n"
            "- A general area or region you're interested in?\n"
            "- What type of place (city, beach, mountains, etc.)?\n"
            "- Any must-have activities or features?\n\n"
            "This will help me narrow down the options!"
        )))
        return state

    # Interpret user's intent
    intent = _interpret_user_intent(state)
    action = intent.get("action")
    destination = intent.get("destination")
    search_refinement = intent.get("search_refinement")

    logger.info(f"Cycle {cycle_count + 1}/{MAX_CYCLES}: Action={action}, Destination={destination}")

    # Handle based on intent
    if action == "destination_confirmed" and destination:
        # User confirmed a destination - patch state
        extracted_info["destination"] = destination
        discovery["resolved"] = True

        # Acknowledge enthusiastically
        trip_type = extracted_info.get('trip_purpose', 'trip')
        add_message(state, AIMessage(content=(
            f"Excellent choice! **{destination}** is perfect for {trip_type}. "
            f"Let me find the best options for you... 🔍"
        )))

        logger.info(f"Destination confirmed: {destination}")
        return state

    elif action in ["needs_options", "wants_more"]:
        # Need to search for destinations

        # Increment cycle
        discovery["cycle_count"] = cycle_count + 1

        # Build search query
        query = _build_search_query(state, search_refinement)

        # Search for destinations
        search_results = _search_destinations(query, extracted_info)

        if not search_results:
            # Fallback if search fails
            add_message(state, AIMessage(content=(
                "I'm having trouble finding specific destinations. "
                "Could you tell me more about what you're looking for? "
                "For example, a region, type of place, or specific activities?"
            )))
            return state

        # Track shown destinations
        shown = discovery.setdefault("shown_destinations", [])
        new_destinations = [d["name"] for d in search_results]
        shown.extend(new_destinations)

        # Format options for user
        options_text = _format_destination_options(search_results, action == "wants_more")
        add_message(state, AIMessage(content=options_text))

        # Store current suggestions
        discovery["suggestions"] = search_results
        discovery["resolved"] = False

        logger.info(f"Presented {len(search_results)} destination options")
        return state

    else:  # unclear
        # User's intent is unclear - ask for clarification
        add_message(state, AIMessage(content=(
            "I want to make sure I find the perfect destination for you! "
            "Could you tell me:\n"
            "- Do you have a specific place in mind?\n"
            "- Or would you like me to suggest some options based on your preferences?"
        )))
        return state


def _format_destination_options(results: List[Dict[str, str]], is_refresh: bool = False) -> str:
    """Format destination options for presentation to user."""

    intro = "Here are some different options:" if is_refresh else "Here are a few destination ideas:"

    lines = [intro, ""]

    for idx, dest in enumerate(results[:3], start=1):
        name = dest.get("name", "Unknown")
        desc = dest.get("description", "")

        # Truncate description
        if len(desc) > 120:
            desc = desc[:120] + "..."

        lines.append(f"**{idx}. {name}** — {desc}")

    lines.append("")
    lines.append("Reply with **1–3** to pick a destination, or let me know if you'd like to see more options!")

    return "\n".join(lines)
