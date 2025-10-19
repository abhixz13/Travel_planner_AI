"""
Progress indicators and loading states for dynamic user feedback.
"""

import streamlit as st
import time
from typing import List, Optional


def show_planning_progress(stages: List[str], current_stage: int = 0):
    """
    Show multi-stage planning progress with animated indicators.

    Args:
        stages: List of stage names
        current_stage: Current stage index (0-based)
    """
    st.markdown("### Planning Your Trip")

    # Create progress bar
    progress = (current_stage + 1) / len(stages)
    progress_bar = st.progress(progress)

    # Show stages with checkmarks
    for idx, stage in enumerate(stages):
        cols = st.columns([1, 10])

        with cols[0]:
            if idx < current_stage:
                st.markdown("✅")
            elif idx == current_stage:
                st.markdown("⏳")
            else:
                st.markdown("⭕")

        with cols[1]:
            if idx == current_stage:
                st.markdown(f"**{stage}**")
            else:
                st.markdown(stage)

    return progress_bar


def animated_thinking_indicator(message: str = "Thinking..."):
    """
    Show animated thinking indicator.

    Args:
        message: Message to display
    """
    placeholder = st.empty()

    dots = ["", ".", "..", "..."]
    for i in range(12):  # 3 seconds total
        placeholder.markdown(f"🤔 {message}{dots[i % 4]}")
        time.sleep(0.25)

    placeholder.empty()


def show_search_status(status: str, destinations_found: int = 0):
    """
    Show destination search status.

    Args:
        status: Current search status
        destinations_found: Number of destinations found
    """
    status_icons = {
        "searching": "🔍",
        "analyzing": "🧠",
        "ranking": "📊",
        "complete": "✅"
    }

    icon = status_icons.get(status, "⏳")

    cols = st.columns([1, 4])
    with cols[0]:
        st.markdown(f"## {icon}")

    with cols[1]:
        st.markdown(f"**{status.title()}**")
        if destinations_found > 0:
            st.caption(f"{destinations_found} destinations analyzed")


def show_itinerary_generation_steps():
    """
    Show step-by-step itinerary generation progress.
    """
    steps = [
        ("📍", "Researching destination"),
        ("🏨", "Finding accommodations"),
        ("🗺️", "Planning daily activities"),
        ("🍽️", "Selecting restaurants"),
        ("✨", "Adding final touches")
    ]

    st.markdown("### Creating Your Itinerary")

    progress_container = st.container()

    with progress_container:
        for idx, (icon, step) in enumerate(steps):
            with st.spinner(f"{icon} {step}..."):
                time.sleep(0.5)  # Simulate work
                st.success(f"✓ {step}")


def show_streaming_status(text: str, complete: bool = False):
    """
    Show streaming text status for real-time updates.

    Args:
        text: Status text
        complete: Whether the status is complete
    """
    if complete:
        st.success(f"✓ {text}")
    else:
        st.info(f"⏳ {text}")


def show_component_loading(component_name: str):
    """
    Show loading state for a specific component.

    Args:
        component_name: Name of the component being loaded
    """
    with st.spinner(f"Loading {component_name}..."):
        placeholder = st.empty()
        placeholder.markdown(f"""
        <div style="text-align: center; padding: 2rem;">
            <div class="pulse">
                Loading {component_name}...
            </div>
        </div>
        """, unsafe_allow_html=True)

        return placeholder


def show_error_state(error_message: str, retry_callback=None):
    """
    Show error state with optional retry button.

    Args:
        error_message: Error message to display
        retry_callback: Optional callback function for retry button
    """
    st.error(f"❌ {error_message}")

    if retry_callback:
        if st.button("🔄 Retry", key="retry_error"):
            retry_callback()


def show_success_animation(message: str):
    """
    Show success message with animation.

    Args:
        message: Success message
    """
    placeholder = st.empty()

    # Show animated checkmark
    placeholder.markdown(f"""
    <div style="text-align: center; padding: 2rem;">
        <div class="bounce" style="font-size: 3rem;">
            ✅
        </div>
        <h3>{message}</h3>
    </div>
    """, unsafe_allow_html=True)

    time.sleep(2)
    placeholder.empty()


def show_typing_indicator():
    """Show typing indicator for AI response."""
    placeholder = st.empty()

    typing_dots = st.markdown("""
    <div style="padding: 1rem;">
        <span class="typing-dot" style="animation: pulse 1.4s infinite;">●</span>
        <span class="typing-dot" style="animation: pulse 1.4s infinite 0.2s;">●</span>
        <span class="typing-dot" style="animation: pulse 1.4s infinite 0.4s;">●</span>
    </div>
    """, unsafe_allow_html=True)

    return placeholder


def show_percentage_progress(current: int, total: int, label: str = "Progress"):
    """
    Show percentage-based progress.

    Args:
        current: Current progress value
        total: Total value
        label: Progress label
    """
    percentage = int((current / total) * 100)

    cols = st.columns([3, 1])

    with cols[0]:
        st.progress(current / total)

    with cols[1]:
        st.metric(label, f"{percentage}%")


def show_stage_indicator(stages: List[str], current: str):
    """
    Show current stage in a multi-stage process.

    Args:
        stages: List of all stages
        current: Current stage name
    """
    current_idx = stages.index(current) if current in stages else 0

    cols = st.columns(len(stages))

    for idx, stage in enumerate(stages):
        with cols[idx]:
            if idx < current_idx:
                st.markdown(f"✅ **{stage}**")
            elif idx == current_idx:
                st.markdown(f"⏳ **{stage}**")
            else:
                st.markdown(f"⭕ {stage}")
