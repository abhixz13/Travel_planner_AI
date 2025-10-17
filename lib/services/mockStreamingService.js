// Mock streaming service that simulates Claude API responses
// This will be replaced with real Claude integration in Phase 4

const MOCK_RESPONSES = {
  greeting: [
    "Hello! I'm your AI trip planner. I can help you plan amazing trips, find accommodations, discover activities, and create complete itineraries.",
    "\n\nTo get started, tell me:",
    "\n- Where are you traveling from?",
    "\n- Where would you like to go?",
    "\n- When are you planning to travel?",
    "\n- How many people are traveling?",
  ],
  destination: [
    "Great choice! Let me search for the best options for your trip.",
    "\n\nI'm analyzing:",
    "\n✈️ Flight options and travel routes",
    "\n🏨 Accommodation recommendations",
    "\n🎯 Popular activities and attractions",
    "\n\nGive me a moment...",
  ],
  activities: [
    "Here are some amazing activities I found for your destination:",
    "\n\n1. **Guided City Tour** - Explore historical landmarks and hidden gems",
    "\n2. **Local Food Experience** - Taste authentic local cuisine",
    "\n3. **Adventure Activities** - Hiking, water sports, or cultural experiences",
    "\n\nWould you like me to add any of these to your itinerary?",
  ],
};

const MOCK_TOOL_RESULTS = {
  travel: {
    section: 'travel',
    summary: 'Found 3 flight options for your dates',
    results: [
      {
        title: 'Direct Flight - Economy',
        snippet: 'Non-stop flight, 6h 30m, $450 per person',
        url: '#',
        price: '$450',
        duration: '6h 30m',
      },
      {
        title: 'One Stop - Budget',
        snippet: '1 stop, 9h 15m, $320 per person',
        url: '#',
        price: '$320',
        duration: '9h 15m',
      },
      {
        title: 'Direct Flight - Business',
        snippet: 'Non-stop, premium seats, 6h 30m, $1,200 per person',
        url: '#',
        price: '$1,200',
        duration: '6h 30m',
      },
    ],
    followUp: 'Which flight option works best for your budget?',
  },
  stays: {
    section: 'stays',
    summary: 'Found 4 highly-rated accommodations',
    results: [
      {
        title: 'Downtown Luxury Hotel',
        snippet: '5-star hotel in city center, rooftop pool, spa',
        url: '#',
        rating: '4.8',
        price: '$280/night',
      },
      {
        title: 'Cozy Boutique Hotel',
        snippet: 'Charming boutique hotel, walkable to attractions',
        url: '#',
        rating: '4.6',
        price: '$150/night',
      },
      {
        title: 'Beachfront Resort',
        snippet: 'All-inclusive resort, private beach access',
        url: '#',
        rating: '4.7',
        price: '$320/night',
      },
      {
        title: 'Budget-Friendly Hostel',
        snippet: 'Clean, safe, social atmosphere, free breakfast',
        url: '#',
        rating: '4.4',
        price: '$45/night',
      },
    ],
    followUp: 'Would you like more details on any of these stays?',
  },
  activities: {
    section: 'activities',
    summary: 'Curated 8 activities based on your interests',
    results: [
      {
        title: 'Historic Walking Tour',
        snippet: '3-hour guided tour of old town and monuments',
        url: '#',
        duration: '3 hours',
        price: '$45',
      },
      {
        title: 'Food & Wine Tasting',
        snippet: 'Sample local specialties with expert guide',
        url: '#',
        duration: '4 hours',
        price: '$85',
      },
      {
        title: 'Sunset Boat Cruise',
        snippet: 'Scenic evening cruise with dinner included',
        url: '#',
        duration: '2.5 hours',
        price: '$95',
      },
      {
        title: 'Museum Pass',
        snippet: 'Access to 5 top museums, skip-the-line entry',
        url: '#',
        duration: 'Flexible',
        price: '$60',
      },
    ],
    followUp: 'Which activities interest you the most?',
  },
};

export class MockStreamingService {
  async *streamResponse(message, context = {}) {
    const lowerMessage = message.toLowerCase();
    
    // Determine response type based on message content
    let responseChunks = [];
    let toolResult = null;

    if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('start')) {
      responseChunks = MOCK_RESPONSES.greeting;
    } else if (lowerMessage.includes('flight') || lowerMessage.includes('travel') || lowerMessage.includes('fly')) {
      responseChunks = ['Let me search for flight options...\n\n'];
      toolResult = MOCK_TOOL_RESULTS.travel;
    } else if (lowerMessage.includes('hotel') || lowerMessage.includes('stay') || lowerMessage.includes('accommodation')) {
      responseChunks = ['Searching for accommodations...\n\n'];
      toolResult = MOCK_TOOL_RESULTS.stays;
    } else if (lowerMessage.includes('activity') || lowerMessage.includes('things to do') || lowerMessage.includes('attractions')) {
      responseChunks = ['Finding activities for you...\n\n'];
      toolResult = MOCK_TOOL_RESULTS.activities;
    } else if (lowerMessage.includes('itinerary') || lowerMessage.includes('plan')) {
      responseChunks = [
        "I can help you create a complete itinerary! ",
        "Based on your preferences, I'll include:",
        "\n\n📍 Day-by-day schedule",
        "\n✈️ Travel arrangements",
        "\n🏨 Accommodation bookings",
        "\n🎯 Activities and experiences",
        "\n\nShall I start building your personalized itinerary?",
      ];
    } else {
      responseChunks = [
        "I understand you're asking about: '",
        message,
        "'\n\nI can help you with:",
        "\n• Finding flights and travel options",
        "\n• Recommending hotels and stays",
        "\n• Suggesting activities and attractions",
        "\n• Creating complete itineraries",
        "\n\nWhat would you like to explore first?",
      ];
    }

    // Simulate streaming with realistic delays
    for (const chunk of responseChunks) {
      await this.delay(30 + Math.random() * 50);
      yield {
        type: 'content',
        content: chunk,
      };
    }

    // If we have tool results, yield them after content
    if (toolResult) {
      await this.delay(500);
      yield {
        type: 'tool',
        content: toolResult,
      };
    }

    // Signal completion
    yield {
      type: 'done',
    };
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // This method signature matches what we'll use for real Claude API
  async createStreamingResponse(messages, options = {}) {
    const lastMessage = messages[messages.length - 1];
    return this.streamResponse(lastMessage.content, options);
  }
}

export const mockStreamingService = new MockStreamingService();
