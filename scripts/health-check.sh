#!/bin/bash

# Health Check Script for Reddit Ghost Publisher MVP
# Performs comprehensive health checks on all system components

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
API_URL="http://localhost:8000"
TIMEOUT=10

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
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Usage function
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Perform health checks on Reddit Ghost Publisher system

OPTIONS:
    -v, --verbose       Verbose output
    -q, --quiet         Quiet mode (errors only)
    -j, --json          Output in JSON format
    -h, --help          Show this help message

EXAMPLES:
    $0                  # Run all health checks
    $0 --verbose        # Run with detailed output
    $0 --json           # Output results in JSON format

EOF
}

# Parse command line arguments
VERBOSE=false
QUIET=false
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        -j|--json)
            JSON_OUTPUT=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Health check results
HEALTH_RESULTS=()
OVERALL_STATUS="healthy"

# Add result to array
add_result() {
    local component="$1"
    local status="$2"
    local message="$3"
    local details="${4:-}"
    
    HEALTH_RESULTS+=("$component:$status:$message:$details")
    
    if [[ "$status" != "pass" ]]; then
        OVERALL_STATUS="unhealthy"
    fi
    
    if [[ "$JSON_OUTPUT" != "true" ]]; then
        case $status in
            pass)
                log_success "$component: $message"
                ;;
            warn)
                log_warning "$component: $message"
                ;;
            fail)
                log_error "$component: $message"
                ;;
        esac
        
        if [[ "$VERBOSE" == "true" && -n "$details" ]]; then
            echo "  Details: $details"
        fi
    fi
}

# Check Docker services
check_docker() {
    local component="Docker"
    
    if ! command -v docker &> /dev/null; then
        add_result "$component" "fail" "Docker not installed"
        return
    fi
    
    if ! docker info >/dev/null 2>&1; then
        add_result "$component" "fail" "Docker daemon not running"
        return
    fi
    
    add_result "$component" "pass" "Docker daemon running"
}

# Check Docker Compose services
check_compose_services() {
    local component="Docker Compose Services"
    
    if ! command -v docker-compose &> /dev/null; then
        add_result "$component" "fail" "docker-compose not installed"
        return
    fi
    
    cd "$PROJECT_ROOT"
    
    # Check if compose file exists
    local compose_file="docker-compose.yml"
    if [[ ! -f "$compose_file" ]]; then
        add_result "$component" "fail" "docker-compose.yml not found"
        return
    fi
    
    # Get service status
    local services_output
    services_output=$(docker-compose ps --services 2>/dev/null || echo "")
    
    if [[ -z "$services_output" ]]; then
        add_result "$component" "warn" "No services defined or running"
        return
    fi
    
    local total_services=0
    local running_services=0
    local failed_services=""
    
    while IFS= read -r service; do
        if [[ -n "$service" ]]; then
            total_services=$((total_services + 1))
            local status
            status=$(docker-compose ps -q "$service" 2>/dev/null | xargs -I {} docker inspect -f '{{.State.Status}}' {} 2>/dev/null || echo "not_found")
            
            if [[ "$status" == "running" ]]; then
                running_services=$((running_services + 1))
            else
                failed_services="$failed_services $service($status)"
            fi
        fi
    done <<< "$services_output"
    
    if [[ $running_services -eq $total_services ]]; then
        add_result "$component" "pass" "All $total_services services running"
    elif [[ $running_services -gt 0 ]]; then
        add_result "$component" "warn" "$running_services/$total_services services running" "Failed:$failed_services"
    else
        add_result "$component" "fail" "No services running" "Services:$failed_services"
    fi
}

# Check API health endpoint
check_api_health() {
    local component="API Health"
    local health_url="$API_URL/health"
    
    if ! command -v curl &> /dev/null; then
        add_result "$component" "warn" "curl not available for health check"
        return
    fi
    
    local response
    local http_code
    
    response=$(curl -s -w "%{http_code}" --max-time $TIMEOUT "$health_url" 2>/dev/null || echo "000")
    http_code="${response: -3}"
    response="${response%???}"
    
    case $http_code in
        200)
            add_result "$component" "pass" "API responding (HTTP $http_code)"
            ;;
        000)
            add_result "$component" "fail" "API not reachable" "URL: $health_url"
            ;;
        *)
            add_result "$component" "fail" "API unhealthy (HTTP $http_code)" "Response: $response"
            ;;
    esac
}

