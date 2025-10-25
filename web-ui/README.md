# AI Trip Planner - Web UI

Simple, intuitive React-based UI for local machine (like Gradio).

## Features

✅ **User-Intuitive Design**
- Single-page interface
- Guided trip setup with chips
- Real-time chat with AI
- Interactive itinerary display

✅ **Quick Setup**
- No build process needed
- Runs on any machine with Python
- Works with existing backend at `localhost:8000`

## Quick Start

### 1. Start Your Backend

```bash
cd /Users/abhijeetsinghx2/Travel_Planner_ai
python api_server.py
```

Backend should run on `http://localhost:8000`

### 2. Start Web UI

```bash
cd web-ui
python3 -m http.server 3000
```

### 3. Open in Browser

```
http://localhost:3000
```

That's it! 🚀

## How to Use

1. **Fill in Trip Details**
   - Select destination (Paris, NYC, Bali, etc.)
   - Enter origin city
   - Choose number of travelers
   - Select budget level
   - Pick interests (Food, Art, Nature, etc.)

2. **Click "Plan My Trip"**
   - AI generates itinerary
   - Shows day-by-day activities
   - Displays costs and timings

3. **Chat with AI**
   - Ask questions about your trip
   - Request changes to itinerary
   - Get recommendations

## Backend Integration

The UI calls these endpoints:

```
POST http://localhost:8000/api/chat
Body: { "message": "..." }
```

Make sure your backend:
- Is running on port 8000
- Has `/api/chat` endpoint
- Returns `{ "message": "...", "itinerary": {...} }`

## Customization

### Change Colors

Edit `styles.css`:

```css
:root {
  --primary: #007AFF;  /* Change to your brand color */
  --primary-light: #5AC8FA;
}
```

### Modify Destinations

Edit `app.js` line 23:

```javascript
const destinations = [
  { id: 'paris', label: 'Paris', icon: '🗼' },
  // Add your destinations here
];
```

### Backend URL

Edit `app.js` line 83 and 176:

```javascript
const response = await fetch('http://localhost:8000/api/chat', {
  // Change URL here
});
```

## Architecture

```
┌─────────────────┐         ┌──────────────────┐
│   Web Browser   │         │   Your Backend   │
│  (localhost:3000)│  ←────→ │  (localhost:8000)│
│                 │  HTTP   │                  │
│  React UI       │  POST   │  Travel Planner  │
│  No build       │  /chat  │  AI Agents       │
└─────────────────┘         └──────────────────┘
```

## Files

```
web-ui/
├── index.html      # HTML wrapper
├── app.js          # React app (single file)
├── styles.css      # Design system
├── package.json    # Metadata
└── README.md       # This file
```

## Browser Support

- Chrome/Edge (recommended)
- Firefox
- Safari
- Any modern browser with ES6+ support

## No Build Required

Uses:
- React from CDN (unpkg.com)
- Babel standalone for JSX
- Pure CSS (no preprocessors)
- Python's built-in HTTP server

Perfect for local development and demos!

## Troubleshooting

### Backend not responding?

```bash
# Check backend health
curl http://localhost:8000/health

# If not running:
cd /Users/abhijeetsinghx2/Travel_Planner_ai
python api_server.py
```

### Port 3000 already in use?

```bash
# Use different port
python3 -m http.server 8080

# Open: http://localhost:8080
```

### UI not updating?

```bash
# Hard refresh in browser
# Mac: Cmd + Shift + R
# Windows: Ctrl + Shift + R
```

## Production Deployment

For production, build optimized version:

```bash
# Install dependencies
npm install

# Build for production
npx vite build

# Serve with nginx/apache
```

But for local use, current setup is perfect! 🎉
