'use client';

import { MapPin, Calendar, Users, DollarSign } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';

export function TripSummaryPanel({ tripContext }) {
  const { origin, destination, startDate, endDate, travelers, budget } = tripContext || {};

  const hasAnyData = origin || destination || startDate || endDate || travelers > 1 || budget;

  if (!hasAnyData) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-lg">Trip Details</CardTitle>
          <CardDescription>
            Start chatting to plan your trip
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground space-y-2">
            <p>👋 Tell me about your travel plans and I'll help you organize everything!</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-lg">Your Trip</CardTitle>
        <CardDescription>
          Current planning details
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {origin && (
          <div className="flex items-start gap-3">
            <MapPin className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium">From</div>
              <div className="text-sm text-muted-foreground">{origin}</div>
            </div>
          </div>
        )}

        {destination && (
          <div className="flex items-start gap-3">
            <MapPin className="h-5 w-5 text-primary mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium">To</div>
              <div className="text-sm text-muted-foreground">{destination}</div>
            </div>
          </div>
        )}

        {(startDate || endDate) && (
          <>
            <Separator />
            <div className="flex items-start gap-3">
              <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-medium">Dates</div>
                <div className="text-sm text-muted-foreground">
                  {startDate && new Date(startDate).toLocaleDateString()}
                  {startDate && endDate && ' - '}
                  {endDate && new Date(endDate).toLocaleDateString()}
                </div>
              </div>
            </div>
          </>
        )}

        {travelers > 0 && (
          <div className="flex items-start gap-3">
            <Users className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium">Travelers</div>
              <div className="text-sm text-muted-foreground">
                {travelers} {travelers === 1 ? 'person' : 'people'}
              </div>
            </div>
          </div>
        )}

        {budget && (
          <div className="flex items-start gap-3">
            <DollarSign className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium">Budget</div>
              <div className="text-sm text-muted-foreground">{budget}</div>
            </div>
          </div>
        )}

        <Separator />

        <div className="space-y-2">
          <div className="text-sm font-medium">Quick Actions</div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="cursor-pointer hover:bg-muted">
              ✈️ Flights
            </Badge>
            <Badge variant="outline" className="cursor-pointer hover:bg-muted">
              🏨 Hotels
            </Badge>
            <Badge variant="outline" className="cursor-pointer hover:bg-muted">
              🎯 Activities
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
