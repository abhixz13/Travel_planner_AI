# core/component_registry.py
"""
Component Reference System - Module 1.1
Tracks and manages structured itinerary components with unique IDs.
"""

from __future__ import annotations
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# ======================== Component ID Generation ========================

def generate_component_id(component_type: str, day_number: Optional[int] = None, 
                         time_slot: Optional[str] = None) -> str:
    """
    Generate a unique, deterministic component ID.
    
    Format: {type}_{day}_{slot}_{uuid_suffix}
    Examples:
        - hotel_main_abc123
        - day1_morning_activity_def456
        - day2_evening_restaurant_ghi789
    
    Args:
        component_type: Type of component (activity, restaurant, hotel, etc.)
        day_number: Day number (1, 2, 3, etc.)
        time_slot: Time slot (morning, afternoon, evening)
    
    Returns:
        Unique component ID string
    """
    parts = []
    
    if day_number is not None:
        parts.append(f"day{day_number}")
    
    if time_slot:
        parts.append(time_slot.lower())
    
    parts.append(component_type.lower())
    
    # Short UUID suffix for uniqueness
    suffix = str(uuid.uuid4())[:8]
    parts.append(suffix)
    
    return "_".join(parts)


# ======================== Component Registration ========================

def register_component(state: Dict[str, Any], component_data: Dict[str, Any], 
                      component_type: str, day_number: Optional[int] = None,
                      time_slot: Optional[str] = None) -> str:
    """
    Register a new component in the itinerary structure.
    
    Args:
        state: GraphState dictionary
        component_data: Component details (name, location, cost, etc.)
        component_type: Type (activity, restaurant, hotel, transport)
        day_number: Day number if part of daily schedule
        time_slot: Time slot if part of daily schedule
    
    Returns:
        Generated component_id
    """
    # Ensure itinerary_components exists
    if "itinerary_components" not in state:
        state["itinerary_components"] = {
            "metadata": {},
            "accommodation": None,
            "transport": None,
            "days": {}
        }
    
    components = state["itinerary_components"]
    component_id = generate_component_id(component_type, day_number, time_slot)
    
    # Add metadata
    component_data["component_id"] = component_id
    component_data["component_type"] = component_type
    component_data["registered_at"] = datetime.now().isoformat()
    
    # Store in appropriate location
    if component_type == "accommodation":
        components["accommodation"] = component_data
        logger.debug(f"Registered accommodation component: {component_id}")
    
    elif component_type == "transport":
        components["transport"] = component_data
        logger.debug(f"Registered transport component: {component_id}")
    
    elif day_number is not None:
        # Part of daily schedule
        day_key = f"day{day_number}"
        if day_key not in components["days"]:
            components["days"][day_key] = {}
        
        if time_slot:
            slot_key = f"{time_slot}_slot"
            components["days"][day_key][slot_key] = component_data
            logger.debug(f"Registered {component_type} for {day_key}/{time_slot}: {component_id}")
        else:
            # Generic day-level component
            if "components" not in components["days"][day_key]:
                components["days"][day_key]["components"] = []
            components["days"][day_key]["components"].append(component_data)
            logger.debug(f"Registered {component_type} for {day_key}: {component_id}")
    
    return component_id


# ======================== Component Retrieval ========================

