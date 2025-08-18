# Reddit Ghost Publisher - Postman Smoke Tests

This directory contains Postman smoke tests for the Reddit Ghost Publisher API. These tests cover the main workflow of collect→process→publish and validate that all critical endpoints are functioning correctly.

## Files

- `reddit-ghost-publisher-smoke-tests.json` - Main Postman collection with all smoke tests
- `test-environment.json` - Local development environment variables
- `staging-environment.json` - Staging environment variables
- `README.md` - This documentation file

## Test Coverage

The smoke tests cover the following endpoints and scenarios:

### Core Functionality
1. **Health Check** (`GET /health`) - Validates system health and dependencies
2. **Metrics** (`GET /metrics`) - Validates Prometheus metrics endpoint
3. **Queue Status** (`GET /api/v1/status/queues`) - Validates queue monitoring
4. **Worker Status** (`GET /api/v1/status/workers`) - Validates worker monitoring

### Main Workflow
5. **Trigger Collection** (`POST /api/v1/collect/trigger`) - Triggers Reddit post collection
6. **Trigger Collection - Duplicate Test** - Tests idempotent behavior
7. **Trigger Processing** (`POST /api/v1/process/trigger`) - Triggers AI processing
8. **Trigger Publishing** (`POST /api/v1/publish/trigger`) - Triggers Ghost publishing
9. **Trigger Publishing - Duplicate Prevention** - Tests duplicate publication prevention

### Compliance & Error Handling
10. **Takedown Request - Valid** (`POST /api/v1/takedown/{id}`) - Tests takedown workflow
11. **Takedown Request - Invalid Email** - Tests validation error handling
12. **Invalid Endpoint - 404 Test** - Tests 404 error handling
13. **Invalid Method - 405 Test** - Tests method not allowed handling

## Environment Variables

### Required Variables
- `base_url` - Base URL of the API (e.g., `http://localhost:8000`)
- `test_subreddit` - Subreddit to use for testing (e.g., `technology`)
- `test_batch_size` - Number of posts to collect in tests (e.g., `5`)
- `test_reddit_post_id` - Test post ID for processing/publishing tests

### Optional Variables
- `api_timeout` - Request timeout in milliseconds (default: `5000`)

## Running Tests

### Using Postman GUI

1. **Import Collection**:
   - Open Postman
   - Click "Import" → "Upload Files"
   - Select `reddit-ghost-publisher-smoke-tests.json`

2. **Import Environment**:
   - Click "Import" → "Upload Files"
   - Select `test-environment.json` (for local) or `staging-environment.json` (for staging)

3. **Select Environment**:
   - In the top-right corner, select the imported environment

4. **Run Collection**:
   - Right-click the collection → "Run collection"
   - Configure run settings and click "Run Reddit Ghost Publisher - Smoke Tests"

### Using Newman (Command Line)

1. **Install Newman**:
   ```bash
   npm install -g newman
   ```

2. **Run Tests Locally**:
   ```bash
   newman run tests/postman/reddit-ghost-publisher-smoke-tests.json \
     -e tests/postman/test-environment.json \
     --reporters cli,json \
     --reporter-json-export results/smoke-test-results.json
   ```

3. **Run Tests on Staging**:
   ```bash
   newman run tests/postman/reddit-ghost-publisher-smoke-tests.json \
     -e tests/postman/staging-environment.json \
     --reporters cli,json \
     --reporter-json-export results/staging-smoke-test-results.json
   ```

### Using Newman in CI/CD

Add to your GitHub Actions workflow:

```yaml
- name: Run Postman Smoke Tests
  run: |
    npm install -g newman
    newman run tests/postman/reddit-ghost-publisher-smoke-tests.json \
      -e tests/postman/test-environment.json \
      --reporters cli,junit \
      --reporter-junit-export test-results.xml
```

## Test Expectations

### Success Criteria
- **100% Pass Rate**: All tests must pass for the smoke test suite to be considered successful
- **Response Times**: All endpoints should respond within acceptable time limits:
  - Health check: < 1000ms
  - Metrics: < 2000ms
  - Status endpoints: < 1000ms
  - Trigger endpoints: < 2000ms
  - Takedown endpoints: < 3000ms

### Test Validations
Each test validates:
- **HTTP Status Codes**: Correct status codes for success and error scenarios
- **Response Structure**: Required fields are present in responses
- **Response Times**: Endpoints respond within acceptable time limits
- **Content Types**: Correct content types (JSON for most, text/plain for metrics)
- **Business Logic**: Workflow-specific validations (e.g., task IDs, duplicate prevention)

## Troubleshooting

### Common Issues

1. **Connection Refused**:
   - Ensure the API server is running
   - Check the `base_url` in your environment

2. **404 Errors**:
   - Verify API routes are correctly implemented
   - Check if the API version matches the test expectations

3. **Timeout Errors**:
   - Increase the `api_timeout` value
   - Check if external dependencies (Redis, PostgreSQL, etc.) are running

4. **Validation Errors**:
   - Ensure test data in environment variables is valid
   - Check if required environment variables are set

### Debug Mode

To run tests with detailed output:

```bash
newman run tests/postman/reddit-ghost-publisher-smoke-tests.json \
  -e tests/postman/test-environment.json \
  --verbose \
  --reporters cli,json \
  --reporter-json-export results/debug-results.json
```

## Integration with Development Workflow

### Pre-commit Hooks
Add smoke tests to pre-commit hooks to catch issues early:

```bash
#!/bin/bash
# Run smoke tests before commit
newman run tests/postman/reddit-ghost-publisher-smoke-tests.json \
  -e tests/postman/test-environment.json \
  --reporters cli
```

### Deployment Validation
Run smoke tests after deployment to validate the system:

```bash
# After deployment, run smoke tests
newman run tests/postman/reddit-ghost-publisher-smoke-tests.json \
  -e tests/postman/staging-environment.json \
  --reporters cli,json \
  --reporter-json-export results/post-deployment-validation.json
```

## Extending Tests

To add new smoke tests:

1. **Add New Request**: Create a new request in the Postman collection
2. **Add Test Scripts**: Include appropriate test validations
3. **Update Environment**: Add any new required variables
4. **Update Documentation**: Document the new test in this README

### Test Script Template

```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has required field", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('field_name');
});

pm.test("Response time is acceptable", function () {
    pm.expect(pm.response.responseTime).to.be.below(2000);
});
```

## Maintenance

- **Regular Updates**: Update tests when API changes
- **Environment Sync**: Keep environment files in sync with actual deployments
- **Performance Monitoring**: Monitor test execution times and adjust thresholds as needed
- **Coverage Review**: Regularly review test coverage and add tests for new endpoints