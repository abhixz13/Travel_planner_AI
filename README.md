# TripMate - AI-Powered Trip Planner 🌍✈️

A modern, interactive web application for planning trips with AI assistance. Built with Next.js 14, featuring real-time streaming chat, personalized itineraries, and beautiful UI components.

## 🎯 Current Status: Phase 1 Complete! 

✅ **Streaming Chat Interface** (MVP - Ready to Use!)
- Beautiful, responsive chat UI with real-time AI streaming
- Token-by-token message rendering
- Interactive result cards (flights, hotels, activities)
- Trip summary context panel
- Toast notifications and micro-interactions
- Mock streaming service (ready for Claude integration)

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ 
- Yarn package manager
- MongoDB (running on localhost:27017)

### Installation

```bash
# Install dependencies
yarn install

# Start development server
yarn dev

# Server will start on http://localhost:3000
```

### Access the App

- **Homepage**: http://localhost:3000
- **Chat Interface**: http://localhost:3000/chat

## 🏗️ Architecture

### Tech Stack
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS + shadcn/ui
- **UI Components**: Radix UI primitives
- **Icons**: Lucide React
- **Database**: MongoDB
- **Streaming**: Server-Sent Events (SSE)
- **State Management**: React hooks + Context
- **Forms**: React Hook Form + Zod

### Project Structure

```
/app
├── app/
│   ├── api/
│   │   ├── chat/stream/route.js      # SSE streaming endpoint
│   │   └── [[...path]]/route.js      # Main API handler (sessions, itineraries)
│   ├── chat/page.js                   # Main chat interface
│   ├── page.js                        # Landing page
│   ├── layout.js                      # Root layout
│   └── globals.css                    # Global styles
├── components/
│   ├── chat/
│   │   ├── ChatMessage.jsx            # Message component
│   │   ├── MessageComposer.jsx        # Input composer
│   │   └── ResultCard.jsx             # Result cards (flights/hotels/activities)
│   ├── trip/
│   │   └── TripSummaryPanel.jsx       # Trip context sidebar
│   └── ui/                            # shadcn/ui components
├── lib/
│   ├── db/
│   │   ├── mongodb.js                 # Database connection
│   │   └── models.js                  # Data models
│   ├── services/
│   │   └── mockStreamingService.js    # Mock AI service
│   └── utils.js                       # Utility functions
└── package.json
```

## 🎨 Features

### Current Features (Phase 1)

#### 1. Interactive Chat Interface
- Real-time streaming responses
- Token-by-token message rendering
- User and assistant messages
- Empty states and loading indicators

#### 2. Result Cards
- Flight options with price and duration
- Hotel recommendations with ratings
- Activity suggestions
- "Add to Itinerary" buttons with feedback
- Hover effects and transitions

#### 3. Trip Context Panel
- Origin and destination tracking
- Date range display
- Traveler count
- Budget tracking
- Quick action badges

#### 4. Message Composer
- Auto-resizing textarea
- Keyboard shortcuts (Cmd/Ctrl + Enter)
- Character limit indicators
- Disabled state during streaming

#### 5. Mock Streaming Service
- Simulates Claude API responses
- Realistic token delays
- Multiple response types (text, tool results)
- Easy swap for real AI integration

## 🔌 API Endpoints

### Chat Streaming
```
POST /api/chat/stream
Body: {
  message: string,
  sessionId: string,
  context: TripContext
}
Response: Server-Sent Events (SSE)
```

### Sessions
```
GET  /api/sessions           # List all sessions
POST /api/sessions           # Create new session
POST /api/sessions/message   # Add message to session
```

### Itineraries
```
GET    /api/itineraries           # List all itineraries
POST   /api/itineraries           # Create itinerary
GET    /api/itineraries/:id       # Get single itinerary
PATCH  /api/itineraries/:id       # Update itinerary
DELETE /api/itineraries/:id       # Delete itinerary
```

## 🎯 Next Steps (Upcoming Phases)

### Phase 2: Authentication (Ready to Implement)
- [ ] NextAuth.js setup
- [ ] Google OAuth integration
- [ ] Protected routes
- [ ] User sessions
- [ ] Sign in/sign up pages

### Phase 3: Itinerary Management
- [ ] Save itineraries from chat
- [ ] Itinerary list page
- [ ] Detail view with editing
- [ ] Export functionality (PDF/Markdown)
- [ ] Share functionality

### Phase 4: Real Claude Integration
- [ ] Replace mock service with Claude API
- [ ] Use Emergent LLM key
- [ ] Maintain streaming interface
- [ ] Add error handling
- [ ] Rate limiting

