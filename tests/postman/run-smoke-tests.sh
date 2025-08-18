#!/bin/bash

# Reddit Ghost Publisher - Smoke Test Runner
# This script runs the Postman smoke tests using Newman

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="test"
OUTPUT_DIR="results"
VERBOSE=false

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment to test (test|staging) [default: test]"
    echo "  -o, --output DIR         Output directory for results [default: results]"
    echo "  -v, --verbose           Enable verbose output"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run tests with default settings"
    echo "  $0 -e staging           # Run tests against staging environment"
    echo "  $0 -v -o ./test-output  # Run with verbose output to custom directory"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
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

# Validate environment
if [[ "$ENVIRONMENT" != "test" && "$ENVIRONMENT" != "staging" ]]; then
    echo -e "${RED}Error: Environment must be 'test' or 'staging'${NC}"
    exit 1
fi

# Set environment file based on selection
if [[ "$ENVIRONMENT" == "staging" ]]; then
    ENV_FILE="staging-environment.json"
else
    ENV_FILE="test-environment.json"
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTION_FILE="$SCRIPT_DIR/reddit-ghost-publisher-smoke-tests.json"
ENVIRONMENT_FILE="$SCRIPT_DIR/$ENV_FILE"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if Newman is installed
if ! command -v newman &> /dev/null; then
    echo -e "${RED}Error: Newman is not installed${NC}"
    echo "Install Newman with: npm install -g newman"
    exit 1
fi

# Check if collection file exists
if [[ ! -f "$COLLECTION_FILE" ]]; then
    echo -e "${RED}Error: Collection file not found: $COLLECTION_FILE${NC}"
    exit 1
fi

# Check if environment file exists
if [[ ! -f "$ENVIRONMENT_FILE" ]]; then
    echo -e "${RED}Error: Environment file not found: $ENVIRONMENT_FILE${NC}"
    exit 1
fi

# Build Newman command
NEWMAN_CMD="newman run \"$COLLECTION_FILE\" -e \"$ENVIRONMENT_FILE\""

# Add reporters
NEWMAN_CMD="$NEWMAN_CMD --reporters cli,json,junit"
NEWMAN_CMD="$NEWMAN_CMD --reporter-json-export \"$OUTPUT_DIR/smoke-test-results.json\""
NEWMAN_CMD="$NEWMAN_CMD --reporter-junit-export \"$OUTPUT_DIR/smoke-test-results.xml\""

# Add verbose flag if requested
if [[ "$VERBOSE" == true ]]; then
    NEWMAN_CMD="$NEWMAN_CMD --verbose"
fi

# Display test information
echo -e "${YELLOW}Reddit Ghost Publisher - Smoke Test Runner${NC}"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "Collection: $(basename "$COLLECTION_FILE")"
echo "Environment File: $(basename "$ENVIRONMENT_FILE")"
echo "Output Directory: $OUTPUT_DIR"
echo "Verbose: $VERBOSE"
echo ""

# Run the tests
echo -e "${YELLOW}Starting smoke tests...${NC}"
echo ""

if eval "$NEWMAN_CMD"; then
    echo ""
    echo -e "${GREEN}✅ All smoke tests passed!${NC}"
    echo ""
    echo "Results saved to:"
    echo "  - JSON: $OUTPUT_DIR/smoke-test-results.json"
    echo "  - JUnit: $OUTPUT_DIR/smoke-test-results.xml"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Some smoke tests failed!${NC}"
    echo ""
    echo "Check the results in:"
    echo "  - JSON: $OUTPUT_DIR/smoke-test-results.json"
    echo "  - JUnit: $OUTPUT_DIR/smoke-test-results.xml"
    exit 1
fi