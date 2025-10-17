'use client';

import { useState } from 'react';
import { Plus, Check, ExternalLink, Star } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export function ResultCard({ result, onSave }) {
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    onSave?.();
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <Card className="hover:shadow-md transition-all hover:border-primary/50 group">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1 flex-1">
            <CardTitle className="text-base leading-tight">{result.title}</CardTitle>
            {result.snippet && (
              <CardDescription className="text-sm">{result.snippet}</CardDescription>
            )}
          </div>
          {result.rating && (
            <Badge variant="secondary" className="shrink-0">
              <Star className="h-3 w-3 mr-1 fill-yellow-400 text-yellow-400" />
              {result.rating}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="pb-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {result.price && (
            <Badge variant="outline" className="font-semibold">
              {result.price}
            </Badge>
          )}
          {result.duration && (
            <Badge variant="outline">
              ⏱️ {result.duration}
            </Badge>
          )}
        </div>
      </CardContent>

      <CardFooter className="flex gap-2 pt-3 border-t">
        <Button
          variant={saved ? "default" : "outline"}
          size="sm"
          className={cn(
            "flex-1 transition-all",
            saved && "bg-green-600 hover:bg-green-700"
          )}
          onClick={handleSave}
        >
          {saved ? (
            <>
              <Check className="h-4 w-4 mr-2" />
              Saved
            </>
          ) : (
            <>
              <Plus className="h-4 w-4 mr-2" />
              Add to Itinerary
            </>
          )}
        </Button>
        {result.url && result.url !== '#' && (
          <Button variant="ghost" size="sm" asChild>
            <a href={result.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
