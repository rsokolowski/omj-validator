#!/bin/bash
cd "$(dirname "$0")"

# Parse arguments
BACKEND_ONLY=false
FRONTEND_ONLY=false
for arg in "$@"; do
    case $arg in
        --backend-only)
            BACKEND_ONLY=true
            ;;
        --frontend-only)
            FRONTEND_ONLY=true
            ;;
    esac
done

# Kill any existing process on port 8000
if [ "$FRONTEND_ONLY" = false ]; then
    PID=$(lsof -ti:8000 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "Stopping existing backend server (PID: $PID)..."
        kill $PID 2>/dev/null
        sleep 1
    fi
fi

# Kill any existing process on port 3000
if [ "$BACKEND_ONLY" = false ]; then
    PID=$(lsof -ti:3000 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "Stopping existing frontend server (PID: $PID)..."
        kill $PID 2>/dev/null
        sleep 1
    fi
fi

# Backend setup
if [ "$FRONTEND_ONLY" = false ]; then
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
fi

# Start frontend
if [ "$BACKEND_ONLY" = false ]; then
    echo "Starting Next.js frontend on http://localhost:3000"
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "Installing frontend dependencies..."
        npm install
    fi
    if [ "$FRONTEND_ONLY" = true ]; then
        npm run dev
        exit 0
    else
        npm run dev &
        FRONTEND_PID=$!
        cd ..
    fi
fi

# Start backend
if [ "$FRONTEND_ONLY" = false ]; then
    echo "Starting FastAPI backend on http://localhost:8000"
    echo ""
    echo "=== OMJ Validator ==="
    echo "Frontend: http://localhost:3000"
    echo "Backend:  http://localhost:8000"
    echo "====================="
    echo ""
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fi
