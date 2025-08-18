# Reddit Ghost Publisher - k6 Performance Tests

This directory contains k6 performance tests for the Reddit Ghost Publisher API. These tests validate that the system meets the performance requirements specified in the design document.

## Performance Requirements

Based on the requirements document, the system must meet:

- **p95 Response Time**: < 300ms for API endpoints
- **Error Rate**: < 5% for all requests
- **E2E Processing Time**: < 5 minutes per post (collect → process → publish)
- **Throughput**: 100 posts per hour (steady state)

## Test Files

### Core Test Scripts
- `performance-test.js` - Basic performance test with gradual load increase
- `load-test.js` - High-load test with up to 100 concurrent users
- `e2e-workflow-test.js` - End-to-end workflow testing (collect → process → publish)

### Utilities
- `run-performance-tests.sh` - Test runner script with multiple options
- `README.md` - This documentation file
- `results/` - Directory for test results (auto-generated)

## Test Types

### 1. Performance Test (`performance-test.js`)
**Purpose**: Validate basic API performance under moderate load

**Test Stages**:
- 2m: Ramp up to 10 users
- 5m: Stay at 10 users  
- 2m: Ramp up to 20 users
- 5m: Stay at 20 users
- 2m: Ramp down to 0 users

**Total Duration**: ~16 minutes

**Endpoints Tested**:
- Health check (`GET /health`)
- Metrics (`GET /metrics`)
- Queue status (`GET /api/v1/status/queues`)
- Worker status (`GET /api/v1/status/workers`)
- Collection trigger (`POST /api/v1/collect/trigger`)
- Processing trigger (`POST /api/v1/process/trigger`)
- Publishing trigger (`POST /api/v1/publish/trigger`)

### 2. Load Test (`load-test.js`)
**Purpose**: Test system behavior under high concurrent load

**Test Stages**:
- 1m: Ramp up to 10 users
- 3m: Ramp up to 50 users
- 5m: Ramp up to 100 users
- 5m: Stay at 100 users (peak load)
- 2m: Ramp down to 0 users

**Total Duration**: ~16 minutes

**Load Distribution**: Weighted endpoint selection based on realistic usage patterns:
- Health check: 30%
- Metrics: 20%
- Queue status: 25%
- Worker status: 15%
- Collection trigger: 5%
- Processing trigger: 3%
- Publishing trigger: 2%

### 3. E2E Workflow Test (`e2e-workflow-test.js`)
**Purpose**: Validate complete workflow performance and reliability

**Test Scenarios**:
- **Steady Load**: 5 concurrent workflows for 10 minutes
- **Spike Test**: 1 → 10 → 1 users over 2.5 minutes

**Total Duration**: ~11 minutes

**Workflow Steps**:
1. Trigger collection
2. Wait for collection completion
3. Trigger processing
4. Wait for processing completion
5. Trigger publishing
6. Wait for publishing completion

## Running Tests

### Prerequisites

1. **Install k6**:
   ```bash
   # macOS
   brew install k6
   
   # Linux
   sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
   echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
   sudo apt-get update
   sudo apt-get install k6
   
   # Windows
   choco install k6
   ```

2. **Ensure API is running**:
   ```bash
   # Start the Reddit Ghost Publisher API
   docker-compose up -d
   
   # Verify it's accessible
   curl http://localhost:8000/health
   ```

### Using the Test Runner Script

The `run-performance-tests.sh` script provides an easy way to run all test types:

```bash
# Basic performance test (default)
./tests/k6/run-performance-tests.sh

# Load test with 100 concurrent users
./tests/k6/run-performance-tests.sh -t load

# E2E workflow test
./tests/k6/run-performance-tests.sh -t e2e

# Test against staging environment
./tests/k6/run-performance-tests.sh -t performance -u https://staging-api.example.com

# Verbose output with custom results directory
./tests/k6/run-performance-tests.sh -v -o ./my-results
```

### Running Tests Directly with k6

```bash
# Performance test
k6 run --env BASE_URL=http://localhost:8000 tests/k6/performance-test.js

# Load test
k6 run --env BASE_URL=http://localhost:8000 tests/k6/load-test.js

# E2E workflow test
k6 run --env BASE_URL=http://localhost:8000 tests/k6/e2e-workflow-test.js
```

### Output Options

```bash
# Save results to JSON and CSV
k6 run --out json=results.json --out csv=results.csv tests/k6/performance-test.js

# Export summary
k6 run --summary-export=summary.json tests/k6/performance-test.js

# Real-time monitoring with InfluxDB (if available)
k6 run --out influxdb=http://localhost:8086/k6 tests/k6/performance-test.js
```

## Understanding Results

### Key Metrics

**Response Time Metrics**:
- `http_req_duration`: Total request duration
- `http_req_waiting`: Time waiting for response
- `http_req_connecting`: Connection establishment time

**Throughput Metrics**:
- `http_reqs`: Total number of HTTP requests
- `http_req_rate`: Requests per second

**Error Metrics**:
- `http_req_failed`: Percentage of failed requests
- `errors`: Custom error rate from test logic

