# core/context_tracker.py
"""
Conversation Context Manager - Module 1.2
Tracks conversation state and resolves implicit references across turns.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


# ======================== Context Initialization ========================

def initialize_context(state: Dict[str, Any]) -> None:
    """
    Initialize conversation context tracking in state.
    
    Args:
        state: GraphState dictionary
    """
    if "conversation_context" not in state:
        state["conversation_context"] = {
            "current_topic": None,
            "current_component_id": None,
            "last_modification": None,
            "pending_decision": None,
            "recent_components": deque(maxlen=10),  # Last 10 discussed components
            "conversation_stage": "initial",  # initial, refining, complete
            "last_user_intent": None,
            "disambiguation_needed": False
        }
        logger.debug("Initialized conversation context tracking.")


# ======================== Context Updates ========================

def update_context(state: Dict[str, Any], **kwargs) -> None:
    """
    Update conversation context with new information.
    
    Args:
        state: GraphState dictionary
        **kwargs: Fields to update in context
            - current_topic: What's being discussed
            - current_component_id: Active component
            - last_modification: Recent change made
            - pending_decision: Awaiting user choice
            - last_user_intent: Detected intent from last message
            - conversation_stage: Current stage
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    for key, value in kwargs.items():
        if key in ctx:
            ctx[key] = value
            logger.debug(f"Context updated: {key} = {value}")
    
    ctx["last_updated"] = datetime.now().isoformat()


def track_component_discussion(state: Dict[str, Any], component_id: str, 
                               component_name: Optional[str] = None) -> None:
    """
    Track that a component was just discussed.
    
    Args:
        state: GraphState dictionary
        component_id: Component that was discussed
        component_name: Optional human-readable name
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    # Add to recent components (deque handles max length)
    entry = {
        "component_id": component_id,
        "name": component_name,
        "timestamp": datetime.now().isoformat()
    }
    
    # Avoid duplicate consecutive entries
    if ctx["recent_components"] and ctx["recent_components"][-1]["component_id"] != component_id:
        ctx["recent_components"].append(entry)
    elif not ctx["recent_components"]:
        ctx["recent_components"].append(entry)
    
    # Update current component
    ctx["current_component_id"] = component_id
    
    logger.debug(f"Tracked component discussion: {component_id} ({component_name})")


def set_pending_decision(state: Dict[str, Any], prompt: str, 
                        options: List[Dict[str, Any]], 
                        decision_type: str = "selection") -> None:
    """
    Mark that we're awaiting a user decision.
    
    Args:
        state: GraphState dictionary
        prompt: Question asked to user
        options: List of choices with metadata
        decision_type: Type of decision (selection, confirmation, custom)
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    ctx["pending_decision"] = {
        "prompt": prompt,
        "options": options,
        "type": decision_type,
        "created_at": datetime.now().isoformat()
    }
    
    logger.debug(f"Set pending decision: {decision_type} with {len(options)} options")


