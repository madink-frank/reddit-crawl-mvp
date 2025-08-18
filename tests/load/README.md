# Load Testing for Reddit Ghost Publisher

This directory contains comprehensive load testing setup for the Reddit Ghost Publisher system using Locust.

## Overview

The load testing framework provides:
- Multiple test scenarios (smoke, normal, high load, stress, spike, endurance)
- Automated performance requirement validation
- Detailed reporting and metrics collection
- System performance monitoring during tests

## Files

- `locustfile.py` - Main Locust test file with user behaviors
- `load_test_config.py` - Configuration management and result analysis
- `run_load_tests.py` - Test runner script
- `test_load_config.py` - Unit tests for load test configuration
- `README.md` - This documentation

## Prerequisites

1. **Install Locust**:
   ```bash
   pip install locust
   ```

2. **Start the Application**:
   ```bash
   # Make sure the Reddit Ghost Publisher is running on http://localhost:8000
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Verify Health Endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

## Test Scenarios

### 1. Smoke Test
- **Purpose**: Quick verification of basic functionality
- **Users**: 1
- **Duration**: 1 minute
- **Expected RPS**: 1

### 2. Normal Load
- **Purpose**: Simulate normal operational load
- **Users**: 10
- **Duration**: 5 minutes
- **Expected RPS**: 10

### 3. High Load
- **Purpose**: Test performance under increased load
- **Users**: 50
- **Duration**: 10 minutes
- **Expected RPS**: 50

### 4. Stress Test
- **Purpose**: Find system breaking point
- **Users**: 100
- **Duration**: 30 minutes
- **Expected RPS**: 100

### 5. Spike Test
- **Purpose**: Test sudden load increases
- **Users**: 200
- **Duration**: 2 minutes
- **Expected RPS**: 200

### 6. Endurance Test
- **Purpose**: Long-running stability test
- **Users**: 20
- **Duration**: 60 minutes
- **Expected RPS**: 20

## Running Tests

### Using the Test Runner Script

1. **List available test configurations**:
   ```bash
   python tests/load/run_load_tests.py --list
   ```

2. **Run a specific test**:
   ```bash
   python tests/load/run_load_tests.py smoke_test
   python tests/load/run_load_tests.py normal_load
   python tests/load/run_load_tests.py stress_test
   ```

3. **Run all tests**:
   ```bash
   python tests/load/run_load_tests.py all
   ```

4. **Run tests against a different host**:
   ```bash
   python tests/load/run_load_tests.py normal_load --host http://staging.example.com
   ```

### Using Locust Directly

1. **Interactive mode (with web UI)**:
   ```bash
   locust -f tests/load/locustfile.py --host=http://localhost:8000
   # Open http://localhost:8089 in browser
   ```

2. **Headless mode**:
   ```bash
   locust -f tests/load/locustfile.py --host=http://localhost:8000 \
          --users=10 --spawn-rate=2 --run-time=5m --headless
   ```

3. **With HTML report**:
   ```bash
   locust -f tests/load/locustfile.py --host=http://localhost:8000 \
          --users=50 --spawn-rate=5 --run-time=10m \
          --html=load_test_report.html --headless
   ```

## User Classes

The load tests include different user behavior patterns:

### RedditPublisherUser
- **Behavior**: Normal API usage patterns
- **Tasks**: Health checks, queue status, trigger operations
- **Wait Time**: 1-3 seconds between requests

### HighLoadUser
- **Behavior**: Rapid API requests
- **Tasks**: Frequent health checks and status requests
- **Wait Time**: 0.1-0.5 seconds between requests

### BurstUser
- **Behavior**: Burst traffic patterns
- **Tasks**: Rapid bursts followed by pauses
- **Wait Time**: 0-0.1 seconds during bursts, 5-10 seconds between bursts

### AdminUser
- **Behavior**: Administrative operations
- **Tasks**: Management operations, slower but more comprehensive
- **Wait Time**: 2-5 seconds between requests

## Performance Requirements

The tests validate against these performance requirements:

| Metric | Target | Stress Test Limit |
|--------|--------|-------------------|
| Average Response Time | < 250ms | < 500ms |
| 95th Percentile | < 300ms | < 1000ms |
| Failure Rate | < 1% | < 5% |
| Requests per Second | 80% of expected | 80% of expected |

## Test Results

Results are saved in the `tests/load/results/` directory:

- **HTML Reports**: Visual reports with charts and graphs
- **CSV Data**: Raw performance data for analysis
- **Markdown Reports**: Summary reports with pass/fail status

### Sample Report Structure

```
# Load Test Report: normal_load

**Test Date:** 2024-01-01 10:00:00
**Description:** Normal operational load test

## Test Configuration
- **Host:** http://localhost:8000
- **Users:** 10
- **Spawn Rate:** 2
- **Run Time:** 5m

## Test Results
- **Total Requests:** 1,000
- **Average Response Time:** 245.50ms
- **95th Percentile:** 298.20ms
- **Failure Rate:** 0.50%

## Performance Check Results
- **Average Response Time:** ✅ PASS
- **95th Percentile Response Time:** ✅ PASS
- **Failure Rate:** ✅ PASS
- **Requests Per Second:** ✅ PASS

## Overall Result: ✅ PASS
```

## Monitoring

During load tests, the system monitors:

- CPU usage
- Memory usage
- Disk usage
- Network I/O
- Queue depths
- Active workers
- Database connections

## Troubleshooting

### Common Issues

1. **Connection Refused**:
   - Ensure the application is running
   - Check the host and port configuration

2. **High Failure Rate**:
   - Check application logs for errors
   - Verify database and Redis connectivity
   - Monitor system resources

3. **Slow Response Times**:
   - Check system resource usage
   - Monitor database performance
   - Review application bottlenecks

4. **Authentication Errors**:
   - Verify JWT token configuration
   - Check authentication middleware

### Performance Optimization Tips

1. **Database Optimization**:
   - Add appropriate indexes
   - Optimize query performance
   - Consider connection pooling

2. **Caching**:
   - Implement Redis caching
   - Use application-level caching
   - Cache static content

3. **Scaling**:
   - Horizontal scaling with load balancer
   - Increase worker processes
   - Scale database resources

4. **Monitoring**:
   - Set up real-time monitoring
   - Configure alerting
   - Track key performance metrics

## Integration with CI/CD

To integrate load testing into your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Load Tests
  run: |
    python tests/load/run_load_tests.py smoke_test
    python tests/load/run_load_tests.py normal_load
  
- name: Upload Test Results
  uses: actions/upload-artifact@v2
  with:
    name: load-test-results
    path: tests/load/results/
```

## Best Practices

1. **Test Environment**:
   - Use production-like environment
   - Ensure consistent test conditions
   - Isolate test environment

2. **Test Data**:
   - Use realistic test data
   - Clean up test data after tests
   - Avoid impacting production data

3. **Gradual Load Increase**:
   - Start with smoke tests
   - Gradually increase load
   - Monitor system behavior

4. **Regular Testing**:
   - Run tests regularly
   - Test after major changes
   - Establish performance baselines

5. **Result Analysis**:
   - Analyze trends over time
   - Identify performance regressions
   - Document optimization efforts