# Task 18.2 Functional Verification Tests

This document describes the implementation of Task 18.2 (기능별 검증 테스트 실행) for the Reddit Ghost Publisher MVP system.

## Overview

Task 18.2 implements comprehensive functional verification tests covering requirements 11.5-11.22 from the specification. These tests validate the core functionality of the Reddit Ghost Publisher system across four main areas:

1. **Reddit Collection Tests** (Requirements 11.5-11.9)
2. **AI Processing Tests** (Requirements 11.10-11.14)  
3. **Ghost Publishing Tests** (Requirements 11.15-11.20)
4. **Architecture/Queue Tests** (Requirements 11.21-11.22)

## Test Implementation

### Files Created/Modified

- `tests/verification/functional_tests.py` - Main functional test implementation
- `tests/verification/run_functional_tests.py` - Test runner for functional tests
- `scripts/run-task-18-2-verification.sh` - Comprehensive test execution script
- `tests/verification/FUNCTIONAL_TESTS.md` - This documentation file

### Test Structure

```
tests/verification/
├── functional_tests.py           # Core test implementations
├── run_functional_tests.py       # Test runner
├── FUNCTIONAL_TESTS.md          # Documentation
├── logs/                        # Test execution logs
├── reports/                     # Test result reports
└── screenshots/                 # Visual test artifacts
```

## Test Categories

### 1. Reddit Collection Tests (Requirements 11.5-11.9)

Tests the Reddit collection functionality including:

- **Top N Collection** (11.5): Verifies collection of specified number of posts from subreddits
- **Rate Limiting** (11.6): Validates 60 RPM compliance and backoff behavior
- **NSFW Filtering** (11.7): Ensures NSFW content is properly filtered out
- **Duplicate Prevention** (11.8): Tests unique constraint enforcement
- **Budget Alerts** (11.9): Validates 80%/100% budget threshold alerts

### 2. AI Processing Tests (Requirements 11.10-11.14)

Tests the AI processing pipeline including:

- **GPT Fallback** (11.10): Tests GPT-4o-mini to GPT-4o fallback logic
- **Tag Extraction** (11.11): Validates 3-5 tag extraction with proper formatting
- **JSON Schema** (11.12): Tests pain_points/product_ideas schema compliance
- **Retry Mechanisms** (11.13): Validates exponential backoff retry logic
- **Token Budget** (11.14): Tests token budget management and blocking

### 3. Ghost Publishing Tests (Requirements 11.15-11.20)

Tests the Ghost CMS publishing functionality including:

- **Template Rendering** (11.15): Validates Article template consistency
- **Authentication** (11.16): Tests Ghost Admin API JWT authentication
- **Image Upload** (11.17): Validates image upload to Ghost Images API
- **Tag Mapping** (11.18): Tests LLM tag to Ghost tag mapping
- **Source Attribution** (11.19): Validates source attribution and takedown notices
- **Publication Idempotency** (11.20): Tests duplicate publication prevention

### 4. Architecture/Queue Tests (Requirements 11.21-11.22)

Tests the system architecture and queue functionality including:

- **Queue Routing** (11.21): Validates collect→process→publish queue routing
- **Manual Scaling Alerts** (11.22): Tests queue threshold alerts for manual scaling

## Running the Tests

### Prerequisites

1. **Staging Environment**: Docker Compose staging environment must be running
2. **Environment Variables**: All required API keys and configuration must be set
3. **External Services**: Reddit, OpenAI, Ghost, and Slack services must be accessible

### Quick Start

Run all functional verification tests:

```bash
./scripts/run-task-18-2-verification.sh
```

### Individual Test Suites

Run specific test categories:

```bash
# Reddit collection tests only
python3 tests/verification/run_functional_tests.py --suite reddit --environment staging

# AI processing tests only  
python3 tests/verification/run_functional_tests.py --suite ai --environment staging

# Ghost publishing tests only
python3 tests/verification/run_functional_tests.py --suite ghost --environment staging

# Architecture/queue tests only
python3 tests/verification/run_functional_tests.py --suite architecture --environment staging

# All tests
python3 tests/verification/run_functional_tests.py --suite all --environment staging
```

### Verbose Output

Enable detailed logging:

```bash
python3 tests/verification/run_functional_tests.py --suite all --verbose --environment staging
```

## Test Results

### Pass Criteria

- **Reddit Collection**: 80% pass rate minimum
- **AI Processing**: 80% pass rate minimum
- **Ghost Publishing**: 90% pass rate minimum
- **Architecture/Queue**: 90% pass rate minimum
- **Overall**: All test suites must pass for task completion

