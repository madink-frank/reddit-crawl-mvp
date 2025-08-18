#!/bin/bash

# Setup Staging Environment for MVP System Verification Tests
# This script prepares the staging environment for comprehensive testing

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running from project root
if [ ! -f "docker-compose.staging.yml" ]; then
    error "Please run this script from the project root directory"
    exit 1
fi

log "Starting staging environment setup for MVP verification tests..."

# 1. Create necessary directories
log "Creating test directories..."
mkdir -p tests/verification/logs
mkdir -p tests/verification/reports
mkdir -p tests/verification/screenshots
mkdir -p tests/verification/artifacts
mkdir -p logs
mkdir -p backups

# 2. Check if .env.staging exists
if [ ! -f ".env.staging" ]; then
    warning ".env.staging not found, creating from template..."
    cp .env.example .env.staging
    warning "Please update .env.staging with your actual API keys and configuration"
fi

# 3. Validate required environment variables
log "Validating environment variables..."
source .env.staging

required_vars=(
    "REDDIT_CLIENT_ID"
    "REDDIT_CLIENT_SECRET"
    "OPENAI_API_KEY"
    "GHOST_ADMIN_KEY"
    "GHOST_API_URL"
    "SLACK_WEBHOOK_URL"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" = "your_${var,,}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    error "Missing or placeholder values for required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    error "Please update .env.staging with actual values before proceeding"
    exit 1
fi

# 4. Stop any existing staging containers
log "Stopping any existing staging containers..."
docker-compose -f docker-compose.staging.yml down --remove-orphans || true

# 5. Build Docker images
log "Building Docker images..."
docker-compose -f docker-compose.staging.yml build --no-cache

# 6. Start staging environment
log "Starting staging environment..."
docker-compose -f docker-compose.staging.yml up -d

# 7. Wait for services to be healthy
log "Waiting for services to be healthy..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    attempt=$((attempt + 1))
    
    # Check PostgreSQL
    if docker-compose -f docker-compose.staging.yml exec -T postgres-staging pg_isready -U postgres > /dev/null 2>&1; then
        postgres_ready=true
    else
        postgres_ready=false
    fi
    
    # Check Redis
    if docker-compose -f docker-compose.staging.yml exec -T redis-staging redis-cli ping > /dev/null 2>&1; then
        redis_ready=true
    else
        redis_ready=false
    fi
    
    # Check API
    if curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
        api_ready=true
    else
        api_ready=false
    fi
    
    if [ "$postgres_ready" = true ] && [ "$redis_ready" = true ] && [ "$api_ready" = true ]; then
        success "All services are healthy!"
        break
    fi
    
    log "Waiting for services... (attempt $attempt/$max_attempts)"
    sleep 10
done

if [ $attempt -eq $max_attempts ]; then
    error "Services failed to become healthy within timeout"
    log "Checking service status..."
    docker-compose -f docker-compose.staging.yml ps
    exit 1
fi

# 8. Run database migrations
log "Running database migrations..."
docker-compose -f docker-compose.staging.yml exec -T api-staging python -m alembic upgrade head

# 9. Verify service connectivity
log "Verifying service connectivity..."

# Test API endpoints
api_endpoints=(
    "/health"
    "/metrics"
    "/api/v1/status/queues"
    "/api/v1/status/workers"
)

for endpoint in "${api_endpoints[@]}"; do
    if curl -s -f "http://localhost:8001$endpoint" > /dev/null; then
        success "API endpoint $endpoint is accessible"
    else
        warning "API endpoint $endpoint is not accessible"
    fi
done

# 10. Initialize test data
log "Initializing test data..."
cat << 'EOF' > /tmp/init_test_data.sql
-- Insert sample test data for verification tests
INSERT INTO posts (
    reddit_post_id, 
    title, 
    subreddit, 
    score, 
    num_comments, 
    created_ts,
    content_hash,
    takedown_status
) VALUES 
(
    'test_post_verification_001',
    'Test Post for Verification',
    'programming',
    100,
    25,
    NOW(),
    'test_hash_001',
    'active'
),
(
    'test_post_verification_002', 
    'Another Test Post',
    'technology',
    250,
    45,
    NOW(),
    'test_hash_002',
    'active'
) ON CONFLICT (reddit_post_id) DO NOTHING;
EOF

docker-compose -f docker-compose.staging.yml exec -T postgres-staging psql -U postgres -d reddit_publisher_staging -f - < /tmp/init_test_data.sql
rm /tmp/init_test_data.sql

# 11. Test Slack webhook (if configured)
if [ "$SLACK_WEBHOOK_URL" != "https://hooks.slack.com/services/TEST/WEBHOOK/URL" ]; then
    log "Testing Slack webhook..."
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"🧪 Staging environment setup complete - verification tests ready to run"}' \
        "$SLACK_WEBHOOK_URL" || warning "Slack webhook test failed"
else
    warning "Slack webhook not configured (using placeholder URL)"
fi

# 12. Create test configuration summary
log "Creating test configuration summary..."
cat << EOF > tests/verification/staging_config.json
{
    "environment": "staging",
    "setup_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "api_base_url": "http://localhost:8001",
    "database_url": "postgresql://postgres:postgres_staging@localhost:5433/reddit_publisher_staging",
    "redis_url": "redis://localhost:6380/0",
    "services": {
        "api": "http://localhost:8001",
        "postgres": "localhost:5433",
        "redis": "localhost:6380"
    },
    "test_configuration": {
        "subreddits": ["programming", "technology"],
        "batch_size": 5,
        "reddit_daily_calls_limit": 100,
        "openai_daily_tokens_limit": 1000,
        "queue_alert_threshold": 10,
        "failure_rate_threshold": 0.05,
        "retry_max": 3,
        "backoff_base": 2,
        "backoff_min": 2,
        "backoff_max": 8
    },
    "external_services": {
        "reddit_api": "https://www.reddit.com",
        "openai_api": "https://api.openai.com",
        "ghost_api": "$GHOST_API_URL",
        "slack_webhook": "$(echo $SLACK_WEBHOOK_URL | sed 's/.*\/services\//***\/services\//')"
    }
}
EOF

# 13. Display final status
log "Staging environment setup complete!"
echo
success "=== STAGING ENVIRONMENT STATUS ==="
echo "API URL: http://localhost:8001"
echo "Database: localhost:5433 (reddit_publisher_staging)"
echo "Redis: localhost:6380"
echo
echo "Running services:"
docker-compose -f docker-compose.staging.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo
success "=== NEXT STEPS ==="
echo "1. Verify all environment variables in .env.staging are correct"
echo "2. Test external API connectivity (Reddit, OpenAI, Ghost, Slack)"
echo "3. Run verification tests:"
echo "   python tests/verification/run_verification_tests.py --environment staging"
echo
echo "To view logs:"
echo "   docker-compose -f docker-compose.staging.yml logs -f [service-name]"
echo
echo "To stop staging environment:"
echo "   docker-compose -f docker-compose.staging.yml down"
echo

log "Setup script completed successfully!"