// User Model
export const createUser = (data) => ({
  userId: data.userId,
  email: data.email,
  name: data.name,
  image: data.image,
  provider: data.provider || 'google',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
});

// Chat Session Model
export const createChatSession = (data) => ({
  sessionId: data.sessionId,
  userId: data.userId,
  title: data.title || 'New Trip',
  messages: data.messages || [],
  tripContext: data.tripContext || {
    origin: null,
    destination: null,
    startDate: null,
    endDate: null,
    travelers: 1,
    budget: null,
  },
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
});

// Itinerary Model
export const createItinerary = (data) => ({
  itineraryId: data.itineraryId,
  userId: data.userId,
  sessionId: data.sessionId,
  title: data.title,
  origin: data.origin,
  destination: data.destination,
  startDate: data.startDate,
  endDate: data.endDate,
  travel: data.travel || null,
  stays: data.stays || null,
  activities: data.activities || null,
  notes: data.notes || '',
  tags: data.tags || [],
  coverImage: data.coverImage || null,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
});
