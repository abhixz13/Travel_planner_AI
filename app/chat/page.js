'use client';

import { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Plus, Menu, Save, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { MessageComposer } from '@/components/chat/MessageComposer';
import { TripSummaryPanel } from '@/components/trip/TripSummaryPanel';
import { useToast } from '@/hooks/use-toast';
import { Toaster } from '@/components/ui/toaster';

export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId] = useState(() => uuidv4());
  const [tripContext, setTripContext] = useState({
    origin: null,
    destination: null,
    startDate: null,
    endDate: null,
    travelers: 1,
    budget: null,
  });
  const [showSidebar, setShowSidebar] = useState(true);
  const scrollAreaRef = useRef(null);
  const messagesEndRef = useRef(null);
  const { toast } = useToast();

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send welcome message on mount
  useEffect(() => {
    const welcomeMessage = {
      role: 'assistant',
      content: "👋 Welcome to your AI Trip Planner! I'm here to help you plan the perfect trip.\n\nTo get started, tell me:\n• Where are you traveling from?\n• Where would you like to go?\n• When are you planning to travel?\n• How many people are traveling?\n\nOr just ask me anything about your trip!",
      timestamp: new Date().toISOString(),
    };
    setMessages([welcomeMessage]);
  }, []);

  const handleSendMessage = async (content) => {
    if (!content.trim()) return;

    // Add user message
    const userMessage = {
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    // Start streaming
    setIsStreaming(true);

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          sessionId,
          context: tripContext,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let assistantMessage = {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      };
      let currentToolResult = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(line => line.trim() !== '');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            if (data === '[DONE]') {
              break;
            }

            try {
              const parsed = JSON.parse(data);

              if (parsed.type === 'content') {
                assistantMessage.content += parsed.content;
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMessage = newMessages[newMessages.length - 1];
                  if (lastMessage?.role === 'assistant' && !lastMessage.toolResult) {
                    newMessages[newMessages.length - 1] = { ...assistantMessage };
                  } else {
                    newMessages.push({ ...assistantMessage });
                  }
                  return newMessages;
                });
              } else if (parsed.type === 'tool') {
                currentToolResult = parsed.content;
                const toolMessage = {
                  role: 'tool',
                  toolResult: currentToolResult,
                  timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, toolMessage]);
              } else if (parsed.type === 'error') {
                throw new Error(parsed.error);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }

      toast({
        title: "Response received",
        description: "I've analyzed your request. Let me know if you need anything else!",
      });
    } catch (error) {
      console.error('Error streaming message:', error);
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to get response. Please try again.",
      });

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: "I apologize, but I encountered an error. Please try again.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSaveToItinerary = (item) => {
    toast({
      title: "Saved to itinerary",
      description: `"${item.title}" has been added to your trip.`,
    });
  };

  const handleNewChat = () => {
    setMessages([{
      role: 'assistant',
      content: "👋 Starting a new trip plan! Tell me where you'd like to go.",
      timestamp: new Date().toISOString(),
    }]);
    setTripContext({
      origin: null,
      destination: null,
      startDate: null,
      endDate: null,
      travelers: 1,
      budget: null,
    });
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      {showSidebar && (
        <div className="w-80 border-r bg-muted/20 flex flex-col">
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Trip Planner
            </h2>
          </div>
          <div className="flex-1 p-4 overflow-auto">
            <TripSummaryPanel tripContext={tripContext} />
          </div>
          <div className="p-4 border-t space-y-2">
            <Button onClick={handleNewChat} className="w-full" variant="outline">
              <Plus className="h-4 w-4 mr-2" />
              New Trip
            </Button>
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b p-4 flex items-center justify-between bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowSidebar(!showSidebar)}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-lg font-semibold">AI Trip Assistant</h1>
              <p className="text-sm text-muted-foreground">
                Ask me anything about your trip
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm">
            <Save className="h-4 w-4 mr-2" />
            Save Itinerary
          </Button>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1" ref={scrollAreaRef}>
          <div className="max-w-4xl mx-auto">
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted-foreground p-8">
                <div className="text-center space-y-3">
                  <Sparkles className="h-12 w-12 mx-auto text-primary" />
                  <h3 className="text-lg font-medium">Start planning your trip</h3>
                  <p className="text-sm">Ask me about destinations, flights, hotels, or activities</p>
                </div>
              </div>
            ) : (
              <div className="space-y-0">
                {messages.map((message, idx) => (
                  <ChatMessage
                    key={idx}
                    message={message}
                    onSaveToItinerary={handleSaveToItinerary}
                  />
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Composer */}
        <div className="border-t p-4 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="max-w-4xl mx-auto">
            <MessageComposer
              onSend={handleSendMessage}
              isStreaming={isStreaming}
            />
            <div className="mt-2 text-xs text-muted-foreground text-center">
              Powered by AI • Currently using mock streaming (ready for Claude integration)
            </div>
          </div>
        </div>
      </div>

      <Toaster />
    </div>
  );
}
