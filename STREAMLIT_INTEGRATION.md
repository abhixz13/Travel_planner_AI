# Streamlit UI Integration Guide

## Overview

Your Streamlit UI is **already integrated** with the backend services, agents, and core components. This guide shows you how to run it.

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│   Streamlit UI      │  HTTP   │   FastAPI Backend    │
│   (Port 8501)       │ ◄─────► │   (Port 8000)        │
│                     │  POST   │                      │
│  - app.py           │  /api/  │  - api_server.py     │
│  - components/      │  chat   │  - core/             │
│  - utils/           │         │  - agents/           │
└─────────────────────┘         └──────────────────────┘
                                          │
                                          ├─► Orchestrator
                                          ├─► Agents (Plan, Refine, etc.)
                                          └─► LLM (OpenAI/Claude)
```

## Quick Start

### Option 1: One-Command Startup (Recommended)

```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai
./start_ui.sh
```

This script automatically:
- ✅ Activates virtual environment
- ✅ Installs dependencies
- ✅ Starts backend API (port 8000)
- ✅ Starts Streamlit UI (port 8501)
- ✅ Opens browser to http://localhost:8501

### Option 2: Manual Startup

**Terminal 1 - Backend:**
```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai
source venv/bin/activate
python api_server.py
```

**Terminal 2 - Streamlit:**
```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai/streamlit_UI
source ../venv/bin/activate
streamlit run app.py
```

## How It Works

### 1. User Interaction Flow

```
User types message in Streamlit
    ↓
streamlit_UI/app.py (handle_user_input)
    ↓
streamlit_UI/utils/api_client.py (send_message)
    ↓
POST http://localhost:8000/api/chat
    ↓
api_server.py (chat endpoint)
    ↓
core/conversation_manager.py (handle_user_input)
    ↓
core/orchestrator.py (run_session)
    ↓