# Check database connectivity
check_database() {
    local component="Database"
    
    # Try to connect via Docker compose
    cd "$PROJECT_ROOT"
    
    if docker-compose exec -T postgres pg_isready >/dev/null 2>&1; then
        add_result "$component" "pass" "PostgreSQL responding"
    else
        add_result "$component" "fail" "PostgreSQL not responding"
    fi
}

# Check Redis connectivity
check_redis() {
    local component="Redis"
    
    cd "$PROJECT_ROOT"
    
    if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        add_result "$component" "pass" "Redis responding"
    else
        add_result "$component" "fail" "Redis not responding"
    fi
}

# Check disk space
check_disk_space() {
    local component="Disk Space"
    local threshold=90
    
    local usage
    usage=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [[ $usage -lt $threshold ]]; then
        add_result "$component" "pass" "Disk usage: ${usage}%"
    elif [[ $usage -lt 95 ]]; then
        add_result "$component" "warn" "Disk usage high: ${usage}%"
    else
        add_result "$component" "fail" "Disk usage critical: ${usage}%"
    fi
}

# Check log files
check_logs() {
    local component="Log Files"
    local log_dir="$PROJECT_ROOT/logs"
    
    if [[ ! -d "$log_dir" ]]; then
        add_result "$component" "warn" "Log directory not found"
        return
    fi
    
    local error_count=0
    local recent_errors=""
    
    # Check for recent errors in log files
    if command -v grep &> /dev/null; then
        recent_errors=$(find "$log_dir" -name "*.log" -mtime -1 -exec grep -l "ERROR\|CRITICAL" {} \; 2>/dev/null | wc -l)
        error_count=$recent_errors
    fi
    
    if [[ $error_count -eq 0 ]]; then
        add_result "$component" "pass" "No recent errors in logs"
    elif [[ $error_count -lt 10 ]]; then
        add_result "$component" "warn" "$error_count log files with recent errors"
    else
        add_result "$component" "fail" "$error_count log files with recent errors"
    fi
}

# Check environment configuration
check_environment() {
    local component="Environment"
    local env_file="$PROJECT_ROOT/.env"
    
    if [[ ! -f "$env_file" ]]; then
        add_result "$component" "fail" ".env file not found"
        return
    fi
    
    # Check for required environment variables
    local required_vars=("POSTGRES_PASSWORD" "REDDIT_CLIENT_ID" "OPENAI_API_KEY" "GHOST_ADMIN_KEY")
    local missing_vars=""
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$env_file" 2>/dev/null; then
            missing_vars="$missing_vars $var"
        fi
    done
    
    if [[ -z "$missing_vars" ]]; then
        add_result "$component" "pass" "Required environment variables present"
    else
        add_result "$component" "fail" "Missing environment variables" "Missing:$missing_vars"
    fi
}

# Output results in JSON format
output_json() {
    local json_results="["
    local first=true
    
    for result in "${HEALTH_RESULTS[@]}"; do
        IFS=':' read -r component status message details <<< "$result"
        
        if [[ "$first" != "true" ]]; then
            json_results="$json_results,"
        fi
        first=false
        
        json_results="$json_results{\"component\":\"$component\",\"status\":\"$status\",\"message\":\"$message\""
        
        if [[ -n "$details" ]]; then
            json_results="$json_results,\"details\":\"$details\""
        fi
        
        json_results="$json_results}"
    done
    
    json_results="$json_results]"
    
    echo "{\"overall_status\":\"$OVERALL_STATUS\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"checks\":$json_results}"
}

# Main function
main() {
    if [[ "$JSON_OUTPUT" != "true" && "$QUIET" != "true" ]]; then
        log_info "Starting Reddit Publisher health checks..."
        echo
    fi
    
    # Run all health checks
    check_docker
    check_compose_services
    check_api_health
    check_database
    check_redis
    check_disk_space
    check_logs
    check_environment
    
    # Output results
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        output_json
    else
        echo
        if [[ "$OVERALL_STATUS" == "healthy" ]]; then
            log_success "Overall system status: HEALTHY"
        else
            log_error "Overall system status: UNHEALTHY"
        fi
        
        if [[ "$QUIET" != "true" ]]; then
            echo
            echo "Health check completed at $(date)"
        fi
    fi
    
    # Exit with appropriate code
    if [[ "$OVERALL_STATUS" == "healthy" ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"