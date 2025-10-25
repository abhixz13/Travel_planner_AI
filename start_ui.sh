#!/bin/bash

# Start script for Travel Planner Streamlit UI
# This script starts both the backend API and Streamlit UI

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  AI Travel Planner Startup     ${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/upgrade dependencies
echo -e "${GREEN}Checking dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt 2>/dev/null || echo "requirements.txt not found, skipping..."
pip install -q streamlit fastapi uvicorn python-dotenv requests

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}Creating .env from .env.example${NC}"
        cp .env.example .env
        echo -e "${YELLOW}Please edit .env with your API keys${NC}"
    fi
fi

# Kill any existing processes on ports 8000 and 8501
echo -e "${GREEN}Checking for existing processes...${NC}"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8501 | xargs kill -9 2>/dev/null || true

# Start backend API in background
echo -e "${GREEN}Starting backend API on port 8000...${NC}"
python api_server.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo -e "${GREEN}Waiting for backend to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is ready!${NC}"
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

# Check if backend started successfully
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Backend may not be fully ready${NC}"
    echo -e "${YELLOW}Check logs/backend.log for details${NC}"
fi

# Start Streamlit UI
echo -e "${GREEN}Starting Streamlit UI on port 8501...${NC}"
echo ""
echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}✓ Services Started Successfully!${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo -e "Backend API:     ${GREEN}http://localhost:8000${NC}"
echo -e "Streamlit UI:    ${GREEN}http://localhost:8501${NC}"
echo -e "Backend Logs:    logs/backend.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Trap Ctrl+C to cleanup
trap "echo ''; echo 'Shutting down services...'; kill $BACKEND_PID 2>/dev/null || true; echo 'All services stopped'; exit" INT TERM

# Start Streamlit (this will block until Ctrl+C)
streamlit run streamlit_UI/app.py --server.port 8501 --server.headless true

# Cleanup on exit (if script ends normally)
echo ""
echo -e "${YELLOW}Shutting down services...${NC}"
kill $BACKEND_PID 2>/dev/null || true
echo -e "${GREEN}✓ All services stopped${NC}"
