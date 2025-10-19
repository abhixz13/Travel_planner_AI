# Travel Planner Streamlit UI

A dynamic, user-intuitive frontend for the AI-powered Travel Planner. Built with Streamlit for a modern, interactive user experience.

## Features

### Core Functionality
- **Interactive Chat Interface**: Natural conversation flow with the AI travel planner
- **Real-time Itinerary Display**: Beautiful, card-based itinerary visualization
- **Hotel Selection**: Choose from 3 curated accommodation options
- **Activity Customization**: Swap activities to match your preferences
- **Progress Indicators**: Visual feedback during planning stages
- **Responsive Design**: Works seamlessly on desktop and mobile devices

### User Experience
- **Dynamic Animations**: Smooth transitions and engaging visual effects
- **Custom Styling**: Modern gradient themes and polished UI components
- **Loading States**: Clear feedback during backend processing
- **Error Handling**: Graceful error messages with retry options
- **Sidebar Overview**: Quick access to trip details and controls

## Project Structure

```
streamlit_UI/
├── app.py                          # Main application entry point
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── components/                     # Reusable UI components
│   ├── __init__.py
│   ├── chat_message.py            # Chat message rendering
│   ├── itinerary_display.py       # Itinerary visualization
│   ├── selection_widgets.py       # Hotel/activity selectors
│   └── progress_indicators.py     # Loading and progress states
├── utils/                         # Utility modules
│   ├── __init__.py
│   └── api_client.py              # Backend API communication
└── assets/                        # Static assets
    └── style.css                  # Custom CSS styling
```

## Setup Instructions

### Prerequisites
- Python 3.9 or higher
- Docker (for backend)
- Backend Travel Planner API running on `localhost:8000`

### Installation

1. **Navigate to the Streamlit UI directory**:
   ```bash
   cd streamlit_UI
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure backend URL** (optional):
   ```bash
   export TRAVEL_PLANNER_API_URL="http://localhost:8000"
   ```
   Default is `http://localhost:8000` if not set.

### Running the Application

1. **Start the backend** (in Docker):
   ```bash
   # From project root
   docker-compose up
   ```

2. **Run Streamlit**:

   **Option A - Using the launcher script (recommended):**
   ```bash
   # From project root
   python3 run_ui.py
   ```

   **Option B - Direct streamlit command:**
   ```bash
   # From streamlit_UI directory
   cd streamlit_UI
   streamlit run app.py
   ```

3. **Open browser**:
   Navigate to `http://localhost:8501`

## Usage Guide

### Starting a Trip

1. **Initial Conversation**: Tell the AI about your trip
   ```
   "I want to plan a 3-day family trip to San Juan Islands"
   ```

2. **Provide Details**: Answer follow-up questions
   - Origin location
   - Travel dates
   - Number of travelers
   - Preferences

3. **View Destinations**: Review suggested destinations and select one

4. **Get Itinerary**: Receive a complete day-by-day itinerary

### Customizing Your Itinerary

#### Selecting a Hotel
1. View the 3 hotel options in the "Accommodation Options" section
2. Use the radio buttons to select your preferred hotel
3. Click "Confirm This Hotel" to lock in your choice

#### Swapping Activities
1. Navigate to "Customize Activities" section
2. Select the day and time slot you want to change
3. Optionally provide a reason (e.g., "prefer outdoor activities")
4. Click "Swap This Activity"
5. View the updated activity

### Chat Features

The chat interface supports:
- **Multi-turn conversations**: Context is maintained throughout
- **Natural language**: Ask questions in plain English
- **Refinement requests**: "Make it more budget-friendly"
- **Specific changes**: "Change Day 2 afternoon to something indoors"

## Components Reference

### Chat Message Component
Renders messages with role-based styling and metadata display.

```python
from streamlit_UI.components import render_message

message = {
    "role": "assistant",
    "content": "Here are some destinations...",
    "metadata": {"destinations": [...]}
}
render_message(message)
```

