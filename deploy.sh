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
SSH_USER=""  # Optional: override SSH user (default: current local user)

# Parse arguments
SERVICE=""
LOGS=false
STATUS=false
SSH_ONLY=false

show_help() {
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Deploy OMJ Validator to production GCP VM."
    echo "Images are pulled from ghcr.io - build locally first with ./build-and-push.sh"
    echo ""
    echo "Options:"
    echo "  --api              Deploy only the API service"
    echo "  --frontend         Deploy only the frontend service"
    echo "  --logs [SERVICE]   View logs (api, frontend, db, or all)"
    echo "  --status           Show container status"
    echo "  --ssh              Open SSH session to VM"
    echo "  --user USER        SSH user on VM (default: current local user)"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./build-and-push.sh && ./deploy.sh   # Build, push, deploy"
    echo "  ./deploy.sh                          # Pull latest and restart"
    echo "  ./deploy.sh --user rsokolowski       # Deploy as specific user"
    echo "  ./deploy.sh --api                    # Deploy only API"
    echo "  ./deploy.sh --frontend               # Deploy only frontend"
    echo "  ./deploy.sh --logs api               # View API logs"
    echo "  ./deploy.sh --status                 # Check container status"
    echo "  ./deploy.sh --ssh                    # SSH into VM"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --api)
            SERVICE="api"
            shift
            ;;
        --frontend)
            SERVICE="frontend"
            shift
            ;;
        --logs)
            LOGS=true
            shift
            ;;
        --status)
            STATUS=true
            shift
            ;;
        --ssh)
            SSH_ONLY=true
            shift
            ;;
        --user)
            SSH_USER="$2"
            shift 2
            ;;
        --user=*)
            SSH_USER="${1#*=}"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        api|frontend|db)
            # Capture service name after --logs
            if [ "$LOGS" = true ]; then
                SERVICE="$1"
            fi
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Build SSH target (user@vm or just vm)
if [ -n "$SSH_USER" ]; then
    SSH_TARGET="$SSH_USER@$VM_NAME"
else
    SSH_TARGET="$VM_NAME"
fi

# Check gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI not found. Install Google Cloud SDK first."
    exit 1
fi

echo "=== OMJ Validator Production Deployment ==="
echo ""

# Handle different modes
if [ "$SSH_ONLY" = true ]; then
    echo "Opening SSH session to $SSH_TARGET..."
    gcloud compute ssh "$SSH_TARGET"
    exit 0
fi

if [ "$STATUS" = true ]; then
    echo "Checking container status..."
    gcloud compute ssh "$SSH_TARGET" --command="cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE ps"
    exit 0
fi

if [ "$LOGS" = true ]; then
    if [ -n "$SERVICE" ]; then
        echo "Streaming logs for $SERVICE..."
        gcloud compute ssh "$SSH_TARGET" --command="sudo docker logs omj-$SERVICE --tail=100 -f"
    else
        echo "Streaming all logs..."
        gcloud compute ssh "$SSH_TARGET" --command="cd $REMOTE_DIR && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE logs -f --tail=100"
    fi
    exit 0
fi

# Main deployment
echo "Deploying to VM: $SSH_TARGET"
echo ""

# Build the deployment command - pull images from ghcr.io then restart
if [ -n "$SERVICE" ]; then
    echo "Deploying service: $SERVICE"
    DEPLOY_CMD="cd $REMOTE_DIR && git pull && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE pull $SERVICE && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d $SERVICE"
else
    echo "Deploying all services"
    DEPLOY_CMD="cd $REMOTE_DIR && git pull && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE pull && sudo docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d"
fi

echo ""
echo "Running: $DEPLOY_CMD"
echo ""

# Execute deployment
gcloud compute ssh "$SSH_TARGET" --command="$DEPLOY_CMD"

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Useful commands:"
echo "  ./deploy.sh --status         # Check container status"
echo "  ./deploy.sh --logs api       # View API logs"
echo "  ./deploy.sh --ssh            # SSH into VM"
echo "  ./build-and-push.sh          # Build and push new images"
echo ""
echo "URL: https://omj-validator.duckdns.org"
