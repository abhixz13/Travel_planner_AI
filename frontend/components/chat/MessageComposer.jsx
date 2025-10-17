'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

export function MessageComposer({ onSend, isStreaming, disabled }) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef(null);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!message.trim() || isStreaming || disabled) return;

    onSend(message.trim());
    setMessage('');
    
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e) => {
    setMessage(e.target.value);
    
    // Auto-resize textarea
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  };

  useEffect(() => {
    if (!isStreaming && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isStreaming]);

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="relative flex items-end gap-2">
        <div className="relative flex-1">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask me about flights, hotels, activities, or anything about your trip..."
            disabled={isStreaming || disabled}
            className={cn(
              "min-h-[60px] max-h-[200px] resize-none pr-12 transition-all",
              "focus-visible:ring-2 focus-visible:ring-primary"
            )}
            rows={1}
          />
          <div className="absolute bottom-2 right-2 text-xs text-muted-foreground">
            {isStreaming ? (
              <span className="flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                AI is thinking...
              </span>
            ) : (
              <span className="opacity-50">⌘ + Enter to send</span>
            )}
          </div>
        </div>
        <Button
          type="submit"
          size="icon"
          disabled={!message.trim() || isStreaming || disabled}
          className="h-[60px] w-12 shrink-0"
        >
          {isStreaming ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Send className="h-5 w-5" />
          )}
        </Button>
      </div>
    </form>
  );
}
