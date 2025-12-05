#!/bin/bash
cd "$(dirname "$0")"

# Kill any existing process on port 8000
PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Stopping existing server (PID: $PID)..."
    kill $PID 2>/dev/null
    sleep 1
fi

source venv/bin/activate
echo "Starting OMJ Validator on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
