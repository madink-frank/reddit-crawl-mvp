# Deployment Guide

This document describes the CI/CD pipeline and deployment process for the Reddit Ghost Publisher.

## Overview

The deployment pipeline consists of:
1. **Automated Testing** - Unit tests, integration tests, and security scans
2. **Docker Image Build** - Multi-platform container builds with security scanning
3. **Manual Approval** - Required approval before production deployment
4. **Automated Deployment** - Zero-downtime deployment with health checks
5. **Post-deployment Verification** - Smoke tests and rollback on failure

## GitHub Secrets Configuration

Configure the following secrets in your GitHub repository:

### Docker Registry
```
DOCKER_USERNAME=your_docker_username
DOCKER_PASSWORD=your_docker_password
DOCKER_REGISTRY=your_registry_url
```

### Production Environment
```
PRODUCTION_URL=https://your-production-url.com
DATABASE_URL=postgresql://user:pass@host:5432/reddit_publisher
REDIS_URL=redis://host:6379
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

### API Keys
```
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_user_agent
OPENAI_API_KEY=your_openai_key
GHOST_ADMIN_KEY=your_ghost_admin_key
GHOST_API_URL=https://your-blog.ghost.io
```

### Notifications
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

### Deployment Approvers
```
DEPLOYMENT_APPROVERS=username1,username2,username3
```

## GitHub Environment Setup

1. Go to your repository Settings → Environments
2. Create a new environment named `production`
3. Add the following protection rules:
   - Required reviewers: Add your deployment approvers
   - Wait timer: 0 minutes (optional)
   - Deployment branches: Limit to `main` branch only

## Pipeline Stages

### 1. Test Stage
Runs on every push and pull request:
- Unit tests with 70% coverage requirement
- Integration tests
- Code linting and security scanning
- Database migration tests

### 2. Build Stage
Runs on pushes to `main` and `develop` branches:
- Multi-stage Docker build
- Security scanning with Trivy
- Image tagging and registry push
- Build artifact generation

### 3. Smoke Tests
Runs after successful build:
- Spins up test environment
- Runs Postman smoke test collection
- Validates critical API endpoints
- Generates test reports

### 4. Deploy Stage
Runs only on `main` branch with manual approval:
- **Manual Approval Required** - Creates GitHub issue for approval
- Pre-deployment backup
- Zero-downtime deployment
- Post-deployment health checks
- Automatic rollback on failure

### 5. Weekly Backup Test
Runs every Monday at 02:00 UTC:
- Creates test database backup
- Performs restore test
- Validates data integrity
- Notifies results via Slack

## Manual Deployment

For manual deployments, use the deployment script:

```bash
# Deploy latest image to production
./scripts/deploy.sh

# Deploy specific image tag
./scripts/deploy.sh your-registry/reddit-publisher:v1.2.3

# Deploy to staging environment
./scripts/deploy.sh reddit-publisher:latest staging
```

## Rollback Process

### Automatic Rollback
The pipeline automatically rolls back if:
- Post-deployment health checks fail
- Smoke tests fail after deployment
- Any critical service fails to start

### Manual Rollback
```bash
# Rollback to previous deployment
docker-compose -f docker-compose.prod.yml down
export DOCKER_IMAGE_TAG="your-registry/reddit-publisher:previous"
docker-compose -f docker-compose.prod.yml up -d
```

## Monitoring Deployment

### Health Checks
- **Application Health**: `GET /health`
- **Metrics**: `GET /metrics`
- **Service Status**: `docker-compose ps`

### Logs
```bash
# View application logs
docker-compose -f docker-compose.prod.yml logs -f api

# View worker logs
docker-compose -f docker-compose.prod.yml logs -f worker-collector
docker-compose -f docker-compose.prod.yml logs -f worker-nlp
docker-compose -f docker-compose.prod.yml logs -f worker-publisher
```

### Slack Notifications
The pipeline sends notifications for:
- ✅ Successful deployments
- ❌ Failed deployments with rollback status
- 📊 Weekly backup test results
- 🚨 Critical deployment issues

## Troubleshooting

### Common Issues

**1. Manual Approval Timeout**
- Check GitHub Issues for approval request
- Ensure approvers have repository access
- Verify DEPLOYMENT_APPROVERS secret is correct

**2. Health Check Failures**
- Check service logs: `docker-compose logs`
- Verify environment variables are set
- Ensure database connectivity

**3. Image Pull Failures**
- Verify Docker registry credentials
- Check image tag exists in registry
- Ensure network connectivity to registry

**4. Rollback Issues**
- Check if previous image tag exists
- Verify backup directory permissions
- Review deployment backup logs

### Emergency Procedures

**Complete Service Outage**
1. Stop all services: `docker-compose -f docker-compose.prod.yml down`
2. Check system resources: `df -h`, `free -m`
3. Review logs: `docker-compose logs`
4. Restart services: `docker-compose -f docker-compose.prod.yml up -d`

**Database Issues**
1. Check PostgreSQL health: `docker-compose exec postgres pg_isready`
2. Review database logs: `docker-compose logs postgres`
3. Restore from backup if needed: `./scripts/restore-database.sh`

**Worker Queue Backup**
1. Check Redis connectivity: `docker-compose exec redis redis-cli ping`
2. Monitor queue sizes: `curl http://localhost:8000/api/v1/status/queues`
3. Scale workers if needed: `docker-compose up -d --scale worker-collector=2`

## Security Considerations

- All secrets are stored in GitHub Secrets (encrypted)
- Docker images are scanned for vulnerabilities
- Production services bind only to localhost
- Logs are rotated and size-limited
- Database backups are encrypted at rest
- Network access is restricted via Docker networks

## Performance Monitoring

Monitor these metrics post-deployment:
- API response times (target: p95 < 300ms)
- Queue processing rates
- Database connection pool usage
- Memory and CPU utilization
- Error rates and failure patterns

For detailed monitoring setup, see the [Monitoring Guide](../docs/monitoring-guide.md).