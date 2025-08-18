# MVP System Verification Tests

This directory contains comprehensive verification tests for the Reddit Ghost Publisher MVP system. These tests validate all requirements from the specification and ensure the system is ready for production deployment.

## Overview

The verification test suite covers all 11 requirements from the specification:

1. **Reddit Collection** - API integration, rate limiting, content filtering
2. **AI Processing** - OpenAI integration, fallback logic, token management
3. **Ghost Publishing** - CMS integration, template rendering, media handling
4. **Architecture** - Queue routing, worker management, scaling alerts
5. **Database** - Schema validation, backup/restore, data integrity
6. **Security** - Secret management, PII masking, takedown workflow
7. **Monitoring** - Health checks, metrics, alerting, reporting
8. **CI/CD** - Test coverage, build process, deployment validation
9. **Performance** - Response times, throughput, processing latency
10. **UX** - Template consistency, tag formatting, image fallbacks
11. **System Integration** - End-to-end workflows, error recovery

## Test Structure

```
tests/verification/
├── README.md                    # This file
├── run_verification_tests.py    # Main test runner
├── test_config.py              # Test configuration and validation criteria
├── seed_data.py                # Test data and sample content
├── staging_config.json         # Generated staging environment config
├── logs/                       # Test execution logs
├── reports/                    # Test reports and results
├── screenshots/                # Visual test artifacts
└── artifacts/                  # Additional test outputs
```

## Prerequisites

### 1. Environment Setup

Before running verification tests, set up the staging environment:

```bash
# From project root
./scripts/setup-staging-environment.sh
```

This script will:
- Create necessary directories
- Validate environment variables
- Start Docker Compose staging environment
- Run database migrations
- Initialize test data
- Verify service connectivity

### 2. Required Environment Variables

Update `.env.staging` with actual values:

```bash
# Reddit API (required)
REDDIT_CLIENT_ID=your_actual_client_id
REDDIT_CLIENT_SECRET=your_actual_client_secret

# OpenAI API (required)
OPENAI_API_KEY=your_actual_openai_key

# Ghost CMS (required)
GHOST_ADMIN_KEY=your_actual_ghost_admin_key
GHOST_API_URL=https://your-staging-blog.ghost.io

# Slack Notifications (required for alert tests)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/TEST/WEBHOOK
```

### 3. External Service Setup

- **Reddit**: Create a Reddit app and obtain API credentials
- **OpenAI**: Set up OpenAI API account with sufficient credits
- **Ghost**: Set up a staging Ghost blog (Ghost Pro or self-hosted)
- **Slack**: Create a test channel and webhook for notifications

## Running Tests

### Quick Start

Run all verification tests:

```bash
python tests/verification/run_verification_tests.py --environment staging
```

### Test Suites

Run specific test suites:

```bash
# Smoke tests (basic functionality)
python tests/verification/run_verification_tests.py --suite smoke

# Functional tests (core features)
python tests/verification/run_verification_tests.py --suite functional

# Performance tests
python tests/verification/run_verification_tests.py --suite performance

# Security tests
python tests/verification/run_verification_tests.py --suite security

# Integration tests (end-to-end)
python tests/verification/run_verification_tests.py --suite integration
```

### Verbose Output

Enable detailed logging:

```bash
python tests/verification/run_verification_tests.py --verbose
```

### Custom Configuration

Use custom test configuration:

```bash
python tests/verification/run_verification_tests.py --config custom_config.json
```

## Test Categories

### 1. Pre-test Setup (Phase 1)

Validates the test environment before running actual tests:

- ✅ Docker Compose staging environment running
- ✅ Environment variables configured
- ✅ External service connectivity
- ✅ Test data initialization

### 2. Smoke Tests (Phase 2)

Basic functionality validation:

- ✅ API health check
- ✅ Basic endpoint accessibility
- ✅ Database connectivity
- ✅ Redis connectivity

