# Task 18.3: System Quality Verification Tests

This directory contains comprehensive verification tests for Task 18.3 "시스템 품질 검증 테스트 실행" (System Quality Verification Test Execution), covering Requirements 11.23-11.33.

## Overview

The system quality verification tests validate that the Reddit Ghost Publisher MVP meets all quality, security, observability, and deployment requirements before production release.

## Test Structure

### Test Categories

1. **Database Tests (Requirements 11.23-11.24)**
   - Schema and constraint validation
   - Index verification  
   - Backup/restore procedures

2. **Security/Compliance Tests (Requirements 11.25-11.27)**
   - Environment variable security
   - PII masking in logs
   - Takedown workflow implementation
   - Reddit API policy compliance

3. **Observability/Alerting Tests (Requirements 11.28-11.30)**
   - /health endpoint functionality
   - /metrics endpoint Prometheus format
   - Failure rate alerting
   - Queue monitoring
   - Daily report generation

4. **CI/Deployment Tests (Requirements 11.31-11.33)**
   - Unit test coverage ≥70%
   - Docker build verification
   - GitHub Actions workflow
   - Postman smoke tests

## Files

### Core Test Files

- `system_quality_tests.py` - Main test implementation class
- `run_task_18_3_tests.py` - Advanced test runner with reporting
- `test_config_18_3.py` - Test configuration and requirement mappings
- `README_TASK_18_3.md` - This documentation file

### Supporting Scripts

- `scripts/run-task-18-3-verification.sh` - Bash-based verification tests
- `scripts/demo-task-18-3.sh` - Demo script showing test capabilities

## Usage

### Quick Start

```bash
# Run all verification tests
python3 tests/verification/run_task_18_3_tests.py

# Run specific requirements
python3 tests/verification/run_task_18_3_tests.py --requirements 11.23 11.24

# Run with parallel execution
python3 tests/verification/run_task_18_3_tests.py --parallel

# List available requirements
python3 tests/verification/run_task_18_3_tests.py --list-requirements
```

### Bash Alternative

```bash
# Run bash-based verification tests
bash scripts/run-task-18-3-verification.sh

# Demo the test structure
bash scripts/demo-task-18-3.sh
```

### Advanced Usage

```bash
# Run with custom configuration
python3 tests/verification/run_task_18_3_tests.py --config custom_config.json

# Save results to specific file
python3 tests/verification/run_task_18_3_tests.py --output results.json

# Skip pre-checks
python3 tests/verification/run_task_18_3_tests.py --no-pre-checks
```

## Requirements Mapping

| Requirement | Test Name | Description |
|-------------|-----------|-------------|
| 11.23 | Database Schema/Constraints Test | Validate database schema, constraints, and indexes |
| 11.24 | Backup/Recovery Test | Test backup creation and recovery procedures |
| 11.25 | Secret Management/Log Masking Test | Test environment variable security and PII masking |
| 11.26 | Takedown Workflow Test | Test takedown request handling and audit logging |
| 11.27 | Reddit API Compliance Test | Test Reddit API policy compliance and rate limiting |
| 11.28 | Health/Metrics Endpoints Test | Test /health and /metrics endpoint functionality |
| 11.29 | Failure Rate/Queue Alerting Test | Test alerting system for failures and queue backlogs |
| 11.30 | Daily Report Test | Test daily report generation and Slack integration |
| 11.31 | Unit Test Coverage Test | Test unit test coverage meets 70% threshold |
| 11.32 | Docker Build/Deployment Test | Test Docker build and CI/CD deployment configuration |
| 11.33 | Postman Smoke Tests | Test API endpoints with Postman smoke test suite |

## Prerequisites

### System Requirements

- Python 3.8+
- PostgreSQL 15 (running)
- Redis (running)
- FastAPI application (running on localhost:8000)
- Docker (for build tests)
- Newman CLI (for Postman tests)

### Environment Variables

Required environment variables for full testing:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=reddit_publisher
DB_USER=postgres
DB_PASSWORD=postgres

# API
API_BASE_URL=http://localhost:8000

