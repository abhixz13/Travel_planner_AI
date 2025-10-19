"""
Chat message rendering component with dynamic styling.
"""

import streamlit as st
from typing import Dict, Any


def render_message(message: Dict[str, Any]):
    """
    Render a chat message with role-based styling.

    Args:
        message: Message dict with 'role', 'content', and optional 'metadata'
    """
    role = message.get("role", "assistant")
    content = message.get("content", "")
    metadata = message.get("metadata", {})
    is_error = message.get("error", False)

    # Determine avatar and styling
    if role == "user":
        avatar = "👤"
        message_class = "user-message"
    else:
        avatar = "✈️"
        message_class = "assistant-message"

    # Render using Streamlit's native chat message
    with st.chat_message(role, avatar=avatar):
        if is_error:
            st.error(content)
        else:
            st.markdown(content)

        # Show metadata if present (destinations, extracted info, etc.)
        if metadata:
            render_metadata(metadata)


def render_metadata(metadata: Dict[str, Any]):
    """
    Render metadata in an expandable section.

    Args:
        metadata: Additional information about the message
    """
    if "destinations" in metadata:
        with st.expander("🗺️ Destination Options", expanded=False):
            destinations = metadata["destinations"]
            for idx, dest in enumerate(destinations[:5], 1):
                st.markdown(f"**{idx}. {dest.get('name', 'Unknown')}**")
                st.caption(dest.get('description', ''))
                st.markdown("---")

    if "extracted_info" in metadata:
        with st.expander("📋 Trip Details", expanded=False):
            info = metadata["extracted_info"]
            cols = st.columns(2)

            with cols[0]:
                if "origin" in info:
                    st.metric("From", info["origin"])
                if "destination" in info:
                    st.metric("To", info["destination"])

            with cols[1]:
                if "duration_days" in info:
                    st.metric("Duration", f"{info['duration_days']} days")
                if "travel_pack" in info:
                    st.metric("Party", info["travel_pack"].title())

    if "status" in metadata:
        status = metadata["status"]
        if status == "searching":
            st.info("🔍 Searching for destinations...")
        elif status == "planning":
            st.info("📝 Creating your itinerary...")
        elif status == "refining":
            st.info("✨ Refining your selection...")
