#!/bin/bash
# Build and push Docker images to GitHub Container Registry
# Usage: ./build-and-push.sh [OPTIONS]
#
# Prerequisites:
#   1. Create a GitHub Personal Access Token (PAT) with 'write:packages' scope
#   2. Login to ghcr.io: echo $GITHUB_PAT | docker login ghcr.io -u YOUR_USERNAME --password-stdin

set -e
cd "$(dirname "$0")"

# Configuration
REGISTRY="ghcr.io/rsokolowski"
API_IMAGE="$REGISTRY/omj-validator-api"
FRONTEND_IMAGE="$REGISTRY/omj-validator-frontend"

# Build args for frontend (must match production docker-compose)
FASTAPI_URL="http://api:8100"
WS_URL="wss://omj-validator.pl"

# Parse arguments
BUILD_API=false
BUILD_FRONTEND=false
TAG="latest"
PUSH=true

show_help() {
    echo "Usage: ./build-and-push.sh [OPTIONS]"
    echo ""
    echo "Build and push Docker images to GitHub Container Registry."
    echo ""
    echo "Options:"
    echo "  --api              Build only the API image"
    echo "  --frontend         Build only the frontend image"
    echo "  --tag TAG          Use specific tag (default: latest)"
    echo "  --no-push          Build only, don't push to registry"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./build-and-push.sh                  # Build and push both images"
    echo "  ./build-and-push.sh --api            # Build and push API only"
    echo "  ./build-and-push.sh --frontend       # Build and push frontend only"
    echo "  ./build-and-push.sh --tag v1.0.0     # Tag as v1.0.0"
    echo "  ./build-and-push.sh --no-push        # Build only, don't push"
    echo ""
    echo "Setup (one-time):"
    echo "  1. Create GitHub PAT at https://github.com/settings/tokens"
    echo "     - Select 'write:packages' scope"
    echo "  2. Login to ghcr.io:"
    echo "     echo YOUR_PAT | docker login ghcr.io -u YOUR_USERNAME --password-stdin"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --api)
            BUILD_API=true
            shift
            ;;
        --frontend)
            BUILD_FRONTEND=true
            shift
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --tag=*)
            TAG="${1#*=}"
            shift
            ;;
        --no-push)
            PUSH=false
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# If no specific service selected, build both
if [ "$BUILD_API" = false ] && [ "$BUILD_FRONTEND" = false ]; then
    BUILD_API=true
    BUILD_FRONTEND=true
fi

echo "=== OMJ Validator Image Build ==="
echo ""

# Build API
if [ "$BUILD_API" = true ]; then
    # The OMJ PDFs and the generated statements are not in the repository (see
    # NOTICE); they are baked into the image from this machine's working copy.
    # A build on a fresh clone would produce a technically working but
    # content-less deployment, so make that impossible to miss.
    PDF_COUNT=$(find tasks -name '*.pdf' 2>/dev/null | wc -l)
    CONTENT_COUNT=$(find data/task_content -name '*.json' 2>/dev/null | wc -l)
    echo "Task PDFs in build context:       $PDF_COUNT"
    echo "Statement files in build context: $CONTENT_COUNT"
    if [ "$PDF_COUNT" -eq 0 ]; then
        echo ""
        echo "ERROR: tasks/ holds no PDF - the image would ship without any task."
        echo "       Run: python download_tasks.py --all-etaps"
        echo "       (or pass --frontend to build only the frontend)"
        exit 1
    fi
    if [ "$CONTENT_COUNT" -eq 0 ]; then
        echo ""
        echo "WARNING: data/task_content/ is empty - deployed tasks will show only"
        echo "         metadata and a link to the PDF."
        echo "         Run: python fix_latex_content.py --all --skip-existing"
        echo ""
    fi

    echo "Building API image: $API_IMAGE:$TAG"
    docker build -t "$API_IMAGE:$TAG" -f Dockerfile .

    if [ "$PUSH" = true ]; then
        echo "Pushing $API_IMAGE:$TAG"
        docker push "$API_IMAGE:$TAG"
    fi
    echo ""
fi

# Build Frontend
if [ "$BUILD_FRONTEND" = true ]; then
    echo "Building frontend image: $FRONTEND_IMAGE:$TAG"
    docker build -t "$FRONTEND_IMAGE:$TAG" \
        --build-arg FASTAPI_URL="$FASTAPI_URL" \
        --build-arg NEXT_PUBLIC_WS_URL="$WS_URL" \
        -f frontend/Dockerfile frontend/

    if [ "$PUSH" = true ]; then
        echo "Pushing $FRONTEND_IMAGE:$TAG"
        docker push "$FRONTEND_IMAGE:$TAG"
    fi
    echo ""
fi

echo "=== Build complete ==="
if [ "$PUSH" = true ]; then
    echo ""
    echo "Images pushed to registry. Deploy with:"
    echo "  ./deploy.sh"
fi
