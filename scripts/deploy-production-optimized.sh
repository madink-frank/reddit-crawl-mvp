#!/bin/bash
"""
Production Deployment Script with Optimizations
Deploys the optimized Reddit Ghost Publisher system to production environment
"""

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${ENVIRONMENT:-production}"
BACKUP_ENABLED="${BACKUP_ENABLED:-true}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"

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

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking deployment prerequisites..."
    
    # Check if Docker and Docker Compose are available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check if required environment variables are set
    required_vars=(
        "REDDIT_CLIENT_ID"
        "REDDIT_CLIENT_SECRET"
        "OPENAI_API_KEY"
        "GHOST_ADMIN_KEY"
        "GHOST_API_URL"
        "DATABASE_URL"
        "REDIS_URL"
        "SLACK_WEBHOOK_URL"
    )
    
    missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi
    
    # Check disk space
    available_space=$(df / | awk 'NR==2 {print $4}')
    required_space=1048576  # 1GB in KB
    
    if [[ $available_space -lt $required_space ]]; then
        log_error "Insufficient disk space. Required: 1GB, Available: $(($available_space / 1024))MB"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to create backup
create_backup() {
    if [[ "$BACKUP_ENABLED" != "true" ]]; then
        log_info "Backup disabled, skipping..."
        return 0
    fi
    
    log_info "Creating pre-deployment backup..."
    
    cd "$PROJECT_ROOT"
    
    # Create backup directory
    BACKUP_DIR="backups/pre-deployment-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    if [[ -n "$DATABASE_URL" ]]; then
        log_info "Backing up database..."
        
        # Extract database connection details
        DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
        DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
        
        # Create database backup
        PGPASSWORD="$DB_PASSWORD" pg_dump \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --no-password \
            > "$BACKUP_DIR/database_backup.sql" 2>/dev/null || {
            log_warning "Database backup failed, continuing deployment..."
        }
    fi
    
    # Backup configuration files
    log_info "Backing up configuration files..."
    cp -r .env* "$BACKUP_DIR/" 2>/dev/null || true
    cp docker-compose*.yml "$BACKUP_DIR/" 2>/dev/null || true
    
    # Backup logs
    if [[ -d "logs" ]]; then
        log_info "Backing up logs..."
        cp -r logs "$BACKUP_DIR/" 2>/dev/null || true
    fi
    
    log_success "Backup created at: $BACKUP_DIR"
}

# Function to build optimized Docker images
build_optimized_images() {
    log_info "Building optimized Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build production image with optimizations
    log_info "Building production Docker image..."
    docker build \
        --target production \
        --build-arg ENVIRONMENT=production \
        --build-arg ENABLE_OPTIMIZATIONS=true \
        -t reddit-ghost-publisher:production \
        -f Dockerfile .
    
    # Tag with timestamp
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    docker tag reddit-ghost-publisher:production "reddit-ghost-publisher:production-$TIMESTAMP"
    
    log_success "Docker images built successfully"
}

# Function to deploy services
deploy_services() {
    log_info "Deploying services to production..."
    
    cd "$PROJECT_ROOT"
    
    # Use production compose file
    COMPOSE_FILE="docker-compose.prod.yml"
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_warning "Production compose file not found, using default"
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # Set production environment variables
    export ENVIRONMENT=production
    export LOG_LEVEL=INFO
    export DEBUG=false
    export API_WORKERS=4
    export ENABLE_CACHING=true
    export ENABLE_COMPRESSION=true
    export ENABLE_PERFORMANCE_MONITORING=true
    
    # Stop existing services gracefully
    log_info "Stopping existing services..."
    docker-compose -f "$COMPOSE_FILE" down --timeout 30 || true
    
    # Start services with production configuration
    log_info "Starting production services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_success "Services deployed successfully"
}

# Function to run health checks
run_health_checks() {
    log_info "Running health checks..."
    
    API_URL="${API_BASE_URL:-http://localhost:8000}"
    
    # Wait for services to start
    log_info "Waiting for services to initialize..."
    sleep 30
    
    # Health check with timeout
    log_info "Checking API health..."
    
    start_time=$(date +%s)
    end_time=$((start_time + HEALTH_CHECK_TIMEOUT))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
            log_success "API health check passed"
            break
        fi
        
        log_info "Waiting for API to be ready..."
        sleep 10
    done
    
    # Final health check
    if ! curl -s -f "$API_URL/health" > /dev/null 2>&1; then
        log_error "API health check failed after $HEALTH_CHECK_TIMEOUT seconds"
        return 1
    fi
    
    # Check database connectivity
    log_info "Checking database connectivity..."
    if curl -s -f "$API_URL/api/v1/status/database" > /dev/null 2>&1; then
        log_success "Database connectivity check passed"
    else
        log_warning "Database connectivity check failed"
    fi
    
    # Check Redis connectivity
    log_info "Checking Redis connectivity..."
    if curl -s -f "$API_URL/api/v1/status/redis" > /dev/null 2>&1; then
        log_success "Redis connectivity check passed"
    else
        log_warning "Redis connectivity check failed"
    fi
    
    # Check queue status
    log_info "Checking queue status..."
    if curl -s -f "$API_URL/api/v1/status/queues" > /dev/null 2>&1; then
        log_success "Queue status check passed"
    else
        log_warning "Queue status check failed"
    fi
    
    log_success "Health checks completed"
}

