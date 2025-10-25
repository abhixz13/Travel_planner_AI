const { useState, useEffect, useRef } = React;

// Main App Component
function App() {
  const [step, setStep] = useState('setup'); // 'setup', 'chat', 'itinerary'
  const [tripContext, setTripContext] = useState({
    destination: '',
    origin: '',
    dates: { start: '', end: '' },
    travelers: 2,
    budget: '',
    interests: [],
  });
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [currentItinerary, setCurrentItinerary] = useState(null);
  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  // Destinations
  const destinations = [
    { id: 'paris', label: 'Paris', icon: '🗼' },
    { id: 'nyc', label: 'NYC', icon: '🗽' },
    { id: 'bali', label: 'Bali', icon: '🌴' },
    { id: 'tokyo', label: 'Tokyo', icon: '🎌' },
    { id: 'rome', label: 'Rome', icon: '🏛' },
  ];

  // Budget options
  const budgets = [
    { id: 'low', label: '$', value: 'Budget' },
    { id: 'medium', label: '$$', value: 'Moderate' },
    { id: 'high', label: '$$$', value: 'Comfortable' },
    { id: 'luxury', label: '$$$$', value: 'Luxury' },
  ];

  // Interests
  const interests = [
    { id: 'food', label: 'Food', icon: '🍽' },
    { id: 'art', label: 'Art', icon: '🎨' },
    { id: 'nature', label: 'Nature', icon: '🏞' },
    { id: 'shopping', label: 'Shopping', icon: '🛍' },
    { id: 'nightlife', label: 'Nightlife', icon: '🎉' },
    { id: 'history', label: 'History', icon: '🏛' },
  ];

  const toggleInterest = (interestId) => {
    setTripContext(prev => ({
      ...prev,
      interests: prev.interests.includes(interestId)
        ? prev.interests.filter(i => i !== interestId)
        : [...prev.interests, interestId]
    }));
  };

  const handlePlanTrip = async () => {
    if (!tripContext.destination || !tripContext.budget) {
      alert('Please select destination and budget');
      return;
    }

    setStep('chat');

    // Initial message
    const welcomeMsg = {
      role: 'assistant',
      content: `Great! I'm planning your ${tripContext.budget} trip to ${tripContext.destination} for ${tripContext.travelers} people. Let me find the best options for you...`,
      timestamp: Date.now(),
    };
    setMessages([welcomeMsg]);
    setIsTyping(true);

    try {
      // Call backend API
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `Plan a trip to ${tripContext.destination} for ${tripContext.travelers} people with a ${tripContext.budget} budget. Interests: ${tripContext.interests.join(', ')}`
        }),
      });

      const data = await response.json();

      setIsTyping(false);
      const botMsg = {
        role: 'assistant',
        content: data.message || data.response || 'I\'ve created a personalized itinerary for you!',
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, botMsg]);

      // If backend returns itinerary, display it
      if (data.itinerary) {
        setCurrentItinerary(data.itinerary);
      } else {
        // Generate sample itinerary for demo
        generateSampleItinerary();
      }
    } catch (error) {
      setIsTyping(false);
      const errorMsg = {
        role: 'assistant',
        content: 'Sorry, I couldn\'t connect to the backend. Here\'s a sample itinerary for you!',
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMsg]);
      generateSampleItinerary();
    }
  };

  const generateSampleItinerary = () => {
    const sample = {
      title: `${tripContext.destination} Adventure`,
      totalCost: 2400,
      days: [
        {
          day: 1,
          date: 'Mon, Aug 12',
          activities: [
            { icon: '✈️', title: 'Arrive at Airport', time: '9:00 AM', duration: '2h', cost: 0 },
            { icon: '🏨', title: 'Check-in Hotel', time: '12:00 PM', duration: '30min', cost: 150 },
            { icon: '🍽', title: 'Lunch at Local Bistro', time: '1:00 PM', duration: '1.5h', cost: 45 },
            { icon: '🎯', title: 'City Walking Tour', time: '3:00 PM', duration: '3h', cost: 30 },
          ]
        },
        {
          day: 2,
          date: 'Tue, Aug 13',
          activities: [
            { icon: '🏛', title: 'Museum Visit', time: '10:00 AM', duration: '3h', cost: 25 },
            { icon: '🍽', title: 'Lunch', time: '1:30 PM', duration: '1h', cost: 40 },
            { icon: '🎨', title: 'Art Gallery', time: '3:00 PM', duration: '2h', cost: 20 },
            { icon: '🍽', title: 'Dinner', time: '7:00 PM', duration: '2h', cost: 65 },
          ]
        },
      ]
    };
    setCurrentItinerary(sample);
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMsg = {
      role: 'user',
      content: inputMessage,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInputMessage('');
    setIsTyping(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: inputMessage }),
      });

      const data = await response.json();
      setIsTyping(false);

      const botMsg = {
        role: 'assistant',
        content: data.message || data.response || 'I understand. Let me help you with that.',
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (error) {
      setIsTyping(false);
      const errorMsg = {
        role: 'assistant',
        content: 'I\'m having trouble connecting. Please try again.',
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMsg]);
    }
  };

  const progress = () => {
    let filled = 0;
    if (tripContext.destination) filled += 33;
    if (tripContext.budget) filled += 33;
    if (tripContext.interests.length > 0) filled += 34;
    return filled;
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>✈️ AI Trip Planner</h1>
        <p>Plan your perfect trip in minutes with AI assistance</p>
      </header>

      <div className="main-content">
        {/* Setup Panel */}
        <div className="setup-panel">
          <h2>Plan Your Trip</h2>

          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress()}%` }}></div>
          </div>

          {/* Destination */}
          <div className="question-group">
            <label className="question-label">Where to?</label>
            <div className="chips-container">
              {destinations.map(dest => (
                <div
                  key={dest.id}
                  className={`chip ${tripContext.destination === dest.label ? 'selected' : ''}`}
                  onClick={() => setTripContext(prev => ({ ...prev, destination: dest.label }))}
                >
                  <span>{dest.icon}</span>
                  <span>{dest.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Origin */}
          <div className="question-group">
            <label className="question-label">From where?</label>
            <input
              type="text"
              className="input-field"
              placeholder="e.g., New York"
              value={tripContext.origin}
              onChange={(e) => setTripContext(prev => ({ ...prev, origin: e.target.value }))}
            />
          </div>

          {/* Travelers */}
          <div className="question-group">
            <label className="question-label">How many travelers?</label>
            <input
              type="number"
              className="input-field"
              min="1"
              max="10"
              value={tripContext.travelers}
              onChange={(e) => setTripContext(prev => ({ ...prev, travelers: parseInt(e.target.value) }))}
            />
          </div>

          {/* Budget */}
          <div className="question-group">
            <label className="question-label">Budget per person?</label>
            <div className="chips-container">
              {budgets.map(budget => (
                <div
                  key={budget.id}
                  className={`chip ${tripContext.budget === budget.value ? 'selected' : ''}`}
                  onClick={() => setTripContext(prev => ({ ...prev, budget: budget.value }))}
                >
                  <span>{budget.label}</span>
                  <span style={{ fontSize: '12px' }}>{budget.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Interests */}
          <div className="question-group">
            <label className="question-label">What interests you? (Pick 2-3)</label>
            <div className="chips-container">
              {interests.map(interest => (
                <div
                  key={interest.id}
                  className={`chip ${tripContext.interests.includes(interest.id) ? 'selected' : ''}`}
                  onClick={() => toggleInterest(interest.id)}
                >
                  <span>{interest.icon}</span>
                  <span>{interest.label}</span>
                </div>
              ))}
            </div>
          </div>

          <button className="plan-button" onClick={handlePlanTrip}>
            ✨ Plan My Trip
          </button>
        </div>

        {/* Chat Panel */}
        <div className="chat-panel">
          {step === 'setup' ? (
            <div className="empty-state">
              <div className="empty-state-icon">✈️</div>
              <h3>Ready to plan your adventure?</h3>
              <p>Fill in your preferences and click "Plan My Trip" to get started</p>
            </div>
          ) : (
            <>
              {tripContext.destination && (
                <div className="trip-summary">
                  <strong>Planning:</strong> {tripContext.destination} · {tripContext.travelers} travelers · {tripContext.budget} budget · {tripContext.interests.join(', ')}
                </div>
              )}

              <div className="chat-messages">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`message ${msg.role}`}>
                    <div className="message-bubble">{msg.content}</div>
                  </div>
                ))}

                {isTyping && (
                  <div className="message assistant">
                    <div className="typing-indicator">
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                    </div>
                  </div>
                )}

                {currentItinerary && (
                  <div className="itinerary-card">
                    <h3>📋 {currentItinerary.title}</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: 'var(--spacing-md)' }}>
                      Total: <span className="price-pill">${currentItinerary.totalCost}</span>
                    </p>

                    {currentItinerary.days.map((day, idx) => (
                      <div key={idx} className="day-section">
                        <div className="day-header">Day {day.day} - {day.date}</div>
                        {day.activities.map((activity, aIdx) => (
                          <div key={aIdx} className="activity">
                            <div className="activity-icon">{activity.icon}</div>
                            <div className="activity-details">
                              <div className="activity-title">{activity.title}</div>
                              <div className="activity-meta">
                                {activity.time} · {activity.duration} · <span className="price-pill">${activity.cost}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              <div className="chat-input-container">
                <textarea
                  className="chat-input"
                  placeholder="Ask me anything about your trip..."
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  rows="1"
                />
                <button
                  className="send-button"
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isTyping}
                >
                  ↑
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// Render
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
