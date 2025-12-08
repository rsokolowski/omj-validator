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

# Create data directory if it doesn't exist
mkdir -p data

# Start PostgreSQL if not running
if ! docker ps --format '{{.Names}}' | grep -q '^omj-postgres$'; then
    echo "Starting PostgreSQL container..."
    docker compose up -d db
    echo "Waiting for PostgreSQL to be ready..."
    TIMEOUT=30
    COUNT=0
    until docker compose exec -T db pg_isready -U omj -d omj > /dev/null 2>&1; do
        sleep 1
        ((COUNT++))
        if [ $COUNT -ge $TIMEOUT ]; then
            echo "ERROR: PostgreSQL failed to start within ${TIMEOUT} seconds."
            exit 1
        fi
    done
    echo "PostgreSQL is ready."
fi

# Run database migrations
echo "Running database migrations..."
alembic upgrade head
if [ $? -ne 0 ]; then
    echo "ERROR: Database migration failed. Please check the logs."
    exit 1
fi

echo "Starting OMJ Validator on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
