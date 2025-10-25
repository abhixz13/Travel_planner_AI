import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const sendChatMessage = async (message, conversationId = null) => {
  try {
    const response = await api.post('/api/chat', {
      message,
      conversation_id: conversationId,
    });
    return response.data;
  } catch (error) {
    console.error('Error sending chat message:', error);
    throw error;
  }
};

export const refineItinerary = async (conversationId, action, params = {}) => {
  try {
    const response = await api.post('/api/refine', {
      conversation_id: conversationId,
      action,
      ...params,
    });
    return response.data;
  } catch (error) {
    console.error('Error refining itinerary:', error);
    throw error;
  }
};

export const checkHealth = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    console.error('Error checking health:', error);
    throw error;
  }
};

export default {
  sendChatMessage,
  refineItinerary,
  checkHealth,
};