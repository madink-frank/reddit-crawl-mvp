#!/bin/bash

# Pre-deployment Check Script
# Validates system readiness for production deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_docker() {
    log_info "Checking Docker installation..."
    if command -v docker >/dev/null 2>&1; then
        log_success "Docker is installed: $(docker --version)"
        if docker info >/dev/null 2>&1; then
            log_success "Docker daemon is running"
        else
            log_error "Docker daemon is not running"
            return 1
        fi
    else
        log_error "Docker is not installed"
        return 1
    fi
}

check_compose() {
    log_info "Checking Docker Compose..."
    if command -v docker-compose >/dev/null 2>&1; then
        log_success "Docker Compose is installed: $(docker-compose --version)"
    else
        log_error "Docker Compose is not installed"
        return 1
    fi
}

check_env_file() {
    log_info "Checking production environment file..."
    if [[ -f "$PROJECT_ROOT/.env.production" ]]; then
        log_success "Production environment file exists"
        
        # Check for placeholder values
        local placeholders=0
        while IFS= read -r line; do
            if [[ "$line" =~ your_|CHANGE_ME|example\.com ]]; then
                log_warning "Placeholder value found: $line"
                ((placeholders++))
            fi
        done < "$PROJECT_ROOT/.env.production"
        
        if [[ $placeholders -gt 0 ]]; then
            log_warning "$placeholders placeholder values need to be updated"
            return 1
        else
            log_success "No placeholder values found"
        fi
    else
        log_error "Production environment file not found"
        return 1
    fi
}

check_required_files() {
    log_info "Checking required files..."
    local required_files=(
        "Dockerfile"
        "docker-compose.prod.yml"
        "scripts/deploy.sh"
        "scripts/backup-database.sh"
        "requirements.txt"
    )
    
    for file in "${required_files[@]}"; do
        if [[ -f "$PROJECT_ROOT/$file" ]]; then
            log_success "$file exists"
        else
            log_error "$file is missing"
            return 1
        fi
    done
}

main() {
    log_info "Starting pre-deployment checks..."
    
    local checks_passed=0
    local total_checks=4
    
    check_docker && ((checks_passed++)) || true
    check_compose && ((checks_passed++)) || true
    check_env_file && ((checks_passed++)) || true
    check_required_files && ((checks_passed++)) || true
    
    echo
    if [[ $checks_passed -eq $total_checks ]]; then
        log_success "All pre-deployment checks passed! ($checks_passed/$total_checks)"
        log_info "Ready for deployment. Run: ./scripts/deploy.sh"
        exit 0
    else
        log_error "Some checks failed ($checks_passed/$total_checks passed)"
        log_info "Please fix the issues above before deploying"
        exit 1
    fi
}

main "$@"