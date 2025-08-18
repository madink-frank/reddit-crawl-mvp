#!/bin/bash

# Task 18.4 Performance Test Runner
# Runs k6 performance tests for Requirements 11.34-11.36

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Default values
BASE_URL="${BASE_URL:-http://localhost:8000}"
K6_BINARY="${K6_BINARY:-k6}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-json}"
SAVE_RESULTS="${SAVE_RESULTS:-true}"

# Test configuration
P95_TARGET_MS="${P95_TARGET_MS:-300}"
ALERT_THRESHOLD_MS="${ALERT_THRESHOLD_MS:-400}"
ERROR_RATE_THRESHOLD="${ERROR_RATE_THRESHOLD:-0.05}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if k6 is installed
check_k6_installation() {
    if ! command -v "$K6_BINARY" &> /dev/null; then
        log_error "k6 is not installed or not in PATH"
        log_info "Please install k6 from https://k6.io/docs/getting-started/installation/"
        exit 1
    fi
    
    local k6_version
    k6_version=$($K6_BINARY version 2>/dev/null | head -n1 || echo "unknown")
    log_info "Using k6: $k6_version"
}

# Function to check API availability
check_api_availability() {
    log_info "Checking API availability at $BASE_URL"
    
    if curl -s -f "$BASE_URL/health" > /dev/null; then
        log_success "API is responding at $BASE_URL"
    else
        log_warning "API is not responding at $BASE_URL"
        log_warning "Tests may fail. Please ensure the API is running."
        
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to create results directory
setup_results_directory() {
    mkdir -p "$RESULTS_DIR"
    log_info "Results will be saved to: $RESULTS_DIR"
}

# Function to run k6 performance test
run_k6_performance_test() {
    local test_name="$1"
    local test_script="$2"
    local output_file="$3"
    
    log_info "Running $test_name..."
    log_info "Script: $test_script"
    log_info "Output: $output_file"
    
    # Set environment variables for k6
    export BASE_URL
    export P95_TARGET_MS
    export ALERT_THRESHOLD_MS
    export ERROR_RATE_THRESHOLD
    
    # Run k6 test
    local k6_cmd=(
        "$K6_BINARY" run
        --out "json=$output_file"
        "$test_script"
    )
    
    log_info "Executing: ${k6_cmd[*]}"
    
    if "${k6_cmd[@]}"; then
        log_success "$test_name completed successfully"
        return 0
    else
        log_error "$test_name failed"
        return 1
    fi
}

# Function to analyze k6 results
analyze_k6_results() {
    local results_file="$1"
    local test_name="$2"
    
    if [[ ! -f "$results_file" ]]; then
        log_error "Results file not found: $results_file"
        return 1
    fi
    
    log_info "Analyzing results for $test_name..."
    
    # Extract key metrics using jq if available
    if command -v jq &> /dev/null; then
        local p95_duration
        local error_rate
        local total_requests
        
        # Parse the k6 JSON output to extract metrics
        # Note: k6 JSON output format has metrics in the final summary
        p95_duration=$(tail -n 20 "$results_file" | jq -r 'select(.type=="Point" and .metric=="http_req_duration") | .data.value' | sort -n | tail -n 1 2>/dev/null || echo "0")
        error_rate=$(tail -n 20 "$results_file" | jq -r 'select(.type=="Point" and .metric=="http_req_failed") | .data.value' | tail -n 1 2>/dev/null || echo "0")
        total_requests=$(grep -c '"type":"Point"' "$results_file" 2>/dev/null || echo "0")
        
        # Simple analysis (more sophisticated analysis would be done in the k6 script itself)
        log_info "Performance Analysis for $test_name:"
        log_info "  Total Requests: $total_requests"
        log_info "  Last Response Time: ${p95_duration}ms"
        log_info "  Last Error Rate: $error_rate"
        
        # Check against thresholds
        if (( $(echo "$p95_duration <= $P95_TARGET_MS" | bc -l 2>/dev/null || echo "0") )); then
            log_success "  ✓ p95 target met (≤${P95_TARGET_MS}ms)"
        else
            log_warning "  ✗ p95 target not met (>${P95_TARGET_MS}ms)"
        fi
        
        if (( $(echo "$error_rate < $ERROR_RATE_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
            log_success "  ✓ Error rate target met (<${ERROR_RATE_THRESHOLD})"
        else
            log_warning "  ✗ Error rate target not met (>=${ERROR_RATE_THRESHOLD})"
        fi
    else
        log_warning "jq not available, skipping detailed analysis"
        log_info "Results saved to: $results_file"
    fi
}

# Function to generate summary report
generate_summary_report() {
    local summary_file="$RESULTS_DIR/task_18_4_performance_summary_$TIMESTAMP.md"
    
    log_info "Generating summary report: $summary_file"
    
    cat > "$summary_file" << EOF
# Task 18.4 Performance Test Results

**Test Execution:** $(date)
**Base URL:** $BASE_URL
**Requirements:** 11.34-11.36

## Test Configuration

- p95 Target: ≤ ${P95_TARGET_MS}ms
- Alert Threshold: < ${ALERT_THRESHOLD_MS}ms  
- Error Rate Threshold: < ${ERROR_RATE_THRESHOLD}

## Test Results

### Requirement 11.34: API p95 Performance
- **Target:** p95 response time ≤ 300ms
- **Alert Threshold:** p95 response time < 400ms
- **Status:** See detailed results in JSON files

### Requirement 11.35: E2E Processing Time  
- **Target:** Each post processes in ≤ 5 minutes
- **Note:** This test is handled by the Python test runner

### Requirement 11.36: Throughput Stability
- **Target:** 100 posts/hour with <5% failure rate
- **Note:** This test is handled by the Python test runner

## Files Generated

EOF

    # List all result files
    for file in "$RESULTS_DIR"/*_"$TIMESTAMP"*; do
        if [[ -f "$file" ]]; then
            echo "- $(basename "$file")" >> "$summary_file"
        fi
    done
    
    cat >> "$summary_file" << EOF

## Next Steps

1. Review detailed JSON results for specific metrics
2. Run the Python test runner for E2E and throughput tests:
   \`\`\`bash
   python tests/verification/run_task_18_4_tests.py
   \`\`\`
3. Analyze any performance issues identified
4. Verify all requirements are met before proceeding

EOF

    log_success "Summary report generated: $summary_file"
}

# Main execution function
main() {
    log_info "Starting Task 18.4 Performance Tests"
    log_info "Target: Requirements 11.34-11.36"
    
    # Pre-flight checks
    check_k6_installation
    check_api_availability
    setup_results_directory
    
    # Test files
    local performance_test_script="$SCRIPT_DIR/task-18-4-performance-test.js"
    local performance_results="$RESULTS_DIR/task_18_4_performance_$TIMESTAMP.json"
    
    # Check if test script exists
    if [[ ! -f "$performance_test_script" ]]; then
        log_error "Performance test script not found: $performance_test_script"
        exit 1
    fi
    
    # Run performance tests
    local test_success=true
    
    log_info "=== Running Requirement 11.34: API p95 Performance Test ==="
    if ! run_k6_performance_test "API p95 Performance" "$performance_test_script" "$performance_results"; then
        test_success=false
    fi
    
    # Analyze results
    if [[ "$test_success" == true ]]; then
        analyze_k6_results "$performance_results" "API p95 Performance"
    fi
    
    # Generate summary
    generate_summary_report
    
    # Final status
    if [[ "$test_success" == true ]]; then
        log_success "All k6 performance tests completed successfully"
        log_info "Next: Run the Python test runner for complete Task 18.4 validation"
        log_info "Command: python tests/verification/run_task_18_4_tests.py"
        exit 0
    else
        log_error "Some performance tests failed"
        log_info "Check the results in: $RESULTS_DIR"
        exit 1
    fi
}

# Help function
show_help() {
    cat << EOF
Task 18.4 Performance Test Runner

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -u, --url URL          Set base URL (default: http://localhost:8000)
    -k, --k6-binary PATH   Set k6 binary path (default: k6)
    -o, --output-dir DIR   Set output directory (default: ./results)
    --p95-target MS        Set p95 target in milliseconds (default: 300)
    --alert-threshold MS   Set alert threshold in milliseconds (default: 400)
    --error-threshold RATE Set error rate threshold (default: 0.05)

Environment Variables:
    BASE_URL               API base URL
    K6_BINARY             Path to k6 binary
    P95_TARGET_MS         p95 target in milliseconds
    ALERT_THRESHOLD_MS    Alert threshold in milliseconds
    ERROR_RATE_THRESHOLD  Error rate threshold

Examples:
    $0                                    # Run with defaults
    $0 -u http://staging.example.com:8000 # Run against staging
    $0 --p95-target 200                   # Set stricter p95 target

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -u|--url)
            BASE_URL="$2"
            shift 2
            ;;
        -k|--k6-binary)
            K6_BINARY="$2"
            shift 2
            ;;
        -o|--output-dir)
            RESULTS_DIR="$2"
            shift 2
            ;;
        --p95-target)
            P95_TARGET_MS="$2"
            shift 2
            ;;
        --alert-threshold)
            ALERT_THRESHOLD_MS="$2"
            shift 2
            ;;
        --error-threshold)
            ERROR_RATE_THRESHOLD="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main "$@"