import { NextResponse } from 'next/server';
import { getDatabase } from '@/lib/db/mongodb';
import { v4 as uuidv4 } from 'uuid';
import { createChatSession, createItinerary } from '@/lib/db/models';

// Health check endpoint
export async function GET(request) {
  const { pathname } = new URL(request.url);

  // Root health check
  if (pathname === '/api' || pathname === '/api/') {
    return NextResponse.json({ 
      status: 'ok',
      message: 'Trip Planner API is running',
      timestamp: new Date().toISOString()
    });
  }

  // Get chat sessions
  if (pathname === '/api/sessions') {
    try {
      const db = await getDatabase();
      const sessions = await db.collection('sessions')
        .find({})
        .sort({ updatedAt: -1 })
        .limit(20)
        .toArray();
      
      return NextResponse.json({ sessions });
    } catch (error) {
      console.error('Error fetching sessions:', error);
      return NextResponse.json(
        { error: 'Failed to fetch sessions' },
        { status: 500 }
      );
    }
  }

  // Get itineraries
  if (pathname === '/api/itineraries') {
    try {
      const db = await getDatabase();
      const itineraries = await db.collection('itineraries')
        .find({})
        .sort({ updatedAt: -1 })
        .toArray();
      
      return NextResponse.json({ itineraries });
    } catch (error) {
      console.error('Error fetching itineraries:', error);
      return NextResponse.json(
        { error: 'Failed to fetch itineraries' },
        { status: 500 }
      );
    }
  }

  // Get single itinerary
  const itineraryMatch = pathname.match(/^\/api\/itineraries\/([^/]+)$/);
  if (itineraryMatch) {
    try {
      const itineraryId = itineraryMatch[1];
      const db = await getDatabase();
      const itinerary = await db.collection('itineraries').findOne({ itineraryId });
      
      if (!itinerary) {
        return NextResponse.json(
          { error: 'Itinerary not found' },
          { status: 404 }
        );
      }
      
      return NextResponse.json({ itinerary });
    } catch (error) {
      console.error('Error fetching itinerary:', error);
      return NextResponse.json(
        { error: 'Failed to fetch itinerary' },
        { status: 500 }
      );
    }
  }

  return NextResponse.json(
    { error: 'Not found' },
    { status: 404 }
  );
}

// Create session or itinerary
export async function POST(request) {
  try {
    const { pathname } = new URL(request.url);
    const body = await request.json();

    // Create new chat session
    if (pathname === '/api/sessions') {
      const db = await getDatabase();
      const session = createChatSession({
        sessionId: uuidv4(),
        userId: body.userId || 'anonymous',
        title: body.title || 'New Trip',
        messages: [],
        tripContext: body.tripContext || {},
      });

      await db.collection('sessions').insertOne(session);
      return NextResponse.json({ session }, { status: 201 });
    }

    // Save message to session
    if (pathname === '/api/sessions/message') {
      const db = await getDatabase();
      const { sessionId, message } = body;

      if (!sessionId || !message) {
        return NextResponse.json(
          { error: 'Session ID and message are required' },
          { status: 400 }
        );
      }

      await db.collection('sessions').updateOne(
        { sessionId },
        {
          $push: { messages: message },
          $set: { updatedAt: new Date().toISOString() },
        }
      );

      return NextResponse.json({ success: true });
    }

    // Create new itinerary
    if (pathname === '/api/itineraries') {
      const db = await getDatabase();
      const itinerary = createItinerary({
        itineraryId: uuidv4(),
        userId: body.userId || 'anonymous',
        sessionId: body.sessionId,
        title: body.title || 'My Trip',
        origin: body.origin,
        destination: body.destination,
        startDate: body.startDate,
        endDate: body.endDate,
        travel: body.travel,
        stays: body.stays,
        activities: body.activities,
        notes: body.notes || '',
      });

      await db.collection('itineraries').insertOne(itinerary);
      return NextResponse.json({ itinerary }, { status: 201 });
    }

    return NextResponse.json(
      { error: 'Not found' },
      { status: 404 }
    );
  } catch (error) {
    console.error('POST error:', error);
    return NextResponse.json(
      { error: 'Failed to process request' },
      { status: 500 }
    );
  }
}

// Update itinerary
export async function PATCH(request) {
  try {
    const { pathname } = new URL(request.url);
    const body = await request.json();

    const itineraryMatch = pathname.match(/^\/api\/itineraries\/([^/]+)$/);
    if (itineraryMatch) {
      const itineraryId = itineraryMatch[1];
      const db = await getDatabase();

      const updateData = { ...body };
      delete updateData.itineraryId;
      updateData.updatedAt = new Date().toISOString();

      await db.collection('itineraries').updateOne(
        { itineraryId },
        { $set: updateData }
      );

      const updated = await db.collection('itineraries').findOne({ itineraryId });
      return NextResponse.json({ itinerary: updated });
    }

    return NextResponse.json(
      { error: 'Not found' },
      { status: 404 }
    );
  } catch (error) {
    console.error('PATCH error:', error);
    return NextResponse.json(
      { error: 'Failed to update' },
      { status: 500 }
    );
  }
}

// Delete itinerary
export async function DELETE(request) {
  try {
    const { pathname } = new URL(request.url);

    const itineraryMatch = pathname.match(/^\/api\/itineraries\/([^/]+)$/);
    if (itineraryMatch) {
      const itineraryId = itineraryMatch[1];
      const db = await getDatabase();

      await db.collection('itineraries').deleteOne({ itineraryId });
      return NextResponse.json({ success: true });
    }

    return NextResponse.json(
      { error: 'Not found' },
      { status: 404 }
    );
  } catch (error) {
    console.error('DELETE error:', error);
    return NextResponse.json(
      { error: 'Failed to delete' },
      { status: 500 }
    );
  }
}
