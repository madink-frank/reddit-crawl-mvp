#!/bin/bash

# Docker image optimization script
# Implements container optimization strategies

set -e

echo "🚀 Optimizing Docker images for Reddit Ghost Publisher..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Build optimized images
build_optimized_images() {
    print_status "Building optimized production images..."
    
    # Build with BuildKit for better optimization
    export DOCKER_BUILDKIT=1
    
    # Build main application image
    docker build \
        --target production \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --tag reddit-publisher:optimized \
        .
    
    # Build API service
    docker build \
        --target production \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --file docker/Dockerfile.api \
        --tag reddit-publisher-api:optimized \
        .
    
    # Build worker service
    docker build \
        --target production \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --file docker/Dockerfile.worker \
        --tag reddit-publisher-worker:optimized \
        .
    
    # Build scheduler service
    docker build \
        --target production \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --file docker/Dockerfile.scheduler \
        --tag reddit-publisher-scheduler:optimized \
        .
}

# Analyze image layers
analyze_layers() {
    print_status "Analyzing image layers..."
    
    local images=("reddit-publisher:optimized" "reddit-publisher-api:optimized" "reddit-publisher-worker:optimized" "reddit-publisher-scheduler:optimized")
    
    for image in "${images[@]}"; do
        echo "Analyzing $image:"
        docker history "$image" --format "table {{.CreatedBy}}\t{{.Size}}" | head -20
        echo ""
    done
}

# Check image sizes
check_sizes() {
    print_status "Checking optimized image sizes..."
    
    echo "Image sizes:"
    docker images | grep -E "(reddit-publisher.*optimized|SIZE)"
}

# Test optimized images
test_images() {
    print_status "Testing optimized images..."
    
    # Test API image
    print_status "Testing API image..."
    docker run --rm -d --name test-api -p 8001:8000 reddit-publisher-api:optimized
    sleep 5
    
    if curl -f http://localhost:8001/health; then
        print_status "API image test passed"
    else
        print_warning "API image test failed"
    fi
    
    docker stop test-api
    
    # Test worker image (quick test)
    print_status "Testing worker image..."
    if docker run --rm reddit-publisher-worker:optimized celery --version; then
        print_status "Worker image test passed"
    else
        print_warning "Worker image test failed"
    fi
}

# Generate optimization report
generate_optimization_report() {
    print_status "Generating optimization report..."
    
    local report_file="optimization-report.md"
    
    cat > "$report_file" << EOF
# Docker Image Optimization Report

Generated on: $(date)

## Image Sizes

\`\`\`
$(docker images | grep -E "(reddit-publisher.*optimized|REPOSITORY)")
\`\`\`

## Optimization Techniques Applied

1. **Multi-stage builds**: Separate development and production stages
2. **Minimal base images**: Using python:3.12-slim
3. **Layer optimization**: Combining RUN commands to reduce layers
4. **Build cache**: Using BuildKit for better caching
5. **Security hardening**: Non-root user, minimal attack surface
6. **Health checks**: Proper container health monitoring

## Recommendations

1. Use image registries with layer deduplication
2. Implement automated image scanning in CI/CD
3. Consider using distroless images for even smaller footprint
4. Monitor image sizes in CI/CD pipeline

EOF

    print_status "Optimization report generated: $report_file"
}

# Main execution
main() {
    build_optimized_images
    analyze_layers
    check_sizes
    test_images
    generate_optimization_report
    
    print_status "Image optimization completed! 🎉"
}

# Run main function
main "$@"