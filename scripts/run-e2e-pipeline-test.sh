#!/bin/bash
"""
End-to-End Pipeline Test Runner Script
Runs comprehensive E2E pipeline integration test for task 20.1
"""

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_ENVIRONMENT="${TEST_ENVIRONMENT:-staging}"
VERBOSE="${VERBOSE:-false}"

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

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is not installed or not in PATH"
        exit 1
    fi
    
    # Check if required environment variables are set
    required_vars=(
        "REDDIT_CLIENT_ID"
        "REDDIT_CLIENT_SECRET"
        "OPENAI_API_KEY"
        "GHOST_ADMIN_KEY"
        "GHOST_API_URL"
        "DATABASE_URL"
        "REDIS_URL"
    )
    
    missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to start staging environment
start_staging_environment() {
    log_info "Starting staging environment..."
    
    cd "$PROJECT_ROOT"
    
    # Check if staging compose file exists
    if [[ ! -f "docker-compose.staging.yml" ]]; then
        log_warning "docker-compose.staging.yml not found, using docker-compose.yml"
        COMPOSE_FILE="docker-compose.yml"
    else
        COMPOSE_FILE="docker-compose.staging.yml"
    fi
    
    # Start services
    log_info "Starting Docker Compose services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Check if API is responding
    API_URL="${API_BASE_URL:-http://localhost:8000}"
    max_attempts=30
    attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
            log_success "API is ready at $API_URL"
            break
        fi
        
        log_info "Waiting for API to be ready... (attempt $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done
    
    if [[ $attempt -gt $max_attempts ]]; then
        log_error "API failed to start within expected time"
        log_info "Checking service logs..."
        docker-compose -f "$COMPOSE_FILE" logs --tail=50
        exit 1
    fi
}

# Function to run E2E pipeline test
run_e2e_test() {
    log_info "Running End-to-End Pipeline Integration Test..."
    
    cd "$PROJECT_ROOT"
    
    # Set up Python environment
    if [[ -f "venv/bin/activate" ]]; then
        log_info "Activating virtual environment..."
        source venv/bin/activate
    fi
    
    # Install test dependencies if needed
    if [[ -f "requirements-test.txt" ]]; then
        log_info "Installing test dependencies..."
        pip install -r requirements-test.txt
    fi
    
    # Run the E2E test
    test_args=("--environment" "$TEST_ENVIRONMENT")
    
    if [[ "$VERBOSE" == "true" ]]; then
        test_args+=("--verbose")
    fi
    
    log_info "Executing E2E pipeline test with arguments: ${test_args[*]}"
    
    # Run the test and capture output
    if python3 tests/verification/e2e_pipeline_test.py "${test_args[@]}"; then
        log_success "E2E Pipeline Test PASSED"
        return 0
    else
        log_error "E2E Pipeline Test FAILED"
        return 1
    fi
}

# Function to collect test artifacts
collect_test_artifacts() {
    log_info "Collecting test artifacts..."
    
    cd "$PROJECT_ROOT"
    
    # Create artifacts directory
    ARTIFACTS_DIR="tests/verification/artifacts/e2e_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$ARTIFACTS_DIR"
    
    # Collect logs
    if [[ -f "tests/verification/logs/e2e_pipeline_test.log" ]]; then
        cp "tests/verification/logs/e2e_pipeline_test.log" "$ARTIFACTS_DIR/"
    fi
    
    # Collect test reports
    if ls tests/verification/reports/e2e_pipeline_test_*.json 1> /dev/null 2>&1; then
        cp tests/verification/reports/e2e_pipeline_test_*.json "$ARTIFACTS_DIR/"
    fi
    
    # Collect Docker logs
    if command -v docker-compose &> /dev/null; then
        log_info "Collecting Docker service logs..."
        
        COMPOSE_FILE="docker-compose.staging.yml"
        if [[ ! -f "$COMPOSE_FILE" ]]; then
            COMPOSE_FILE="docker-compose.yml"
        fi
        
        # Get logs from all services
        services=("api" "worker-collector" "worker-nlp" "worker-publisher" "scheduler")
        
        for service in "${services[@]}"; do
            if docker-compose -f "$COMPOSE_FILE" ps -q "$service" > /dev/null 2>&1; then
                log_info "Collecting logs for service: $service"
                docker-compose -f "$COMPOSE_FILE" logs --tail=1000 "$service" > "$ARTIFACTS_DIR/${service}_logs.txt" 2>&1 || true
            fi
        done
    fi
    
    # Collect system metrics
    log_info "Collecting system metrics..."
    {
        echo "=== System Information ==="
        uname -a
        echo ""
        echo "=== Docker Version ==="
        docker --version
        echo ""
        echo "=== Docker Compose Version ==="
        docker-compose --version
        echo ""
        echo "=== Python Version ==="
        python3 --version
        echo ""
        echo "=== Disk Usage ==="
        df -h
        echo ""
        echo "=== Memory Usage ==="
        free -h
        echo ""
        echo "=== Running Containers ==="
        docker ps
    } > "$ARTIFACTS_DIR/system_info.txt"
    
    log_success "Test artifacts collected in: $ARTIFACTS_DIR"
}

