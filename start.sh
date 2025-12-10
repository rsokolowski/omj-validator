#!/bin/bash
# Development startup script using Docker Compose
# Starts PostgreSQL, FastAPI backend, and Next.js frontend

set -e
cd "$(dirname "$0")"

# Parse arguments
BACKEND_ONLY=false
FRONTEND_ONLY=false
BUILD=false

for arg in "$@"; do
    case $arg in
        --backend-only)
            BACKEND_ONLY=true
            ;;
        --frontend-only)
            FRONTEND_ONLY=true
            ;;
        --build)
            BUILD=true
            ;;
        --help|-h)
            echo "Usage: ./start.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backend-only   Start only PostgreSQL and FastAPI backend"
            echo "  --frontend-only  Start only Next.js frontend (requires backend running)"
            echo "  --build          Force rebuild of Docker images"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./start.sh                    # Start full stack"
            echo "  ./start.sh --build            # Rebuild and start full stack"
            echo "  ./start.sh --backend-only     # Start DB + API only"
            echo ""
            echo "To stop: docker compose down"
            echo "To stop and remove data: docker compose down -v"
            exit 0
            ;;
    esac
done

# Check for .env file
if [ ! -f .env ]; then
    echo "ERROR: .env file not found."
    echo "Create one based on .env.example or copy the existing .env file."
    exit 1
fi

# Check for required GEMINI_API_KEY (must be non-empty and not commented)
if ! grep -qE "^GEMINI_API_KEY=.+" .env 2>/dev/null; then
    echo "ERROR: GEMINI_API_KEY is not set in .env file."
    exit 1
fi

# Create data directories and files if they don't exist
mkdir -p data/uploads data/tasks
touch data/skills.json 2>/dev/null || true

# Build arguments
BUILD_ARG=""
if [ "$BUILD" = true ]; then
    BUILD_ARG="--build"
fi

# Determine which services to start
if [ "$FRONTEND_ONLY" = true ]; then
    SERVICES="frontend"
elif [ "$BACKEND_ONLY" = true ]; then
    SERVICES="db api"
else
    SERVICES=""  # Empty means all services
fi

echo "=== OMJ Validator Development ==="
echo ""

# Start services
if [ -n "$SERVICES" ]; then
    echo "Starting services: $SERVICES"
    docker compose up $BUILD_ARG $SERVICES
else
    echo "Starting all services..."
    echo ""
    echo "Frontend: http://localhost:3000"
    echo "Backend:  http://localhost:8000"
    echo "Database: localhost:5433"
    echo ""
    echo "Press Ctrl+C to stop all services"
    echo "================================"
    echo ""
    docker compose up $BUILD_ARG
fi
