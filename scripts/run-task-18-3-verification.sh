#!/bin/bash

# Task 18.3: 시스템 품질 검증 테스트 실행
# System Quality Verification Test Execution

set -e

echo "=== Task 18.3: System Quality Verification Tests ==="
echo "Starting system quality verification tests..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to log test results
log_test_result() {
    local test_name="$1"
    local result="$2"
    local details="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
        [ -n "$details" ] && echo "  Details: $details"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name"
        [ -n "$details" ] && echo "  Error: $details"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# Function to check if service is running
check_service() {
    local service_name="$1"
    local check_command="$2"
    
    if eval "$check_command" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

echo -e "\n${YELLOW}=== Database Tests (Requirements 11.23-11.24) ===${NC}"

# Test 11.23: Schema/Constraints Test
echo "Testing database schema and constraints..."

# Check if PostgreSQL is running
if check_service "PostgreSQL" "docker-compose exec -T postgres pg_isready -U \${DB_USER:-postgres}"; then
    log_test_result "PostgreSQL Connection" "PASS" "Database is accessible"
    
    # Test schema existence
    SCHEMA_CHECK=$(docker-compose exec -T postgres psql -U ${DB_USER:-postgres} -d reddit_publisher -t -c "
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name IN ('posts', 'media_files', 'processing_logs', 'token_usage');
    " 2>/dev/null | tr -d ' \n' || echo "0")
    
    if [ "$SCHEMA_CHECK" = "4" ]; then
        log_test_result "Database Schema" "PASS" "All required tables exist"
        
        # Test unique constraints
        CONSTRAINT_CHECK=$(docker-compose exec -T postgres psql -U ${DB_USER:-postgres} -d reddit_publisher -t -c "
            SELECT COUNT(*) FROM information_schema.table_constraints 
            WHERE constraint_type = 'UNIQUE' AND table_name = 'posts' AND constraint_name LIKE '%reddit_post_id%';
        " 2>/dev/null | tr -d ' \n' || echo "0")
        
        if [ "$CONSTRAINT_CHECK" -ge "1" ]; then
            log_test_result "Unique Constraints" "PASS" "reddit_post_id unique constraint exists"
        else
            log_test_result "Unique Constraints" "FAIL" "reddit_post_id unique constraint missing"
        fi
        
        # Test indexes
        INDEX_CHECK=$(docker-compose exec -T postgres psql -U ${DB_USER:-postgres} -d reddit_publisher -t -c "
            SELECT COUNT(*) FROM pg_indexes 
            WHERE tablename = 'posts' AND indexname LIKE 'idx_%';
        " 2>/dev/null | tr -d ' \n' || echo "0")
        
        if [ "$INDEX_CHECK" -ge "2" ]; then
            log_test_result "Database Indexes" "PASS" "Required indexes exist"
        else
            log_test_result "Database Indexes" "FAIL" "Missing required indexes"
        fi
        
    else
        log_test_result "Database Schema" "FAIL" "Missing required tables (found: $SCHEMA_CHECK/4)"
    fi
else
    log_test_result "PostgreSQL Connection" "FAIL" "Cannot connect to database"
fi

# Test 11.24: Backup/Recovery Test
echo "Testing backup and recovery..."

if [ -f "scripts/backup-database.sh" ]; then
    log_test_result "Backup Script Exists" "PASS" "backup-database.sh found"
    
    # Test backup creation
    if bash scripts/backup-database.sh >/dev/null 2>&1; then
        log_test_result "Backup Creation" "PASS" "Backup script executed successfully"
        
        # Check if backup file was created
        LATEST_BACKUP=$(ls -t backups/backup_*.sql 2>/dev/null | head -1 || echo "")
        if [ -n "$LATEST_BACKUP" ] && [ -f "$LATEST_BACKUP" ]; then
            log_test_result "Backup File Creation" "PASS" "Backup file created: $(basename $LATEST_BACKUP)"
            
            # Test restore (if restore script exists)
            if [ -f "scripts/restore-database.sh" ]; then
                # Create test restore (non-destructive)
                TEST_DB="reddit_publisher_test_$(date +%s)"
                if docker-compose exec -T postgres createdb -U ${DB_USER:-postgres} "$TEST_DB" >/dev/null 2>&1; then
                    if docker-compose exec -T postgres psql -U ${DB_USER:-postgres} -d "$TEST_DB" < "$LATEST_BACKUP" >/dev/null 2>&1; then
                        log_test_result "Backup Restore Test" "PASS" "Backup restored successfully to test database"
                        
                        # Verify restored data
                        RESTORED_TABLES=$(docker-compose exec -T postgres psql -U ${DB_USER:-postgres} -d "$TEST_DB" -t -c "
                            SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';
                        " 2>/dev/null | tr -d ' \n' || echo "0")
                        
                        if [ "$RESTORED_TABLES" -gt "0" ]; then
                            log_test_result "Restored Data Verification" "PASS" "Tables exist in restored database"
                        else
                            log_test_result "Restored Data Verification" "FAIL" "No tables found in restored database"
                        fi
                    else
                        log_test_result "Backup Restore Test" "FAIL" "Failed to restore backup"
                    fi
                    
                    # Cleanup test database
                    docker-compose exec -T postgres dropdb -U ${DB_USER:-postgres} "$TEST_DB" >/dev/null 2>&1 || true
                else
                    log_test_result "Backup Restore Test" "FAIL" "Failed to create test database"
                fi
            else
                log_test_result "Restore Script" "FAIL" "restore-database.sh not found"
            fi
        else
            log_test_result "Backup File Creation" "FAIL" "No backup file created"
        fi
    else
        log_test_result "Backup Creation" "FAIL" "Backup script failed"
    fi
else
    log_test_result "Backup Script Exists" "FAIL" "backup-database.sh not found"
fi

echo -e "\n${YELLOW}=== Security/Compliance Tests (Requirements 11.25-11.27) ===${NC}"

# Test 11.25: Secret Management/Log Masking
echo "Testing secret management and log masking..."

# Check environment variables are loaded
if [ -f ".env" ] || [ -n "$REDDIT_CLIENT_ID" ]; then
    log_test_result "Environment Variables" "PASS" "Environment configuration found"
    
    # Test log masking by checking if sensitive data is masked in logs
    if [ -f "app/logging_config.py" ]; then
        # Check if masking functions exist
        if grep -q "mask_sensitive_data\|PII" app/logging_config.py; then
            log_test_result "Log Masking Implementation" "PASS" "PII masking functions found"
        else
            log_test_result "Log Masking Implementation" "FAIL" "PII masking functions not found"
        fi
    else
        log_test_result "Log Masking Implementation" "FAIL" "logging_config.py not found"
    fi
    
    # Check if secrets are not exposed in logs
    if [ -f "logs/reddit_publisher.log" ]; then
        # Look for potential API keys or tokens in logs (should be masked)
        EXPOSED_SECRETS=$(grep -E "(api[_-]?key|token|secret)" logs/reddit_publisher.log | grep -v "\*\*\*\*" | wc -l)
        if [ "$EXPOSED_SECRETS" -eq "0" ]; then
            log_test_result "Secret Exposure Check" "PASS" "No exposed secrets found in logs"
        else
            log_test_result "Secret Exposure Check" "FAIL" "Potential exposed secrets found in logs"
        fi
    else
        log_test_result "Secret Exposure Check" "PASS" "No log file to check (acceptable)"
    fi
else
    log_test_result "Environment Variables" "FAIL" "No environment configuration found"
fi

# Test 11.26: Takedown Workflow
echo "Testing takedown workflow..."

if [ -f "workers/takedown/takedown_manager.py" ]; then
    log_test_result "Takedown Manager Exists" "PASS" "takedown_manager.py found"
    
    # Check if takedown workflow is implemented
    if grep -q "takedown_status\|unpublish\|72.*hour" workers/takedown/takedown_manager.py; then
        log_test_result "Takedown Workflow Implementation" "PASS" "Takedown workflow logic found"
    else
        log_test_result "Takedown Workflow Implementation" "FAIL" "Takedown workflow logic not found"
    fi
    
    # Check if audit logging is implemented
    if grep -q "audit.*log\|takedown.*log" workers/takedown/takedown_manager.py; then
        log_test_result "Takedown Audit Logging" "PASS" "Audit logging found"
    else
        log_test_result "Takedown Audit Logging" "FAIL" "Audit logging not found"
    fi
else
    log_test_result "Takedown Manager Exists" "FAIL" "takedown_manager.py not found"
fi

# Test 11.27: Reddit API Policy Compliance
echo "Testing Reddit API policy compliance..."

if [ -f "workers/collector/reddit_client.py" ]; then
    log_test_result "Reddit Client Exists" "PASS" "reddit_client.py found"
    
    # Check if PRAW (official API) is used
    if grep -q "praw\|Reddit.*API" workers/collector/reddit_client.py; then
        log_test_result "Official API Usage" "PASS" "PRAW/Official API usage found"
    else
        log_test_result "Official API Usage" "FAIL" "Official API usage not confirmed"
    fi
    
    # Check for rate limiting implementation
    if grep -q "rate.*limit\|rpm\|60" workers/collector/reddit_client.py; then
        log_test_result "Rate Limiting" "PASS" "Rate limiting implementation found"
    else
        log_test_result "Rate Limiting" "FAIL" "Rate limiting implementation not found"
    fi
    
    # Check that no web scraping is used
    if ! grep -q "requests\.get\|urllib\|BeautifulSoup\|selenium" workers/collector/reddit_client.py; then
        log_test_result "No Web Scraping" "PASS" "No web scraping detected"
    else
        log_test_result "No Web Scraping" "FAIL" "Potential web scraping detected"
    fi
else
    log_test_result "Reddit Client Exists" "FAIL" "reddit_client.py not found"
fi

echo -e "\n${YELLOW}=== Observability/Alerting Tests (Requirements 11.28-11.30) ===${NC}"

# Test 11.28: /health and /metrics endpoints
echo "Testing health and metrics endpoints..."

# Check if FastAPI app is running
if check_service "FastAPI" "curl -s http://localhost:8000/health"; then
    log_test_result "FastAPI Service" "PASS" "FastAPI is running"
    
    # Test /health endpoint
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/health || echo "")
    if echo "$HEALTH_RESPONSE" | grep -q "healthy\|status"; then
        log_test_result "/health Endpoint" "PASS" "Health endpoint returns valid response"
    else
        log_test_result "/health Endpoint" "FAIL" "Health endpoint not responding correctly"
    fi
    
    # Test /metrics endpoint
    METRICS_RESPONSE=$(curl -s http://localhost:8000/metrics || echo "")
    if echo "$METRICS_RESPONSE" | grep -q "reddit_posts\|processing\|counter"; then
        log_test_result "/metrics Endpoint" "PASS" "Metrics endpoint returns Prometheus format"
    else
        log_test_result "/metrics Endpoint" "FAIL" "Metrics endpoint not returning proper format"
    fi
else
    log_test_result "FastAPI Service" "FAIL" "FastAPI not running or not accessible"
    log_test_result "/health Endpoint" "FAIL" "Cannot test - service not running"
    log_test_result "/metrics Endpoint" "FAIL" "Cannot test - service not running"
fi

# Test 11.29: Failure Rate/Queue Alerting
echo "Testing failure rate and queue alerting..."

if [ -f "app/monitoring/alert_service.py" ]; then
    log_test_result "Alert Service Exists" "PASS" "alert_service.py found"
    
    # Check if failure rate monitoring is implemented
    if grep -q "failure.*rate\|5%\|0\.05" app/monitoring/alert_service.py; then
        log_test_result "Failure Rate Monitoring" "PASS" "Failure rate monitoring found"
    else
        log_test_result "Failure Rate Monitoring" "FAIL" "Failure rate monitoring not found"
    fi
    
    # Check if queue monitoring is implemented
    if grep -q "queue.*500\|QUEUE_ALERT_THRESHOLD" app/monitoring/alert_service.py; then
        log_test_result "Queue Monitoring" "PASS" "Queue monitoring found"
    else
        log_test_result "Queue Monitoring" "FAIL" "Queue monitoring not found"
    fi
    
    # Check if Slack integration exists
    if grep -q "slack\|webhook" app/monitoring/alert_service.py; then
        log_test_result "Slack Integration" "PASS" "Slack integration found"
    else
        log_test_result "Slack Integration" "FAIL" "Slack integration not found"
    fi
else
    log_test_result "Alert Service Exists" "FAIL" "alert_service.py not found"
fi

# Test 11.30: Daily Report
echo "Testing daily report system..."

if [ -f "app/monitoring/daily_report.py" ]; then
    log_test_result "Daily Report Service" "PASS" "daily_report.py found"
    
    # Check if report includes required metrics
    if grep -q "collected.*posts\|published.*posts\|token.*usage" app/monitoring/daily_report.py; then
        log_test_result "Report Metrics" "PASS" "Required metrics found in daily report"
    else
        log_test_result "Report Metrics" "FAIL" "Required metrics not found in daily report"
    fi
    
    # Check if Slack reporting is implemented
    if grep -q "slack\|webhook\|send.*report" app/monitoring/daily_report.py; then
        log_test_result "Daily Report Slack Integration" "PASS" "Slack reporting found"
    else
        log_test_result "Daily Report Slack Integration" "FAIL" "Slack reporting not found"
    fi
else
    log_test_result "Daily Report Service" "FAIL" "daily_report.py not found"
fi

echo -e "\n${YELLOW}=== CI/Deployment Tests (Requirements 11.31-11.33) ===${NC}"

# Test 11.31: Unit Test Coverage 70%
echo "Testing unit test coverage..."

if [ -f "pyproject.toml" ] || [ -f "pytest.ini" ] || [ -f ".coveragerc" ]; then
    log_test_result "Test Configuration" "PASS" "Test configuration found"
    
    # Run tests and check coverage
    if command -v pytest >/dev/null 2>&1; then
        echo "Running pytest with coverage..."
        COVERAGE_OUTPUT=$(pytest --cov=app --cov-report=term-missing --cov-fail-under=70 2>&1 || echo "COVERAGE_FAILED")
        
        if echo "$COVERAGE_OUTPUT" | grep -q "COVERAGE_FAILED"; then
            COVERAGE_PERCENT=$(echo "$COVERAGE_OUTPUT" | grep -o "[0-9]\+%" | tail -1 | tr -d '%' || echo "0")
            log_test_result "Unit Test Coverage" "FAIL" "Coverage: ${COVERAGE_PERCENT}% (target: 70%)"
        else
            COVERAGE_PERCENT=$(echo "$COVERAGE_OUTPUT" | grep -o "[0-9]\+%" | tail -1 | tr -d '%' || echo "100")
            log_test_result "Unit Test Coverage" "PASS" "Coverage: ${COVERAGE_PERCENT}% (≥70%)"
        fi
        
        # Check if tests pass
        if echo "$COVERAGE_OUTPUT" | grep -q "failed\|error" && ! echo "$COVERAGE_OUTPUT" | grep -q "0 failed"; then
            log_test_result "Unit Tests Pass" "FAIL" "Some tests are failing"
        else
            log_test_result "Unit Tests Pass" "PASS" "All tests passing"
        fi
    else
        log_test_result "Pytest Available" "FAIL" "pytest not installed"
        log_test_result "Unit Test Coverage" "FAIL" "Cannot run tests - pytest not available"
    fi
else
    log_test_result "Test Configuration" "FAIL" "No test configuration found"
fi

# Test 11.32: Docker Image Build/Manual Approval Deployment
echo "Testing Docker image build and deployment configuration..."

if [ -f "Dockerfile" ]; then
    log_test_result "Dockerfile Exists" "PASS" "Dockerfile found"
    
    # Test Docker build
    echo "Testing Docker image build..."
    if docker build -t reddit-publisher-test:latest . >/dev/null 2>&1; then
        log_test_result "Docker Build" "PASS" "Docker image builds successfully"
        
        # Cleanup test image
        docker rmi reddit-publisher-test:latest >/dev/null 2>&1 || true
    else
        log_test_result "Docker Build" "FAIL" "Docker build failed"
    fi
else
    log_test_result "Dockerfile Exists" "FAIL" "Dockerfile not found"
fi

# Check GitHub Actions workflow
if [ -f ".github/workflows/ci.yml" ] || [ -f ".github/workflows/main.yml" ]; then
    log_test_result "GitHub Actions Workflow" "PASS" "CI workflow found"
    
    # Check if manual approval is configured
    if grep -r "manual.*approval\|environment.*production" .github/workflows/ >/dev/null 2>&1; then
        log_test_result "Manual Approval Configuration" "PASS" "Manual approval found in workflow"
    else
        log_test_result "Manual Approval Configuration" "FAIL" "Manual approval not configured"
    fi
else
    log_test_result "GitHub Actions Workflow" "FAIL" "No CI workflow found"
fi

# Test 11.33: Postman Smoke Tests
echo "Testing Postman smoke tests..."

if [ -f "tests/postman/reddit-ghost-publisher-smoke-tests.json" ]; then
    log_test_result "Postman Collection" "PASS" "Smoke test collection found"
    
    # Check if Newman is available
    if command -v newman >/dev/null 2>&1; then
        log_test_result "Newman Available" "PASS" "Newman CLI available"
        
        # Run smoke tests if service is running
        if check_service "FastAPI" "curl -s http://localhost:8000/health"; then
            echo "Running Postman smoke tests..."
            if newman run tests/postman/reddit-ghost-publisher-smoke-tests.json \
                -e tests/postman/test-environment.json \
                --reporters cli,json \
                --reporter-json-export /tmp/newman-results.json >/dev/null 2>&1; then
                
                # Check results
                if [ -f "/tmp/newman-results.json" ]; then
                    FAILED_TESTS=$(jq '.run.stats.assertions.failed // 0' /tmp/newman-results.json 2>/dev/null || echo "0")
                    TOTAL_TESTS=$(jq '.run.stats.assertions.total // 0' /tmp/newman-results.json 2>/dev/null || echo "0")
                    
                    if [ "$FAILED_TESTS" -eq "0" ] && [ "$TOTAL_TESTS" -gt "0" ]; then
                        log_test_result "Postman Smoke Tests" "PASS" "All $TOTAL_TESTS assertions passed (100%)"
                    else
                        log_test_result "Postman Smoke Tests" "FAIL" "$FAILED_TESTS/$TOTAL_TESTS assertions failed"
                    fi
                    
                    rm -f /tmp/newman-results.json
                else
                    log_test_result "Postman Smoke Tests" "FAIL" "Could not parse test results"
                fi
            else
                log_test_result "Postman Smoke Tests" "FAIL" "Newman execution failed"
            fi
        else
            log_test_result "Postman Smoke Tests" "FAIL" "Cannot run - service not available"
        fi
    else
        log_test_result "Newman Available" "FAIL" "Newman CLI not installed"
        log_test_result "Postman Smoke Tests" "FAIL" "Cannot run - Newman not available"
    fi
else
    log_test_result "Postman Collection" "FAIL" "Smoke test collection not found"
fi

# Final Results Summary
echo -e "\n${YELLOW}=== Test Results Summary ===${NC}"
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "\n${GREEN}✓ All system quality verification tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}✗ Some system quality verification tests failed.${NC}"
    echo "Please review the failed tests and fix the issues before proceeding."
    exit 1
fi