'use client';

import { useState } from 'react';
import { Copy, Check, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ResultCard } from './ResultCard';

export function ChatMessage({ message, onSaveToItinerary }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  const isTool = message.role === 'tool';

  return (
    <div
      className={cn(
        'group relative flex gap-4 px-4 py-6 hover:bg-muted/30 transition-colors',
        isUser && 'flex-row-reverse'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
        )}
      >
        {isUser ? 'U' : '🤖'}
      </div>

      {/* Content */}
      <div className="flex-1 space-y-3 overflow-hidden">
        {/* Text content */}
        {(isUser || isAssistant) && (
          <div
            className={cn(
              'prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap break-words',
              isUser && 'text-right'
            )}
          >
            {message.content}
          </div>
        )}

        {/* Tool results (cards) */}
        {isTool && message.toolResult && (
          <div className="space-y-4">
            {message.toolResult.summary && (
              <div className="text-sm font-medium text-muted-foreground">
                {message.toolResult.summary}
              </div>
            )}
            {message.toolResult.results && (
              <div className="grid gap-3">
                {message.toolResult.results.map((result, idx) => (
                  <ResultCard
                    key={idx}
                    result={result}
                    onSave={() => onSaveToItinerary?.(result)}
                  />
                ))}
              </div>
            )}
            {message.toolResult.followUp && (
              <div className="text-sm text-muted-foreground italic pt-2">
                {message.toolResult.followUp}
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        {isAssistant && (
          <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleCopy}
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
