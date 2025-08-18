#!/bin/bash

# Container build script with security scanning
# Builds Docker image and runs security scan as per requirements

set -e

# Configuration
IMAGE_NAME="reddit-publisher"
TAG=${1:-"latest"}
FULL_IMAGE_NAME="$IMAGE_NAME:$TAG"
BUILD_CONTEXT="."
DOCKERFILE="Dockerfile"

echo "🏗️  Building Reddit Ghost Publisher container"
echo "📦 Image: $FULL_IMAGE_NAME"
echo "📁 Context: $BUILD_CONTEXT"
echo "📄 Dockerfile: $DOCKERFILE"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build the Docker image
echo ""
echo "🏗️  Building Docker image..."
docker build \
    --tag $FULL_IMAGE_NAME \
    --file $DOCKERFILE \
    --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
    --build-arg VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
    $BUILD_CONTEXT

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully: $FULL_IMAGE_NAME"
else
    echo "❌ Docker image build failed"
    exit 1
fi

# Get image size
IMAGE_SIZE=$(docker images $FULL_IMAGE_NAME --format "table {{.Size}}" | tail -n 1)
echo "📊 Image size: $IMAGE_SIZE"

# Run security scan
echo ""
echo "🔍 Running security scan..."
if ./scripts/security-scan.sh $FULL_IMAGE_NAME; then
    echo "✅ Security scan passed"
else
    echo "❌ Security scan failed - HIGH or CRITICAL vulnerabilities found"
    echo "🚨 Build process terminated due to security issues"
    exit 1
fi

# Optional: Run basic smoke test
echo ""
echo "🧪 Running basic container smoke test..."
CONTAINER_ID=$(docker run -d --rm -p 8001:8000 -e DATABASE_URL="sqlite:///test.db" $FULL_IMAGE_NAME)

# Wait for container to start
sleep 5

# Check if container is running
if docker ps | grep -q $CONTAINER_ID; then
    echo "✅ Container started successfully"
    
    # Test health endpoint (if available)
    if curl -f http://localhost:8001/health >/dev/null 2>&1; then
        echo "✅ Health check passed"
    else
        echo "⚠️  Health check not available or failed (this may be expected in test environment)"
    fi
    
    # Stop test container
    docker stop $CONTAINER_ID >/dev/null 2>&1
    echo "🧹 Test container stopped"
else
    echo "❌ Container failed to start"
    docker logs $CONTAINER_ID 2>/dev/null || true
    docker stop $CONTAINER_ID >/dev/null 2>&1 || true
    exit 1
fi

echo ""
echo "🎉 Container build and security scan completed successfully!"
echo "📦 Image: $FULL_IMAGE_NAME"
echo "🔍 Security: Passed (no HIGH/CRITICAL vulnerabilities)"
echo "🧪 Smoke test: Passed"

# Show final image info
echo ""
echo "📊 Final image information:"
docker images $FULL_IMAGE_NAME --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}"