def clear_pending_decision(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Clear and return pending decision.
    
    Args:
        state: GraphState dictionary
    
    Returns:
        The pending decision that was cleared, or None
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    decision = ctx.get("pending_decision")
    ctx["pending_decision"] = None
    
    if decision:
        logger.debug(f"Cleared pending decision: {decision.get('type')}")
    
    return decision


# ======================== Context Retrieval ========================

def get_current_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get the current conversation context.
    
    Args:
        state: GraphState dictionary
    
    Returns:
        Context dictionary
    """
    initialize_context(state)
    return state["conversation_context"]


def get_recent_components(state: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get recently discussed components.
    
    Args:
        state: GraphState dictionary
        limit: Maximum number to return
    
    Returns:
        List of recent component entries (most recent first)
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    recent = list(ctx["recent_components"])
    recent.reverse()  # Most recent first
    return recent[:limit]


def get_current_component(state: Dict[str, Any]) -> Optional[str]:
    """
    Get the currently focused component ID.
    
    Args:
        state: GraphState dictionary
    
    Returns:
        Component ID or None
    """
    initialize_context(state)
    return state["conversation_context"].get("current_component_id")


def get_pending_decision(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get pending decision if any.
    
    Args:
        state: GraphState dictionary
    
    Returns:
        Pending decision dictionary or None
    """
    initialize_context(state)
    return state["conversation_context"].get("pending_decision")


# ======================== Implicit Reference Resolution ========================

def resolve_implicit_reference(state: Dict[str, Any], user_message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Resolve implicit references like "that one", "the first option", "it".
    
    Uses conversation context to infer what the user is referring to.
    
    Args:
        state: GraphState dictionary
        user_message: User's message
    
    Returns:
        Tuple of (component_id, component_data) or None
    """
    from core.component_registry import get_component
    
    initialize_context(state)
    ctx = state["conversation_context"]
    msg_lower = user_message.lower()
    
    # ===== Check for pending decision responses =====
    pending = ctx.get("pending_decision")
    if pending:
        # Numeric selection: "1", "option 2", "the first one"
        import re
        num_match = re.search(r'\b(\d+)\b', msg_lower)
        if num_match:
            idx = int(num_match.group(1)) - 1
            options = pending.get("options", [])
            if 0 <= idx < len(options):
                option = options[idx]
                comp_id = option.get("component_id")
                if comp_id:
                    comp = get_component(state, comp_id)
                    if comp:
                        logger.debug(f"Resolved numeric selection {idx+1} -> {comp_id}")
                        return comp_id, comp
        
        # Ordinal references: "first", "second", "last"
        ordinals = {
            "first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4,
            "last": -1, "final": -1
        }
        for word, idx in ordinals.items():
            if word in msg_lower:
                options = pending.get("options", [])
                if idx < len(options):
                    option = options[idx]
                    comp_id = option.get("component_id")
                    if comp_id:
                        comp = get_component(state, comp_id)
                        if comp:
                            logger.debug(f"Resolved ordinal '{word}' -> {comp_id}")
                            return comp_id, comp
    
    # ===== Pronoun references =====
    pronouns = ["it", "that", "this", "that one", "this one"]
    has_pronoun = any(pron in msg_lower for pron in pronouns)
    
    if has_pronoun:
        # Try current component first
        current_id = ctx.get("current_component_id")
        if current_id:
            comp = get_component(state, current_id)
            if comp:
                logger.debug(f"Resolved pronoun -> current component {current_id}")
                return current_id, comp
        
        # Try most recent component
        recent = ctx.get("recent_components", [])
        if recent:
            last = recent[-1]
            comp_id = last.get("component_id")
            comp = get_component(state, comp_id)
            if comp:
                logger.debug(f"Resolved pronoun -> recent component {comp_id}")
                return comp_id, comp
    
    # ===== "The [type]" references =====
    # e.g., "the restaurant", "the hotel", "the activity"
    if msg_lower.startswith("the "):
        type_words = {
            "restaurant": "restaurant",
            "hotel": "accommodation",
            "activity": "activity",
            "attraction": "activity"
        }
        
        for word, comp_type in type_words.items():
            if word in msg_lower:
                # Find most recent component of that type
                recent = ctx.get("recent_components", [])
                for entry in reversed(recent):
                    comp_id = entry.get("component_id")
                    comp = get_component(state, comp_id)
                    if comp and comp.get("component_type") == comp_type:
                        logger.debug(f"Resolved 'the {word}' -> {comp_id}")
                        return comp_id, comp
    
    logger.debug("Could not resolve implicit reference")
    return None


# ======================== Context Analysis ========================

def should_clarify(state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Determine if we need to ask the user for clarification.
    
    Args:
        state: GraphState dictionary
    
    Returns:
        Tuple of (should_clarify, clarification_message)
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    # If disambiguation flag is set
    if ctx.get("disambiguation_needed"):
        # Check what needs disambiguation
        recent = get_recent_components(state, limit=3)
        if len(recent) > 1:
            names = [r.get("name", r.get("component_id")) for r in recent]
            msg = f"I found multiple items. Did you mean:\n"
            for i, name in enumerate(names, 1):
                msg += f"{i}. {name}\n"
            return True, msg
    
    return False, None


def detect_topic_change(state: Dict[str, Any], new_intent: str) -> bool:
    """
    Detect if the user has changed topics.
    
    Args:
        state: GraphState dictionary
        new_intent: Newly detected intent
    
    Returns:
        True if topic changed significantly
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    last_intent = ctx.get("last_user_intent")
    if not last_intent:
        return False
    
    # Topic changes if intents are very different
    # For example: swap_component -> adjust_pace is a change
    # But swap_component -> swap_component is not
    
    topic_groups = {
        "swap": ["swap_component", "filter_by_attribute"],
        "schedule": ["adjust_pace", "add_activity", "remove_activity"],
        "budget": ["filter_by_attribute", "optimize_cost"],
        "logistics": ["optimize_logistics", "adjust_timing"]
    }
    
    last_group = None
    new_group = None
    
    for group, intents in topic_groups.items():
        if last_intent in intents:
            last_group = group
        if new_intent in intents:
            new_group = group
    
    changed = last_group != new_group and last_group is not None
    if changed:
        logger.debug(f"Topic change detected: {last_intent} -> {new_intent}")
    
    return changed


# ======================== Context Reset ========================

def reset_context(state: Dict[str, Any], keep_history: bool = True) -> None:
    """
    Reset conversation context (e.g., after completing a refinement).
    
    Args:
        state: GraphState dictionary
        keep_history: If True, keep recent_components; if False, clear everything
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    recent = list(ctx.get("recent_components", [])) if keep_history else []
    
    ctx.clear()
    ctx.update({
        "current_topic": None,
        "current_component_id": None,
        "last_modification": None,
        "pending_decision": None,
        "recent_components": deque(recent, maxlen=10),
        "conversation_stage": "initial",
        "last_user_intent": None,
        "disambiguation_needed": False
    })
    
    logger.debug(f"Reset context (kept history: {keep_history})")


# ======================== Integration Helpers ========================

def context_summary(state: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of current context.
    Useful for debugging and logging.
    
    Args:
        state: GraphState dictionary
    
    Returns:
        Summary string
    """
    initialize_context(state)
    ctx = state["conversation_context"]
    
    lines = ["=== Conversation Context ==="]
    lines.append(f"Stage: {ctx.get('conversation_stage')}")
    lines.append(f"Current topic: {ctx.get('current_topic')}")
    lines.append(f"Current component: {ctx.get('current_component_id')}")
    lines.append(f"Last intent: {ctx.get('last_user_intent')}")
    
    pending = ctx.get("pending_decision")
    if pending:
        lines.append(f"Pending decision: {pending.get('type')} ({len(pending.get('options', []))} options)")
    
    recent = ctx.get("recent_components", [])
    if recent:
        lines.append(f"Recent components ({len(recent)}):")
        for r in list(recent)[-3:]:
            lines.append(f"  - {r.get('name', r.get('component_id'))}")
    
    return "\n".join(lines)