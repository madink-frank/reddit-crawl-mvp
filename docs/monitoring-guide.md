# Reddit Publisher Monitoring Guide

This guide covers the comprehensive monitoring and alerting setup for the Reddit Publisher system.

## Overview

The monitoring stack consists of:
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Dashboards and visualization
- **Alertmanager**: Alert routing and notification management
- **Slack Integration**: Real-time notifications

## Quick Start

1. Set up environment variables:
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
export GRAFANA_PASSWORD="your-secure-password"
```

2. Run the setup script:
```bash
./scripts/setup-monitoring.sh
```

3. Access the monitoring interfaces:
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

## Dashboards

### 1. System Overview
**URL**: http://localhost:3000/d/reddit-publisher-system

Monitors basic system metrics:
- CPU Usage
- Memory Usage
- Disk Usage
- Network I/O

**Key Metrics**:
- `node_cpu_seconds_total`: CPU usage by mode
- `node_memory_MemAvailable_bytes`: Available memory
- `node_filesystem_avail_bytes`: Available disk space
- `node_network_receive_bytes_total`: Network receive bytes

### 2. Application Metrics
**URL**: http://localhost:3000/d/reddit-publisher-app

Monitors application-specific metrics:
- API Request Rate
- Response Time (p95, p50)
- Error Rate
- External API Usage
- Database Metrics

**Key Metrics**:
- `fastapi_requests_total`: Total API requests
- `fastapi_request_duration_seconds`: Request duration histogram
- `reddit_api_calls_total`: Reddit API calls
- `openai_tokens_used`: OpenAI token usage
- `postgresql_connections_active`: Active DB connections

### 3. Queue Monitoring
**URL**: http://localhost:3000/d/reddit-publisher-queue

Monitors Celery queue system:
- Queue Depth by queue type
- Active Workers
- Task Processing Time
- Success/Failure Rates
- Worker Status

**Key Metrics**:
- `celery_queue_length`: Queue depth by queue name
- `celery_active_workers`: Number of active workers
- `celery_task_duration_seconds`: Task execution time
- `celery_task_success_total`: Successful tasks
- `celery_task_failure_total`: Failed tasks

### 4. Business Metrics
**URL**: http://localhost:3000/d/reddit-publisher-business

Monitors business KPIs:
- Content Pipeline Throughput
- Daily Token Usage
- Operating Costs
- Content Quality Metrics
- Success Rates

**Key Metrics**:
- `posts_collected_total`: Posts collected from Reddit
- `posts_processed_total`: Posts processed by AI
- `posts_published_total`: Posts published to Ghost
- `openai_cost_usd_total`: OpenAI costs
- `post_velocity_score`: Content velocity scores

## Alerting

### Alert Rules

#### Critical Alerts
- **HighTokenUsage**: Daily OpenAI token usage > 800K tokens
- **HighAPIErrorRate**: API error rate > 5%
- **HighMemoryUsage**: Memory usage > 85%
- **HighDiskUsage**: Disk usage > 80%
- **ServiceDown**: Any service is down
- **CeleryWorkerDown**: No active Celery workers

#### Warning Alerts
- **HighQueueDepth**: Queue depth > 1000 jobs
- **APIRateLimitApproaching**: Reddit API usage > 80 calls/hour
- **HighAPIResponseTime**: p95 response time > 400ms
- **DatabaseConnectionsHigh**: Active DB connections > 80
- **RedisMemoryHigh**: Redis memory usage > 80%
- **TaskFailureRateHigh**: Task failure rate > 10%

### Notification Channels

#### Slack Channels
- `#alerts-critical`: Critical alerts requiring immediate attention
- `#alerts-warning`: Warning alerts for monitoring
- `#reddit-publisher-alerts`: Service-specific alerts

#### Escalation Policy

**Critical Alerts**:
1. Immediate notification to #alerts-critical
2. After 15min: Mention @channel
3. After 30min: Mention @here + email notification
4. After 1h: Mention @channel + SMS notification

**Warning Alerts**:
1. Immediate notification to #alerts-warning
2. After 1h: Mention @here
3. After 4h: Email notification

### Testing Alerts

Test Slack webhook integration:
```bash
python scripts/test-slack-webhook.py
```

Manually trigger test alert:
```bash
# Access Alertmanager
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "service": "reddit-publisher",
      "severity": "warning"
    },
    "annotations": {
      "summary": "Test alert",
      "description": "This is a test alert"
    }
  }]'
```

## Metrics Reference

### Custom Application Metrics

#### Reddit Collector
```python
reddit_api_calls_total = Counter('reddit_api_calls_total', 'Total Reddit API calls')
posts_collected_total = Counter('posts_collected_total', 'Total posts collected')
reddit_api_errors_total = Counter('reddit_api_errors_total', 'Reddit API errors')
```