# Function to cleanup staging environment
cleanup_staging_environment() {
    log_info "Cleaning up staging environment..."
    
    cd "$PROJECT_ROOT"
    
    COMPOSE_FILE="docker-compose.staging.yml"
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # Stop and remove containers
    docker-compose -f "$COMPOSE_FILE" down -v || true
    
    # Remove any test-specific volumes or networks if needed
    # docker volume prune -f || true
    
    log_success "Staging environment cleaned up"
}

# Function to generate test report
generate_test_report() {
    local test_result=$1
    
    log_info "Generating test report..."
    
    cd "$PROJECT_ROOT"
    
    # Find the latest test report
    latest_report=$(ls -t tests/verification/reports/e2e_pipeline_test_*.json 2>/dev/null | head -1)
    
    if [[ -n "$latest_report" && -f "$latest_report" ]]; then
        log_info "Latest test report: $latest_report"
        
        # Extract key metrics from the report
        if command -v jq &> /dev/null; then
            echo ""
            echo "=== E2E PIPELINE TEST SUMMARY ==="
            echo "Test Result: $(jq -r '.overall_success' "$latest_report")"
            echo "Duration: $(jq -r '.duration_seconds' "$latest_report") seconds"
            echo "Environment: $(jq -r '.environment' "$latest_report")"
            
            echo ""
            echo "Stage Results:"
            jq -r '.stages | to_entries[] | "  \(.key): \(.value.success)"' "$latest_report"
            
            if [[ "$(jq -r '.published_urls | length' "$latest_report")" -gt 0 ]]; then
                echo ""
                echo "Published Posts:"
                jq -r '.published_urls[]' "$latest_report" | sed 's/^/  - /'
            fi
            
            echo "==============================================="
        else
            log_warning "jq not available, cannot parse JSON report"
            echo "Raw report available at: $latest_report"
        fi
    else
        log_warning "No test report found"
    fi
}

# Main execution function
main() {
    local test_result=0
    
    echo "=============================================="
    echo "E2E PIPELINE INTEGRATION TEST RUNNER"
    echo "=============================================="
    echo "Environment: $TEST_ENVIRONMENT"
    echo "Verbose: $VERBOSE"
    echo "Project Root: $PROJECT_ROOT"
    echo "=============================================="
    
    # Trap to ensure cleanup happens
    trap 'cleanup_staging_environment' EXIT
    
    # Run test sequence
    check_prerequisites
    start_staging_environment
    
    if run_e2e_test; then
        test_result=0
        log_success "E2E Pipeline Test completed successfully"
    else
        test_result=1
        log_error "E2E Pipeline Test failed"
    fi
    
    # Always collect artifacts and generate report
    collect_test_artifacts
    generate_test_report $test_result
    
    return $test_result
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --environment)
                TEST_ENVIRONMENT="$2"
                shift 2
                ;;
            --verbose)
                VERBOSE="true"
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --environment ENV    Test environment (staging|production) [default: staging]"
                echo "  --verbose           Enable verbose logging"
                echo "  --help              Show this help message"
                echo ""
                echo "Environment Variables:"
                echo "  TEST_ENVIRONMENT    Test environment (overridden by --environment)"
                echo "  VERBOSE            Enable verbose logging (overridden by --verbose)"
                echo "  API_BASE_URL       Base URL for API [default: http://localhost:8000]"
                echo ""
                echo "Required Environment Variables:"
                echo "  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, OPENAI_API_KEY"
                echo "  GHOST_ADMIN_KEY, GHOST_API_URL, DATABASE_URL, REDIS_URL"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Run main function
    if main; then
        exit 0
    else
        exit 1
    fi
fi