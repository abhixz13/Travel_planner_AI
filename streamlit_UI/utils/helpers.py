"""
Helper utilities for the Streamlit Travel Planner UI.
"""

import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


def format_date(date_str: str, format_in: str = "%Y-%m-%d", format_out: str = "%B %d, %Y") -> str:
    """
    Format date string from one format to another.

    Args:
        date_str: Input date string
        format_in: Input date format
        format_out: Output date format

    Returns:
        Formatted date string
    """
    try:
        date_obj = datetime.strptime(date_str, format_in)
        return date_obj.strftime(format_out)
    except (ValueError, TypeError):
        return date_str


def calculate_total_cost(itinerary: Dict[str, Any], hotel_index: int = 0) -> Dict[str, float]:
    """
    Calculate total estimated cost for the trip.

    Args:
        itinerary: Itinerary data
        hotel_index: Selected hotel index (0-based)

    Returns:
        Dictionary with cost breakdown
    """
    costs = {
        "accommodation": 0.0,
        "activities": 0.0,
        "dining": 0.0,
        "transport": 0.0,
        "total": 0.0
    }

    # Accommodation
    hotels = itinerary.get("accommodation_options", [])
    if hotels and hotel_index < len(hotels):
        hotel = hotels[hotel_index]
        duration = itinerary.get("metadata", {}).get("duration_days", 0)
        costs["accommodation"] = hotel.get("price_per_night", 0) * duration

    # Transport
    transport = itinerary.get("transport", {})
    costs["transport"] = transport.get("estimated_cost", 0) or 0

    # Activities and dining
    for day in itinerary.get("days", []):
        for slot_name in ["morning", "afternoon", "evening"]:
            slot = day.get(slot_name, {})

            # Activity costs
            activity = slot.get("activity")
            if activity:
                costs["activities"] += activity.get("cost_adult", 0) or 0

            # Dining costs
            restaurant = slot.get("restaurant")
            if restaurant:
                costs["dining"] += restaurant.get("average_cost_per_person", 0) or 0

    costs["total"] = sum([
        costs["accommodation"],
        costs["activities"],
        costs["dining"],
        costs["transport"]
    ])

    return costs


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format currency amount.

    Args:
        amount: Amount to format
        currency: Currency code

    Returns:
        Formatted currency string
    """
    if currency == "USD":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def parse_time_range(time_range: str) -> tuple:
    """
    Parse time range string into start and end times.

    Args:
        time_range: Time range string (e.g., "9:00 AM - 12:00 PM")

    Returns:
        Tuple of (start_time, end_time)
    """
    try:
        parts = time_range.split("-")
        if len(parts) == 2:
            start = parts[0].strip()
            end = parts[1].strip()
            return (start, end)
    except Exception:
        pass
    return (time_range, time_range)


def get_activity_icon(activity_type: str) -> str:
    """
    Get emoji icon for activity type.

    Args:
        activity_type: Type of activity

    Returns:
        Emoji icon
    """
    icons = {
        "attraction": "🏛️",
        "outdoor": "🌲",
        "indoor": "🏢",
        "educational": "📚",
        "entertainment": "🎭",
        "beach": "🏖️",
        "museum": "🖼️",
        "park": "🌳",
        "shopping": "🛍️",
        "sports": "⚽"
    }
    return icons.get(activity_type.lower(), "🎯")


def get_meal_icon(meal_type: str) -> str:
    """
    Get emoji icon for meal type.

    Args:
        meal_type: Type of meal

    Returns:
        Emoji icon
    """
    icons = {
        "breakfast": "🥐",
        "lunch": "🍱",
        "dinner": "🍽️",
        "snack": "🍪"
    }
    return icons.get(meal_type.lower(), "🍴")


def get_transport_icon(mode: str) -> str:
    """
    Get emoji icon for transport mode.

    Args:
        mode: Transport mode

    Returns:
        Emoji icon
    """
    icons = {
        "driving": "🚗",
        "flying": "✈️",
        "train": "🚄",
        "bus": "🚌",
        "ferry": "⛴️",
        "walking": "🚶"
    }
    return icons.get(mode.lower(), "🚗")


def format_duration(minutes: int) -> str:
    """
    Format duration in minutes to human-readable string.

    Args:
        minutes: Duration in minutes

    Returns:
        Formatted duration string
    """
    if minutes < 60:
        return f"{minutes} min"

    hours = minutes // 60
    remaining_mins = minutes % 60

    if remaining_mins == 0:
        return f"{hours}h"

    return f"{hours}h {remaining_mins}m"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)].rstrip() + suffix


def is_family_friendly(itinerary: Dict[str, Any]) -> bool:
    """
    Check if itinerary is family-friendly.

    Args:
        itinerary: Itinerary data

    Returns:
        True if family-friendly
    """
    travel_pack = itinerary.get("metadata", {}).get("travel_pack", "")
    return travel_pack.lower() == "family"


def get_session_value(key: str, default: Any = None) -> Any:
    """
    Safely get value from Streamlit session state.

    Args:
        key: Session state key
        default: Default value if key doesn't exist

    Returns:
        Session state value or default
    """
    return st.session_state.get(key, default)


def set_session_value(key: str, value: Any):
    """
    Set value in Streamlit session state.

    Args:
        key: Session state key
        value: Value to set
    """
    st.session_state[key] = value


def clear_session():
    """Clear all session state."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def validate_itinerary(itinerary: Dict[str, Any]) -> tuple:
    """
    Validate itinerary data structure.

    Args:
        itinerary: Itinerary data

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_keys = ["metadata", "accommodation_options", "days"]

    for key in required_keys:
        if key not in itinerary:
            return (False, f"Missing required key: {key}")

    if not itinerary.get("days"):
        return (False, "No days in itinerary")

    if len(itinerary.get("accommodation_options", [])) < 3:
        return (False, "Need at least 3 accommodation options")

    return (True, None)


def format_travel_pack(travel_pack: str) -> str:
    """
    Format travel pack type for display.

    Args:
        travel_pack: Raw travel pack string

    Returns:
        Formatted travel pack string
    """
    formats = {
        "solo": "Solo Traveler",
        "couple": "Couple",
        "family": "Family",
        "friends": "Friends",
        "other": "Group"
    }
    return formats.get(travel_pack.lower(), travel_pack.title())
