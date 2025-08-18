# Monitoring and Alerting Response Procedures

## Overview

This document outlines the procedures for responding to monitoring alerts and managing the observability infrastructure for the Reddit Ghost Publisher system. It provides step-by-step response procedures for different alert types and severity levels.

## Alert Classification and Response Times

### Severity Levels

| Severity | Response Time | Description | Examples |
|----------|---------------|-------------|----------|
| **Critical (P0)** | 15 minutes | System outage, data loss, security breach | Complete API outage, database corruption, security incident |
| **High (P1)** | 1 hour | Significant degradation, partial outage | High error rates, external API failures, worker failures |
| **Medium (P2)** | 4 hours | Performance issues, non-critical failures | High response times, queue backlogs, resource warnings |
| **Low (P3)** | 24 hours | Minor issues, maintenance alerts | Disk space warnings, certificate expiry notices |

## Alert Response Procedures

### Critical Alerts (P0)

#### System Outage Alert

**Alert**: `SystemDown` - API health check failing

**Immediate Response (0-15 minutes):**

1. **Acknowledge Alert**
   ```bash
   # Update incident status
   curl -X POST "$INCIDENT_MANAGEMENT_URL/incidents" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Reddit Publisher System Outage",
       "severity": "critical",
       "status": "investigating"
     }'
   ```

2. **Initial Assessment**
   ```bash
   # Check system status
   curl -f https://your-domain.com/health || echo "System is down"
   
   # Check infrastructure
   ssh ops@your-server "docker-compose ps"
   ssh ops@your-server "systemctl status docker nginx"
   
   # Check DNS resolution
   nslookup your-domain.com
   dig your-domain.com
   ```

3. **Notify Stakeholders**
   ```bash
   # Send critical alert to team
   curl -X POST -H 'Content-type: application/json' \
     --data '{
       "text": "🚨 CRITICAL: Reddit Publisher system is DOWN",
       "channel": "#incidents",
       "username": "AlertBot"
     }' \
     "$SLACK_WEBHOOK_URL"
   
   # Send email to on-call team
   echo "CRITICAL: Reddit Publisher system outage detected at $(date)" | \
     mail -s "CRITICAL ALERT: System Outage" ops-team@your-domain.com
   ```

**Investigation and Resolution (15-60 minutes):**

1. **Quick Recovery Attempts**
   ```bash
   # Try service restart
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart"
   
   # Check if services come back up
   sleep 30
   curl -f https://your-domain.com/health
   ```

2. **Detailed Investigation**
   ```bash
   # Check system resources
   ssh ops@your-server "df -h && free -h && top -bn1 | head -10"
   
   # Check application logs
   ssh ops@your-server "tail -n 100 /var/log/reddit-publisher/app.log | grep ERROR"
   
   # Check Docker logs
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose logs --tail=50"
   ```

3. **Escalation if Needed**
   ```bash
   # If issue persists after 30 minutes, escalate
   curl -X POST "$INCIDENT_MANAGEMENT_URL/incidents/$INCIDENT_ID/escalate" \
     -H "Content-Type: application/json" \
     -d '{"escalation_level": "senior_engineer"}'
   ```

#### Database Corruption Alert

**Alert**: `DatabaseCorruption` - Data integrity check failed

**Immediate Response:**

1. **Stop All Write Operations**
   ```bash
   # Stop workers to prevent further corruption
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose stop worker-collector worker-nlp worker-publisher"
   
   # Put API in read-only mode
   ssh ops@your-server "docker exec -it reddit-publisher-api-1 touch /tmp/readonly_mode"
   ```

2. **Assess Corruption Scope**
   ```bash
   # Check database integrity
   ssh ops@your-server "docker exec -it postgres psql -U $DB_USER -d $DB_NAME -c '
   SELECT schemaname, tablename, 
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
          (SELECT count(*) FROM information_schema.columns WHERE table_name = tablename) as columns
   FROM pg_tables 
   WHERE schemaname = 'public'
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;'"
   
   # Check for specific corruption indicators
   ssh ops@your-server "docker exec -it postgres psql -U $DB_USER -d $DB_NAME -c '
   SELECT COUNT(*) as total_posts FROM posts;
   SELECT COUNT(*) as null_ids FROM posts WHERE id IS NULL;
   SELECT COUNT(*) as invalid_timestamps FROM posts WHERE created_at > NOW();'"
   ```

