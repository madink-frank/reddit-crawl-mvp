#!/bin/bash
"""
Task 18.2 Verification Test Execution Script
Executes functional verification tests for Reddit Ghost Publisher MVP
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}TASK 18.2 FUNCTIONAL VERIFICATION TESTS${NC}"
echo -e "${BLUE}Reddit Ghost Publisher MVP System${NC}"
echo -e "${BLUE}============================================================${NC}"

# Check if staging environment is running
echo -e "\n${YELLOW}Checking staging environment...${NC}"
if ! docker-compose -f docker-compose.staging.yml ps | grep -q "Up"; then
    echo -e "${RED}Error: Staging environment is not running${NC}"
    echo -e "${YELLOW}Please start the staging environment first:${NC}"
    echo "  docker-compose -f docker-compose.staging.yml up -d"
    exit 1
fi

echo -e "${GREEN}✓ Staging environment is running${NC}"

# Check required environment variables
echo -e "\n${YELLOW}Checking environment variables...${NC}"
required_vars=("REDDIT_CLIENT_ID" "REDDIT_CLIENT_SECRET" "OPENAI_API_KEY" "GHOST_ADMIN_KEY" "GHOST_API_URL" "SLACK_WEBHOOK_URL")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        missing_vars+=("$var")
    fi
done

if [[ ${#missing_vars[@]} -gt 0 ]]; then
    echo -e "${RED}Error: Missing required environment variables:${NC}"
    for var in "${missing_vars[@]}"; do
        echo -e "${RED}  - $var${NC}"
    done
    echo -e "${YELLOW}Please set these variables in your .env.staging file${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All required environment variables are set${NC}"

# Create logs directory
mkdir -p tests/verification/logs
mkdir -p tests/verification/reports

# Function to run test suite
run_test_suite() {
    local suite_name=$1
    local suite_description=$2
    
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$suite_description${NC}"
    echo -e "${BLUE}============================================================${NC}"
    
    if python3 tests/verification/run_functional_tests.py \
        --environment staging \
        --suite "$suite_name" \
        --verbose \
        --output "tests/verification/reports/task_18_2_${suite_name}_results.json"; then
        echo -e "${GREEN}✓ $suite_description - PASSED${NC}"
        return 0
    else
        echo -e "${RED}✗ $suite_description - FAILED${NC}"
        return 1
    fi
}

# Track overall results
overall_result=0

# Run individual test suites
echo -e "\n${YELLOW}Starting functional verification tests...${NC}"

# Reddit Collection Tests (Requirements 11.5-11.9)
if ! run_test_suite "reddit" "REDDIT COLLECTION TESTS (Requirements 11.5-11.9)"; then
    overall_result=1
fi

# AI Processing Tests (Requirements 11.10-11.14)
if ! run_test_suite "ai" "AI PROCESSING TESTS (Requirements 11.10-11.14)"; then
    overall_result=1
fi

# Ghost Publishing Tests (Requirements 11.15-11.20)
if ! run_test_suite "ghost" "GHOST PUBLISHING TESTS (Requirements 11.15-11.20)"; then
    overall_result=1
fi

# Architecture/Queue Tests (Requirements 11.21-11.22)
if ! run_test_suite "architecture" "ARCHITECTURE/QUEUE TESTS (Requirements 11.21-11.22)"; then
    overall_result=1
fi

# Run comprehensive test suite
echo -e "\n${BLUE}============================================================${NC}"
echo -e "${BLUE}COMPREHENSIVE FUNCTIONAL VERIFICATION${NC}"
echo -e "${BLUE}============================================================${NC}"

if python3 tests/verification/run_functional_tests.py \
    --environment staging \
    --suite all \
    --verbose \
    --output "tests/verification/reports/task_18_2_comprehensive_results.json"; then
    echo -e "${GREEN}✓ Comprehensive functional verification - PASSED${NC}"
else
    echo -e "${RED}✗ Comprehensive functional verification - FAILED${NC}"
    overall_result=1
fi

# Generate final report
echo -e "\n${BLUE}============================================================${NC}"
echo -e "${BLUE}TASK 18.2 COMPLETION REPORT${NC}"
echo -e "${BLUE}============================================================${NC}"

if [[ $overall_result -eq 0 ]]; then
    echo -e "${GREEN}🎉 TASK 18.2 COMPLETED SUCCESSFULLY${NC}"
    echo -e "${GREEN}All functional verification tests have passed.${NC}"
    echo -e "${GREEN}Requirements 11.5-11.22 have been verified.${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Review test reports in tests/verification/reports/"
    echo "  2. Proceed to Task 18.3 (System Quality Verification)"
    echo "  3. Update task status to 'completed' in tasks.md"
else
    echo -e "${RED}❌ TASK 18.2 INCOMPLETE${NC}"
    echo -e "${RED}Some functional verification tests have failed.${NC}"
    echo ""
    echo -e "${YELLOW}Required Actions:${NC}"
    echo "  1. Review failed test details in logs/"
    echo "  2. Fix identified issues in the system"
    echo "  3. Re-run verification tests"
    echo "  4. Ensure all tests pass before proceeding"
fi

# Show test artifacts
echo -e "\n${YELLOW}Test Artifacts:${NC}"
echo "  Logs: tests/verification/logs/"
echo "  Reports: tests/verification/reports/"
echo "  Screenshots: tests/verification/screenshots/"

# Show system status
echo -e "\n${YELLOW}System Status:${NC}"
docker-compose -f docker-compose.staging.yml ps

echo -e "\n${BLUE}============================================================${NC}"

exit $overall_result