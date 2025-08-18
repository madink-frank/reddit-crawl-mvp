# API Documentation

## Overview

The Reddit Ghost Publisher API provides endpoints for managing the automated content collection, processing, and publishing pipeline. This is an MVP system designed for single-node deployment with simplified authentication and monitoring.

The API is built with FastAPI and provides basic endpoints for health checking, manual task triggering, status monitoring, and metrics collection.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://your-domain.com`

## Authentication

The MVP system uses simplified environment variable-based authentication without complex role management.

### Environment Variable Authentication

Basic authentication is handled through environment variables. No complex JWT or API key management is implemented in the MVP.

```bash
# All endpoints are accessible without authentication in MVP
# Production deployments should add authentication middleware

# Example request
curl "http://localhost:8000/health"
```

**Note**: For production deployment, implement authentication middleware or use a reverse proxy with authentication.

## Core Endpoints

### Health Check Endpoints

#### GET /health
Basic health check with dependency status information.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "database": {
      "status": "healthy",
      "response_time_ms": 12.5
    },
    "redis": {
      "status": "healthy", 
      "response_time_ms": 3.2
    },
    "external_apis": {
      "reddit": "healthy",
      "openai": "healthy", 
      "ghost": "healthy"
    }
  }
}
```

### Manual Task Trigger Endpoints

#### POST /api/v1/collect/trigger
Manually trigger Reddit content collection.

**Request Body:**
```json
{
  "subreddits": ["python", "programming"],
  "sort_type": "hot",
  "limit": 20
}
```

**Response:**
```json
{
  "task_id": "collect_abc123",
  "status": "queued",
  "message": "Collection task queued",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### POST /api/v1/process/trigger
Manually trigger AI content processing.

**Request Body:**
```json
{
  "post_ids": ["post1", "post2"]
}
```

**Response:**
```json
{
  "task_id": "process_def456", 
  "status": "queued",
  "message": "Processing task queued for 2 posts",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### POST /api/v1/publish/trigger
Manually trigger Ghost CMS publishing.

**Request Body:**
```json
{
  "post_ids": ["post1", "post2"]
}
```

**Response:**
```json
{
  "task_id": "publish_ghi789",
  "status": "queued", 
  "message": "Publishing task queued for 2 posts",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Takedown Request Endpoint

#### POST /api/v1/takedown/{reddit_post_id}
Handle takedown requests for published content.

**Request Body:**
```json
{
  "reason": "Copyright infringement",
  "contact_email": "requester@example.com"
}
```

**Response:**
```json
{
  "status": "processed",
  "message": "Content unpublished, deletion scheduled in 72h",
  "reddit_post_id": "abc123",
  "scheduled_deletion": "2024-01-18T10:30:00Z"
}
```

### Status Monitoring Endpoints

#### GET /api/v1/status/queues
Get status of all Celery queues with Redis-based metrics.

**Response:**
```json
{
  "collect": {
    "active": 2,
    "reserved": 0,
    "scheduled": 1,
    "queued": 5
  },
  "process": {
    "active": 1,
    "reserved": 0, 
    "scheduled": 0,
    "queued": 12
  },
  "publish": {
    "active": 1,
    "reserved": 0,
    "scheduled": 0,
    "queued": 3
  }
}
```

#### GET /api/v1/status/workers
Get status of all Celery workers with heartbeat information.

**Response:**
```json
{
  "worker-collector-1": {
    "status": "online",
    "active_tasks": 2,
    "heartbeat": "2024-01-15T10:29:45Z",
    "queues": ["collect"]
  },
  "worker-nlp-1": {
    "status": "online", 
    "active_tasks": 1,
    "heartbeat": "2024-01-15T10:29:50Z",
    "queues": ["process"]
  },
  "worker-publisher-1": {
    "status": "online",
    "active_tasks": 1, 
    "heartbeat": "2024-01-15T10:29:48Z",
    "queues": ["publish"]
  }
}
```



### Metrics Endpoint

#### GET /metrics
Prometheus metrics endpoint with DB-based aggregation.

**Response:** Prometheus text format metrics including:
```
# HELP reddit_posts_collected_total Total Reddit posts collected
# TYPE reddit_posts_collected_total counter
reddit_posts_collected_total 1250

# HELP posts_processed_total Total posts processed with AI
# TYPE posts_processed_total counter
posts_processed_total 890

# HELP posts_published_total Total posts published to Ghost
# TYPE posts_published_total counter
posts_published_total 845

# HELP processing_failures_total Total processing failures
# TYPE processing_failures_total counter
processing_failures_total 23

# HELP api_errors_total Total external API errors by type
# TYPE api_errors_total counter
api_errors_total{service="reddit",error_type="429"} 5
api_errors_total{service="openai",error_type="timeout"} 2
api_errors_total{service="ghost",error_type="5xx"} 1
```

## Error Handling

The API uses standard HTTP status codes and returns consistent error responses:

```json
{
  "error": "Validation failed",
  "detail": "Field 'subreddits' is required",
  "status_code": 422,
  "timestamp": "2024-01-15T10:30:00Z",
  "path": "/api/v1/collect/trigger"
}
```

### Common Status Codes

- **200**: Success
- **400**: Bad Request  
- **404**: Not Found
- **422**: Validation Error
- **500**: Internal Server Error
- **503**: Service Unavailable

**Note**: The MVP does not implement rate limiting or authentication. These should be added via reverse proxy or middleware in production.

## OpenAPI/Swagger Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## SDK and Client Libraries

### Python Client Example

```python
import requests
from typing import List, Dict, Any

class RedditPublisherClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """Get system health status"""
        response = self.session.get(f'{self.base_url}/health')
        response.raise_for_status()
        return response.json()
    
    def trigger_collection(self, subreddits: List[str], sort_type: str = 'hot', 
                          limit: int = 20) -> Dict[str, Any]:
        """Trigger Reddit content collection"""
        data = {
            'subreddits': subreddits,
            'sort_type': sort_type,
            'limit': limit
        }
        response = self.session.post(f'{self.base_url}/api/v1/collect/trigger', json=data)
        response.raise_for_status()
        return response.json()
    
    def trigger_processing(self, post_ids: List[str]) -> Dict[str, Any]:
        """Trigger AI content processing"""
        data = {'post_ids': post_ids}
        response = self.session.post(f'{self.base_url}/api/v1/process/trigger', json=data)
        response.raise_for_status()
        return response.json()
    
    def trigger_publishing(self, post_ids: List[str]) -> Dict[str, Any]:
        """Trigger Ghost publishing"""
        data = {'post_ids': post_ids}
        response = self.session.post(f'{self.base_url}/api/v1/publish/trigger', json=data)
        response.raise_for_status()
        return response.json()
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status"""
        response = self.session.get(f'{self.base_url}/api/v1/status/queues')
        response.raise_for_status()
        return response.json()
    
    def get_worker_status(self) -> Dict[str, Any]:
        """Get worker status"""
        response = self.session.get(f'{self.base_url}/api/v1/status/workers')
        response.raise_for_status()
        return response.json()
    
    def request_takedown(self, reddit_post_id: str, reason: str, 
                        contact_email: str) -> Dict[str, Any]:
        """Request content takedown"""
        data = {
            'reason': reason,
            'contact_email': contact_email
        }
        response = self.session.post(f'{self.base_url}/api/v1/takedown/{reddit_post_id}', json=data)
        response.raise_for_status()
        return response.json()

# Usage example
client = RedditPublisherClient('http://localhost:8000')

# Check system health
health = client.health_check()
print(f"System status: {health['status']}")

# Trigger collection
result = client.trigger_collection(['python', 'programming'])
print(f"Task ID: {result['task_id']}")

# Check queue status
queues = client.get_queue_status()
print(f"Collect queue: {queues['collect']['queued']} pending")
```

### cURL Examples

```bash
# Health check
curl "http://localhost:8000/health"

# Trigger collection
curl -X POST "http://localhost:8000/api/v1/collect/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "subreddits": ["python", "programming"],
    "sort_type": "hot",
    "limit": 20
  }'

# Trigger processing
curl -X POST "http://localhost:8000/api/v1/process/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "post_ids": ["post1", "post2"]
  }'

# Trigger publishing
curl -X POST "http://localhost:8000/api/v1/publish/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "post_ids": ["post1", "post2"]
  }'

# Get queue status
curl "http://localhost:8000/api/v1/status/queues"

# Get worker status
curl "http://localhost:8000/api/v1/status/workers"

# Get system metrics
curl "http://localhost:8000/metrics"

# Request takedown
curl -X POST "http://localhost:8000/api/v1/takedown/abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Copyright infringement",
    "contact_email": "requester@example.com"
  }'
```

## Slack Notifications

The system sends notifications to Slack for important events:

### Notification Types

1. **Budget Alerts**: When API/token usage reaches 80% or 100%
2. **Queue Alerts**: When queue depth exceeds 500 items
3. **Failure Rate Alerts**: When failure rate exceeds 5% in 5-minute window
4. **Daily Reports**: Summary of daily activity

### Slack Configuration

Configure Slack notifications in your environment:
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
export QUEUE_ALERT_THRESHOLD=500
export FAILURE_RATE_THRESHOLD=0.05
```

### Notification Format

```json
{
  "text": "🚨 [HIGH] Reddit Publisher Alert",
  "attachments": [
    {
      "color": "danger",
      "fields": [
        {"title": "Service", "value": "collector", "short": true},
        {"title": "Message", "value": "Queue depth exceeded threshold", "short": false},
        {"title": "Queue Depth", "value": "523", "short": true},
        {"title": "Threshold", "value": "500", "short": true}
      ]
    }
  ]
}
```

## Best Practices

### 1. Error Handling
- Always check HTTP status codes
- Implement exponential backoff for retries
- Log errors with sufficient context
- Monitor external API quotas

### 2. Monitoring
- Monitor queue depths and processing rates
- Set up Slack alerts for system health issues
- Track API usage and costs via /metrics endpoint
- Use health check endpoint for load balancer configuration

### 3. Performance
- Use appropriate batch sizes (default: 20 posts)
- Monitor response times via /metrics
- Check queue status before triggering large batches
- Allow time for processing between triggers

### 4. Content Management
- Use takedown endpoint for content removal requests
- Monitor daily reports for processing statistics
- Check worker status if processing seems slow

## Troubleshooting

### Common Issues

1. **Task Failures**
   - Check /health endpoint for service status
   - Monitor queue status for backlogs
   - Verify external service connectivity (Reddit, OpenAI, Ghost)
   - Check Slack notifications for error details

2. **High Response Times**
   - Check /api/v1/status/queues for queue depths
   - Monitor /metrics endpoint for processing rates
   - Verify database and Redis connectivity

3. **External API Errors**
   - Reddit API: Check daily quota usage
   - OpenAI API: Monitor token budget consumption
   - Ghost CMS: Verify admin key and API URL

4. **Queue Backlogs**
   - Check /api/v1/status/workers for worker health
   - Monitor Slack alerts for queue threshold breaches
   - Consider manual scaling if queues exceed 500 items

### Getting Help

- Check the /health endpoint for system status
- Review /metrics endpoint for error counts
- Monitor Slack notifications for real-time alerts
- Check application logs for detailed error messages