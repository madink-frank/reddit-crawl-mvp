# Operations Manual - MVP

## Overview

This manual provides guidance for deploying, operating, and maintaining the Reddit Ghost Publisher MVP system. The MVP is designed for single-node deployment with simplified architecture, basic monitoring, and manual scaling operations.

## Table of Contents

- [System Architecture](#system-architecture)
- [Manual Deployment Procedures](#manual-deployment-procedures)
- [Environment Configuration](#environment-configuration)
- [Basic Monitoring](#basic-monitoring)
- [Maintenance Tasks](#maintenance-tasks)
- [Backup and Recovery](#backup-and-recovery)
- [Security Operations](#security-operations)
- [Manual Scaling](#manual-scaling)
- [Slack Alert Response](#slack-alert-response)

## System Architecture

### MVP Single Node Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI API   │    │   Celery Beat   │    │   Backup Cron   │
│   (Port 8000)   │    │   Scheduler     │    │   Container     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Celery Workers  │    │     Redis       │    │   PostgreSQL    │
│ (3 Single-Conc) │────│   (Message      │────│   (Primary      │
│ collect/process │    │    Queue)       │    │   Database)     │
│ /publish        │    └─────────────────┘    └─────────────────┘
└─────────────────┘             │                       │
         │                      │                       │
         │                      │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Basic Logs    │    │  Environment    │    │   External      │
│   (JSON Format) │    │   Variables     │    │   Services      │
│   + Slack       │    │   (No Vault)    │    │ (Reddit, OpenAI,│
│   Alerts        │    │                 │    │    Ghost)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Service Dependencies (MVP)

- **FastAPI API**: Depends on PostgreSQL, Redis
- **Celery Workers**: Depend on PostgreSQL, Redis, External APIs
- **Celery Beat**: Depends on Redis, PostgreSQL
- **Basic Monitoring**: /health, /metrics endpoints, Slack notifications

## Manual Deployment Procedures

### Pre-Deployment Checklist (MVP)

#### Infrastructure Requirements

- [ ] **Single Node Resources**
  - Minimum: 2 vCPU, 4GB RAM
  - Recommended: 4 vCPU, 8GB RAM for production
  - Storage: 50GB SSD minimum

- [ ] **Network Requirements**
  - Basic HTTP/HTTPS access (reverse proxy optional)
  - Domain name or IP address
  - Basic firewall rules (ports 8000, 5432, 6379)

- [ ] **External Services**
  - Reddit API credentials configured
  - OpenAI API key with sufficient credits
  - Ghost CMS instance accessible
  - Slack webhook URL for notifications

#### Environment Preparation

```bash
# 1. Create deployment directory
sudo mkdir -p /opt/reddit-ghost-publisher
cd /opt/reddit-ghost-publisher

# 2. Clone repository
git clone https://github.com/your-org/reddit-ghost-publisher.git .
git checkout main

# 3. Set up environment
cp .env.example .env
# Edit .env with production values

# 4. Create necessary directories
sudo mkdir -p /var/log/reddit-publisher
sudo mkdir -p /var/lib/reddit-publisher/backups
sudo chown -R $USER:$USER /var/log/reddit-publisher
sudo chown -R $USER:$USER /var/lib/reddit-publisher
```

### Manual Deployment (MVP)

#### Single Node Docker Compose Deployment

```bash
# 1. Build and deploy services
docker-compose build
docker-compose up -d

# 2. Verify deployment
docker-compose ps
docker-compose logs -f

# 3. Run health checks
curl -f http://localhost:8000/health || echo "Health check failed"

# 4. Check individual services
curl http://localhost:8000/api/v1/status/queues
curl http://localhost:8000/api/v1/status/workers
curl http://localhost:8000/metrics
```

#### Manual Deployment Script

```bash
#!/bin/bash
# deploy.sh - Manual deployment script

set -e

echo "🚀 Starting Reddit Ghost Publisher deployment..."

# 1. Pull latest code
git pull origin main

# 2. Build containers
echo "📦 Building containers..."
docker-compose build

# 3. Stop existing services
echo "⏹️ Stopping existing services..."
docker-compose down

# 4. Start services
echo "▶️ Starting services..."
docker-compose up -d

# 5. Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# 6. Run health checks
echo "🏥 Running health checks..."
if curl -f http://localhost:8000/health; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    docker-compose logs
    exit 1
fi

# 7. Run smoke tests
echo "🧪 Running smoke tests..."
if command -v newman &> /dev/null; then
    newman run tests/postman/smoke-tests.json --environment tests/postman/test-env.json
    if [ $? -eq 0 ]; then
        echo "✅ Smoke tests passed"
    else
        echo "❌ Smoke tests failed - rolling back"
        docker-compose down
        exit 1
    fi
else
    echo "⚠️ Newman not installed, skipping smoke tests"
fi

echo "🎉 Deployment completed successfully!"
```

### Post-Deployment Verification

```bash
# 1. Basic health checks
curl -f http://localhost:8000/health
curl -f http://localhost:8000/metrics

# 2. API functionality (no authentication in MVP)
curl http://localhost:8000/api/v1/status/queues
curl http://localhost:8000/api/v1/status/workers

# 3. Database connectivity
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "SELECT COUNT(*) FROM posts;"

# 4. Redis connectivity
docker exec -it reddit-ghost-publisher-redis-1 redis-cli ping

# 5. Celery workers
docker exec -it reddit-ghost-publisher-worker-collector-1 celery -A app.celery_app inspect ping

# 6. Test manual triggers
curl -X POST http://localhost:8000/api/v1/collect/trigger \
  -H "Content-Type: application/json" \
  -d '{"subreddits": ["test"], "sort_type": "hot", "limit": 5}'

# 7. Check logs for errors
docker-compose logs --tail=50 | grep -i error
```

## Environment Configuration

### Environment Variables (MVP)

#### Production Environment File

```bash
# /opt/reddit-ghost-publisher/.env

# Application Configuration
DEBUG=false
ENVIRONMENT=production
TZ=UTC

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Database Configuration (PostgreSQL only)
DATABASE_URL=postgresql://postgres:your_password@postgres:5432/reddit_publisher
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=20

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_TIMEZONE=UTC

# Reddit API Configuration with Budget Limits
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=RedditGhostPublisher/1.0
REDDIT_RATE_LIMIT_RPM=60
REDDIT_DAILY_CALLS_LIMIT=5000

# OpenAI Configuration with Budget Limits
OPENAI_API_KEY=your_openai_api_key
OPENAI_PRIMARY_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODEL=gpt-4o
OPENAI_DAILY_TOKENS_LIMIT=100000

# Cost per 1K tokens (fixed internal cost map)
COST_GPT4O_MINI_PER_1K=0.00015
COST_GPT4O_PER_1K=0.005

# Ghost CMS Configuration
GHOST_ADMIN_KEY=your_ghost_admin_key
GHOST_API_URL=https://your-blog.ghost.io
GHOST_JWT_EXPIRY=300
DEFAULT_OG_IMAGE_URL=https://your-blog.ghost.io/content/images/default-og.jpg

# Scheduling Configuration (Cron expressions)
COLLECT_CRON=0 * * * *
BACKUP_CRON=0 4 * * *

# Content Processing Configuration
SUBREDDITS=programming,technology,webdev
BATCH_SIZE=20
CONTENT_MIN_SCORE=10
CONTENT_MIN_COMMENTS=5

# Monitoring and Alerting
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

# Alert Thresholds
QUEUE_ALERT_THRESHOLD=500
FAILURE_RATE_THRESHOLD=0.05

# Worker Configuration (Single node)
WORKER_COLLECTOR_CONCURRENCY=1
WORKER_NLP_CONCURRENCY=1
WORKER_PUBLISHER_CONCURRENCY=1

# Retry Configuration (Constants)
RETRY_MAX=3
BACKOFF_BASE=2
BACKOFF_MIN=2
BACKOFF_MAX=8

# Security Configuration (Environment variables only, no Vault)
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Database Credentials (for Docker Compose)
POSTGRES_DB=reddit_publisher
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_PORT=5432

# Redis Configuration (for Docker Compose)
REDIS_PORT=6379
```

### Environment Variable Security (MVP)

#### Secure Environment Variable Management

```bash
# 1. Set proper file permissions
chmod 600 /opt/reddit-ghost-publisher/.env
chown root:root /opt/reddit-ghost-publisher/.env

# 2. Use environment variable validation
# Add to your deployment script:
validate_env_vars() {
    required_vars=(
        "REDDIT_CLIENT_ID"
        "REDDIT_CLIENT_SECRET" 
        "OPENAI_API_KEY"
        "GHOST_ADMIN_KEY"
        "SLACK_WEBHOOK_URL"
        "DATABASE_URL"
        "REDIS_URL"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            echo "❌ Required environment variable $var is not set"
            exit 1
        fi
    done
    echo "✅ All required environment variables are set"
}

# 3. Mask sensitive values in logs
# This is handled automatically by the application's PII masking logic
```

#### Environment Variable Backup

```bash
# Create encrypted backup of environment variables
gpg --symmetric --cipher-algo AES256 --output .env.backup.gpg .env

# Store backup securely (example with AWS S3)
aws s3 cp .env.backup.gpg s3://your-backup-bucket/config/

# To restore:
aws s3 cp s3://your-backup-bucket/config/.env.backup.gpg .
gpg --decrypt .env.backup.gpg > .env
```

### Optional Reverse Proxy Configuration

#### Basic Nginx Configuration (Optional)

```nginx
# /etc/nginx/sites-available/reddit-publisher
server {
    listen 80;
    server_name your-domain.com;

    # Basic proxy configuration
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Basic timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        access_log off;
    }

    # Metrics endpoint (restrict if needed)
    location /metrics {
        # Uncomment to restrict access
        # allow 192.168.1.0/24;
        # deny all;
        
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

#### Direct Access (Default MVP)

The MVP runs directly on port 8000 without requiring a reverse proxy:

```bash
# Access the application directly
curl http://your-server:8000/health
curl http://your-server:8000/api/v1/status/queues
curl http://your-server:8000/metrics
```

## Basic Monitoring

### Built-in Monitoring Endpoints

#### Health Check Monitoring

```bash
# Basic health check
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "database": {"status": "healthy", "response_time_ms": 12.5},
    "redis": {"status": "healthy", "response_time_ms": 3.2},
    "external_apis": {
      "reddit": "healthy",
      "openai": "healthy", 
      "ghost": "healthy"
    }
  }
}
```

#### Queue Status Monitoring

```bash
# Check queue depths
curl http://localhost:8000/api/v1/status/queues

# Expected response:
{
  "collect": {"active": 1, "reserved": 0, "scheduled": 0, "queued": 5},
  "process": {"active": 1, "reserved": 0, "scheduled": 0, "queued": 12},
  "publish": {"active": 1, "reserved": 0, "scheduled": 0, "queued": 3}
}
```

#### Worker Status Monitoring

```bash
# Check worker health
curl http://localhost:8000/api/v1/status/workers

# Expected response:
{
  "worker-collector-1": {
    "status": "online",
    "active_tasks": 1,
    "heartbeat": "2024-01-15T10:29:45Z",
    "queues": ["collect"]
  },
  "worker-nlp-1": {
    "status": "online", 
    "active_tasks": 1,
    "heartbeat": "2024-01-15T10:29:50Z",
    "queues": ["process"]
  }
}
```

#### Metrics Endpoint

```bash
# Get Prometheus metrics
curl http://localhost:8000/metrics

# Key metrics to monitor:
# - reddit_posts_collected_total
# - posts_processed_total  
# - posts_published_total
# - processing_failures_total
# - api_errors_total{service="reddit",error_type="429"}
```

### Slack Alert Configuration

#### Alert Types and Thresholds

1. **Queue Depth Alerts**: When queue > 500 items
2. **Failure Rate Alerts**: When failure rate > 5% in 5-minute window
3. **Budget Alerts**: When API/token usage reaches 80% or 100%
4. **Daily Reports**: Summary of daily activity

#### Slack Alert Response Procedures

**Queue Depth Alert (>500 items)**
```bash
# 1. Check current queue status
curl http://localhost:8000/api/v1/status/queues

# 2. Check worker status
curl http://localhost:8000/api/v1/status/workers

# 3. If workers are healthy, consider manual scaling:
docker-compose up -d --scale worker-collector=2
docker-compose up -d --scale worker-nlp=2
docker-compose up -d --scale worker-publisher=2

# 4. Monitor queue reduction
watch -n 30 'curl -s http://localhost:8000/api/v1/status/queues | jq'
```

**Failure Rate Alert (>5%)**
```bash
# 1. Check recent errors
docker-compose logs --tail=100 | grep -i error

# 2. Check external API status
curl -I https://oauth.reddit.com/api/v1/me
curl -I https://api.openai.com/v1/models
curl -I https://your-ghost-site.com/

# 3. Check system resources
docker stats
df -h

# 4. If needed, restart services
docker-compose restart worker-collector worker-nlp worker-publisher
```

**Budget Alert (80% usage)**
```bash
# 1. Check current usage via logs
docker-compose logs | grep -i "budget\|quota\|limit"

# 2. Review daily usage patterns
curl http://localhost:8000/metrics | grep -E "(reddit_calls|openai_tokens)"

# 3. Consider reducing collection frequency temporarily
# Edit COLLECT_CRON in .env from "0 * * * *" to "0 */2 * * *"
# Then restart: docker-compose restart celery-beat
```

### Daily Monitoring Checklist

#### Automated Daily Report

The system sends daily reports to Slack with:
- Posts collected, processed, published
- Token usage and cost estimates
- Error counts by service
- Queue status summary

#### Manual Daily Checks

```bash
# 1. Check overall system health
curl http://localhost:8000/health

# 2. Review error logs
docker-compose logs --since=24h | grep -i error | wc -l

# 3. Check disk usage
df -h

# 4. Verify backup completion
ls -la /var/lib/reddit-publisher/backups/ | head -5

# 5. Check queue backlogs
curl -s http://localhost:8000/api/v1/status/queues | jq '.[] | select(.queued > 100)'
```

## Maintenance Tasks

### Daily Tasks (Automated)

#### Backup Container (Automated via Docker Compose)

The backup container runs daily at 4 AM UTC:

```bash
# Check backup container status
docker-compose logs backup

# Verify backup files
ls -la /var/lib/reddit-publisher/backups/

# Expected files:
# backup_20240115_040001.sql.gz
# backup_20240114_040001.sql.gz
# ... (7 days retained)
```

#### Daily Verification Checklist

```bash
#!/bin/bash
# daily-check.sh - Run this manually each day

echo "🔍 Daily Reddit Ghost Publisher Health Check"

# 1. System health
echo "1. Checking system health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ System healthy"
else
    echo "❌ System health check failed"
fi

# 2. Queue status
echo "2. Checking queue status..."
QUEUE_STATUS=$(curl -s http://localhost:8000/api/v1/status/queues)
COLLECT_QUEUED=$(echo $QUEUE_STATUS | jq -r '.collect.queued')
PROCESS_QUEUED=$(echo $QUEUE_STATUS | jq -r '.process.queued')
PUBLISH_QUEUED=$(echo $QUEUE_STATUS | jq -r '.publish.queued')

if [ "$COLLECT_QUEUED" -lt 100 ] && [ "$PROCESS_QUEUED" -lt 100 ] && [ "$PUBLISH_QUEUED" -lt 100 ]; then
    echo "✅ Queue depths normal (C:$COLLECT_QUEUED, P:$PROCESS_QUEUED, Pub:$PUBLISH_QUEUED)"
else
    echo "⚠️ High queue depths detected (C:$COLLECT_QUEUED, P:$PROCESS_QUEUED, Pub:$PUBLISH_QUEUED)"
fi

# 3. Disk usage
echo "3. Checking disk usage..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo "✅ Disk usage normal ($DISK_USAGE%)"
else
    echo "⚠️ High disk usage ($DISK_USAGE%)"
fi

# 4. Recent errors
echo "4. Checking for recent errors..."
ERROR_COUNT=$(docker-compose logs --since=24h | grep -i error | wc -l)
if [ "$ERROR_COUNT" -lt 10 ]; then
    echo "✅ Error count normal ($ERROR_COUNT in last 24h)"
else
    echo "⚠️ High error count ($ERROR_COUNT in last 24h)"
fi

# 5. Backup verification
echo "5. Checking backup status..."
LATEST_BACKUP=$(ls -t /var/lib/reddit-publisher/backups/backup_*.sql.gz 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_AGE=$(find "$LATEST_BACKUP" -mtime -1)
    if [ -n "$BACKUP_AGE" ]; then
        echo "✅ Recent backup found: $(basename $LATEST_BACKUP)"
    else
        echo "⚠️ Latest backup is older than 24 hours"
    fi
else
    echo "❌ No backups found"
fi

echo "📊 Daily check completed"
```

### Weekly Tasks (Manual)

#### Weekly Maintenance Checklist

```bash
#!/bin/bash
# weekly-maintenance.sh - Run manually each week

echo "🔧 Weekly Reddit Ghost Publisher Maintenance"

# 1. System updates
echo "1. Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Docker cleanup
echo "2. Cleaning up Docker resources..."
docker system prune -f
docker volume prune -f

# 3. Database maintenance
echo "3. Running database maintenance..."
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "
VACUUM ANALYZE posts;
VACUUM ANALYZE processing_logs;
VACUUM ANALYZE token_usage;
VACUUM ANALYZE media_files;
"

# 4. Log cleanup
echo "4. Cleaning up old logs..."
find /var/log/reddit-publisher -name "*.log" -mtime +30 -delete
docker-compose logs --tail=0 # Clear container logs

# 5. Backup verification
echo "5. Testing backup restore..."
LATEST_BACKUP=$(ls -t /var/lib/reddit-publisher/backups/backup_*.sql.gz | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    # Test restore to temporary database
    docker exec -it reddit-ghost-publisher-postgres-1 createdb -U postgres test_restore
    gunzip -c "$LATEST_BACKUP" | docker exec -i reddit-ghost-publisher-postgres-1 psql -U postgres -d test_restore
    RECORD_COUNT=$(docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d test_restore -t -c "SELECT COUNT(*) FROM posts;")
    echo "✅ Backup restore test: $RECORD_COUNT records"
    docker exec -it reddit-ghost-publisher-postgres-1 dropdb -U postgres test_restore
else
    echo "❌ No backup found for testing"
fi

# 6. Performance check
echo "6. Checking performance metrics..."
curl -s http://localhost:8000/metrics | grep -E "(reddit_posts_collected_total|posts_processed_total|posts_published_total|processing_failures_total)"

echo "🎉 Weekly maintenance completed"
```

### Monthly Tasks (Manual)

#### Monthly Review Checklist

```bash
#!/bin/bash
# monthly-review.sh - Run manually each month

echo "📊 Monthly Reddit Ghost Publisher Review"

# 1. Cost analysis
echo "1. Analyzing costs..."
MONTHLY_TOKENS=$(docker-compose logs --since=720h | grep -i "token.*usage" | wc -l)
echo "Estimated monthly token usage events: $MONTHLY_TOKENS"

# 2. Performance analysis
echo "2. Analyzing performance..."
curl -s http://localhost:8000/metrics > /tmp/monthly-metrics.txt
echo "Current metrics saved to /tmp/monthly-metrics.txt"

# 3. Security check
echo "3. Running basic security checks..."
# Check for exposed ports
netstat -tuln | grep -E ":8000|:5432|:6379"

# Check file permissions
ls -la /opt/reddit-ghost-publisher/.env

# 4. Capacity planning
echo "4. Checking capacity..."
df -h
docker stats --no-stream

# 5. Archive old data (optional)
echo "5. Archiving old data..."
ARCHIVE_DATE=$(date -d '90 days ago' '+%Y-%m-%d')
echo "Consider archiving posts older than $ARCHIVE_DATE"

echo "📈 Monthly review completed"
```

## Backup and Recovery

### Automated Backup System (MVP)

#### Backup Container Configuration

The backup system runs as a dedicated container with cron:

```yaml
# From docker-compose.yml
backup:
  image: postgres:15-alpine
  command: >
    sh -c "
      echo '${BACKUP_CRON:-0 4 * * *} /usr/local/bin/backup-database.sh' | crontab - &&
      crond -f
    "
  environment:
    - PGHOST=postgres
    - PGUSER=${POSTGRES_USER}
    - PGPASSWORD=${POSTGRES_PASSWORD}
    - PGDATABASE=reddit_publisher
  volumes:
    - ./scripts/backup-database.sh:/usr/local/bin/backup-database.sh:ro
    - postgres_backups:/backups
  depends_on:
    - postgres
  restart: unless-stopped
```

#### Backup Script

```bash
# scripts/backup-database.sh
#!/bin/bash
set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="reddit_publisher"

# Create backup
pg_dump -h postgres -U ${PGUSER} -d ${DB_NAME} > ${BACKUP_DIR}/backup_${DATE}.sql

# Compress backup
gzip ${BACKUP_DIR}/backup_${DATE}.sql

# Keep only last 7 days
find ${BACKUP_DIR} -name "backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: backup_${DATE}.sql.gz"
```

#### Manual Backup

```bash
# Create immediate backup
docker exec -it reddit-ghost-publisher-backup-1 /usr/local/bin/backup-database.sh

# Or create backup manually
docker exec -it reddit-ghost-publisher-postgres-1 pg_dump -U postgres reddit_publisher | gzip > backup_manual_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Backup Verification

#### Weekly Restore Test

```bash
#!/bin/bash
# test-backup-restore.sh - Run weekly to verify backups

set -e

echo "🧪 Testing backup restore..."

# Get latest backup
LATEST_BACKUP=$(ls -t /var/lib/reddit-publisher/backups/backup_*.sql.gz | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup files found"
    exit 1
fi

echo "Testing backup: $(basename $LATEST_BACKUP)"

# Create test database
docker exec -it reddit-ghost-publisher-postgres-1 createdb -U postgres test_restore

# Restore backup
gunzip -c "$LATEST_BACKUP" | docker exec -i reddit-ghost-publisher-postgres-1 psql -U postgres -d test_restore

# Verify data
RECORD_COUNT=$(docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d test_restore -t -c "SELECT COUNT(*) FROM posts;")
INDEX_COUNT=$(docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d test_restore -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';")

echo "✅ Restore test successful:"
echo "   Records: $RECORD_COUNT"
echo "   Indexes: $INDEX_COUNT"

# Cleanup test database
docker exec -it reddit-ghost-publisher-postgres-1 dropdb -U postgres test_restore

echo "🎉 Backup verification completed"
```

### Disaster Recovery Procedures (MVP)

#### Complete System Recovery

```bash
#!/bin/bash
# disaster-recovery.sh - Complete system recovery procedure

set -e

echo "🚨 Starting disaster recovery procedure..."

# 1. Prepare new environment
echo "1. Setting up new environment..."
mkdir -p /opt/reddit-ghost-publisher-recovery
cd /opt/reddit-ghost-publisher-recovery

# 2. Clone repository
echo "2. Cloning repository..."
git clone https://github.com/your-org/reddit-ghost-publisher.git .
git checkout main

# 3. Restore configuration
echo "3. Restoring configuration..."
# Restore .env from backup (manual step)
echo "⚠️ MANUAL STEP: Copy .env file from backup"
echo "   Expected location: /path/to/env/backup/.env"
read -p "Press Enter when .env is restored..."

# 4. Start infrastructure services
echo "4. Starting infrastructure services..."
docker-compose up -d postgres redis

# Wait for services to be ready
sleep 30

# 5. Restore database
echo "5. Restoring database..."
BACKUP_FILE="/path/to/backup.sql.gz"
if [ -f "$BACKUP_FILE" ]; then
    gunzip -c "$BACKUP_FILE" | docker exec -i reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher
    echo "✅ Database restored"
else
    echo "❌ Backup file not found: $BACKUP_FILE"
    echo "⚠️ MANUAL STEP: Locate and restore database backup"
    read -p "Press Enter when database is restored..."
fi

# 6. Start application services
echo "6. Starting application services..."
docker-compose up -d

# Wait for services to be ready
sleep 60

# 7. Verify recovery
echo "7. Verifying recovery..."
if curl -f http://localhost:8000/health; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    docker-compose logs
    exit 1
fi

# 8. Test functionality
echo "8. Testing functionality..."
curl -s http://localhost:8000/api/v1/status/queues | jq
curl -s http://localhost:8000/api/v1/status/workers | jq

echo "🎉 Disaster recovery completed successfully!"
echo "📋 Next steps:"
echo "   - Update DNS records if needed"
echo "   - Monitor logs for issues"
echo "   - Verify external API connectivity"
echo "   - Test manual triggers"
```

#### Partial Recovery Scenarios

**Database Corruption:**
```bash
# 1. Stop application services (keep infrastructure)
docker-compose stop api worker-collector worker-nlp worker-publisher

# 2. Backup current corrupted database (just in case)
docker exec -it reddit-ghost-publisher-postgres-1 pg_dump -U postgres reddit_publisher > corrupted_backup_$(date +%Y%m%d_%H%M%S).sql

# 3. Drop and recreate database
docker exec -it reddit-ghost-publisher-postgres-1 dropdb -U postgres reddit_publisher
docker exec -it reddit-ghost-publisher-postgres-1 createdb -U postgres reddit_publisher

# 4. Restore from latest backup
LATEST_BACKUP=$(ls -t /var/lib/reddit-publisher/backups/backup_*.sql.gz | head -1)
gunzip -c "$LATEST_BACKUP" | docker exec -i reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher

# 5. Restart application services
docker-compose start api worker-collector worker-nlp worker-publisher

# 6. Verify recovery
curl http://localhost:8000/health
```

**Redis Data Loss:**
```bash
# Redis data is ephemeral, just restart workers to rebuild queues
docker-compose restart worker-collector worker-nlp worker-publisher celery-beat

# Verify queue status
curl http://localhost:8000/api/v1/status/queues
```

**Configuration Loss:**
```bash
# 1. Restore from version control
git checkout main
git pull origin main

# 2. Restore environment variables from backup
# (Manual step - restore .env from secure backup)

# 3. Restart all services
docker-compose restart

# 4. Verify configuration
curl http://localhost:8000/health
```

**Container Issues:**
```bash
# 1. Rebuild containers
docker-compose build --no-cache

# 2. Restart services
docker-compose down
docker-compose up -d

# 3. Check logs
docker-compose logs -f
```

## Security Operations

### Basic Security Monitoring (MVP)

#### Log Analysis

```bash
# Check for errors in application logs
docker-compose logs | grep -i "error\|exception\|failed"

# Monitor for suspicious patterns
docker-compose logs | grep -i "injection\|script\|unauthorized"

# Check for external API errors
docker-compose logs | grep -E "(reddit|openai|ghost).*error"
```

#### Environment Variable Security

```bash
# Verify environment file permissions
ls -la /opt/reddit-ghost-publisher/.env
# Should be: -rw------- (600) root root

# Check for exposed secrets in logs (should be masked)
docker-compose logs | grep -E "(api_key|secret|password|token)" || echo "✅ No exposed secrets found"

# Verify PII masking is working
docker-compose logs | grep -E "(\*\*\*\*)" && echo "✅ PII masking active" || echo "⚠️ Check PII masking"
```

#### Basic Security Checklist

```bash
#!/bin/bash
# security-check.sh - Basic security verification

echo "🔒 Basic Security Check"

# 1. Check file permissions
echo "1. Checking file permissions..."
ENV_PERMS=$(stat -c "%a" /opt/reddit-ghost-publisher/.env)
if [ "$ENV_PERMS" = "600" ]; then
    echo "✅ Environment file permissions correct"
else
    echo "⚠️ Environment file permissions: $ENV_PERMS (should be 600)"
fi

# 2. Check for exposed ports
echo "2. Checking exposed ports..."
netstat -tuln | grep -E ":8000|:5432|:6379"

# 3. Check Docker security
echo "3. Checking Docker security..."
docker ps --format "table {{.Names}}\t{{.Ports}}"

# 4. Verify external API connectivity
echo "4. Testing external API security..."
curl -I https://oauth.reddit.com/api/v1/me 2>/dev/null | head -1
curl -I https://api.openai.com/v1/models 2>/dev/null | head -1

echo "🔒 Security check completed"
```

### Takedown Request Handling

#### Takedown Workflow (2-Stage Process)

```bash
# Handle takedown request via API
curl -X POST http://localhost:8000/api/v1/takedown/reddit_post_id_here \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Copyright infringement",
    "contact_email": "requester@example.com"
  }'

# Expected response:
{
  "status": "processed",
  "message": "Content unpublished, deletion scheduled in 72h",
  "reddit_post_id": "abc123",
  "scheduled_deletion": "2024-01-18T10:30:00Z"
}
```

#### Takedown Audit Log

```bash
# Check takedown audit logs
docker-compose logs | grep -i "takedown"

# Expected log entries:
# - takedown_request_received
# - unpublished_immediately  
# - takedown_deletion_completed
```

## Manual Scaling

### Performance Monitoring

#### Basic Performance Checks

```bash
# Check API response times
time curl http://localhost:8000/health

# Monitor system resources
docker stats --no-stream

# Check queue processing rates
curl -s http://localhost:8000/metrics | grep -E "(processed_total|failures_total)"

# Database performance check
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "
SELECT 
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables 
ORDER BY n_tup_ins DESC;
"
```

### Manual Scaling Procedures

#### Scale Workers Up (High Queue Depth)

```bash
# When queue depth > 500, scale up workers
echo "📈 Scaling up workers due to high queue depth"

# Check current queue status
curl -s http://localhost:8000/api/v1/status/queues | jq

# Scale up workers (from 1 to 2 each)
docker-compose up -d --scale worker-collector=2
docker-compose up -d --scale worker-nlp=2  
docker-compose up -d --scale worker-publisher=2

# Monitor scaling effect
echo "⏳ Monitoring queue reduction..."
for i in {1..10}; do
    echo "Check $i:"
    curl -s http://localhost:8000/api/v1/status/queues | jq '.[] | {queue: .queue, queued: .queued}'
    sleep 30
done
```

#### Scale Workers Down (Low Queue Depth)

```bash
# When queue depth < 100 and workers > 1, scale down
echo "📉 Scaling down workers due to low queue depth"

# Scale down to single workers
docker-compose up -d --scale worker-collector=1
docker-compose up -d --scale worker-nlp=1
docker-compose up -d --scale worker-publisher=1

echo "✅ Scaled down to single workers"
```

#### Resource-Based Scaling

```bash
# Check system resources
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')

echo "Memory usage: ${MEMORY_USAGE}%"
echo "CPU usage: ${CPU_USAGE}%"

if [ "$MEMORY_USAGE" -gt 80 ]; then
    echo "⚠️ High memory usage - consider scaling down or adding resources"
fi

if [ "$CPU_USAGE" -gt 80 ]; then
    echo "⚠️ High CPU usage - consider scaling down or adding resources"
fi
```

### Performance Optimization

#### Database Maintenance

```bash
# Weekly database maintenance
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "
-- Vacuum and analyze tables
VACUUM ANALYZE posts;
VACUUM ANALYZE processing_logs;
VACUUM ANALYZE token_usage;
VACUUM ANALYZE media_files;

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

#### Redis Optimization

```bash
# Check Redis memory usage
docker exec -it reddit-ghost-publisher-redis-1 redis-cli info memory

# Clear old cache data if needed (CAUTION: Will clear cache)
# docker exec -it reddit-ghost-publisher-redis-1 redis-cli flushdb

# Monitor Redis performance
docker exec -it reddit-ghost-publisher-redis-1 redis-cli --latency -i 1
```

## Slack Alert Response

### Alert Types and Response Procedures

#### Queue Depth Alert (>500 items)

**Alert Message:**
```
🚨 [HIGH] Reddit Publisher Alert
Service: collector
Message: Queue depth exceeded threshold
Queue Depth: 523
Threshold: 500
```

**Response Procedure:**
```bash
# 1. Acknowledge alert in Slack
# Reply with: "🔍 Investigating queue depth alert"

# 2. Check current status
curl -s http://localhost:8000/api/v1/status/queues | jq

# 3. Check worker health
curl -s http://localhost:8000/api/v1/status/workers | jq

# 4. If workers are healthy, scale up
docker-compose up -d --scale worker-collector=2

# 5. Monitor for 15 minutes
watch -n 60 'curl -s http://localhost:8000/api/v1/status/queues | jq ".collect.queued"'

# 6. Update Slack when resolved
# Reply with: "✅ Queue depth normalized, scaled to 2 workers"
```

#### Failure Rate Alert (>5%)

**Alert Message:**
```
🚨 [HIGH] Reddit Publisher Alert  
Service: nlp_pipeline
Message: Failure rate exceeded 5% in last 5 minutes
Failure Rate: 8.2%
Time Window: 5 minutes
```

**Response Procedure:**
```bash
# 1. Check recent errors
docker-compose logs --tail=100 worker-nlp | grep -i error

# 2. Check external API status
curl -I https://api.openai.com/v1/models

# 3. Check token budget
curl -s http://localhost:8000/metrics | grep openai_tokens

# 4. If API issue, wait for recovery
# If budget issue, reduce processing temporarily

# 5. Restart workers if needed
docker-compose restart worker-nlp

# 6. Monitor failure rate
curl -s http://localhost:8000/metrics | grep processing_failures_total
```

#### Budget Alert (80% usage)

**Alert Message:**
```
⚠️ [MEDIUM] Reddit Publisher Alert
Service: openai
Message: Daily token budget 80% reached
Usage: 80,000 / 100,000 tokens
Projected Daily: 95,000 tokens
```

**Response Procedure:**
```bash
# 1. Check current usage
curl -s http://localhost:8000/metrics | grep openai_tokens

# 2. Review recent processing
docker-compose logs --since=1h | grep -i "token.*usage"

# 3. Consider reducing collection frequency
# Edit .env: COLLECT_CRON=0 */2 * * * (every 2 hours)
# Restart: docker-compose restart celery-beat

# 4. Monitor usage for rest of day
# 5. Reset will happen automatically at UTC 00:00
```

#### Daily Report

**Report Message:**
```
📊 Daily Reddit Publisher Report
Posts Collected: 245
Posts Published: 238
Token Usage: 45,230
Est. Cost: $2.26
```

**Review Actions:**
```bash
# 1. Verify numbers look reasonable
curl -s http://localhost:8000/metrics | grep -E "(collected_total|published_total)"

# 2. Check for any anomalies
# - Unusually high/low collection numbers
# - High token usage relative to posts
# - High failure rates

# 3. No action needed if numbers are normal
# 4. Investigate if numbers seem unusual
```

This operations manual provides guidance for managing the Reddit Ghost Publisher MVP system. The focus is on simple, manual procedures that ensure reliable operation while keeping complexity minimal.