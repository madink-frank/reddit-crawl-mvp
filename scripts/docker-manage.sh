#!/bin/bash

# Docker Management Script for Reddit Ghost Publisher MVP
# Simplifies common Docker operations

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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

# Usage function
usage() {
    cat << EOF
Usage: $0 <COMMAND> [OPTIONS]

Docker management commands for Reddit Ghost Publisher

COMMANDS:
    start           Start all services
    stop            Stop all services
    restart         Restart all services
    status          Show service status
    logs            Show service logs
    build           Build Docker images
    clean           Clean up containers and images
    shell           Open shell in container
    backup          Create database backup
    restore         Restore database from backup

OPTIONS:
    -e, --env ENV   Environment (development|production) [default: development]
    -f, --follow    Follow logs (for logs command)
    -s, --service   Specific service name (for logs/shell commands)
    -h, --help      Show this help message

EXAMPLES:
    $0 start                    # Start all services
    $0 start -e production      # Start production services
    $0 logs -f                  # Follow all logs
    $0 logs -s api              # Show API logs only
    $0 shell -s postgres        # Open shell in postgres container
    $0 clean                    # Clean up Docker resources

EOF
}

# Parse command line arguments
COMMAND=""
ENVIRONMENT="development"
FOLLOW_LOGS=false
SERVICE=""

if [[ $# -eq 0 ]]; then
    usage
    exit 1
fi

COMMAND="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -f|--follow)
            FOLLOW_LOGS=true
            shift
            ;;
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ "$ENVIRONMENT" != "development" && "$ENVIRONMENT" != "production" ]]; then
    log_error "Environment must be 'development' or 'production'"
    exit 1
fi

# Set compose file based on environment
COMPOSE_FILE="docker-compose.yml"
if [[ "$ENVIRONMENT" == "production" ]]; then
    COMPOSE_FILE="docker-compose.prod.yml"
fi

# Change to project root
cd "$PROJECT_ROOT"

# Check if compose file exists
if [[ ! -f "$COMPOSE_FILE" ]]; then
    log_error "Compose file not found: $COMPOSE_FILE"
    exit 1
fi

# Start services
start_services() {
    log_info "Starting services in $ENVIRONMENT mode..."
    
    if docker-compose -f "$COMPOSE_FILE" up -d; then
        log_success "Services started successfully"
        
        # Wait a moment and show status
        sleep 3
        show_status
    else
        log_error "Failed to start services"
        exit 1
    fi
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    
    if docker-compose -f "$COMPOSE_FILE" down; then
        log_success "Services stopped successfully"
    else
        log_error "Failed to stop services"
        exit 1
    fi
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    
    if docker-compose -f "$COMPOSE_FILE" restart; then
        log_success "Services restarted successfully"
        
        # Wait a moment and show status
        sleep 3
        show_status
    else
        log_error "Failed to restart services"
        exit 1
    fi
}

# Show service status
show_status() {
    log_info "Service status:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo
    log_info "Resource usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker-compose -f "$COMPOSE_FILE" ps -q) 2>/dev/null || true
}

# Show logs
show_logs() {
    local log_args=""
    
    if [[ "$FOLLOW_LOGS" == "true" ]]; then
        log_args="$log_args -f"
    fi
    
    if [[ -n "$SERVICE" ]]; then
        log_info "Showing logs for service: $SERVICE"
        docker-compose -f "$COMPOSE_FILE" logs $log_args "$SERVICE"
    else
        log_info "Showing logs for all services"
        docker-compose -f "$COMPOSE_FILE" logs $log_args
    fi
}

# Build images
build_images() {
    log_info "Building Docker images..."
    
    if docker-compose -f "$COMPOSE_FILE" build --no-cache; then
        log_success "Images built successfully"
    else
        log_error "Failed to build images"
        exit 1
    fi
}

# Clean up Docker resources
clean_resources() {
    log_info "Cleaning up Docker resources..."
    
    # Stop and remove containers
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
    
    # Remove unused images
    log_info "Removing unused images..."
    docker image prune -f
    
    # Remove unused volumes (with confirmation)
    echo
    read -p "Remove unused volumes? This may delete data! (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume prune -f
        log_success "Unused volumes removed"
    fi
    
    # Remove unused networks
    docker network prune -f
    
    log_success "Docker cleanup completed"
}

# Open shell in container
open_shell() {
    if [[ -z "$SERVICE" ]]; then
        log_error "Service name required for shell command. Use -s option."
        exit 1
    fi
    
    local container_id
    container_id=$(docker-compose -f "$COMPOSE_FILE" ps -q "$SERVICE" 2>/dev/null || true)
    
    if [[ -z "$container_id" ]]; then
        log_error "Service '$SERVICE' not found or not running"
        exit 1
    fi
    
    log_info "Opening shell in $SERVICE container..."
    
    # Try bash first, then sh
    if docker exec -it "$container_id" bash 2>/dev/null; then
        true
    elif docker exec -it "$container_id" sh 2>/dev/null; then
        true
    else
        log_error "Failed to open shell in container"
        exit 1
    fi
}

# Create database backup
create_backup() {
    log_info "Creating database backup..."
    
    if [[ -f "$PROJECT_ROOT/scripts/backup-database.sh" ]]; then
        "$PROJECT_ROOT/scripts/backup-database.sh"
    else
        log_error "Backup script not found"
        exit 1
    fi
}

# Restore database
restore_database() {
    log_info "Restoring database..."
    
    if [[ -f "$PROJECT_ROOT/scripts/restore-database.sh" ]]; then
        "$PROJECT_ROOT/scripts/restore-database.sh"
    else
        log_error "Restore script not found"
        exit 1
    fi
}

# Main command handler
case "$COMMAND" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    build)
        build_images
        ;;
    clean)
        clean_resources
        ;;
    shell)
        open_shell
        ;;
    backup)
        create_backup
        ;;
    restore)
        restore_database
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac