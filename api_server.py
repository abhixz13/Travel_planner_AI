"""
FastAPI server for Travel Planner backend.
Provides REST API endpoints for the Streamlit UI.
"""

import os
import uuid
import logging
import time
import json
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path

from core.logging_config import configure_logging
from core.conversation_manager import (
    initiate_conversation,
    handle_user_input,
    get_conversation_history
)
from core.orchestrator import run_session

# Load environment variables
load_dotenv()
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
configure_logging()

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logs directory if it doesn't exist
logs_dir = Path("/app/logs" if os.path.exists("/app") else "logs")
logs_dir.mkdir(exist_ok=True)

# Set up file handler for monitoring logs
monitoring_handler = logging.FileHandler(logs_dir / "user_interactions.log")
monitoring_handler.setLevel(logging.INFO)
monitoring_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
monitoring_handler.setFormatter(monitoring_formatter)

# Create separate logger for user interactions
interaction_logger = logging.getLogger("user_interactions")
interaction_logger.setLevel(logging.INFO)
interaction_logger.addHandler(monitoring_handler)
interaction_logger.addHandler(logging.StreamHandler())  # Also log to console


# Real-time monitoring middleware
class UserInteractionMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to monitor and log all user interactions in real-time."""

    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()

        # Extract client info
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        # Log incoming request
        interaction_logger.info(
            f">>> INCOMING REQUEST | {method} {path} | Client: {client_host}"
        )

        # Try to capture request body for monitoring (only for POST requests)
        request_body = None
        if method == "POST" and path in ["/api/chat", "/api/refine"]:
            try:
                body_bytes = await request.body()
                request_body = json.loads(body_bytes.decode())

                # Log request details
                if path == "/api/chat":
                    conv_id = request_body.get("conversation_id", "new")
                    message_preview = request_body.get("message", "")[:100]
                    interaction_logger.info(
                        f"    Chat Request | ConvID: {conv_id} | Message: {message_preview}..."
                    )
                elif path == "/api/refine":
                    conv_id = request_body.get("conversation_id", "unknown")
                    action = request_body.get("action", "unknown")
                    interaction_logger.info(
                        f"    Refine Request | ConvID: {conv_id} | Action: {action}"
                    )

                # Reconstruct request with body
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive

            except Exception as e:
                interaction_logger.warning(f"    Could not parse request body: {e}")

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code

            # Calculate processing time
            process_time = time.time() - start_time

            # Log response
            interaction_logger.info(
                f"<<< RESPONSE | {method} {path} | Status: {status_code} | "
                f"Time: {process_time:.3f}s | Client: {client_host}"
            )

            # Add processing time header
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except Exception as e:
            process_time = time.time() - start_time
            interaction_logger.error(
                f"!!! ERROR | {method} {path} | Error: {str(e)} | "
                f"Time: {process_time:.3f}s | Client: {client_host}"
            )
            raise


# Initialize FastAPI app
app = FastAPI(
    title="Travel Planner API",
    description="AI-powered travel planning assistant",
    version="1.0.0"
)

# Add monitoring middleware (before CORS)
app.add_middleware(UserInteractionMonitoringMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for conversation states
conversations: Dict[str, Any] = {}


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    itinerary: Optional[Dict[str, Any]] = None


class RefineRequest(BaseModel):
    conversation_id: str
    action: str
    hotel_index: Optional[int] = None
    day_number: Optional[int] = None
    time_slot: Optional[str] = None
    reason: Optional[str] = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    active_conversations = len(conversations)
    return {
        "status": "healthy",
        "service": "travel-planner-api",
        "active_conversations": active_conversations,
        "monitoring": "enabled"
    }


@app.get("/healthz")
async def healthz():
    """Kubernetes-style health check."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Handle chat messages from the user.

    Args:
        request: Chat request with message and optional conversation_id

    Returns:
        ChatResponse with AI response and conversation state
    """
    logger.info(f"Received chat request: conversation_id={request.conversation_id}, message={request.message[:50]}...")
    try:
        # Get or create conversation
        conversation_id = request.conversation_id or str(uuid.uuid4())
        logger.info(f"Using conversation_id: {conversation_id}")

        if conversation_id not in conversations:
            # Initialize new conversation
            state = initiate_conversation(
                system_prompt="You are an AI travel planner assistant. Be helpful and engaging."
            )
            conversations[conversation_id] = state
        else:
            state = conversations[conversation_id]

        # Process user input
        state = handle_user_input(state, request.message)

        # Run the AI session
        state = run_session(state)

        # Update stored state
        conversations[conversation_id] = state

        # Extract response
        history = get_conversation_history(state)
        last_ai_message = ""
        if history:
            last_ai_message = next(
                (msg['content'] for msg in reversed(history) if msg['role'] == 'assistant'),
                ""
            )

        # Extract itinerary if available
        itinerary = None
        if hasattr(state, 'itinerary') and state.itinerary:
            itinerary = state.itinerary
        elif isinstance(state, dict) and 'itinerary' in state:
            itinerary = state['itinerary']

        return ChatResponse(
            conversation_id=conversation_id,
            message=last_ai_message,
            metadata={},
            itinerary=itinerary
        )

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


@app.post("/api/refine")
async def refine(request: RefineRequest):
    """
    Handle itinerary refinement requests (hotel selection, activity swapping).

    Args:
        request: Refinement request with action and parameters

    Returns:
        Updated conversation state and itinerary
    """
    logger.info(f"Received refine request: action={request.action}, conversation_id={request.conversation_id}")
    try:
        if request.conversation_id not in conversations:
            logger.error(f"Conversation not found: {request.conversation_id}")
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )

        state = conversations[request.conversation_id]

        # Build refinement message
        if request.action == "select_hotel":
            message = f"I'd like to select hotel option {request.hotel_index}"
            logger.info(f"Hotel selection: index={request.hotel_index}")
        elif request.action == "swap_activity":
            reason_text = f" because {request.reason}" if request.reason else ""
            message = f"Can you suggest a different {request.time_slot} activity for day {request.day_number}{reason_text}?"
            logger.info(f"Activity swap: day={request.day_number}, slot={request.time_slot}")
        else:
            logger.error(f"Unknown action: {request.action}")
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {request.action}"
            )

        # Process refinement as a regular message
        logger.info(f"Processing refinement message: {message}")
        state = handle_user_input(state, message)
        state = run_session(state)
        conversations[request.conversation_id] = state
        logger.info("Refinement processed successfully")

        # Extract response
        history = get_conversation_history(state)
        last_ai_message = ""
        if history:
            last_ai_message = next(
                (msg['content'] for msg in reversed(history) if msg['role'] == 'assistant'),
                ""
            )

        # Extract itinerary
        itinerary = None
        if hasattr(state, 'itinerary') and state.itinerary:
            itinerary = state.itinerary
        elif isinstance(state, dict) and 'itinerary' in state:
            itinerary = state['itinerary']

        return {
            "conversation_id": request.conversation_id,
            "message": last_ai_message,
            "itinerary": itinerary
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in refine endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing refinement: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Travel Planner API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