## 🔄 Swapping Mock to Real AI

The mock streaming service is designed to be easily replaced with real Claude integration:

```javascript
// Current: lib/services/mockStreamingService.js
export class MockStreamingService {
  async *streamResponse(message, context) {
    // Mock implementation
  }
}

// Future: lib/services/claudeService.js
export class ClaudeService {
  async *streamResponse(message, context) {
    // Real Claude API implementation
    // Same interface, different backend
  }
}
```

Just update the import in `/api/chat/stream/route.js`:
```javascript
// Change from:
import { mockStreamingService } from '@/lib/services/mockStreamingService';

// To:
import { claudeService } from '@/lib/services/claudeService';
```

## 🎨 UI Components

All UI components are from shadcn/ui and fully customizable:

- Button, Card, Badge, Separator
- Textarea, ScrollArea
- Toast notifications
- All components support dark mode
- Accessible by default (ARIA labels, keyboard nav)

## 🌐 Environment Variables

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=tripplanner
NEXT_PUBLIC_BASE_URL=https://your-domain.com
CORS_ORIGINS=*
```

## 🧪 Testing the Chat Interface

1. Navigate to `/chat`
2. Try these queries:
   - "Show me flight options" → See flight cards
   - "I need hotel recommendations" → See hotel cards  
   - "What activities can I do?" → See activity cards
   - "Plan a trip to Paris" → Get planning assistance

## 🎯 Key Features Demonstrated

- ✅ Real-time streaming (token-by-token)
- ✅ Interactive result cards
- ✅ Toast notifications
- ✅ Smooth animations
- ✅ Responsive design
- ✅ Keyboard shortcuts
- ✅ Empty states
- ✅ Loading indicators
- ✅ Context panel
- ✅ Beautiful modern UI

## 🚧 Development Notes

### Hot Reload
- Frontend and backend have hot reload enabled
- Only restart when:
  - Installing new dependencies
  - Modifying .env files

### Service Commands
```bash
# Restart all services
sudo supervisorctl restart all

# Check status
sudo supervisorctl status

# View logs
tail -f /var/log/supervisor/nextjs.out.log
```

## 📝 Database Models

### ChatSession
```javascript
{
  sessionId: string,
  userId: string,
  title: string,
  messages: Array,
  tripContext: {
    origin: string,
    destination: string,
    startDate: string,
    endDate: string,
    travelers: number,
    budget: string
  },
  createdAt: string,
  updatedAt: string
}
```

### Itinerary
```javascript
{
  itineraryId: string,
  userId: string,
  sessionId: string,
  title: string,
  origin: string,
  destination: string,
  startDate: string,
  endDate: string,
  travel: ToolResult,
  stays: ToolResult,
  activities: ToolResult,
  notes: string,
  tags: Array,
  coverImage: string,
  createdAt: string,
  updatedAt: string
}
```

## 🎉 What's Working Now

The current implementation provides:

1. **Complete Chat Experience**
   - Send messages and receive streaming responses
   - See realistic flight, hotel, and activity recommendations
   - Interactive cards with save functionality
   - Toast notifications for actions

2. **Beautiful UI**
   - Modern, clean design
   - Smooth transitions and animations
   - Responsive layout
   - Dark mode ready

3. **Ready for Real AI**
   - Mock service matches real API interface
   - Easy swap to Claude
   - All infrastructure in place

## 🔧 Customization

### Adding New Result Types

Edit `/lib/services/mockStreamingService.js`:

```javascript
const MOCK_TOOL_RESULTS = {
  restaurants: {
    section: 'restaurants',
    summary: 'Found 5 restaurants',
    results: [...],
    followUp: 'Which cuisine interests you?'
  }
}
```

### Styling

All styles use Tailwind CSS. Key design tokens in `tailwind.config.js`:

- Colors: primary, secondary, muted, accent
- Spacing: Container (max-w-4xl for chat)
- Typography: Inter font family

## 📱 Responsive Design

- Desktop: Full sidebar + chat
- Tablet: Collapsible sidebar
- Mobile: Hamburger menu for sidebar

## 🎓 Learning Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui Components](https://ui.shadcn.com)
- [Tailwind CSS](https://tailwindcss.com)
- [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

## 📄 License

This project is part of the TripMate application.

---

**Built with ❤️ using Next.js, shadcn/ui, and modern web technologies**

**Current Status**: Phase 1 Complete - Streaming chat interface with mock AI responses. Ready for authentication and real Claude integration!
