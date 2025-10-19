# Quick Start Guide

Get the Travel Planner UI running in under 5 minutes!

## Option 1: Local Development (Fastest)

### Step 1: Install Dependencies
```bash
cd streamlit_UI
pip install -r requirements.txt
```

### Step 2: Run Streamlit

**Recommended - Using the launcher:**
```bash
# From project root
python3 run_ui.py
```

**Alternative - Direct command:**
```bash
# From streamlit_UI directory
cd streamlit_UI
streamlit run app.py
```

### Step 3: Open Browser
Visit: `http://localhost:8501`

**Note**: Ensure the backend is running on `http://localhost:8000`

---

## Option 2: Docker (Production-Ready)

### Step 1: Build Image
```bash
docker build -t travel-planner-ui .
```

### Step 2: Run Container
```bash
docker run -p 8501:8501 \
  -e TRAVEL_PLANNER_API_URL=http://backend:8000 \
  travel-planner-ui
```

### Step 3: Open Browser
Visit: `http://localhost:8501`

---

## Option 3: Docker Compose (Full Stack)

From the project root directory:

```bash
docker-compose up
```

This will start:
- Backend API (port 8000)
- Streamlit UI (port 8501)

Access the UI at: `http://localhost:8501`

---

## First Conversation

Once the app is running, try this example:

1. **You**: "I want to plan a 3-day family trip near Seattle"

2. **AI**: Asks for details (origin, dates, preferences)

3. **You**: "We're coming from California, leaving October 24th"

4. **AI**: Suggests destinations

5. **You**: "San Juan Islands sounds perfect!"

6. **AI**: Creates your complete itinerary with:
   - 3 hotel options
   - Day-by-day activities
   - Restaurant recommendations
   - Travel tips

7. **Customize**: Select hotel, swap activities, refine details

---

## Troubleshooting

### "Cannot connect to backend"
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not, start it
cd ..
python3 run.py
```

### Port already in use
```bash
# Use a different port
streamlit run app.py --server.port=8502
```

### Import errors
```bash
# Ensure you're in the correct directory
cd streamlit_UI

# Check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/.."
```

---

## Next Steps

- Read the [full README](README.md) for detailed documentation
- Explore the [components](components/) to understand the UI structure
- Check the [API client](utils/api_client.py) for backend integration
- Customize [styles](assets/style.css) to match your brand

---

## Need Help?

- Backend not responding? Check Docker: `docker ps`
- UI not loading? Check browser console: F12 → Console
- Styling issues? Clear cache: Ctrl+Shift+R (Cmd+Shift+R on Mac)

Happy planning! ✈️
