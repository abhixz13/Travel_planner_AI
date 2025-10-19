"""
Itinerary display component with interactive cards and animations.
"""

import streamlit as st
from typing import Dict, Any, List


def render_itinerary_card(itinerary: Dict[str, Any]):
    """
    Render the full itinerary in an attractive card layout.

    Args:
        itinerary: Structured itinerary data
    """
    if not itinerary:
        return

    metadata = itinerary.get("metadata", {})

    # Header section
    st.markdown(f"""
    <div class="itinerary-header">
        <h1>🗺️ Your {metadata.get('destination', 'Trip')} Adventure</h1>
        <p class="subtitle">{metadata.get('departure_date', '')} to {metadata.get('return_date', '')}</p>
    </div>
    """, unsafe_allow_html=True)

    # Transportation section
    if "transport" in itinerary:
        render_transport_section(itinerary["transport"])

    # Hotels section
    if "accommodation_options" in itinerary:
        render_hotels_section(itinerary["accommodation_options"])

    # Day-by-day itinerary
    if "days" in itinerary:
        render_days_section(itinerary["days"])

    # Pro tips section
    if "pro_tips" in itinerary:
        render_pro_tips(itinerary["pro_tips"])


def render_transport_section(transport: Dict[str, Any]):
    """Render transportation details."""
    with st.expander("🚗 How to Get There", expanded=True):
        cols = st.columns([1, 2])

        with cols[0]:
            mode_emoji = {
                "driving": "🚗",
                "flying": "✈️",
                "train": "🚄",
                "bus": "🚌"
            }
            emoji = mode_emoji.get(transport.get("mode", ""), "🚗")
            st.markdown(f"### {emoji} {transport.get('mode', 'Unknown').title()}")

            if transport.get("duration_minutes"):
                hours = transport["duration_minutes"] // 60
                minutes = transport["duration_minutes"] % 60
                st.metric("Duration", f"{hours}h {minutes}m")

            if transport.get("estimated_cost"):
                st.metric("Est. Cost", f"${transport['estimated_cost']}")

        with cols[1]:
            st.markdown(transport.get("description", ""))

            if transport.get("recommendations"):
                st.markdown("**Travel Tips:**")
                for tip in transport["recommendations"]:
                    st.markdown(f"- {tip}")


def render_hotels_section(hotels: List[Dict[str, Any]]):
    """Render hotel options in cards."""
    st.markdown("### 🏨 Accommodation Options")

    cols = st.columns(3)

    for idx, hotel in enumerate(hotels[:3]):
        with cols[idx]:
            with st.container():
                st.markdown(f"""
                <div class="hotel-card">
                    <h4>{idx + 1}. {hotel.get('name', 'Hotel')}</h4>
                    <p class="price">${hotel.get('price_per_night', 0)}/night</p>
                    <p class="location">📍 {hotel.get('location', 'Unknown')}</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(hotel.get("description", ""))

                if hotel.get("features"):
                    st.markdown("**Features:**")
                    for feature in hotel["features"][:3]:
                        st.markdown(f"✓ {feature}")

                if hotel.get("booking_url"):
                    st.link_button("View Details", hotel["booking_url"], use_container_width=True)


def render_days_section(days: List[Dict[str, Any]]):
    """Render day-by-day itinerary."""
    st.markdown("---")
    st.markdown("### 📅 Day-by-Day Itinerary")

    for day in days:
        day_num = day.get("day_number", 1)
        theme = day.get("theme", "Exploration")

        with st.expander(f"**Day {day_num}: {theme}**", expanded=False):
            # Morning slot
            if "morning" in day:
                render_time_slot("morning", day["morning"], "🌅")

            # Afternoon slot
            if "afternoon" in day:
                render_time_slot("afternoon", day["afternoon"], "☀️")

            # Evening slot
            if "evening" in day:
                render_time_slot("evening", day["evening"], "🌆")


def render_time_slot(slot_name: str, slot_data: Dict[str, Any], emoji: str):
    """Render a single time slot (morning/afternoon/evening)."""
    st.markdown(f"#### {emoji} {slot_name.title()} ({slot_data.get('time_range', 'N/A')})")

    # Activity
    if slot_data.get("activity"):
        activity = slot_data["activity"]

        cols = st.columns([3, 1])
        with cols[0]:
            st.markdown(f"**🎯 {activity.get('name', 'Activity')}**")
            st.caption(f"⏱️ {activity.get('time_start', '')} • {activity.get('duration_minutes', 0)} minutes")

        with cols[1]:
            if activity.get("cost_adult") is not None:
                st.metric("Adult", f"${activity['cost_adult']}")
            if activity.get("cost_child") is not None:
                st.metric("Child", f"${activity['cost_child']}")

        st.markdown(activity.get("description", ""))

        if activity.get("tips"):
            with st.container():
                st.markdown("**Tips:**")
                for tip in activity["tips"]:
                    st.markdown(f"💡 {tip}")

        # Toddler-friendly badge
        if activity.get("toddler_friendly"):
            st.success("👶 Toddler-Friendly")

    # Restaurant
    if slot_data.get("restaurant"):
        restaurant = slot_data["restaurant"]

        cols = st.columns([3, 1])
        with cols[0]:
            st.markdown(f"**🍽️ {restaurant.get('name', 'Restaurant')}**")
            st.caption(f"🕐 {restaurant.get('time', '')} • {restaurant.get('cuisine', '')} • {restaurant.get('price_range', '')}")

        with cols[1]:
            if restaurant.get("average_cost_per_person"):
                st.metric("Per Person", f"${restaurant['average_cost_per_person']}")

        st.markdown(restaurant.get("description", ""))

        if restaurant.get("toddler_friendly_features"):
            st.markdown("**Family Features:**")
            for feature in restaurant["toddler_friendly_features"]:
                st.markdown(f"✓ {feature}")

    st.markdown("---")


def render_pro_tips(tips: List[str]):
    """Render pro tips section."""
    if not tips:
        return

    with st.expander("💡 Pro Tips for Your Trip", expanded=False):
        for idx, tip in enumerate(tips, 1):
            st.markdown(f"{idx}. {tip}")