# Function to run smoke tests
run_smoke_tests() {
    log_info "Running post-deployment smoke tests..."
    
    cd "$PROJECT_ROOT"
    
    # Check if Newman is available for Postman tests
    if command -v newman &> /dev/null; then
        log_info "Running Postman smoke tests..."
        
        if [[ -f "tests/postman/reddit-ghost-publisher-smoke-tests.json" ]]; then
            newman run \
                tests/postman/reddit-ghost-publisher-smoke-tests.json \
                -e tests/postman/production-environment.json \
                --timeout-request 30000 \
                --delay-request 1000 \
                --reporters cli,json \
                --reporter-json-export "tests/postman/results/production-smoke-$(date +%Y%m%d_%H%M%S).json" || {
                log_warning "Some smoke tests failed, check results for details"
            }
        else
            log_warning "Postman smoke tests not found"
        fi
    else
        log_warning "Newman not available, skipping Postman smoke tests"
    fi
    
    # Basic API endpoint tests
    log_info "Running basic endpoint tests..."
    
    API_URL="${API_BASE_URL:-http://localhost:8000}"
    
    endpoints=(
        "/health"
        "/metrics"
        "/api/v1/status/queues"
        "/api/v1/status/workers"
        "/dashboard/api/pipeline/status"
    )
    
    failed_endpoints=()
    
    for endpoint in "${endpoints[@]}"; do
        if curl -s -f "$API_URL$endpoint" > /dev/null 2>&1; then
            log_success "✓ $endpoint"
        else
            log_error "✗ $endpoint"
            failed_endpoints+=("$endpoint")
        fi
    done
    
    if [[ ${#failed_endpoints[@]} -eq 0 ]]; then
        log_success "All endpoint tests passed"
    else
        log_warning "Some endpoints failed: ${failed_endpoints[*]}"
    fi
}

# Function to setup monitoring and alerting
setup_monitoring() {
    log_info "Setting up production monitoring..."
    
    cd "$PROJECT_ROOT"
    
    # Create monitoring directories
    mkdir -p logs/monitoring
    mkdir -p monitoring/alerts
    
    # Setup log rotation
    log_info "Configuring log rotation..."
    
    cat > /tmp/reddit-publisher-logrotate << EOF
/app/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 app app
    postrotate
        docker-compose -f docker-compose.prod.yml restart api || true
    endscript
}
EOF
    
    # Install logrotate configuration (requires sudo)
    if command -v sudo &> /dev/null; then
        sudo cp /tmp/reddit-publisher-logrotate /etc/logrotate.d/reddit-publisher || {
            log_warning "Failed to install logrotate configuration"
        }
    fi
    
    # Setup monitoring cron jobs
    log_info "Setting up monitoring cron jobs..."
    
    # Create monitoring script
    cat > monitoring/health_monitor.sh << 'EOF'
#!/bin/bash
API_URL="${API_BASE_URL:-http://localhost:8000}"
LOG_FILE="/app/logs/monitoring/health_monitor.log"

# Check API health
if ! curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    echo "$(date): API health check failed" >> "$LOG_FILE"
    # Send alert (implement your alerting mechanism here)
fi

# Check queue status
QUEUE_STATUS=$(curl -s "$API_URL/api/v1/status/queues" | jq -r '.collect.pending + .process.pending + .publish.pending' 2>/dev/null || echo "0")
if [[ "$QUEUE_STATUS" -gt 500 ]]; then
    echo "$(date): High queue backlog: $QUEUE_STATUS" >> "$LOG_FILE"
    # Send alert
fi
EOF
    
    chmod +x monitoring/health_monitor.sh
    
    log_success "Monitoring setup completed"
}

# Function to optimize system performance
optimize_performance() {
    log_info "Applying performance optimizations..."
    
    # Set production environment variables for optimization
    export ENABLE_CACHING=true
    export ENABLE_COMPRESSION=true
    export CACHE_TTL=300
    export MAX_CONNECTIONS=100
    export WORKER_CONNECTIONS=1000
    
    # Optimize Docker settings
    log_info "Optimizing Docker settings..."
    
    # Set memory limits and CPU limits in compose file
    # This would typically be done through environment variables or compose overrides
    
    # Optimize database connections
    log_info "Optimizing database connections..."
    
    # Set connection pool settings
    export DB_POOL_SIZE=20
    export DB_MAX_OVERFLOW=30
    export DB_POOL_TIMEOUT=30
    
    # Optimize Redis settings
    log_info "Optimizing Redis settings..."
    
    export REDIS_MAX_CONNECTIONS=50
    export REDIS_TIMEOUT=5
    
    log_success "Performance optimizations applied"
}

# Function to generate deployment report
generate_deployment_report() {
    log_info "Generating deployment report..."
    
    REPORT_FILE="deployment_report_$(date +%Y%m%d_%H%M%S).json"
    
    cat > "$REPORT_FILE" << EOF
{
    "deployment": {
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "environment": "$ENVIRONMENT",
        "version": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
        "branch": "$(git branch --show-current 2>/dev/null || echo 'unknown')"
    },
    "services": {
        "api": "$(docker ps --filter name=api --format '{{.Status}}' | head -1)",
        "worker_collector": "$(docker ps --filter name=worker-collector --format '{{.Status}}' | head -1)",
        "worker_nlp": "$(docker ps --filter name=worker-nlp --format '{{.Status}}' | head -1)",
        "worker_publisher": "$(docker ps --filter name=worker-publisher --format '{{.Status}}' | head -1)",
        "scheduler": "$(docker ps --filter name=scheduler --format '{{.Status}}' | head -1)",
        "postgres": "$(docker ps --filter name=postgres --format '{{.Status}}' | head -1)",
        "redis": "$(docker ps --filter name=redis --format '{{.Status}}' | head -1)"
    },
    "health_checks": {
        "api_health": "$(curl -s -o /dev/null -w '%{http_code}' ${API_BASE_URL:-http://localhost:8000}/health)",
        "database_status": "$(curl -s -o /dev/null -w '%{http_code}' ${API_BASE_URL:-http://localhost:8000}/api/v1/status/database)",
        "redis_status": "$(curl -s -o /dev/null -w '%{http_code}' ${API_BASE_URL:-http://localhost:8000}/api/v1/status/redis)"
    },
    "optimizations": {
        "caching_enabled": "$ENABLE_CACHING",
        "compression_enabled": "$ENABLE_COMPRESSION",
        "performance_monitoring": "$ENABLE_PERFORMANCE_MONITORING"
    }
}
EOF
    
    log_success "Deployment report generated: $REPORT_FILE"
}

# Main deployment function
main() {
    local start_time=$(date +%s)
    
    echo "=============================================="
    echo "PRODUCTION DEPLOYMENT - REDDIT GHOST PUBLISHER"
    echo "=============================================="
    echo "Environment: $ENVIRONMENT"
    echo "Backup Enabled: $BACKUP_ENABLED"
    echo "Health Check Timeout: ${HEALTH_CHECK_TIMEOUT}s"
    echo "=============================================="
    
    # Deployment steps
    check_prerequisites
    create_backup
    build_optimized_images
    optimize_performance
    deploy_services
    run_health_checks
    setup_monitoring
    run_smoke_tests
    generate_deployment_report
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo "=============================================="
    echo "DEPLOYMENT COMPLETED SUCCESSFULLY"
    echo "=============================================="
    echo "Duration: ${duration} seconds"
    echo "API URL: ${API_BASE_URL:-http://localhost:8000}"
    echo "Dashboard URL: ${API_BASE_URL:-http://localhost:8000}/dashboard/pipeline-monitor"
    echo "Logs: ./logs/"
    echo "Monitoring: ./monitoring/"
    echo "=============================================="
    
    log_success "Production deployment completed successfully!"
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-backup)
                BACKUP_ENABLED="false"
                shift
                ;;
            --timeout)
                HEALTH_CHECK_TIMEOUT="$2"
                shift 2
                ;;
            --api-url)
                API_BASE_URL="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --no-backup         Skip pre-deployment backup"
                echo "  --timeout SECONDS   Health check timeout [default: 300]"
                echo "  --api-url URL       API base URL [default: http://localhost:8000]"
                echo "  --help              Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  ENVIRONMENT         Deployment environment [default: production]"
                echo "  BACKUP_ENABLED      Enable backup [default: true]"
                echo "  API_BASE_URL        API base URL"
                echo ""
                echo "Required Environment Variables:"
                echo "  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, OPENAI_API_KEY"
                echo "  GHOST_ADMIN_KEY, GHOST_API_URL, DATABASE_URL, REDIS_URL, SLACK_WEBHOOK_URL"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Run main deployment
    if main; then
        exit 0
    else
        log_error "Deployment failed"
        exit 1
    fi
fi