**Custom Metrics**:
- `workflow_duration`: E2E workflow completion time
- `workflow_success`: E2E workflow success rate
- `posts_processed`: Number of posts successfully processed

### Thresholds

All tests include thresholds that must be met for the test to pass:

```javascript
thresholds: {
  http_req_duration: ['p(95)<300'],  // 95% under 300ms
  http_req_failed: ['rate<0.05'],    // Less than 5% failures
  workflow_duration: ['p(95)<300000'], // E2E under 5 minutes
}
```

### Result Analysis

**Successful Test**:
- All thresholds pass (green checkmarks)
- Error rate < 5%
- p95 response time < 300ms
- No timeout errors

**Failed Test**:
- One or more thresholds fail (red X marks)
- High error rate or response times
- Workflow timeouts in E2E tests

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Performance Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  performance-test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
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
    
    - name: Setup k6
      run: |
        sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
        echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
        sudo apt-get update
        sudo apt-get install k6
    
    - name: Start API
      run: |
        docker-compose up -d
        sleep 30  # Wait for services to be ready
    
    - name: Run Performance Tests
      run: |
        ./tests/k6/run-performance-tests.sh -t performance
    
    - name: Upload Results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: k6-results
        path: tests/k6/results/
```

### Pre-deployment Validation

```bash
#!/bin/bash
# pre-deploy-performance-check.sh

echo "Running pre-deployment performance validation..."

# Run quick performance test
./tests/k6/run-performance-tests.sh -t performance -u $STAGING_URL

if [ $? -eq 0 ]; then
    echo "✅ Performance tests passed - deployment can proceed"
    exit 0
else
    echo "❌ Performance tests failed - blocking deployment"
    exit 1
fi
```

## Troubleshooting

### Common Issues

**1. Connection Refused**
```
Error: Cannot connect to API at http://localhost:8000
```
- Ensure the API server is running
- Check if the port is correct
- Verify firewall settings

**2. High Error Rates**
```
✗ http_req_failed: rate>0.05
```
- Check API logs for errors
- Verify database connectivity
- Check if external services (Redis, PostgreSQL) are running

**3. Slow Response Times**
```
✗ http_req_duration: p(95)>300
```
- Check system resources (CPU, memory)
- Verify database performance
- Check for network latency issues

**4. E2E Workflow Timeouts**
```
✗ workflow_duration: p(95)>300000
```
- Check Celery worker status
- Verify queue processing
- Check external API dependencies (Reddit, OpenAI, Ghost)

### Debug Mode

Run tests with verbose output for debugging:

```bash
./tests/k6/run-performance-tests.sh -v -t performance
```

### Monitoring During Tests

Monitor system resources during tests:

```bash
# Terminal 1: Run performance test
./tests/k6/run-performance-tests.sh -t load

# Terminal 2: Monitor system resources
htop

# Terminal 3: Monitor API logs
docker-compose logs -f api

# Terminal 4: Monitor queue status
watch -n 5 'curl -s http://localhost:8000/api/v1/status/queues | jq'
```

## Extending Tests

### Adding New Endpoints

1. **Add to performance-test.js**:
   ```javascript
   function testNewEndpoint() {
     const response = http.get(`${BASE_URL}/api/v1/new-endpoint`);
     
     const success = check(response, {
       'new endpoint status is 200': (r) => r.status === 200,
       'new endpoint response time < 300ms': (r) => r.timings.duration < 300,
     });
     
     apiResponseTime.add(response.timings.duration);
     errorRate.add(!success);
   }
   ```

2. **Add to load-test.js**:
   ```javascript
   const ENDPOINTS = [
     // ... existing endpoints
     { path: '/api/v1/new-endpoint', weight: 10, method: 'GET' },
   ];
   ```

### Custom Metrics

Add custom metrics for specific business logic:

```javascript
import { Counter, Rate, Trend } from 'k6/metrics';

const customMetric = new Counter('custom_operations');
const customSuccessRate = new Rate('custom_success_rate');
const customDuration = new Trend('custom_operation_duration');

// In your test function
customMetric.add(1);
customSuccessRate.add(operationSucceeded);
customDuration.add(operationTime);
```

### Environment-Specific Configuration

Create environment-specific test configurations:

```javascript
// config/staging.js
export const stagingConfig = {
  stages: [
    { duration: '1m', target: 5 },  // Lower load for staging
    { duration: '2m', target: 5 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // More lenient for staging
    http_req_failed: ['rate<0.1'],
  },
};
```

## Best Practices

1. **Start Small**: Begin with low load and gradually increase
2. **Monitor Resources**: Watch CPU, memory, and network during tests
3. **Test Realistic Scenarios**: Use realistic data and user patterns
4. **Baseline First**: Establish performance baselines before optimization
5. **Test Early**: Include performance tests in CI/CD pipeline
6. **Document Results**: Keep records of performance test results over time
7. **Test Dependencies**: Include external service dependencies in tests
8. **Clean Up**: Ensure tests don't leave test data in the system