#!/bin/bash
# Production deployment script - deploys to NUC server via SSH
# Usage: ./deploy.sh [OPTIONS]

set -e
cd "$(dirname "$0")"

# Configuration
SSH_KEY="$HOME/.ssh/nuc/id_rsa"
SSH_HOST="rsokolowski@192.168.86.68"
REMOTE_DIR="~/omj-validator"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

# Parse arguments
SERVICE=""
LOGS=false
STATUS=false
SSH_ONLY=false

ssh_cmd() {
    ssh -i "$SSH_KEY" "$SSH_HOST" "$@"
}

show_help() {
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Deploy OMJ Validator to production NUC server."
    echo "Images are pulled from ghcr.io - build locally first with ./build-and-push.sh"
    echo ""
    echo "Options:"
    echo "  --api              Deploy only the API service"
    echo "  --frontend         Deploy only the frontend service"
    echo "  --logs [SERVICE]   View logs (api, frontend, db, or all)"
    echo "  --status           Show container status"
    echo "  --ssh              Open SSH session to server"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./build-and-push.sh && ./deploy.sh   # Build, push, deploy"
    echo "  ./deploy.sh                          # Pull latest and restart"
    echo "  ./deploy.sh --api                    # Deploy only API"
    echo "  ./deploy.sh --frontend               # Deploy only frontend"
    echo "  ./deploy.sh --logs api               # View API logs"
    echo "  ./deploy.sh --status                 # Check container status"
    echo "  ./deploy.sh --ssh                    # SSH into server"
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

echo "=== OMJ Validator Production Deployment ==="
echo ""

# Handle different modes
if [ "$SSH_ONLY" = true ]; then
    echo "Opening SSH session to $SSH_HOST..."
    ssh -i "$SSH_KEY" "$SSH_HOST"
    exit 0
fi

if [ "$STATUS" = true ]; then
    echo "Checking container status..."
    ssh_cmd "cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE ps"
    exit 0
fi

if [ "$LOGS" = true ]; then
    if [ -n "$SERVICE" ]; then
        echo "Streaming logs for $SERVICE..."
        ssh_cmd "docker logs omj-$SERVICE --tail=100 -f"
    else
        echo "Streaming all logs..."
        ssh_cmd "cd $REMOTE_DIR && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE logs -f --tail=100"
    fi
    exit 0
fi

# Main deployment
echo "Deploying to: $SSH_HOST"
echo ""

# Build the deployment command - pull images from ghcr.io then restart
if [ -n "$SERVICE" ]; then
    echo "Deploying service: $SERVICE"
    DEPLOY_CMD="cd $REMOTE_DIR && git pull && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE pull $SERVICE && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d $SERVICE"
else
    echo "Deploying all services"
    DEPLOY_CMD="cd $REMOTE_DIR && git pull && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE pull && docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d"
fi

echo ""
echo "Running: $DEPLOY_CMD"
echo ""

# Execute deployment
ssh_cmd "$DEPLOY_CMD"

echo ""
echo "=== Deployment complete ==="
echo ""
echo "Useful commands:"
echo "  ./deploy.sh --status         # Check container status"
echo "  ./deploy.sh --logs api       # View API logs"
echo "  ./deploy.sh --ssh            # SSH into server"
echo "  ./build-and-push.sh          # Build and push new images"
echo ""
echo "URL: https://omj-validator.pl"
