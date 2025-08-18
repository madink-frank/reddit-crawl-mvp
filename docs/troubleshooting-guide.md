# Troubleshooting Guide - MVP

## Overview

This guide provides step-by-step troubleshooting procedures for common issues encountered with the Reddit Ghost Publisher MVP system. It focuses on single-node deployment issues, basic monitoring problems, and external API integration issues.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Application Issues](#application-issues)
- [Database Issues](#database-issues)
- [Redis and Queue Issues](#redis-and-queue-issues)
- [External API Issues](#external-api-issues)
- [Performance Issues](#performance-issues)
- [Deployment Issues](#deployment-issues)
- [Slack Alert Troubleshooting](#slack-alert-troubleshooting)
- [Emergency Procedures](#emergency-procedures)

## Quick Diagnostics

### System Health Check

```bash
# Quick health assessment (MVP)
curl -f http://localhost:8000/health || echo "❌ Health check failed"

# Check all services status
docker-compose ps

# Check system resources
df -h
free -h
docker stats --no-stream
```

### Log Analysis

```bash
# Check Docker container logs (MVP)
docker-compose logs --tail=50 api
docker-compose logs --tail=50 worker-collector
docker-compose logs --tail=50 worker-nlp
docker-compose logs --tail=50 worker-publisher

# Check for errors across all services
docker-compose logs | grep -i error | tail -20

# Check for specific issues
docker-compose logs | grep -E "(reddit|openai|ghost).*error"
```

### Network Connectivity

```bash
# Test external API connectivity (MVP)
curl -I https://oauth.reddit.com/api/v1/me
curl -I https://api.openai.com/v1/models
curl -I https://your-ghost-site.com/ghost/api/admin/site/

# Test internal service connectivity
docker exec -it reddit-ghost-publisher-postgres-1 pg_isready
docker exec -it reddit-ghost-publisher-redis-1 redis-cli ping
```

## Application Issues

### Issue: API Returns 500 Internal Server Error

#### Symptoms
- HTTP 500 responses from API endpoints
- "Internal server error" messages
- Application logs show unhandled exceptions

#### Diagnosis
```bash
# Check FastAPI container logs
docker-compose logs api --tail=100

# Test specific endpoints
curl -v http://localhost:8000/health
curl -v http://localhost:8000/api/v1/status/queues
```

#### Solutions

**1. Database Connection Issues**
```bash
# Check database connectivity
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "SELECT 1;"

# If connection fails, restart database
docker-compose restart postgres

# Check database logs
docker-compose logs postgres --tail=50
```

**2. Redis Connection Issues**
```bash
# Check Redis connectivity
docker exec -it reddit-ghost-publisher-redis-1 redis-cli ping

# If connection fails, restart Redis
docker-compose restart redis

# Check Redis logs
docker-compose logs redis --tail=50
```

**3. Configuration Issues**
```bash
# Verify environment variables are loaded
docker exec -it reddit-ghost-publisher-api-1 env | grep -E "(DATABASE_URL|REDIS_URL|REDDIT_CLIENT_ID|OPENAI_API_KEY|GHOST_ADMIN_KEY)"

# Check if .env file exists and is readable
docker exec -it reddit-ghost-publisher-api-1 ls -la /app/.env
```

### Issue: Celery Workers Not Processing Tasks

#### Symptoms
- Tasks stuck in pending state
- Queue depth continuously increasing
- No task completion logs

#### Diagnosis
```bash
# Check worker status via API (MVP)
curl http://localhost:8000/api/v1/status/workers

# Check queue status
curl http://localhost:8000/api/v1/status/queues

# Check worker logs
docker-compose logs worker-collector --tail=100
docker-compose logs worker-nlp --tail=100
docker-compose logs worker-publisher --tail=100

# Check if workers are running
docker-compose ps | grep worker
```

#### Solutions

**1. Worker Process Issues**
```bash
# Restart all workers
docker-compose restart worker-collector worker-nlp worker-publisher

# Check worker resource usage
docker stats reddit-ghost-publisher-worker-collector-1 reddit-ghost-publisher-worker-nlp-1 reddit-ghost-publisher-worker-publisher-1

# If needed, scale workers manually
docker-compose up -d --scale worker-collector=2
```

**2. Task Serialization Issues**
```bash
# Check for serialization errors in logs
docker-compose logs worker-collector | grep -i "serializ"

# Check Redis queue lengths directly
docker exec -it reddit-ghost-publisher-redis-1 redis-cli llen collect
docker exec -it reddit-ghost-publisher-redis-1 redis-cli llen process
docker exec -it reddit-ghost-publisher-redis-1 redis-cli llen publish

# Restart Celery beat scheduler
docker-compose restart celery-beat
```

**3. External API Issues Blocking Workers**
```bash
# Check if workers are stuck on external API calls
docker-compose logs worker-collector | grep -E "(reddit|timeout|error)"
docker-compose logs worker-nlp | grep -E "(openai|timeout|error)"
docker-compose logs worker-publisher | grep -E "(ghost|timeout|error)"

# Test external APIs manually
curl -I https://oauth.reddit.com/api/v1/me
curl -I https://api.openai.com/v1/models
curl -I https://your-ghost-site.com/ghost/api/admin/site/
```

## Database Issues

### Issue: Database Connection Timeouts

#### Symptoms
- "Connection timeout" errors
- Slow database queries
- Connection pool exhaustion

#### Diagnosis
```bash
# Check database connectivity
docker exec -it reddit-ghost-publisher-postgres-1 pg_isready

# Check active connections
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher \
  -c "SELECT count(*) FROM pg_stat_activity;"

# Check connection pool status
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher \
  -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"
```

#### Solutions

**1. Restart Database Service**
```bash
# Simple restart often resolves connection issues
docker-compose restart postgres

# Wait for database to be ready
sleep 10
docker exec -it reddit-ghost-publisher-postgres-1 pg_isready
```

**2. Check Database Resources**
```bash
# Check database container resources
docker stats reddit-ghost-publisher-postgres-1 --no-stream

# Check database logs for errors
docker-compose logs postgres --tail=50

# Check disk space
df -h
```

**3. Connection Pool Issues**
```bash
# If connection pool is exhausted, restart application services
docker-compose restart api worker-collector worker-nlp worker-publisher

# Check if connections are released
sleep 30
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher \
  -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

## Redis and Queue Issues

### Issue: Redis Memory Exhaustion

#### Symptoms
- Redis OOM errors
- Task queuing failures
- Workers unable to connect to Redis

#### Diagnosis
```bash
# Check Redis memory usage
docker exec -it reddit-ghost-publisher-redis-1 redis-cli info memory

# Check Redis container resources
docker stats reddit-ghost-publisher-redis-1 --no-stream

# Check queue lengths
docker exec -it reddit-ghost-publisher-redis-1 redis-cli llen collect
docker exec -it reddit-ghost-publisher-redis-1 redis-cli llen process
docker exec -it reddit-ghost-publisher-redis-1 redis-cli llen publish
```

#### Solutions

**1. Restart Redis Service**
```bash
# Simple restart to clear memory
docker-compose restart redis

# Wait for Redis to be ready
sleep 5
docker exec -it reddit-ghost-publisher-redis-1 redis-cli ping
```

**2. Clear Queue Data (if safe)**
```bash
# CAUTION: This will clear all queued tasks
# Only do this if you can afford to lose pending tasks

# Clear all Redis data
docker exec -it reddit-ghost-publisher-redis-1 redis-cli flushall

# Restart workers to reconnect
docker-compose restart worker-collector worker-nlp worker-publisher
```

**3. Check for Memory Leaks**
```bash
# Check Redis logs for memory warnings
docker-compose logs redis --tail=50

# Monitor memory usage over time
watch -n 10 'docker exec -it reddit-ghost-publisher-redis-1 redis-cli info memory | grep used_memory_human'
```

## External API Issues

### Issue: Reddit API Rate Limiting

#### Symptoms
- "Rate limit exceeded" errors
- HTTP 429 responses from Reddit
- Collection tasks failing repeatedly

#### Diagnosis
```bash
# Check Reddit API errors in logs
docker-compose logs worker-collector | grep -i "reddit.*rate\|429\|rate.*limit"

# Check current daily usage
curl -s http://localhost:8000/metrics | grep reddit_calls

# Test Reddit API connectivity
curl -I https://oauth.reddit.com/api/v1/me
```

#### Solutions

**1. Wait for Rate Limit Reset**
```bash
# Check when rate limit resets (usually 1 minute for Reddit)
echo "Waiting for Reddit rate limit to reset..."
sleep 60

# Check if collection resumes
docker-compose logs worker-collector --tail=20
```

**2. Reduce Collection Frequency**
```bash
# Temporarily reduce collection frequency
# Edit .env file:
# COLLECT_CRON=0 */2 * * *  # Every 2 hours instead of hourly

# Restart scheduler
docker-compose restart celery-beat

echo "Collection frequency reduced to every 2 hours"
```

**3. Check Daily Budget**
```bash
# Check if approaching daily limit
DAILY_CALLS=$(curl -s http://localhost:8000/metrics | grep reddit_calls_total | awk '{print $2}')
DAILY_LIMIT=$(docker exec -it reddit-ghost-publisher-api-1 env | grep REDDIT_DAILY_CALLS_LIMIT | cut -d= -f2)

echo "Daily calls: $DAILY_CALLS / $DAILY_LIMIT"

if [ "$DAILY_CALLS" -gt $((DAILY_LIMIT * 80 / 100)) ]; then
    echo "⚠️ Approaching daily limit - consider reducing collection"
fi
```

## Performance Issues

### Issue: High API Response Times

#### Symptoms
- API responses taking > 5 seconds
- Timeout errors
- Slow health checks

#### Diagnosis
```bash
# Check API response times
time curl http://localhost:8000/health

# Check system resources
docker stats --no-stream
df -h
free -h

# Check database performance
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "
SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del 
FROM pg_stat_user_tables 
ORDER BY n_tup_ins DESC;
"
```

#### Solutions

**1. Restart Services**
```bash
# Simple restart often resolves performance issues
docker-compose restart api

# Check if performance improves
time curl http://localhost:8000/health
```

**2. Database Maintenance**
```bash
# Run database maintenance
docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "
VACUUM ANALYZE posts;
VACUUM ANALYZE processing_logs;
VACUUM ANALYZE token_usage;
"

echo "Database maintenance completed"
```

**3. Check Resource Usage**
```bash
# Check if system is under resource pressure
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
echo "Memory usage: ${MEMORY_USAGE}%"

if [ "$MEMORY_USAGE" -gt 90 ]; then
    echo "⚠️ High memory usage - consider restarting services"
    docker-compose restart
fi
```

## Slack Alert Troubleshooting

### Issue: Slack Notifications Not Working

#### Symptoms
- No Slack alerts received
- Expected notifications missing
- Webhook errors in logs

#### Diagnosis
```bash
# Check Slack webhook configuration
docker exec -it reddit-ghost-publisher-api-1 env | grep SLACK_WEBHOOK_URL

# Check for Slack-related errors in logs
docker-compose logs | grep -i slack

# Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test notification from troubleshooting"}' \
  $SLACK_WEBHOOK_URL
```

#### Solutions

**1. Verify Webhook URL**
```bash
# Check if webhook URL is correctly configured
WEBHOOK_URL=$(docker exec -it reddit-ghost-publisher-api-1 env | grep SLACK_WEBHOOK_URL | cut -d= -f2)

if [[ $WEBHOOK_URL == *"hooks.slack.com"* ]]; then
    echo "✅ Webhook URL format looks correct"
else
    echo "❌ Webhook URL format incorrect"
    echo "Expected format: https://hooks.slack.com/services/..."
fi
```

**2. Test Notification Function**
```bash
# Send test notification
python3 << EOF
import requests
import os

webhook_url = os.getenv('SLACK_WEBHOOK_URL')
if webhook_url:
    payload = {
        "text": "🧪 Test notification from Reddit Ghost Publisher",
        "attachments": [{
            "color": "good",
            "fields": [
                {"title": "Status", "value": "Testing", "short": True},
                {"title": "Time", "value": "$(date)", "short": True}
            ]
        }]
    }
    response = requests.post(webhook_url, json=payload)
    print(f"Response: {response.status_code}")
else:
    print("SLACK_WEBHOOK_URL not set")
EOF
```

### Issue: Wrong Alert Thresholds

#### Symptoms
- Too many alerts
- Missing important alerts
- Alerts for normal conditions

#### Diagnosis
```bash
# Check current threshold settings
docker exec -it reddit-ghost-publisher-api-1 env | grep -E "(QUEUE_ALERT_THRESHOLD|FAILURE_RATE_THRESHOLD)"

# Check current metrics
curl -s http://localhost:8000/api/v1/status/queues | jq
curl -s http://localhost:8000/metrics | grep failures_total
```

#### Solutions

**1. Adjust Queue Threshold**
```bash
# If getting too many queue alerts, increase threshold
# Edit .env file:
# QUEUE_ALERT_THRESHOLD=1000  # Increase from 500

# Restart services
docker-compose restart

echo "Queue alert threshold increased to 1000"
```

**2. Adjust Failure Rate Threshold**
```bash
# If getting too many failure alerts, increase threshold
# Edit .env file:
# FAILURE_RATE_THRESHOLD=0.10  # Increase from 0.05 (5% to 10%)

# Restart services
docker-compose restart

echo "Failure rate threshold increased to 10%"
```

## Emergency Procedures

### Complete System Outage

#### Immediate Actions (First 15 minutes)

1. **Assess Scope**
   ```bash
   # Check if it's a complete outage
   curl -f http://localhost:8000/health
   docker-compose ps
   ```

2. **Check Infrastructure**
   ```bash
   # Check system resources
   df -h
   free -h
   docker stats --no-stream
   ```

3. **Notify Team**
   ```bash
   # Send alert to Slack
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"🚨 CRITICAL: Reddit Publisher system outage detected"}' \
     $SLACK_WEBHOOK_URL
   ```

#### Recovery Actions (15-60 minutes)

1. **Quick Restart**
   ```bash
   # Try quick restart first
   docker-compose restart
   
   # Wait and test
   sleep 30
   curl -f http://localhost:8000/health
   ```

2. **Full Restart if Needed**
   ```bash
   # If quick restart fails, full restart
   docker-compose down
   docker-compose up -d
   
   # Wait for services to be ready
   sleep 60
   curl -f http://localhost:8000/health
   ```

3. **Check External Dependencies**
   ```bash
   # Verify external services are accessible
   curl -I https://oauth.reddit.com/api/v1/me
   curl -I https://api.openai.com/v1/models
   curl -I https://your-ghost-site.com/ghost/api/admin/site/
   ```

4. **Database Recovery (if needed)**
   ```bash
   # If database is corrupted, restore from backup
   LATEST_BACKUP=$(ls -t /var/lib/reddit-publisher/backups/backup_*.sql.gz | head -1)
   
   if [ -n "$LATEST_BACKUP" ]; then
       echo "Restoring from: $LATEST_BACKUP"
       docker-compose stop api worker-collector worker-nlp worker-publisher
       
       # Restore database
       gunzip -c "$LATEST_BACKUP" | docker exec -i reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher
       
       # Restart application
       docker-compose start api worker-collector worker-nlp worker-publisher
   fi
   ```

### Data Corruption Emergency

#### Immediate Actions

1. **Stop Application Services**
   ```bash
   # Keep infrastructure running, stop application
   docker-compose stop api worker-collector worker-nlp worker-publisher
   ```

2. **Create Emergency Backup**
   ```bash
   # Backup current state before any changes
   docker exec -it reddit-ghost-publisher-postgres-1 pg_dump -U postgres reddit_publisher > emergency_backup_$(date +%Y%m%d_%H%M%S).sql
   ```

3. **Assess Damage**
   ```bash
   # Check data integrity
   docker exec -it reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher -c "
   SELECT COUNT(*) as total_posts FROM posts;
   SELECT COUNT(*) as posts_with_summary FROM posts WHERE summary_ko IS NOT NULL;
   SELECT COUNT(*) as published_posts FROM posts WHERE ghost_url IS NOT NULL;
   "
   ```

4. **Restore from Backup**
   ```bash
   # Find latest good backup
   LATEST_BACKUP=$(ls -t /var/lib/reddit-publisher/backups/backup_*.sql.gz | head -1)
   
   # Drop and recreate database
   docker exec -it reddit-ghost-publisher-postgres-1 dropdb -U postgres reddit_publisher
   docker exec -it reddit-ghost-publisher-postgres-1 createdb -U postgres reddit_publisher
   
   # Restore from backup
   gunzip -c "$LATEST_BACKUP" | docker exec -i reddit-ghost-publisher-postgres-1 psql -U postgres -d reddit_publisher
   
   # Restart application services
   docker-compose start api worker-collector worker-nlp worker-publisher
   ```

### Quick Recovery Checklist

```bash
#!/bin/bash
# emergency-recovery.sh - Quick recovery script

echo "🚨 Emergency Recovery Procedure"

# 1. Check system status
echo "1. Checking system status..."
docker-compose ps

# 2. Try health check
echo "2. Testing health check..."
if curl -f http://localhost:8000/health; then
    echo "✅ System is healthy"
    exit 0
fi

# 3. Quick restart
echo "3. Attempting quick restart..."
docker-compose restart
sleep 30

if curl -f http://localhost:8000/health; then
    echo "✅ Quick restart successful"
    exit 0
fi

# 4. Full restart
echo "4. Attempting full restart..."
docker-compose down
docker-compose up -d
sleep 60

if curl -f http://localhost:8000/health; then
    echo "✅ Full restart successful"
    exit 0
fi

# 5. Check for database issues
echo "5. Checking database..."
if ! docker exec -it reddit-ghost-publisher-postgres-1 pg_isready; then
    echo "❌ Database not ready - may need backup restore"
    exit 1
fi

echo "❌ Recovery failed - manual intervention required"
exit 1
```

This troubleshooting guide provides practical solutions for the MVP system. Focus on simple restarts and basic diagnostics before attempting complex recovery procedures.