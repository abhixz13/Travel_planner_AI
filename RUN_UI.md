# How to Run the Streamlit UI

## Simple 2-Step Startup (Recommended)

### Step 1: Start Backend (Terminal 1)

```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai
python api_server.py
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Keep this terminal open!**

---

### Step 2: Start Streamlit (Terminal 2)

```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai
streamlit run streamlit_UI/app.py
```

**Expected output:**
```
You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

**Browser will auto-open to http://localhost:8501**

---

## Troubleshooting

### Issue: "ModuleNotFoundError"

**Solution:** Install dependencies

```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai
pip install streamlit requests python-dotenv fastapi uvicorn
```

### Issue: "Port 8000 already in use"

**Solution:** Kill existing process

```bash
lsof -ti:8000 | xargs kill -9
```

Then restart backend.

### Issue: "Port 8501 already in use"

**Solution:** Kill existing Streamlit

```bash
lsof -ti:8501 | xargs kill -9
```

Then restart Streamlit.

### Issue: Backend not responding

**Check 1:** Is backend running?
```bash
curl http://localhost:8000/health
```

**Check 2:** Do you have API keys in .env?
```bash
cat .env | grep API_KEY
```

If no .env file:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY or ANTHROPIC_API_KEY
```

---

## Quick Test

Once both are running:

1. Go to http://localhost:8501
2. Type: **"I want to plan a family trip to Orlando"**
3. Wait for AI response
4. Answer the clarification questions
5. View your itinerary!

---

## Alternative: One-Command Startup

Use the automated script:

```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai
./start_ui.sh
```

**Note:** This starts both services. Press Ctrl+C to stop both.

---

## What Each Service Does

**Backend (Port 8000):**
- Runs your AI agents
- Processes chat messages
- Generates itineraries
- Handles refinements

**Streamlit UI (Port 8501):**
- Beautiful web interface
- Chat with AI
- Display itineraries
- Interactive hotel/activity selection

---

## Environment Variables

Required in `.env`:

```bash
# Choose ONE:
OPENAI_API_KEY=sk-...          # For GPT-4
# OR
ANTHROPIC_API_KEY=sk-ant-...   # For Claude

# Optional:
LANGCHAIN_TRACING_V2=false
```

---

## Screenshots

Once running, you should see:

**Terminal 1 (Backend):**
```
INFO: Uvicorn running on http://0.0.0.0:8000
```

**Terminal 2 (Streamlit):**
```
Local URL: http://localhost:8501
```

**Browser:**
```
┌─────────────────────────────────┐
│  ✈️ AI Travel Planner            │
│                                 │
│  Start a conversation...        │
│  > I want to plan...            │
└─────────────────────────────────┘
```

---

## Stop Services

**Method 1:** Press `Ctrl+C` in each terminal

**Method 2:** Kill processes manually
```bash
lsof -ti:8000 | xargs kill -9  # Backend
lsof -ti:8501 | xargs kill -9  # Streamlit
```

---

## Next Steps

1. ✅ Start both services (2 terminals)
2. ✅ Open http://localhost:8501
3. ✅ Test with a trip request
4. ✅ Explore features (hotel selection, activity swapping)
5. 🎨 Customize UI (see STREAMLIT_INTEGRATION.md)

---

**That's it! Enjoy planning trips with AI!** 🎉