#### NLP Pipeline
```python
openai_tokens_used = Counter('openai_tokens_used', 'OpenAI tokens consumed', ['type'])
openai_cost_usd_total = Counter('openai_cost_usd_total', 'OpenAI costs in USD')
posts_processed_total = Counter('posts_processed_total', 'Total posts processed')
processing_duration_seconds = Histogram('processing_duration_seconds', 'Processing time')
```

#### Publisher
```python
ghost_publish_success_total = Counter('ghost_publish_success_total', 'Successful Ghost publications')
ghost_publish_errors_total = Counter('ghost_publish_errors_total', 'Ghost publication errors')
posts_published_total = Counter('posts_published_total', 'Total posts published')
```

#### Celery Metrics
```python
celery_queue_length = Gauge('celery_queue_length', 'Queue length', ['queue_name'])
celery_active_workers = Gauge('celery_active_workers', 'Active worker count')
celery_task_duration_seconds = Histogram('celery_task_duration_seconds', 'Task execution time', ['task_name'])
celery_task_success_total = Counter('celery_task_success_total', 'Successful tasks', ['task_name'])
celery_task_failure_total = Counter('celery_task_failure_total', 'Failed tasks', ['task_name'])
```

## Configuration

### Prometheus Configuration
Location: `docker/prometheus.yml`

Key settings:
- Scrape interval: 15s
- Evaluation interval: 15s
- Retention: 200h
- Alertmanager integration enabled

### Alertmanager Configuration
Location: `docker/alertmanager/alertmanager.yml`

Key features:
- Slack webhook integration
- Alert grouping and routing
- Inhibition rules
- Escalation policies

### Grafana Configuration
Location: `docker/grafana/provisioning/`

Features:
- Auto-provisioned dashboards
- Prometheus datasource
- Alert rules and contact points
- Notification policies

## Troubleshooting

### Common Issues

#### Grafana Dashboard Not Loading
```bash
# Check Grafana logs
docker-compose logs grafana

# Verify provisioning files
ls -la docker/grafana/provisioning/dashboards/
```

#### Alerts Not Firing
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Verify alert rules
curl http://localhost:9090/api/v1/rules

# Check Alertmanager status
curl http://localhost:9093/api/v1/status
```

#### Slack Notifications Not Working
```bash
# Test webhook manually
python scripts/test-slack-webhook.py

# Check Alertmanager logs
docker-compose logs alertmanager

# Verify webhook URL in environment
echo $SLACK_WEBHOOK_URL
```

### Log Locations
- Grafana: `docker-compose logs grafana`
- Prometheus: `docker-compose logs prometheus`
- Alertmanager: `docker-compose logs alertmanager`

### Health Checks
```bash
# Check all monitoring services
docker-compose ps prometheus grafana alertmanager

# Verify metrics endpoints
curl http://localhost:8000/metrics  # FastAPI metrics
curl http://localhost:9090/metrics  # Prometheus metrics
```

## Maintenance

### Regular Tasks

#### Weekly
- Review alert thresholds
- Check dashboard accuracy
- Verify notification channels

#### Monthly
- Update Grafana dashboards
- Review and optimize alert rules
- Check storage usage for Prometheus

#### Quarterly
- Review escalation policies
- Update monitoring documentation
- Performance tune monitoring stack

### Backup and Recovery

#### Grafana Dashboards
```bash
# Export dashboards
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
  http://localhost:3000/api/dashboards/uid/reddit-publisher-system

# Import dashboards
curl -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -d @dashboard.json \
  http://localhost:3000/api/dashboards/db
```

#### Prometheus Data
```bash
# Backup Prometheus data
docker run --rm -v reddit_crawl_mvp_prometheus_data:/data \
  -v $(pwd)/backups:/backup alpine \
  tar czf /backup/prometheus-$(date +%Y%m%d).tar.gz /data
```

## Performance Tuning

### Prometheus
- Adjust retention period based on storage
- Optimize scrape intervals for high-cardinality metrics
- Use recording rules for complex queries

### Grafana
- Use template variables for dynamic dashboards
- Optimize query performance with proper time ranges
- Cache frequently accessed dashboards

### Alertmanager
- Group related alerts to reduce noise
- Use inhibition rules to prevent alert storms
- Optimize notification routing for faster delivery

## Security

### Access Control
- Use strong passwords for Grafana admin
- Restrict network access to monitoring ports
- Enable HTTPS for production deployments

### Secrets Management
- Store Slack webhook URLs securely
- Rotate API keys regularly
- Use environment variables for sensitive data

### Audit Logging
- Enable audit logs in Grafana
- Monitor access to monitoring interfaces
- Track configuration changes