# External Services (for compliance testing)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
OPENAI_API_KEY=your_openai_key
GHOST_ADMIN_KEY=your_ghost_admin_key
SLACK_WEBHOOK_URL=your_slack_webhook
```

### Python Dependencies

```bash
pip install psycopg2-binary redis requests
```

## Test Configuration

### Default Configuration

The tests use default configuration values that can be overridden:

```python
# Database configuration
database:
  host: localhost
  port: 5432
  database: reddit_publisher
  user: postgres
  password: postgres

# API configuration  
observability:
  api_base_url: http://localhost:8000
  health_endpoint: /health
  metrics_endpoint: /metrics

# Test thresholds
ci:
  coverage_threshold: 70.0
  docker_build_timeout: 300
```

### Custom Configuration

Create a JSON configuration file to override defaults:

```json
{
  "database": {
    "host": "custom-db-host",
    "port": "5433"
  },
  "observability": {
    "api_base_url": "http://staging.example.com:8000"
  },
  "ci": {
    "coverage_threshold": 80.0
  }
}
```

## Test Results

### Output Format

Tests generate detailed JSON results:

```json
{
  "execution_info": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-01T00:05:00Z", 
    "duration_seconds": 300,
    "task": "18.3 시스템 품질 검증 테스트 실행"
  },
  "requirement_summary": {
    "total_requirements": 11,
    "passed_requirements": 10,
    "failed_requirements": 1,
    "error_requirements": 0,
    "success_rate": 90.9
  },
  "test_summary": {
    "total_tests": 45,
    "passed_tests": 42,
    "failed_tests": 3,
    "success_rate": 93.3
  },
  "requirement_results": {
    "11.23": {
      "requirement_id": "11.23",
      "name": "Database Schema/Constraints Test",
      "status": "PASS",
      "tests": [...]
    }
  }
}
```

### Console Output

```
=== TASK 18.3: SYSTEM QUALITY VERIFICATION TEST RESULTS ===
Task: 18.3 시스템 품질 검증 테스트 실행
Duration: 45.23 seconds
Completed: 2024-01-01T00:05:00Z

Requirement Results:
  Total Requirements: 11
  Passed: 10 (90.9%)
  Failed: 1
  Errors: 0

Test Results:
  Total Tests: 45
  Passed: 42 (93.3%)
  Failed: 3

✓ OVERALL RESULT: ALL SYSTEM QUALITY VERIFICATION TESTS PASSED
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check if PostgreSQL is running
   docker-compose ps postgres
   
   # Check connection
   psql -h localhost -U postgres -d reddit_publisher -c "SELECT 1;"
   ```

2. **API Not Responding**
   ```bash
   # Check if FastAPI is running
   curl http://localhost:8000/health
   
   # Check docker-compose services
   docker-compose ps api
   ```

3. **Missing Dependencies**
   ```bash
   # Install required packages
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Newman Not Available**
   ```bash
   # Install Newman globally
   npm install -g newman
   
   # Or use Docker
   docker run --rm -v $(pwd):/workspace postman/newman:latest run collection.json
   ```

### Test-Specific Issues

- **Coverage Tests Failing**: Ensure pytest and coverage are installed
- **Docker Build Tests Failing**: Ensure Docker daemon is running
- **Postman Tests Failing**: Check if API endpoints are accessible

## Integration with CI/CD

### GitHub Actions Integration

```yaml
name: System Quality Verification

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality-verification:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
        npm install -g newman
    
    - name: Run System Quality Verification Tests
      run: |
        python3 tests/verification/run_task_18_3_tests.py
      env:
        DB_HOST: localhost
        DB_USER: postgres
        DB_PASSWORD: postgres
        API_BASE_URL: http://localhost:8000
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: quality-verification-results
        path: task_18_3_results_*.json
```

## Contributing

When adding new verification tests:

1. Add test methods to `SystemQualityVerifier` class
2. Update `REQUIREMENT_TEST_MAPPING` in `test_config_18_3.py`
3. Add expected outcomes to `EXPECTED_OUTCOMES`
4. Update this README with new requirements
5. Test both Python and bash execution paths

## License

This verification test suite is part of the Reddit Ghost Publisher MVP project and follows the same license terms.