### Output Formats

Test results are generated in multiple formats:

1. **Console Output**: Real-time test execution status
2. **JSON Reports**: Detailed results in `tests/verification/reports/`
3. **Log Files**: Execution logs in `tests/verification/logs/`

### Sample Output

```
============================================================
REDDIT COLLECTION TESTS (Requirements 11.5-11.9)
============================================================

Reddit Collection Test Results:
--------------------------------------------------
  top_n_collection: ✅ PASS
    Message: Collected 10 posts (expected >= 5)
  rate_limiting: ✅ PASS
    Message: RPM: 45.2, Rate limit errors: 0
  nsfw_filtering: ✅ PASS
    Message: Found 0 NSFW posts in database (expected 0)
  duplicate_prevention: ✅ PASS
    Message: Added 3 new posts (expected <= 6 due to duplicates)
  budget_alerts: ✅ PASS
    Message: Budget alerts: ['80_percent'], Collection stopped: True

Overall: ✅ PASS (Pass Rate: 100.0%)
```

## Test Implementation Details

### Mock vs Real Testing

The functional tests are designed to work with both mock and real external services:

- **Mock Mode**: Uses simulated responses for rapid testing
- **Real Mode**: Connects to actual Reddit, OpenAI, Ghost, and Slack APIs

### Database Integration

Tests interact with the staging database to:

- Verify post collection and storage
- Check constraint enforcement
- Validate data integrity
- Test schema compliance

### External Service Testing

Tests validate integration with:

- **Reddit API**: Rate limiting, authentication, data collection
- **OpenAI API**: Model fallback, token management, response parsing
- **Ghost CMS**: Authentication, publishing, image upload
- **Slack**: Webhook notifications, alert formatting

### Error Handling

Tests validate error handling for:

- Network timeouts and failures
- API rate limiting and quotas
- Authentication failures
- Data validation errors
- Resource constraints

## Troubleshooting

### Common Issues

1. **Environment Not Running**
   ```bash
   docker-compose -f docker-compose.staging.yml up -d
   ```

2. **Missing Environment Variables**
   - Check `.env.staging` file
   - Verify all required API keys are set

3. **External Service Connectivity**
   - Test Reddit API access
   - Verify OpenAI API key
   - Check Ghost CMS configuration
   - Validate Slack webhook URL

4. **Database Connection Issues**
   - Check PostgreSQL container status
   - Verify database migrations
   - Test connection manually

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
DEBUG=true python3 tests/verification/run_functional_tests.py --verbose --suite all
```

### Log Analysis

Check specific service logs:

```bash
# API logs
docker-compose -f docker-compose.staging.yml logs api-staging

# Worker logs
docker-compose -f docker-compose.staging.yml logs worker-collector
docker-compose -f docker-compose.staging.yml logs worker-nlp
docker-compose -f docker-compose.staging.yml logs worker-publisher

# Database logs
docker-compose -f docker-compose.staging.yml logs postgres-staging
```

## Task Completion Criteria

Task 18.2 is considered complete when:

1. ✅ All Reddit collection tests pass (Requirements 11.5-11.9)
2. ✅ All AI processing tests pass (Requirements 11.10-11.14)
3. ✅ All Ghost publishing tests pass (Requirements 11.15-11.20)
4. ✅ All architecture/queue tests pass (Requirements 11.21-11.22)
5. ✅ Overall pass rate ≥ 95%
6. ✅ No critical failures in core functionality
7. ✅ Test reports generated successfully

## Next Steps

After Task 18.2 completion:

1. **Update Task Status**: Mark task as completed in `tasks.md`
2. **Review Reports**: Analyze detailed test results
3. **Fix Issues**: Address any identified problems
4. **Proceed to Task 18.3**: System Quality Verification Tests
5. **Document Findings**: Update system documentation

## Integration with CI/CD

The functional tests can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run Functional Verification Tests
  run: |
    ./scripts/run-task-18-2-verification.sh
  env:
    REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
    REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    GHOST_ADMIN_KEY: ${{ secrets.GHOST_ADMIN_KEY }}
    GHOST_API_URL: ${{ secrets.GHOST_API_URL }}
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Maintenance

### Regular Updates

- Update test data as system evolves
- Refresh API credentials as needed
- Adjust thresholds based on performance
- Add new tests for new features

### Performance Monitoring

- Track test execution times
- Monitor resource usage during tests
- Optimize slow test cases
- Maintain test environment health

This comprehensive functional verification test suite ensures that all core functionality of the Reddit Ghost Publisher MVP system works correctly according to the specified requirements.