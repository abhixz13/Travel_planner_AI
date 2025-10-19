"""
Interactive selection widgets for hotels and activities.
Allows users to refine their itinerary choices.
"""

import streamlit as st
from typing import Dict, Any, List


def render_hotel_selector(itinerary: Dict[str, Any]):
    """
    Render hotel selection widget with visual cards.

    Args:
        itinerary: Current itinerary data
    """
    hotels = itinerary.get("accommodation_options", [])
    if not hotels:
        return

    st.markdown("Choose your preferred accommodation:")

    # Create radio buttons with custom styling
    selected_hotel = st.radio(
        "Select Hotel",
        options=range(len(hotels)),
        format_func=lambda i: f"{hotels[i].get('name', 'Hotel')} - ${hotels[i].get('price_per_night', 0)}/night",
        key="hotel_selection",
        label_visibility="collapsed"
    )

    # Show detailed card for selected hotel
    if selected_hotel is not None:
        hotel = hotels[selected_hotel]

        with st.container():
            cols = st.columns([2, 1])

            with cols[0]:
                st.markdown(f"### ✓ {hotel.get('name', 'Selected Hotel')}")
                st.markdown(f"📍 **Location:** {hotel.get('location', 'N/A')}")
                st.markdown(hotel.get("description", ""))

                if hotel.get("features"):
                    st.markdown("**Amenities:**")
                    feature_cols = st.columns(2)
                    for idx, feature in enumerate(hotel["features"]):
                        with feature_cols[idx % 2]:
                            st.markdown(f"✓ {feature}")

            with cols[1]:
                st.metric("Price per Night", f"${hotel.get('price_per_night', 0)}")

                if hotel.get("booking_url"):
                    st.link_button("Book Now", hotel["booking_url"], use_container_width=True)

        # Confirm selection button
        if st.button("✓ Confirm This Hotel", key="confirm_hotel", use_container_width=True, type="primary"):
            if st.session_state.get("conversation_id"):
                handle_hotel_confirmation(selected_hotel + 1)  # 1-indexed
            else:
                st.warning("Please start a conversation first")


def handle_hotel_confirmation(hotel_index: int):
    """
    Handle hotel selection confirmation.

    Args:
        hotel_index: Selected hotel index (1-indexed)
    """
    client = st.session_state.get("client")
    conversation_id = st.session_state.get("conversation_id")

    if not client or not conversation_id:
        st.error("Unable to confirm selection")
        return

    with st.spinner("Confirming your selection..."):
        response = client.select_hotel(conversation_id, hotel_index)

        if "error" not in response:
            st.success(f"✓ Hotel {hotel_index} confirmed!")
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.get("message", "Hotel selection confirmed!"),
            })
            st.rerun()
        else:
            st.error(response.get("message", "Failed to confirm selection"))


def render_activity_swapper(itinerary: Dict[str, Any]):
    """
    Render activity swapping widget for customization.

    Args:
        itinerary: Current itinerary data
    """
    days = itinerary.get("days", [])
    if not days:
        return

    st.markdown("Don't like an activity? Swap it for something else!")

    # Create a selectbox for day and time slot
    cols = st.columns([2, 2, 3])

    with cols[0]:
        selected_day = st.selectbox(
            "Day",
            options=range(len(days)),
            format_func=lambda i: f"Day {days[i].get('day_number', i+1)}",
            key="swap_day_select"
        )

    with cols[1]:
        time_slots = ["morning", "afternoon", "evening"]
        selected_slot = st.selectbox(
            "Time Slot",
            options=time_slots,
            format_func=lambda s: s.title(),
            key="swap_slot_select"
        )

    with cols[2]:
        swap_reason = st.text_input(
            "Why swap? (optional)",
            placeholder="e.g., prefer outdoor activities",
            key="swap_reason"
        )

    # Show current activity
    if selected_day is not None and selected_slot:
        day_data = days[selected_day]
        slot_data = day_data.get(selected_slot, {})
        current_activity = slot_data.get("activity")

        if current_activity:
            with st.expander("Current Activity", expanded=True):
                st.markdown(f"**{current_activity.get('name', 'Unknown')}**")
                st.caption(f"{current_activity.get('type', '')} • {current_activity.get('duration_minutes', 0)} min")
                st.markdown(current_activity.get("description", ""))

            # Swap button
            if st.button("🔄 Swap This Activity", key="swap_activity_btn", use_container_width=True):
                handle_activity_swap(
                    day_data.get("day_number", selected_day + 1),
                    selected_slot,
                    swap_reason if swap_reason else None
                )
        else:
            st.info("This time slot has a restaurant, not an activity")


def handle_activity_swap(day_number: int, time_slot: str, reason: str = None):
    """
    Handle activity swap request.

    Args:
        day_number: Day number (1-indexed)
        time_slot: Time slot name
        reason: Optional reason for swapping
    """
    client = st.session_state.get("client")
    conversation_id = st.session_state.get("conversation_id")

    if not client or not conversation_id:
        st.error("Unable to swap activity")
        return

    with st.spinner("Finding a better activity..."):
        response = client.swap_activity(
            conversation_id,
            day_number,
            time_slot,
            reason
        )

        if "error" not in response:
            st.success("✓ Activity swapped!")
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.get("message", "I've updated the activity for you!"),
            })

            # Update itinerary if provided
            if "itinerary" in response:
                st.session_state.current_itinerary = response["itinerary"]

            st.rerun()
        else:
            st.error(response.get("message", "Failed to swap activity"))


def render_feedback_widget():
    """Render feedback widget for the itinerary."""
    st.markdown("---")
    st.markdown("### 📝 How's your itinerary?")

    cols = st.columns(4)

    feedback_options = {
        "perfect": ("🎉", "Perfect!"),
        "good": ("👍", "Good"),
        "okay": ("👌", "Okay"),
        "needs_work": ("🤔", "Needs work")
    }

    for idx, (key, (emoji, label)) in enumerate(feedback_options.items()):
        with cols[idx]:
            if st.button(f"{emoji}\n{label}", key=f"feedback_{key}", use_container_width=True):
                st.session_state.feedback = key
                st.toast(f"Thanks for your feedback! {emoji}")

    # Additional comments
    if st.session_state.get("feedback"):
        comments = st.text_area(
            "Any specific feedback?",
            placeholder="Tell us what you'd like to change...",
            key="feedback_comments"
        )

        if comments and st.button("Submit Feedback", type="primary"):
            st.success("Feedback submitted! Thank you!")
            st.session_state.feedback_comments = comments