**Pass Criteria**: 100% of smoke tests must pass

### 3. Functional Tests (Phase 3)

Core feature validation per requirements:

#### Reddit Collection (Req 1)
- ✅ Collect top N posts from specified subreddits
- ✅ Rate limiting compliance (60 RPM)
- ✅ NSFW content filtering
- ✅ Duplicate prevention
- ✅ Budget alerts (80%/100% thresholds)

#### AI Processing (Req 2)
- ✅ GPT-4o-mini primary processing
- ✅ GPT-4o fallback logic
- ✅ Tag extraction (3-5 tags)
- ✅ JSON schema compliance
- ✅ Retry mechanisms
- ✅ Token budget management

#### Ghost Publishing (Req 3)
- ✅ Article template rendering
- ✅ Admin API authentication
- ✅ Image upload and processing
- ✅ Tag mapping
- ✅ Source attribution
- ✅ Publication idempotency

#### Architecture (Req 4)
- ✅ Queue routing (collect/process/publish)
- ✅ Manual scaling alerts
- ✅ Worker health monitoring

**Pass Criteria**: 95% of functional tests must pass

### 4. Performance Tests (Phase 4)

Performance and scalability validation:

- ✅ API response times (p95 < 300ms)
- ✅ End-to-end processing time (< 5 minutes)
- ✅ Throughput capacity (100 posts/hour)

**Pass Criteria**: 90% of performance tests must pass

### 5. Security Tests (Phase 5)

Security and compliance validation:

- ✅ Secret masking in logs
- ✅ Takedown workflow (72-hour SLA)
- ✅ API policy compliance

**Pass Criteria**: 100% of security tests must pass

### 6. Integration Tests (Phase 6)

End-to-end workflow validation:

- ✅ Full pipeline (collect → process → publish)
- ✅ Error recovery mechanisms
- ✅ Monitoring and alerting

**Pass Criteria**: 95% of integration tests must pass

## Test Results

### Report Generation

Test results are automatically saved to:

- `tests/verification/reports/verification_report_[timestamp].json`
- Console output with summary statistics
- Individual test logs in `tests/verification/logs/`

### Report Format

```json
{
  "test_run_id": "verification_1234567890",
  "environment": "staging",
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T01:00:00Z",
  "duration_seconds": 3600,
  "overall_result": {
    "passed": true,
    "pass_rate": 0.98,
    "total_tests": 50,
    "passed_tests": 49,
    "failed_tests": 1
  },
  "suite_results": {
    "setup": { "passed": true, "tests": {...} },
    "smoke": { "passed": true, "tests": {...} },
    "functional": { "passed": true, "tests": {...} },
    "performance": { "passed": true, "tests": {...} },
    "security": { "passed": true, "tests": {...} },
    "integration": { "passed": true, "tests": {...} }
  },
  "summary": {
    "functional_compliance": true,
    "performance_compliance": true,
    "security_compliance": true,
    "operational_readiness": true
  },
  "recommendations": [
    "All tests passed - system ready for production"
  ]
}
```

### Pass/Fail Criteria

The system passes verification if:

1. **Setup Phase**: 100% pass rate
2. **Smoke Tests**: 100% pass rate
3. **Overall Pass Rate**: ≥95%
4. **Critical Requirements**: 100% pass rate for security tests
5. **Performance Targets**: Meet all specified SLAs

## Troubleshooting

### Common Issues

#### Environment Setup Failures

```bash
# Check Docker Compose status
docker-compose -f docker-compose.staging.yml ps

# View service logs
docker-compose -f docker-compose.staging.yml logs api-staging
docker-compose -f docker-compose.staging.yml logs postgres-staging
docker-compose -f docker-compose.staging.yml logs redis-staging

# Restart services
docker-compose -f docker-compose.staging.yml restart
```

#### API Connectivity Issues

