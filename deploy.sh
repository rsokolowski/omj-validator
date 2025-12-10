#!/bin/bash
# Production deployment script - deploys to GCP VM via SSH
# Usage: ./deploy.sh [OPTIONS]

set -e
cd "$(dirname "$0")"

# Configuration
VM_NAME="omj-validator"
REMOTE_DIR="~/omj-validator"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

# Parse arguments
SERVICE=""
LOGS=false
STATUS=false
SSH_ONLY=false
NO_BUILD=false

show_help() {
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Deploy OMJ Validator to production GCP VM."
    echo ""
    echo "Options:"
    echo "  --api              Deploy only the API service"
    echo "  --frontend         Deploy only the frontend service"
    echo "  --no-build         Pull and restart without rebuilding images"
    echo "  --logs [SERVICE]   View logs (api, frontend, db, or all)"
    echo "  --status           Show container status"
    echo "  --ssh              Open SSH session to VM"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh                  # Full deploy (pull, build, restart)"
    echo "  ./deploy.sh --api            # Deploy only API"
    echo "  ./deploy.sh --frontend       # Deploy only frontend"
    echo "  ./deploy.sh --no-build       # Quick deploy without rebuild"
    echo "  ./deploy.sh --logs api       # View API logs"
    echo "  ./deploy.sh --status         # Check container status"
    echo "  ./deploy.sh --ssh            # SSH into VM"
}

for arg in "$@"; do
    case $arg in
        --api)
            SERVICE="api"
            ;;
        --frontend)
            SERVICE="frontend"
            ;;
        --no-build)
            NO_BUILD=true
            ;;
        --logs)
            LOGS=true
            ;;
        --status)
            STATUS=true
            ;;
        --ssh)
            SSH_ONLY=true
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        api|frontend|db)
            # Capture service name after --logs
            if [ "$LOGS" = true ]; then
                SERVICE="$arg"
            fi
            ;;
    esac
done

# Check gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI not found. Install Google Cloud SDK first."
    exit 1
fi

echo "=== OMJ Validator Production Deployment ==="
echo ""

# Handle different modes
if [ "$SSH_ONLY" = true ]; then
    echo "Opening SSH session to $VM_NAME..."
    gcloud compute ssh "$VM_NAME"
    exit 0
fi

if [ "$STATUS" = true ]; then
    echo "Checking container status..."
    gcloud compute ssh "$VM_NAME" --command="cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE ps"
    exit 0
fi

if [ "$LOGS" = true ]; then
    if [ -n "$SERVICE" ]; then
        echo "Streaming logs for $SERVICE..."
        gcloud compute ssh "$VM_NAME" --command="sudo docker logs omj-$SERVICE --tail=100 -f"
    else
        echo "Streaming all logs..."
        gcloud compute ssh "$VM_NAME" --command="cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE logs -f --tail=100"
    fi
    exit 0
fi

# Main deployment
echo "Deploying to VM: $VM_NAME"
echo ""

# Build the deployment command
if [ "$NO_BUILD" = true ]; then
    BUILD_CMD=""
else
    BUILD_CMD="--build"
fi

if [ -n "$SERVICE" ]; then
    echo "Deploying service: $SERVICE"
    DEPLOY_CMD="cd $REMOTE_DIR && git pull && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d $BUILD_CMD $SERVICE"
else
    echo "Deploying all services"
    DEPLOY_CMD="cd $REMOTE_DIR && git pull && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d $BUILD_CMD"
fi

echo ""
echo "Running: $DEPLOY_CMD"
echo ""

# Execute deployment
gcloud compute ssh "$VM_NAME" --command="$DEPLOY_CMD"

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Useful commands:"
echo "  ./deploy.sh --status       # Check container status"
echo "  ./deploy.sh --logs api     # View API logs"
echo "  ./deploy.sh --ssh          # SSH into VM"
echo ""
echo "URL: https://omj-validator.duckdns.org"
