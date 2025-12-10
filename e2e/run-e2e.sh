#!/bin/bash
#
# E2E Test Runner Script
#
# Usage:
#   ./run-e2e.sh              # Run all tests
#   ./run-e2e.sh --headed     # Run with browser visible
#   ./run-e2e.sh --ui         # Run with Playwright UI
#   ./run-e2e.sh --debug      # Run in debug mode
#   ./run-e2e.sh navigation   # Run specific test file
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}OMJ Validator E2E Tests${NC}"
echo "================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Install npm dependencies if needed
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing npm dependencies...${NC}"
    npm install
fi

# Install Playwright browsers if needed
if ! npx playwright --version > /dev/null 2>&1; then
    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    npx playwright install chromium
fi

# Always rebuild and restart services to ensure we test latest code
# Docker layer caching makes this cheap when nothing changed
echo -e "${YELLOW}Building and starting E2E services...${NC}"
docker compose -f "$PROJECT_ROOT/docker-compose.e2e.yml" up -d --build

echo -e "${YELLOW}Waiting for services to be healthy...${NC}"

# Wait for frontend to be ready (with timeout)
TIMEOUT=120
ELAPSED=0
while ! curl -s http://localhost:3200 > /dev/null 2>&1; do
    if [ $ELAPSED -ge $TIMEOUT ]; then
        echo -e "${RED}Timeout waiting for services${NC}"
        docker compose -f "$PROJECT_ROOT/docker-compose.e2e.yml" logs
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    echo -n "."
done
echo ""

echo -e "${GREEN}Services ready!${NC}"

# Run tests
echo -e "${YELLOW}Running Playwright tests...${NC}"
echo ""

# Pass through any arguments
npx playwright test "$@"

TEST_EXIT_CODE=$?

# Show results
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo ""
    echo -e "${RED}Some tests failed${NC}"
    echo "Run 'npx playwright show-report' in the e2e directory to view the report"
fi

exit $TEST_EXIT_CODE