agents/* (clarification, plan, refine, etc.)
    ↓
Response flows back to Streamlit UI
```

### 2. Backend Integration Points

**API Endpoint:** `/api/chat`
- **Request:** `{ "message": "...", "conversation_id": "..." }`
- **Response:** `{ "conversation_id": "...", "message": "...", "itinerary": {...} }`

**Code Location:** `api_server.py:197-260`

```python
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Get/create conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Initialize or retrieve state
    if conversation_id not in conversations:
        state = initiate_conversation(...)
    else:
        state = conversations[conversation_id]

    # Process with core + agents
    state = handle_user_input(state, request.message)
    state = run_session(state)  # ← This runs your agents

    # Return response
    return ChatResponse(
        conversation_id=conversation_id,
        message=last_ai_message,
        itinerary=state.itinerary
    )
```

### 3. Agent Integration

The backend `run_session()` automatically routes through your agents:

1. **Clarification Agent** - Extracts trip details
2. **Travel Options Agent** - Searches destinations
3. **Accommodation Agent** - Finds hotels
4. **Activities Agent** - Plans activities
5. **Plan Composer Agent** - Assembles itinerary
6. **Refinement Agent** - Handles changes

All agent logic in `agents/*.py` is automatically used!

### 4. Streamlit Components

**Chat Interface** (`components/chat_message.py`)
- Displays conversation history
- Shows metadata (destinations, extracted info)
- Error handling

**Itinerary Display** (`components/itinerary_display.py`)
- Day-by-day cards
- Hotel options with pricing
- Activities with timing and costs
- Pro tips section

**Selection Widgets** (`components/selection_widgets.py`)
- Hotel selector with confirmation
- Activity swapper
- Feedback widget

## Features

### ✅ Fully Integrated

- ✅ **Multi-turn conversations** - Maintains context across messages
- ✅ **Agent orchestration** - All agents work automatically
- ✅ **Itinerary generation** - Creates complete day-by-day plans
- ✅ **Hotel selection** - Choose from 3 options
- ✅ **Activity swapping** - Replace activities you don't like
- ✅ **Error handling** - Graceful fallbacks
- ✅ **Monitoring** - Logs all interactions

### UI Features

- 🎨 **Beautiful design** - Clean, modern interface
- 💬 **Chat-based** - Natural conversation flow
- 📊 **Visual itinerary** - Cards with icons and pricing
- 🏨 **Hotel comparison** - Side-by-side options
- 🔄 **Live updates** - Real-time responses
- 📱 **Responsive** - Works on all screen sizes

## Configuration

### Environment Variables

Create `.env` in project root:

```bash
# OpenAI API (required)
OPENAI_API_KEY=your_key_here

# Or Anthropic Claude
ANTHROPIC_API_KEY=your_key_here

# Backend URL (optional, defaults to localhost:8000)
TRAVEL_PLANNER_API_URL=http://localhost:8000

# LangSmith tracing (optional)
LANGCHAIN_TRACING_V2=false
```

### Streamlit Config

Located at `streamlit_UI/.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#007AFF"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F5F5F5"
textColor = "#000000"

[server]
port = 8501
headless = false
```

## Testing

### 1. Health Check

```bash
# Check backend
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "service": "travel-planner-api",
  "active_conversations": 0,
  "monitoring": "enabled"
}
```

### 2. Test Conversation

In Streamlit UI:
1. Type: "I want to plan a family trip to Orlando"
2. Wait for AI response (clarification questions)
3. Answer questions about dates, budget, etc.
4. View generated itinerary
5. Try selecting different hotels
6. Try swapping activities

### 3. Check Logs

```bash
# Backend logs
tail -f logs/backend.log
tail -f logs/user_interactions.log

# Streamlit logs
# Visible in Terminal 2
```

## Troubleshooting

### Backend won't start

**Error:** `Address already in use`
```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9

# Restart
python api_server.py
```

### Streamlit can't connect

**Error:** `Cannot connect to backend`
```bash
# Check backend is running
curl http://localhost:8000/health

# Check .env has API keys
cat .env | grep API_KEY
```

### No response from AI

**Issue:** Timeout or slow response

**Solution:**
- Check API key is valid
- Increase timeout in `api_client.py:57` (currently 600s)
- Check internet connection
- Review logs/backend.log for errors

### Itinerary not displaying

**Issue:** Response doesn't include itinerary

**Check:**
1. Backend logs show agent execution?
2. State includes itinerary data?
3. JSON structure matches expected format?

**Debug:**
```python
# Add to api_server.py:242
print("STATE:", state)
print("ITINERARY:", state.get('itinerary'))
```

## Customization

### Change UI Theme

Edit `streamlit_UI/.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#FF6B35"  # Your brand color
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

### Modify Chat Prompts

Edit `streamlit_UI/components/chat_message.py`:

```python
def render_message(message: Dict[str, Any]):
    # Change avatar
    if role == "user":
        avatar = "👤"  # Change this
    else:
        avatar = "🤖"  # Or this
```

### Add New Features

Example: Add export button

```python
# streamlit_UI/app.py

if st.session_state.current_itinerary:
    if st.button("📥 Export as PDF"):
        pdf_data = generate_pdf(st.session_state.current_itinerary)
        st.download_button(
            "Download PDF",
            data=pdf_data,
            file_name="itinerary.pdf",
            mime="application/pdf"
        )
```

## File Structure

```
Travel_Planner_ai/
├── api_server.py              # FastAPI backend
├── start_ui.sh                # Startup script
├── core/                      # Core logic
│   ├── orchestrator.py        # Agent orchestration
│   ├── conversation_manager.py
│   └── state.py
├── agents/                    # AI agents
│   ├── clarification_agent.py
│   ├── travel_options_agent.py
│   ├── accommodation_agent.py
│   ├── activities_agent.py
│   ├── plan_composer_agent.py
│   └── refinement_agent.py
└── streamlit_UI/              # Streamlit frontend
    ├── app.py                 # Main app
    ├── components/            # UI components
    │   ├── chat_message.py
    │   ├── itinerary_display.py
    │   └── selection_widgets.py
    ├── utils/                 # Utilities
    │   ├── api_client.py      # Backend API client
    │   └── helpers.py
    ├── assets/                # CSS, images
    ├── .streamlit/            # Config
    └── requirements.txt       # Dependencies
```

## Development Tips

### Hot Reload

Both services support hot reload:
- **Backend:** FastAPI reloads on code changes
- **Streamlit:** Auto-reloads on file save

### Debug Mode

Enable detailed logging:

```python
# api_server.py
logging.basicConfig(level=logging.DEBUG)
```

### Test Individual Components

```bash
# Test API client
cd streamlit_UI/utils
python -c "from api_client import TravelPlannerClient; c = TravelPlannerClient(); print(c.health_check())"

# Test component
cd streamlit_UI
python -c "from components.chat_message import render_message; import streamlit as st; st.write('test')"
```

## Performance

### Response Times

- **Simple clarification:** 2-5 seconds
- **Destination search:** 10-30 seconds
- **Full itinerary:** 30-60 seconds

### Optimization

- Responses are streamed where possible
- Conversation state is cached
- Agent results are reused

## Security

### Production Checklist

- [ ] Add authentication to API
- [ ] Use HTTPS
- [ ] Validate all inputs
- [ ] Rate limit API requests
- [ ] Secure API keys in environment
- [ ] Add CORS restrictions
- [ ] Enable logging rotation

## Support

### Common Questions

**Q: Can I use Claude instead of GPT-4?**
A: Yes! Set `ANTHROPIC_API_KEY` in `.env`

**Q: How do I customize the itinerary format?**
A: Edit `core/component_schemas.py` and `agents/plan_composer_agent.py`

**Q: Can I add more agents?**
A: Yes! Create new agent in `agents/` and add to orchestrator routing

**Q: How do I deploy this?**
A: Use Docker (Dockerfile included) or cloud platforms (Streamlit Cloud, Railway, etc.)

## Next Steps

1. ✅ Start both services: `./start_ui.sh`
2. ✅ Open http://localhost:8501
3. ✅ Test a complete flow
4. 🎨 Customize theme and styling
5. 🚀 Deploy to production (optional)

---

**Everything is already connected and working!** Just run `./start_ui.sh` and start planning trips! 🎉
