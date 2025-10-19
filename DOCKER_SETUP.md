# Docker Backend Setup and Real-Time Monitoring

## Overview
The Travel Planner backend has been successfully configured to run in Docker with real-time monitoring of user interactions.

## What Was Set Up

### 1. Docker Configuration
- **Dockerfile**: Multi-stage build optimized for Python 3.11
  - Health checks on `/health` endpoint
  - Runs as non-root user (appuser)
  - Exposes port 8000

- **docker-compose.yml**: Container orchestration
  - Service name: `backend`
  - Container name: `travel_planner_backend`
  - Port mapping: `8000:8000`
  - Environment variable support via `.env` file
  - Volume mount for logs: `./logs:/app/logs`
  - Auto-restart policy: `unless-stopped`

### 2. Real-Time Monitoring Implementation
Added comprehensive monitoring middleware in `api_server.py`:

**UserInteractionMonitoringMiddleware** tracks:
- Incoming HTTP requests (method, path, client IP)
- Request bodies for `/api/chat` and `/api/refine` endpoints
- Response status codes
- Processing time for each request
- Error tracking with detailed logging

**Logging Output**:
- Console logging (stdout)
- File logging to `/app/logs/user_interactions.log`
- Timestamped format: `YYYY-MM-DD HH:MM:SS | LEVEL | MESSAGE`

**Example Log Format**:
```
>>> INCOMING REQUEST | POST /api/chat | Client: 172.18.0.1
    Chat Request | ConvID: abc123 | Message: Hello backend test...
<<< RESPONSE | POST /api/chat | Status: 200 | Time: 1.234s | Client: 172.18.0.1
```

### 3. Enhanced Health Endpoint
The `/health` endpoint now returns:
```json
{
  "status": "healthy",
  "service": "travel-planner-api",
  "active_conversations": 0,
  "monitoring": "enabled"
}
```

## Usage

### Starting the Backend
```bash
docker-compose up -d --build backend
```

### Checking Status
```bash
# View container status
docker-compose ps backend

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f backend

# View monitoring logs inside container
docker exec travel_planner_backend cat logs/user_interactions.log
```

### Stopping the Backend
```bash
docker-compose down
```

### Rebuilding After Code Changes
```bash
docker-compose up -d --build backend
```

## API Endpoints

1. **Health Check**
   - `GET /health` - Returns service health status
   - `GET /healthz` - Kubernetes-style health check

2. **Chat API**
   - `POST /api/chat` - Process user chat messages
   - Body: `{"message": "...", "conversation_id": "..."}`

3. **Refinement API**
   - `POST /api/refine` - Handle itinerary refinement requests
   - Actions: `select_hotel`, `swap_activity`

4. **Root**
   - `GET /` - Service information and API docs link

## Monitoring Features

### Real-Time Tracking
- Every request is logged with timestamp
- Client IP addresses tracked
- Request/response timing measured
- Conversation IDs logged for debugging
- Error stack traces captured

### Performance Metrics
- Processing time added to response headers (`X-Process-Time`)
- Active conversation count in health endpoint
- Request/response correlation

## Current Status

✅ Backend running in Docker container
✅ Port 8000 exposed and accessible
✅ Health checks passing
✅ Real-time monitoring middleware active
✅ Logs directory mounted and accessible
✅ Environment variables loaded from .env
✅ CORS enabled for frontend connectivity

## Testing

Test requests processed successfully:
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip to Paris"}'
```

Both endpoints responding correctly with monitoring active.

## Next Steps

To view monitoring in action:
1. Send requests to `/api/chat` or `/api/refine`
2. Monitor docker logs: `docker-compose logs -f backend`
3. Check the mounted logs directory: `./logs/user_interactions.log`
4. Access FastAPI docs: `http://localhost:8000/docs`

## Architecture

```
Client Request
    ↓
UserInteractionMonitoringMiddleware (logs incoming)
    ↓
FastAPI App (processes request)
    ↓
UserInteractionMonitoringMiddleware (logs response + timing)
    ↓
Response to Client
```

All interactions are logged in real-time to both console and file for comprehensive monitoring and debugging.