3. **Initiate Recovery**
   ```bash
   # Create emergency backup of current state
   ssh ops@your-server "docker exec -it postgres pg_dump -U $DB_USER -d $DB_NAME > /tmp/emergency_backup_$(date +%Y%m%d_%H%M%S).sql"
   
   # Restore from latest known good backup
   ssh ops@your-server "
   cd /opt/reddit-publisher
   gunzip -c /var/lib/reddit-publisher/backups/latest_good.sql.gz | \
     docker exec -i postgres psql -U $DB_USER -d $DB_NAME
   "
   ```

### High Priority Alerts (P1)

#### High API Error Rate

**Alert**: `HighAPIErrorRate` - Error rate > 10% for 5 minutes

**Response Procedure:**

1. **Immediate Assessment**
   ```bash
   # Check current error rate
   curl -s "http://prometheus:9090/api/v1/query?query=rate(http_requests_total{status_code=~'5..'}[5m])" | \
     jq '.data.result[0].value[1]'
   
   # Check recent errors in logs
   ssh ops@your-server "tail -n 200 /var/log/reddit-publisher/app.log | grep ERROR | tail -20"
   
   # Check specific error patterns
   ssh ops@your-server "grep -E '(500|502|503|504)' /var/log/nginx/access.log | tail -20"
   ```

2. **Identify Root Cause**
   ```bash
   # Check database connectivity
   ssh ops@your-server "docker exec -it postgres pg_isready"
   
   # Check Redis connectivity
   ssh ops@your-server "docker exec -it redis redis-cli ping"
   
   # Check external API status
   curl -I https://oauth.reddit.com/api/v1/me
   curl -I https://api.openai.com/v1/models
   curl -I https://your-ghost-site.com/
   ```

3. **Apply Fixes**
   ```bash
   # If database issues, restart database
   if ! ssh ops@your-server "docker exec -it postgres pg_isready"; then
     ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart postgres"
   fi
   
   # If Redis issues, restart Redis
   if ! ssh ops@your-server "docker exec -it redis redis-cli ping"; then
     ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart redis"
   fi
   
   # If application issues, restart API
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart api"
   ```

#### Worker Failure Alert

**Alert**: `CeleryWorkerDown` - No active workers detected

**Response Procedure:**

1. **Check Worker Status**
   ```bash
   # Check worker containers
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose ps | grep worker"
   
   # Check Celery worker status
   ssh ops@your-server "cd /opt/reddit-publisher && docker exec -it worker-collector celery -A app.celery_app inspect ping"
   ```

2. **Restart Failed Workers**
   ```bash
   # Restart all workers
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart worker-collector worker-nlp worker-publisher"
   
   # Verify workers are back online
   sleep 30
   ssh ops@your-server "cd /opt/reddit-publisher && docker exec -it worker-collector celery -A app.celery_app inspect active"
   ```

3. **Check Queue Status**
   ```bash
   # Check queue depths
   curl -H "X-API-Key: $API_KEY" https://your-domain.com/api/v1/status/queues
   
   # If queues are backed up, scale workers
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose up -d --scale worker-collector=3 --scale worker-nlp=2"
   ```

### Medium Priority Alerts (P2)

#### High Queue Depth

**Alert**: `HighQueueDepth` - Queue depth > 1000 tasks

**Response Procedure:**

1. **Assess Queue Status**
   ```bash
   # Get detailed queue information
   curl -H "X-API-Key: $API_KEY" https://your-domain.com/api/v1/status/queues | jq '.'
   
   # Check Redis queue lengths directly
   ssh ops@your-server "docker exec -it redis redis-cli llen celery:collect"
   ssh ops@your-server "docker exec -it redis redis-cli llen celery:process"
   ssh ops@your-server "docker exec -it redis redis-cli llen celery:publish"
   ```

2. **Scale Workers**
   ```bash
   # Scale up workers based on queue type
   if [ "$QUEUE_NAME" = "collect" ]; then
     ssh ops@your-server "cd /opt/reddit-publisher && docker-compose up -d --scale worker-collector=4"
   elif [ "$QUEUE_NAME" = "process" ]; then
     ssh ops@your-server "cd /opt/reddit-publisher && docker-compose up -d --scale worker-nlp=3"
   elif [ "$QUEUE_NAME" = "publish" ]; then
     ssh ops@your-server "cd /opt/reddit-publisher && docker-compose up -d --scale worker-publisher=3"
   fi
   ```

3. **Monitor Progress**
   ```bash
   # Monitor queue reduction over time
   for i in {1..10}; do
     echo "Check $i at $(date):"
     curl -s -H "X-API-Key: $API_KEY" https://your-domain.com/api/v1/status/queues | \
       jq '.[] | {name: .name, pending: .pending, active: .active}'
     sleep 60
   done
   ```

