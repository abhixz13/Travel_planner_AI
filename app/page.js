'use client';

import { ArrowRight, Sparkles, MapPin, Calendar, Plane } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20">
      {/* Header */}
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2 font-bold text-xl">
            <Sparkles className="h-6 w-6 text-primary" />
            <span>TripMate</span>
          </div>
          <nav className="flex items-center gap-4">
            <Link href="/chat">
              <Button variant="ghost">Sign In</Button>
            </Link>
            <Link href="/chat">
              <Button>
                Get Started
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border bg-muted/50 text-sm">
            <Sparkles className="h-4 w-4 text-primary" />
            <span>AI-Powered Trip Planning</span>
          </div>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight">
            Plan Your Perfect Trip
            <br />
            <span className="text-primary">With AI Assistance</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Chat with our AI assistant to discover destinations, find flights, book hotels,
            and create personalized itineraries—all in one place.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link href="/chat">
              <Button size="lg" className="text-lg px-8">
                Start Planning
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Button size="lg" variant="outline" className="text-lg px-8">
              Watch Demo
            </Button>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-20">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">
            Everything You Need in One Place
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            <Card className="border-2 hover:border-primary/50 transition-all hover:shadow-lg">
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Plane className="h-6 w-6 text-primary" />
                </div>
                <CardTitle>Smart Travel Search</CardTitle>
                <CardDescription>
                  Find the best flights, hotels, and activities with AI-powered recommendations
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-2 hover:border-primary/50 transition-all hover:shadow-lg">
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Calendar className="h-6 w-6 text-primary" />
                </div>
                <CardTitle>Personalized Itineraries</CardTitle>
                <CardDescription>
                  Create and save custom itineraries tailored to your preferences and budget
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="border-2 hover:border-primary/50 transition-all hover:shadow-lg">
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <MapPin className="h-6 w-6 text-primary" />
                </div>
                <CardTitle>Real-Time Chat</CardTitle>
                <CardDescription>
                  Chat naturally with AI to refine your plans and get instant recommendations
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-4 py-20">
        <Card className="max-w-4xl mx-auto bg-primary text-primary-foreground border-0">
          <CardContent className="p-12 text-center space-y-6">
            <h2 className="text-3xl font-bold">Ready to Start Your Journey?</h2>
            <p className="text-lg opacity-90">
              Join thousands of travelers who use AI to plan their perfect trips.
            </p>
            <Link href="/chat">
              <Button size="lg" variant="secondary" className="text-lg px-8">
                Start Planning Now
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>© 2024 TripMate. AI-powered trip planning made easy.</p>
        </div>
      </footer>
    </div>
  );
}
