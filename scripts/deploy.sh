#!/bin/bash

# Reddit Publisher Deployment Script
# Usage: ./scripts/deploy.sh [IMAGE_TAG] [ENVIRONMENT]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEFAULT_IMAGE_TAG="reddit-publisher:latest"
DEFAULT_ENVIRONMENT="production"

# Parse arguments
IMAGE_TAG="${1:-$DEFAULT_IMAGE_TAG}"
ENVIRONMENT="${2:-$DEFAULT_ENVIRONMENT}"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validation functions
validate_environment() {
    if [[ ! -f "$PROJECT_ROOT/.env.${ENVIRONMENT}" ]]; then
        log_error "Environment file .env.${ENVIRONMENT} not found"
        exit 1
    fi
    
    # Source environment variables
    set -a
    source "$PROJECT_ROOT/.env.${ENVIRONMENT}"
    set +a
    
    log_info "Environment: $ENVIRONMENT"
    log_info "Image tag: $IMAGE_TAG"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running"
        exit 1
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "docker-compose is not installed"
        exit 1
    fi
    
    # Check if curl is available for health checks
    if ! command -v curl >/dev/null 2>&1; then
        log_error "curl is not installed"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

backup_current_deployment() {
    log_info "Creating backup of current deployment..."
    
    # Create backup directory
    BACKUP_DIR="$PROJECT_ROOT/deployment-backups/$TIMESTAMP"
    mkdir -p "$BACKUP_DIR"
    
    # Backup current docker-compose state
    if docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" ps --services >/dev/null 2>&1; then
        docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" config > "$BACKUP_DIR/docker-compose.backup.yml"
        log_info "Current deployment state backed up to $BACKUP_DIR"
    else
        log_warning "No current deployment found to backup"
    fi
    
    # Export current environment
    env | grep -E '^(DOCKER_IMAGE_TAG|DATABASE_URL|REDIS_URL)' > "$BACKUP_DIR/environment.backup" || true
    
    log_success "Backup completed"
}

pull_new_image() {
    log_info "Pulling new Docker image: $IMAGE_TAG"
    
    if docker pull "$IMAGE_TAG"; then
        log_success "Image pulled successfully"
    else
        log_error "Failed to pull image: $IMAGE_TAG"
        exit 1
    fi
}

stop_current_deployment() {
    log_info "Stopping current deployment..."
    
    cd "$PROJECT_ROOT"
    
    # Gracefully stop services
    if docker-compose -f docker-compose.prod.yml ps --services >/dev/null 2>&1; then
        docker-compose -f docker-compose.prod.yml down --remove-orphans
        log_success "Current deployment stopped"
    else
        log_info "No current deployment to stop"
    fi
}

start_new_deployment() {
    log_info "Starting new deployment..."
    
    cd "$PROJECT_ROOT"
    
    # Export image tag for docker-compose
    export DOCKER_IMAGE_TAG="$IMAGE_TAG"
    
    # Start services
    docker-compose -f docker-compose.prod.yml up -d
    
    log_success "New deployment started"
}

wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    local max_attempts=30
    local attempt=1
    local health_url="${PRODUCTION_URL:-http://localhost:8000}/health"
    
    while [ $attempt -le $max_attempts ]; do
        log_info "Health check attempt $attempt/$max_attempts..."
        
        if curl -f -s "$health_url" >/dev/null 2>&1; then
            log_success "Services are ready"
            return 0
        fi
        
        sleep 10
        ((attempt++))
    done
    
    log_error "Services failed to become ready within timeout"
    return 1
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    local base_url="${PRODUCTION_URL:-http://localhost:8000}"
    
    # Check health endpoint
    if ! curl -f -s "$base_url/health" >/dev/null; then
        log_error "Health check failed"
        return 1
    fi
    
    # Check metrics endpoint
    if ! curl -f -s "$base_url/metrics" >/dev/null; then
        log_error "Metrics endpoint check failed"
        return 1
    fi
    
    # Check if workers are running
    local running_services=$(docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" ps --services --filter "status=running" | wc -l)
    if [ "$running_services" -lt 5 ]; then
        log_error "Not all services are running (expected: 5+, actual: $running_services)"
        return 1
    fi
    
    log_success "Deployment verification passed"
    return 0
}

rollback_deployment() {
    log_error "Deployment failed, initiating rollback..."
    
    # Stop failed deployment
    docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" down --remove-orphans
    
    # Find latest backup
    local latest_backup=$(find "$PROJECT_ROOT/deployment-backups" -name "docker-compose.backup.yml" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [[ -n "$latest_backup" && -f "$latest_backup" ]]; then
        log_info "Rolling back to previous deployment..."
        
        # Restore previous environment
        local backup_dir=$(dirname "$latest_backup")
        if [[ -f "$backup_dir/environment.backup" ]]; then
            source "$backup_dir/environment.backup"
        fi
        
        # Use previous image tag or fallback
        export DOCKER_IMAGE_TAG="${DOCKER_IMAGE_TAG:-reddit-publisher:previous}"
        
        # Start previous deployment
        docker-compose -f docker-compose.prod.yml up -d
        
        # Wait and verify rollback
        if wait_for_services && verify_deployment; then
            log_success "Rollback completed successfully"
        else
            log_error "Rollback failed - manual intervention required"
            exit 1
        fi
    else
        log_error "No backup found for rollback - manual intervention required"
        exit 1
    fi
}

cleanup_old_backups() {
    log_info "Cleaning up old deployment backups..."
    
    # Keep only last 5 backups
    find "$PROJECT_ROOT/deployment-backups" -maxdepth 1 -type d -name "20*" | sort -r | tail -n +6 | xargs rm -rf
    
    log_success "Cleanup completed"
}

tag_successful_deployment() {
    log_info "Tagging successful deployment..."
    
    # Tag current image as 'previous' for future rollbacks
    local registry="${DOCKER_REGISTRY:-}"
    if [[ -n "$registry" ]]; then
        local previous_tag="${registry}/reddit-publisher:previous"
        docker tag "$IMAGE_TAG" "$previous_tag"
        
        if docker push "$previous_tag"; then
            log_success "Image tagged as previous: $previous_tag"
        else
            log_warning "Failed to push previous tag - rollback may not work"
        fi
    fi
}

send_notification() {
    local status="$1"
    local message="$2"
    
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local color="good"
        local emoji="✅"
        
        if [[ "$status" != "success" ]]; then
            color="danger"
            emoji="❌"
        fi
        
        local payload=$(cat <<EOF
{
    "text": "$emoji Deployment $status",
    "attachments": [
        {
            "color": "$color",
            "fields": [
                {"title": "Environment", "value": "$ENVIRONMENT", "short": true},
                {"title": "Image", "value": "$IMAGE_TAG", "short": true},
                {"title": "Timestamp", "value": "$TIMESTAMP", "short": true},
                {"title": "Message", "value": "$message", "short": false}
            ]
        }
    ]
}
EOF
        )
        
        curl -X POST -H 'Content-type: application/json' \
             --data "$payload" \
             "$SLACK_WEBHOOK_URL" >/dev/null 2>&1 || true
    fi
}

# Main deployment function
main() {
    log_info "Starting Reddit Publisher deployment..."
    log_info "Timestamp: $TIMESTAMP"
    
    # Validate inputs and environment
    validate_environment
    check_prerequisites
    
    # Create deployment backup
    backup_current_deployment
    
    # Pull new image
    pull_new_image
    
    # Deploy new version
    stop_current_deployment
    start_new_deployment
    
    # Wait for services and verify
    if wait_for_services && verify_deployment; then
        # Success path
        tag_successful_deployment
        cleanup_old_backups
        send_notification "success" "Deployment completed successfully"
        log_success "Deployment completed successfully!"
        
        # Display service status
        log_info "Service status:"
        docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" ps
        
    else
        # Failure path
        rollback_deployment
        send_notification "failed" "Deployment failed and was rolled back"
        log_error "Deployment failed and was rolled back"
        exit 1
    fi
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; rollback_deployment; exit 1' INT TERM

# Run main function
main "$@"