#### High Resource Usage

**Alert**: `HighCPUUsage` - CPU usage > 90% for 5 minutes

**Response Procedure:**

1. **Identify Resource Consumers**
   ```bash
   # Check top processes
   ssh ops@your-server "top -bn1 | head -20"
   
   # Check Docker container resource usage
   ssh ops@your-server "docker stats --no-stream"
   
   # Check specific process details
   ssh ops@your-server "ps aux --sort=-%cpu | head -10"
   ```

2. **Apply Immediate Relief**
   ```bash
   # If specific container is consuming too much CPU
   ssh ops@your-server "docker update --cpus='2.0' container-name"
   
   # If memory is also high, restart the problematic service
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart worker-nlp"
   ```

3. **Scale Resources if Needed**
   ```bash
   # If sustained high usage, consider scaling up
   # This would typically involve infrastructure changes
   echo "Consider scaling up infrastructure if high usage persists"
   ```

### Low Priority Alerts (P3)

#### Disk Space Warning

**Alert**: `HighDiskUsage` - Disk usage > 85%

**Response Procedure:**

1. **Assess Disk Usage**
   ```bash
   # Check disk usage breakdown
   ssh ops@your-server "df -h"
   ssh ops@your-server "du -sh /var/log/* | sort -hr | head -10"
   ssh ops@your-server "du -sh /var/lib/docker/* | sort -hr | head -10"
   ```

2. **Clean Up Space**
   ```bash
   # Clean up old logs
   ssh ops@your-server "find /var/log/reddit-publisher -name '*.log' -mtime +30 -delete"
   
   # Clean up Docker resources
   ssh ops@your-server "docker system prune -f"
   ssh ops@your-server "docker image prune -a -f"
   
   # Clean up old database backups
   ssh ops@your-server "find /var/lib/reddit-publisher/backups -name '*.sql.gz' -mtime +90 -delete"
   ```

3. **Schedule Maintenance**
   ```bash
   # If cleanup doesn't provide enough space, schedule disk expansion
   echo "Disk cleanup completed. Consider expanding disk if usage remains high."
   ```

#### Certificate Expiry Warning

**Alert**: `CertificateExpiring` - SSL certificate expires in 30 days

**Response Procedure:**

1. **Check Certificate Status**
   ```bash
   # Check current certificate
   echo | openssl s_client -connect your-domain.com:443 2>/dev/null | \
     openssl x509 -noout -dates
   
   # Check Let's Encrypt status
   ssh ops@your-server "certbot certificates"
   ```

2. **Renew Certificate**
   ```bash
   # Attempt renewal
   ssh ops@your-server "certbot renew --dry-run"
   ssh ops@your-server "certbot renew"
   
   # Reload web server
   ssh ops@your-server "systemctl reload nginx"
   ```

3. **Verify Renewal**
   ```bash
   # Verify new certificate
   echo | openssl s_client -connect your-domain.com:443 2>/dev/null | \
     openssl x509 -noout -dates
   ```

## Monitoring Dashboard Response

### Grafana Dashboard Issues

#### Dashboard Not Loading

**Symptoms**: Blank dashboards, "No data" messages

**Response:**

1. **Check Data Source**
   ```bash
   # Test Prometheus connectivity
   curl http://prometheus:9090/api/v1/query?query=up
   
   # Check Grafana data source configuration
   curl -u admin:admin http://localhost:3000/api/datasources
   ```

2. **Verify Metrics Collection**
   ```bash
   # Check if metrics are being collected
   curl http://localhost:8000/metrics | grep reddit_publisher
   
   # Check Prometheus targets
   curl http://prometheus:9090/api/v1/targets
   ```

3. **Restart Services if Needed**
   ```bash
   # Restart Grafana
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart grafana"
   
   # Restart Prometheus
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose restart prometheus"
   ```

### Prometheus Issues

#### Prometheus Not Scraping Metrics

**Symptoms**: Missing metrics, scrape failures

**Response:**

1. **Check Prometheus Configuration**
   ```bash
   # Verify configuration
   ssh ops@your-server "docker exec -it prometheus promtool check config /etc/prometheus/prometheus.yml"
   
   # Check targets status
   curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .job, health: .health, lastError: .lastError}'
   ```

2. **Fix Network Issues**
   ```bash
   # Test connectivity between containers
   ssh ops@your-server "docker exec -it prometheus ping api"
   ssh ops@your-server "docker exec -it prometheus telnet api 8000"
   ```

3. **Reload Configuration**
   ```bash
   # Reload Prometheus configuration
   ssh ops@your-server "docker exec -it prometheus kill -HUP 1"
   ```

