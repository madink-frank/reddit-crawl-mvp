#!/bin/bash

# Run MVP System Verification Tests
# Wrapper script for easy test execution

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="staging"
SUITE="all"
VERBOSE=false
SETUP_ENV=false

# Usage function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Test environment (staging|production) [default: staging]"
    echo "  -s, --suite SUITE        Test suite to run (smoke|functional|performance|security|integration|all) [default: all]"
    echo "  -v, --verbose            Enable verbose logging"
    echo "  --setup                  Setup staging environment before running tests"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests in staging"
    echo "  $0 --setup                           # Setup environment and run all tests"
    echo "  $0 -s smoke -v                       # Run smoke tests with verbose output"
    echo "  $0 -e production -s functional       # Run functional tests in production"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--suite)
            SUITE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --setup)
            SETUP_ENV=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}Error: Environment must be 'staging' or 'production'${NC}"
    exit 1
fi

# Validate suite
valid_suites=("smoke" "functional" "performance" "security" "integration" "all")
if [[ ! " ${valid_suites[@]} " =~ " ${SUITE} " ]]; then
    echo -e "${RED}Error: Suite must be one of: ${valid_suites[*]}${NC}"
    exit 1
fi

# Check if running from project root
if [ ! -f "docker-compose.staging.yml" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

echo -e "${BLUE}=== MVP System Verification Tests ===${NC}"
echo "Environment: $ENVIRONMENT"
echo "Test Suite: $SUITE"
echo "Verbose: $VERBOSE"
echo ""

# Setup staging environment if requested
if [ "$SETUP_ENV" = true ]; then
    echo -e "${YELLOW}Setting up staging environment...${NC}"
    ./scripts/setup-staging-environment.sh
    echo ""
fi

# Check if staging environment is running (for staging tests)
if [ "$ENVIRONMENT" = "staging" ]; then
    echo -e "${BLUE}Checking staging environment...${NC}"
    
    # Check if Docker Compose services are running
    if ! docker-compose -f docker-compose.staging.yml ps | grep -q "Up"; then
        echo -e "${YELLOW}Staging environment not running. Starting it now...${NC}"
        docker-compose -f docker-compose.staging.yml up -d
        
        # Wait for services to be ready
        echo "Waiting for services to be ready..."
        sleep 30
        
        # Check health
        max_attempts=10
        attempt=0
        while [ $attempt -lt $max_attempts ]; do
            if curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
                echo -e "${GREEN}Staging environment is ready!${NC}"
                break
            fi
            attempt=$((attempt + 1))
            echo "Waiting for API to be ready... (attempt $attempt/$max_attempts)"
            sleep 10
        done
        
        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}Error: Staging environment failed to start properly${NC}"
            echo "Service status:"
            docker-compose -f docker-compose.staging.yml ps
            exit 1
        fi
    else
        echo -e "${GREEN}Staging environment is already running${NC}"
    fi
    echo ""
fi

# Prepare test command
TEST_CMD="python tests/verification/run_verification_tests.py --environment $ENVIRONMENT"

if [ "$SUITE" != "all" ]; then
    TEST_CMD="$TEST_CMD --suite $SUITE"
fi

if [ "$VERBOSE" = true ]; then
    TEST_CMD="$TEST_CMD --verbose"
fi

# Create logs directory if it doesn't exist
mkdir -p tests/verification/logs

# Run the tests
echo -e "${BLUE}Running verification tests...${NC}"
echo "Command: $TEST_CMD"
echo ""

# Execute tests and capture exit code
set +e
$TEST_CMD
TEST_EXIT_CODE=$?
set -e

# Display results
echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}=== VERIFICATION TESTS PASSED ===${NC}"
    echo -e "${GREEN}✅ All tests completed successfully${NC}"
    
    if [ "$ENVIRONMENT" = "staging" ]; then
        echo ""
        echo "Next steps:"
        echo "1. Review test reports in tests/verification/reports/"
        echo "2. Address any warnings or recommendations"
        echo "3. Run production verification if ready"
        echo "4. Proceed with production deployment"
    fi
else
    echo -e "${RED}=== VERIFICATION TESTS FAILED ===${NC}"
    echo -e "${RED}❌ Some tests failed (exit code: $TEST_EXIT_CODE)${NC}"
    
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Check test logs in tests/verification/logs/"
    echo "2. Review service logs:"
    echo "   docker-compose -f docker-compose.staging.yml logs [service-name]"
    echo "3. Verify environment configuration in .env.staging"
    echo "4. Test external service connectivity"
    echo "5. Check the troubleshooting section in tests/verification/README.md"
fi

echo ""
echo "Test reports available in: tests/verification/reports/"
echo "Test logs available in: tests/verification/logs/"

# Show recent test report if available
LATEST_REPORT=$(ls -t tests/verification/reports/verification_report_*.json 2>/dev/null | head -1)
if [ -n "$LATEST_REPORT" ]; then
    echo "Latest report: $LATEST_REPORT"
    
    # Extract summary from JSON report
    if command -v jq >/dev/null 2>&1; then
        echo ""
        echo -e "${BLUE}Test Summary:${NC}"
        jq -r '.overall_result | "Total Tests: \(.total_tests)\nPassed: \(.passed_tests)\nFailed: \(.failed_tests)\nPass Rate: \(.pass_rate * 100 | round)%"' "$LATEST_REPORT"
    fi
fi

echo ""
if [ "$ENVIRONMENT" = "staging" ]; then
    echo "To stop staging environment:"
    echo "  docker-compose -f docker-compose.staging.yml down"
fi

exit $TEST_EXIT_CODE