def get_component(state: Dict[str, Any], component_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a component by its ID.
    
    Args:
        state: GraphState dictionary
        component_id: Unique component identifier
    
    Returns:
        Component data dictionary or None if not found
    """
    components = state.get("itinerary_components", {})
    
    # Check accommodation
    if components.get("accommodation", {}).get("component_id") == component_id:
        return components["accommodation"]
    
    # Check transport
    if components.get("transport", {}).get("component_id") == component_id:
        return components["transport"]
    
    # Check daily schedule
    for day_key, day_data in components.get("days", {}).items():
        # Check time slots
        for slot_key, slot_data in day_data.items():
            if isinstance(slot_data, dict) and slot_data.get("component_id") == component_id:
                return slot_data
            
            # Check component lists
            if slot_key == "components" and isinstance(slot_data, list):
                for comp in slot_data:
                    if isinstance(comp, dict) and comp.get("component_id") == component_id:
                        return comp
    
    logger.debug(f"Component not found: {component_id}")
    return None


def get_component_path(state: Dict[str, Any], component_id: str) -> Optional[List[str]]:
    """
    Get the path to a component in the state structure.
    
    Args:
        state: GraphState dictionary
        component_id: Unique component identifier
    
    Returns:
        List of keys representing the path, or None if not found
        Example: ["itinerary_components", "days", "day1", "morning_slot"]
    """
    components = state.get("itinerary_components", {})
    
    # Check accommodation
    if components.get("accommodation", {}).get("component_id") == component_id:
        return ["itinerary_components", "accommodation"]
    
    # Check transport
    if components.get("transport", {}).get("component_id") == component_id:
        return ["itinerary_components", "transport"]
    
    # Check daily schedule
    for day_key, day_data in components.get("days", {}).items():
        for slot_key, slot_data in day_data.items():
            if isinstance(slot_data, dict) and slot_data.get("component_id") == component_id:
                return ["itinerary_components", "days", day_key, slot_key]
            
            # Check component lists
            if slot_key == "components" and isinstance(slot_data, list):
                for idx, comp in enumerate(slot_data):
                    if isinstance(comp, dict) and comp.get("component_id") == component_id:
                        return ["itinerary_components", "days", day_key, slot_key, str(idx)]
    
    return None


# ======================== Natural Language Resolution ========================

def find_component(state: Dict[str, Any], reference: str, 
                  context_day: Optional[int] = None) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Resolve natural language reference to a component.
    
    Examples:
        - "Day 2 dinner" -> finds day2_evening_restaurant component
        - "the hotel" -> finds accommodation component
        - "morning activity" -> finds current/context day morning activity
        - "lunch" -> finds lunch/midday restaurant
    
    Args:
        state: GraphState dictionary
        reference: Natural language reference
        context_day: Current context day number for implicit references
    
    Returns:
        Tuple of (component_id, component_data) or (None, None) if not found
    """
    ref_lower = reference.lower().strip()
    components = state.get("itinerary_components", {})
    
    # ===== Accommodation references =====
    if any(word in ref_lower for word in ["hotel", "accommodation", "lodging", "stay", "where we're staying"]):
        acc = components.get("accommodation")
        if acc:
            return acc.get("component_id"), acc
    
    # ===== Transport references =====
    if any(word in ref_lower for word in ["transport", "travel", "getting there", "drive", "flight"]):
        trans = components.get("transport")
        if trans:
            return trans.get("component_id"), trans
    
    # ===== Day-specific references =====
    # Extract day number from reference
    import re
    day_match = re.search(r'\bday\s*(\d+)\b', ref_lower)
    target_day = None
    
    if day_match:
        target_day = int(day_match.group(1))
    elif context_day is not None:
        target_day = context_day
    
    if target_day is not None:
        day_key = f"day{target_day}"
        day_data = components.get("days", {}).get(day_key, {})
        
        # Determine time slot from reference
        time_slot = None
        if any(word in ref_lower for word in ["morning", "breakfast", "am"]):
            time_slot = "morning"
        elif any(word in ref_lower for word in ["afternoon", "lunch", "midday", "noon"]):
            time_slot = "afternoon"
        elif any(word in ref_lower for word in ["evening", "dinner", "night", "pm"]):
            time_slot = "evening"
        
        if time_slot:
            slot_key = f"{time_slot}_slot"
            slot_data = day_data.get(slot_key)
            if isinstance(slot_data, dict):
                # Further filter by component type
                comp_type = slot_data.get("component_type", "")
                
                # Restaurant/dining references
                if any(word in ref_lower for word in ["restaurant", "dinner", "lunch", "breakfast", "meal", "eat"]):
                    if "restaurant" in comp_type or "dining" in comp_type:
                        return slot_data.get("component_id"), slot_data
                
                # Activity references
                elif any(word in ref_lower for word in ["activity", "attraction", "visit", "do", "see"]):
                    if "activity" in comp_type or "attraction" in comp_type:
                        return slot_data.get("component_id"), slot_data
                
                # Generic - return whatever is in that slot
                else:
                    return slot_data.get("component_id"), slot_data
    
    # ===== Fuzzy matching by name =====
    # If nothing found yet, search by name similarity
    all_components = _collect_all_components(components)
    for comp_id, comp_data in all_components:
        comp_name = (comp_data.get("name") or "").lower()
        if ref_lower in comp_name or comp_name in ref_lower:
            return comp_id, comp_data
    
    logger.debug(f"Could not resolve component reference: '{reference}'")
    return None, None


def _collect_all_components(components: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Helper to flatten all components for searching."""
    result = []
    
    # Accommodation
    if components.get("accommodation"):
        acc = components["accommodation"]
        result.append((acc.get("component_id"), acc))
    
    # Transport
    if components.get("transport"):
        trans = components["transport"]
        result.append((trans.get("component_id"), trans))
    
    # Days
    for day_data in components.get("days", {}).values():
        for slot_data in day_data.values():
            if isinstance(slot_data, dict) and "component_id" in slot_data:
                result.append((slot_data["component_id"], slot_data))
            elif isinstance(slot_data, list):
                for comp in slot_data:
                    if isinstance(comp, dict) and "component_id" in comp:
                        result.append((comp["component_id"], comp))
    
    return result


# ======================== Component Listing ========================

def list_components_by_type(state: Dict[str, Any], component_type: str) -> List[Dict[str, Any]]:
    """
    Get all components of a specific type.
    
    Args:
        state: GraphState dictionary
        component_type: Type to filter by (activity, restaurant, etc.)
    
    Returns:
        List of matching components
    """
    components = state.get("itinerary_components", {})
    results = []
    
    for comp_id, comp_data in _collect_all_components(components):
        if comp_data.get("component_type") == component_type:
            results.append(comp_data)
    
    return results


def list_components_by_day(state: Dict[str, Any], day_number: int) -> Dict[str, Any]:
    """
    Get all components for a specific day.
    
    Args:
        state: GraphState dictionary
        day_number: Day number
    
    Returns:
        Dictionary with time slots and their components
    """
    components = state.get("itinerary_components", {})
    day_key = f"day{day_number}"
    return components.get("days", {}).get(day_key, {})


# ======================== Component Updates ========================

def update_component(state: Dict[str, Any], component_id: str, 
                    updates: Dict[str, Any]) -> bool:
    """
    Update a component's data.
    
    Args:
        state: GraphState dictionary
        component_id: Component to update
        updates: Dictionary of fields to update
    
    Returns:
        True if successful, False if component not found
    """
    component = get_component(state, component_id)
    if not component:
        logger.warning(f"Cannot update non-existent component: {component_id}")
        return False
    
    # Update fields
    component.update(updates)
    component["last_modified"] = datetime.now().isoformat()
    
    logger.debug(f"Updated component {component_id}: {list(updates.keys())}")
    return True


def delete_component(state: Dict[str, Any], component_id: str) -> bool:
    """
    Remove a component from the itinerary.
    
    Args:
        state: GraphState dictionary
        component_id: Component to delete
    
    Returns:
        True if successful, False if component not found
    """
    path = get_component_path(state, component_id)
    if not path:
        logger.warning(f"Cannot delete non-existent component: {component_id}")
        return False
    
    # Navigate to parent and delete
    current = state
    for key in path[:-1]:
        if isinstance(current, list):
            current = current[int(key)]
        else:
            current = current[key]
    
    last_key = path[-1]
    if isinstance(current, list):
        del current[int(last_key)]
    else:
        del current[last_key]
    
    logger.debug(f"Deleted component: {component_id}")
    return True