## Alert Escalation Procedures

### Escalation Matrix

| Time Elapsed | Action | Responsible |
|--------------|--------|-------------|
| 0-15 min | Initial response | On-call engineer |
| 15-30 min | Senior engineer notification | On-call engineer |
| 30-60 min | Team lead notification | Senior engineer |
| 60+ min | Management notification | Team lead |

### Escalation Commands

```bash
# Escalate to senior engineer
curl -X POST "$PAGERDUTY_API_URL/incidents/$INCIDENT_ID/escalate" \
  -H "Authorization: Token token=$PAGERDUTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "escalation_level": "senior_engineer",
    "message": "Issue not resolved within 15 minutes"
  }'

# Escalate to team lead
curl -X POST "$PAGERDUTY_API_URL/incidents/$INCIDENT_ID/escalate" \
  -H "Authorization: Token token=$PAGERDUTY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "escalation_level": "team_lead",
    "message": "Issue not resolved within 30 minutes"
  }'
```

## Post-Incident Procedures

### Incident Resolution

1. **Verify Resolution**
   ```bash
   # Confirm system is healthy
   curl -f https://your-domain.com/health
   curl -H "X-API-Key: $API_KEY" https://your-domain.com/api/v1/status/system
   
   # Check all services are running
   ssh ops@your-server "cd /opt/reddit-publisher && docker-compose ps"
   ```

2. **Update Incident Status**
   ```bash
   # Mark incident as resolved
   curl -X PUT "$INCIDENT_MANAGEMENT_URL/incidents/$INCIDENT_ID" \
     -H "Content-Type: application/json" \
     -d '{
       "status": "resolved",
       "resolution_summary": "System restored after database restart"
     }'
   ```

3. **Notify Stakeholders**
   ```bash
   # Send resolution notification
   curl -X POST -H 'Content-type: application/json' \
     --data '{
       "text": "✅ RESOLVED: Reddit Publisher system is back online",
       "channel": "#incidents"
     }' \
     "$SLACK_WEBHOOK_URL"
   ```

### Post-Mortem Process

1. **Schedule Post-Mortem Meeting**
   - Within 24 hours for critical incidents
   - Within 1 week for high priority incidents

2. **Gather Data**
   ```bash
   # Export relevant logs
   ssh ops@your-server "tar -czf incident_logs_$(date +%Y%m%d).tar.gz /var/log/reddit-publisher/"
   
   # Export metrics data
   curl "http://prometheus:9090/api/v1/query_range?query=up&start=$(date -d '2 hours ago' +%s)&end=$(date +%s)&step=60" > incident_metrics.json
   ```

3. **Document Lessons Learned**
   - Root cause analysis
   - Timeline of events
   - Actions taken
   - Preventive measures
   - Process improvements

## Maintenance Windows

### Scheduled Maintenance

1. **Pre-Maintenance Checklist**
   ```bash
   # Create maintenance backup
   ssh ops@your-server "/opt/reddit-publisher/scripts/backup-database.sh"
   
   # Notify users
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text": "🔧 Scheduled maintenance starting in 30 minutes"}' \
     "$SLACK_WEBHOOK_URL"
   
   # Put system in maintenance mode
   ssh ops@your-server "docker exec -it reddit-publisher-api-1 touch /tmp/maintenance_mode"
   ```

2. **During Maintenance**
   ```bash
   # Disable alerting
   curl -X POST "$ALERTMANAGER_URL/api/v1/silences" \
     -H "Content-Type: application/json" \
     -d '{
       "matchers": [{"name": "job", "value": "reddit-publisher"}],
       "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
       "endsAt": "'$(date -u -d '+2 hours' +%Y-%m-%dT%H:%M:%S.%3NZ)'",
       "comment": "Scheduled maintenance window"
     }'
   
   # Perform maintenance tasks
   # ...
   ```

3. **Post-Maintenance**
   ```bash
   # Remove maintenance mode
   ssh ops@your-server "docker exec -it reddit-publisher-api-1 rm -f /tmp/maintenance_mode"
   
   # Verify system health
   curl -f https://your-domain.com/health
   
   # Re-enable alerting
   curl -X DELETE "$ALERTMANAGER_URL/api/v1/silence/$SILENCE_ID"
   
   # Notify completion
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text": "✅ Scheduled maintenance completed successfully"}' \
     "$SLACK_WEBHOOK_URL"
   ```

This monitoring and alerting procedures document provides comprehensive guidance for responding to various system alerts and maintaining the observability infrastructure.