```bash
# Test API directly
curl http://localhost:8001/health

# Check API logs
docker-compose -f docker-compose.staging.yml logs api-staging

# Verify environment variables
docker-compose -f docker-compose.staging.yml exec api-staging env | grep -E "(REDDIT|OPENAI|GHOST|SLACK)"
```

#### Database Issues

```bash
# Connect to database
docker-compose -f docker-compose.staging.yml exec postgres-staging psql -U postgres -d reddit_publisher_staging

# Check database schema
docker-compose -f docker-compose.staging.yml exec postgres-staging psql -U postgres -d reddit_publisher_staging -c "\dt"

# Run migrations manually
docker-compose -f docker-compose.staging.yml exec api-staging python -m alembic upgrade head
```

#### External Service Issues

```bash
# Test Reddit API
curl -H "User-Agent: RedditGhostPublisher/1.0-staging" https://www.reddit.com/api/v1/me

# Test OpenAI API
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# Test Ghost API
curl -H "Authorization: Ghost $GHOST_JWT_TOKEN" $GHOST_API_URL/ghost/api/admin/site/
```

### Debug Mode

Run tests with debug logging:

```bash
DEBUG=true python tests/verification/run_verification_tests.py --verbose
```

### Manual Test Execution

Execute individual test components:

```bash
# Test Reddit collection
docker-compose -f docker-compose.staging.yml exec api-staging python -c "
from workers.collector.tasks import collect_reddit_posts
result = collect_reddit_posts.delay(['programming'], 'hot')
print(result.get())
"

# Test AI processing
docker-compose -f docker-compose.staging.yml exec api-staging python -c "
from workers.nlp_pipeline.tasks import process_content_with_ai
# Add test code here
"

# Test Ghost publishing
docker-compose -f docker-compose.staging.yml exec api-staging python -c "
from workers.publisher.tasks import publish_to_ghost
# Add test code here
"
```

## Continuous Integration

### GitHub Actions Integration

Add to `.github/workflows/verification.yml`:

```yaml
name: MVP Verification Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday 2 AM

jobs:
  verification:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup staging environment
      run: ./scripts/setup-staging-environment.sh
      env:
        REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
        REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        GHOST_ADMIN_KEY: ${{ secrets.GHOST_ADMIN_KEY }}
        GHOST_API_URL: ${{ secrets.GHOST_API_URL }}
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
    
    - name: Run verification tests
      run: python tests/verification/run_verification_tests.py --environment staging
    
    - name: Upload test reports
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: verification-reports
        path: tests/verification/reports/
```

### Local Development

Run verification tests before commits:

```bash
# Add to .git/hooks/pre-push
#!/bin/bash
echo "Running verification tests..."
python tests/verification/run_verification_tests.py --suite smoke
if [ $? -ne 0 ]; then
    echo "Verification tests failed. Push aborted."
    exit 1
fi
```

## Production Readiness

The system is considered production-ready when:

✅ **Functional Compliance**: All core features working as specified  
✅ **Performance Compliance**: Meeting all SLA targets  
✅ **Security Compliance**: All security requirements satisfied  
✅ **Operational Readiness**: Monitoring, alerting, and recovery mechanisms functional  

### Final Checklist

Before production deployment:

- [ ] All verification tests passing (≥95% overall)
- [ ] Performance targets met (p95 < 300ms, E2E < 5min)
- [ ] Security tests 100% passing
- [ ] External service integrations validated
- [ ] Monitoring and alerting functional
- [ ] Backup and recovery tested
- [ ] Documentation complete
- [ ] Team training completed

## Support

For issues with verification tests:

1. Check the troubleshooting section above
2. Review test logs in `tests/verification/logs/`
3. Examine service logs with Docker Compose
4. Validate environment configuration
5. Test external service connectivity

For questions about specific test requirements, refer to:
- `tests/verification/test_config.py` - Test validation criteria
- `tests/verification/seed_data.py` - Test data and expectations
- `.kiro/specs/reddit-ghost-publisher/requirements.md` - Original requirements