#!/bin/bash

# Reddit Ghost Publisher - Performance Test Runner
# This script runs k6 performance tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="performance"
BASE_URL="http://localhost:8000"
OUTPUT_DIR="results"
VERBOSE=false

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --test-type TYPE     Type of test to run (performance|load|e2e) [default: performance]"
    echo "  -u, --url URL            Base URL for the API [default: http://localhost:8000]"
    echo "  -o, --output DIR         Output directory for results [default: results]"
    echo "  -v, --verbose           Enable verbose output"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Test Types:"
    echo "  performance             Basic performance test with gradual load increase"
    echo "  load                    High-load test with up to 100 concurrent users"
    echo "  e2e                     End-to-end workflow test"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run basic performance test"
    echo "  $0 -t load                           # Run load test"
    echo "  $0 -t e2e -u http://staging.api.com # Run E2E test against staging"
    echo "  $0 -v -o ./perf-results              # Run with verbose output"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--test-type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -u|--url)
            BASE_URL="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Validate test type
if [[ "$TEST_TYPE" != "performance" && "$TEST_TYPE" != "load" && "$TEST_TYPE" != "e2e" ]]; then
    echo -e "${RED}Error: Test type must be 'performance', 'load', or 'e2e'${NC}"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set test file based on type
case $TEST_TYPE in
    "performance")
        TEST_FILE="$SCRIPT_DIR/performance-test.js"
        TEST_DESCRIPTION="Performance Test (gradual load increase)"
        ;;
    "load")
        TEST_FILE="$SCRIPT_DIR/load-test.js"
        TEST_DESCRIPTION="Load Test (up to 100 concurrent users)"
        ;;
    "e2e")
        TEST_FILE="$SCRIPT_DIR/e2e-workflow-test.js"
        TEST_DESCRIPTION="End-to-End Workflow Test"
        ;;
esac

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if k6 is installed
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}Error: k6 is not installed${NC}"
    echo "Install k6 from: https://k6.io/docs/getting-started/installation/"
    exit 1
fi

# Check if test file exists
if [[ ! -f "$TEST_FILE" ]]; then
    echo -e "${RED}Error: Test file not found: $TEST_FILE${NC}"
    exit 1
fi

# Test API connectivity
echo -e "${YELLOW}Testing API connectivity...${NC}"
if ! curl -s -f "$BASE_URL/health" > /dev/null; then
    echo -e "${RED}Error: Cannot connect to API at $BASE_URL${NC}"
    echo "Please ensure the API is running and accessible"
    exit 1
fi
echo -e "${GREEN}✅ API is accessible${NC}"

# Display test information
echo ""
echo -e "${BLUE}Reddit Ghost Publisher - Performance Test Runner${NC}"
echo "=================================================="
echo "Test Type: $TEST_DESCRIPTION"
echo "Test File: $(basename "$TEST_FILE")"
echo "Base URL: $BASE_URL"
echo "Output Directory: $OUTPUT_DIR"
echo "Verbose: $VERBOSE"
echo ""

# Build k6 command
K6_CMD="k6 run"

# Add environment variables
K6_CMD="$K6_CMD --env BASE_URL=$BASE_URL"

# Add output options
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
K6_CMD="$K6_CMD --out json=$OUTPUT_DIR/k6-results-$TIMESTAMP.json"
K6_CMD="$K6_CMD --out csv=$OUTPUT_DIR/k6-results-$TIMESTAMP.csv"

# Add summary export
K6_CMD="$K6_CMD --summary-export=$OUTPUT_DIR/k6-summary-$TIMESTAMP.json"

# Add verbose flag if requested
if [[ "$VERBOSE" == true ]]; then
    K6_CMD="$K6_CMD --verbose"
fi

# Add test file
K6_CMD="$K6_CMD \"$TEST_FILE\""

# Display expected test duration based on test type
case $TEST_TYPE in
    "performance")
        echo -e "${YELLOW}Expected duration: ~16 minutes${NC}"
        echo "Test stages: 2m ramp-up → 5m steady → 2m ramp-up → 5m steady → 2m ramp-down"
        ;;
    "load")
        echo -e "${YELLOW}Expected duration: ~16 minutes${NC}"
        echo "Test stages: 1m → 3m → 5m → 5m steady at 100 users → 2m ramp-down"
        ;;
    "e2e")
        echo -e "${YELLOW}Expected duration: ~11 minutes${NC}"
        echo "Test scenarios: Steady load (10m) + Spike test (1m)"
        ;;
esac

echo ""
echo -e "${YELLOW}Performance targets:${NC}"
echo "- p95 response time: < 300ms"
echo "- Error rate: < 5%"
echo "- E2E workflow: < 5 minutes"
echo ""

# Confirm before starting long-running test
if [[ "$TEST_TYPE" == "load" ]]; then
    echo -e "${YELLOW}⚠️  This is a high-load test that will generate significant traffic.${NC}"
    echo -e "${YELLOW}   Make sure your system can handle 100 concurrent users.${NC}"
    echo ""
    read -p "Continue with load test? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Load test cancelled"
        exit 0
    fi
fi

# Run the test
echo -e "${YELLOW}Starting $TEST_DESCRIPTION...${NC}"
echo ""

if eval "$K6_CMD"; then
    echo ""
    echo -e "${GREEN}✅ Performance test completed successfully!${NC}"
    echo ""
    echo "Results saved to:"
    echo "  - JSON: $OUTPUT_DIR/k6-results-$TIMESTAMP.json"
    echo "  - CSV: $OUTPUT_DIR/k6-results-$TIMESTAMP.csv"
    echo "  - Summary: $OUTPUT_DIR/k6-summary-$TIMESTAMP.json"
    echo ""
    
    # Display quick summary if summary file exists
    SUMMARY_FILE="$OUTPUT_DIR/k6-summary-$TIMESTAMP.json"
    if [[ -f "$SUMMARY_FILE" ]]; then
        echo -e "${BLUE}Quick Summary:${NC}"
        if command -v jq &> /dev/null; then
            echo "HTTP Requests: $(jq -r '.metrics.http_reqs.count // "N/A"' "$SUMMARY_FILE")"
            echo "Average Response Time: $(jq -r '.metrics.http_req_duration.avg // "N/A"' "$SUMMARY_FILE")ms"
            echo "95th Percentile: $(jq -r '.metrics.http_req_duration["p(95)"] // "N/A"' "$SUMMARY_FILE")ms"
            echo "Error Rate: $(jq -r '.metrics.http_req_failed.rate // "N/A"' "$SUMMARY_FILE")"
        else
            echo "Install 'jq' to see detailed summary"
        fi
    fi
    
    exit 0
else
    echo ""
    echo -e "${RED}❌ Performance test failed!${NC}"
    echo ""
    echo "Check the results in:"
    echo "  - JSON: $OUTPUT_DIR/k6-results-$TIMESTAMP.json"
    echo "  - CSV: $OUTPUT_DIR/k6-results-$TIMESTAMP.csv"
    echo "  - Summary: $OUTPUT_DIR/k6-summary-$TIMESTAMP.json"
    exit 1
fi