### Itinerary Display Component
Renders complete itinerary with interactive cards.

```python
from streamlit_UI.components import render_itinerary_card

itinerary = {
    "metadata": {...},
    "accommodation_options": [...],
    "days": [...],
    "pro_tips": [...]
}
render_itinerary_card(itinerary)
```

### Selection Widgets
Hotel and activity selection interfaces.

```python
from streamlit_UI.components import render_hotel_selector, render_activity_swapper

render_hotel_selector(itinerary)
render_activity_swapper(itinerary)
```

### Progress Indicators
Visual feedback for loading states.

```python
from streamlit_UI.components import show_planning_progress, show_typing_indicator

stages = ["Searching", "Analyzing", "Planning", "Finalizing"]
show_planning_progress(stages, current_stage=1)
```

## API Client

The `TravelPlannerClient` handles all backend communication.

### Sending Messages
```python
from streamlit_UI.utils import TravelPlannerClient

client = TravelPlannerClient()
response = client.send_message(
    message="I want to visit San Diego",
    conversation_id=None
)
```

### Selecting Hotels
```python
response = client.select_hotel(
    conversation_id="abc123",
    hotel_index=2  # 1-indexed
)
```

### Swapping Activities
```python
response = client.swap_activity(
    conversation_id="abc123",
    day_number=2,
    time_slot="afternoon",
    reason="prefer outdoor activities"
)
```

## Styling and Theming

Custom styles are defined in `assets/style.css` with:
- **CSS Variables**: Easy theme customization
- **Animations**: Fade-in, slide, bounce effects
- **Responsive Design**: Mobile-friendly breakpoints
- **Custom Scrollbars**: Themed scroll elements
- **Gradient Themes**: Modern color schemes

### Customizing Colors
Edit `assets/style.css`:
```css
:root {
    --primary-color: #4A90E2;      /* Blue */
    --secondary-color: #50C878;    /* Green */
    --accent-color: #FF6B6B;       /* Red */
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAVEL_PLANNER_API_URL` | `http://localhost:8000` | Backend API endpoint |

## Troubleshooting

### Cannot Connect to Backend
**Error**: "Cannot connect to the backend. Please ensure Docker is running."

**Solutions**:
1. Verify Docker is running: `docker ps`
2. Check backend is healthy: `curl http://localhost:8000/health`
3. Verify correct API URL in environment

### Import Errors
**Error**: `ModuleNotFoundError: No module named 'streamlit_UI'`

**Solution**:
```bash
# Ensure parent directory is in Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/Travel_Planner_ai"
```

### Styling Not Applied
**Solution**:
1. Check `assets/style.css` exists
2. Verify file path in `app.py`
3. Clear browser cache and reload

## Development

### Adding New Components

1. Create component file in `components/`:
   ```python
   # components/my_component.py
   import streamlit as st

   def render_my_component(data):
       st.markdown("My Component")
   ```

2. Update `components/__init__.py`:
   ```python
   from .my_component import render_my_component
   __all__ = [..., "render_my_component"]
   ```

3. Use in `app.py`:
   ```python
   from streamlit_UI.components import render_my_component
   ```

### Testing

Run Streamlit in debug mode:
```bash
streamlit run app.py --logger.level=debug
```

## Performance Tips

1. **Session State**: Use `st.session_state` to avoid recomputation
2. **Caching**: Use `@st.cache_data` for expensive operations
3. **Lazy Loading**: Load components only when needed
4. **Debouncing**: Add delays to prevent excessive API calls

## Contributing

When adding features:
1. Follow existing code structure
2. Add docstrings to all functions
3. Update this README
4. Test on different screen sizes
5. Ensure Docker backend compatibility

## License

Part of the Travel Planner AI project.

## Support

For issues related to:
- **UI bugs**: Check browser console for errors
- **Backend connectivity**: Verify Docker and API health
- **Feature requests**: Document use case and benefits
