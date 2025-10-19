"""
Streamlit Travel Planner UI
Dynamic chat interface for planning family trips with AI assistance.
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.api_client import TravelPlannerClient
from components.chat_message import render_message
from components.itinerary_display import render_itinerary_card
from components.selection_widgets import render_hotel_selector, render_activity_swapper

# Page configuration
st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
css_file = Path(__file__).parent / "assets" / "style.css"
if css_file.exists():
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None

    if "client" not in st.session_state:
        st.session_state.client = TravelPlannerClient()

    if "current_itinerary" not in st.session_state:
        st.session_state.current_itinerary = None

    if "processing" not in st.session_state:
        st.session_state.processing = False


def render_sidebar():
    """Render sidebar with trip information and controls."""
    with st.sidebar:
        st.title("✈️ AI Travel Planner")
        st.markdown("---")

        # Trip status
        if st.session_state.current_itinerary:
            st.success("Itinerary Ready!")

            metadata = st.session_state.current_itinerary.get("metadata", {})

            with st.expander("Trip Overview", expanded=True):
                st.write(f"**Destination:** {metadata.get('destination', 'N/A')}")
                st.write(f"**From:** {metadata.get('origin', 'N/A')}")
                st.write(f"**Duration:** {metadata.get('duration_days', 'N/A')} days")
                st.write(f"**Dates:** {metadata.get('departure_date', 'N/A')} to {metadata.get('return_date', 'N/A')}")
                st.write(f"**Travel Party:** {metadata.get('travel_pack', 'N/A').title()}")
        else:
            st.info("Start a conversation to plan your trip")

        st.markdown("---")

        # New conversation button
        if st.button("🔄 Start New Trip", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.session_state.current_itinerary = None
            st.rerun()

        st.markdown("---")
        st.caption("Powered by GPT-4 and LangGraph")


def render_chat_interface():
    """Render main chat interface."""
    st.title("Plan Your Perfect Family Trip")

    # Display chat messages
    chat_container = st.container()

    with chat_container:
        for message in st.session_state.messages:
            render_message(message)

    # Show itinerary if available
    if st.session_state.current_itinerary:
        st.markdown("---")
        render_itinerary_card(st.session_state.current_itinerary)

        # Hotel selection widget
        st.markdown("### 🏨 Choose Your Accommodation")
        render_hotel_selector(st.session_state.current_itinerary)

        # Activity swapping widget
        st.markdown("### 🎯 Customize Activities")
        render_activity_swapper(st.session_state.current_itinerary)

    # Processing indicator
    if st.session_state.processing:
        with st.spinner("Planning your perfect trip..."):
            st.empty()


def handle_user_input(user_message: str):
    """Process user input and get AI response."""
    # Add user message to chat
    st.session_state.messages.append({
        "role": "user",
        "content": user_message
    })

    # Set processing flag
    st.session_state.processing = True

    try:
        # Send to backend
        response = st.session_state.client.send_message(
            message=user_message,
            conversation_id=st.session_state.conversation_id
        )

        # Update conversation ID
        if "conversation_id" in response:
            st.session_state.conversation_id = response["conversation_id"]

        # Add AI response to chat
        st.session_state.messages.append({
            "role": "assistant",
            "content": response.get("message", ""),
            "metadata": response.get("metadata", {})
        })

        # Update itinerary if present
        if "itinerary" in response:
            st.session_state.current_itinerary = response["itinerary"]

    except Exception as e:
        st.error(f"Error communicating with backend: {str(e)}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": "I'm having trouble connecting to the planning service. Please try again.",
            "error": True
        })

    finally:
        st.session_state.processing = False


def main():
    """Main application entry point."""
    initialize_session_state()
    render_sidebar()
    render_chat_interface()

    # Chat input at the bottom
    if prompt := st.chat_input("Tell me about your dream trip...", key="chat_input"):
        handle_user_input(prompt)
        st.rerun()


if __name__ == "__main__":
    main()
