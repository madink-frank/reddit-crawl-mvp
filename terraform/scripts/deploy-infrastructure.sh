#!/bin/bash

# Complete infrastructure deployment script for Reddit Ghost Publisher
# Automates the entire deployment process

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage
usage() {
    cat << EOF
Usage: $0 <environment> [options]

Environments:
  dev         Deploy development environment
  prod        Deploy production environment

Options:
  --skip-terraform    Skip Terraform deployment
  --skip-docker       Skip Docker image building
  --skip-deploy       Skip application deployment
  --auto-approve      Auto approve all changes
  --destroy           Destroy infrastructure instead of deploy
  --verbose, -v       Verbose output

Examples:
  $0 dev                      # Full development deployment
  $0 prod --auto-approve      # Production deployment with auto-approve
  $0 dev --destroy            # Destroy development environment
  $0 prod --skip-terraform    # Deploy only application to existing infrastructure

EOF
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    local missing_tools=()
    
    if ! command -v terraform &> /dev/null; then
        missing_tools+=("terraform")
    fi
    
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        missing_tools+=("docker-compose")
    fi
    
    if ! command -v jq &> /dev/null; then
        missing_tools+=("jq")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    print_status "All prerequisites satisfied"
}

# Load environment configuration
load_environment() {
    local env="$1"
    
    print_header "Loading Environment Configuration"
    
    if [[ ! -f "$TERRAFORM_DIR/environments/$env/terraform.tfvars" ]]; then
        print_error "Environment configuration not found: $env"
        exit 1
    fi
    
    # Extract domain name from tfvars
    DOMAIN_NAME=$(grep '^domain_name' "$TERRAFORM_DIR/environments/$env/terraform.tfvars" | cut -d'"' -f2)
    
    if [[ -z "$DOMAIN_NAME" ]]; then
        print_error "Domain name not found in environment configuration"
        exit 1
    fi
    
    print_status "Environment: $env"
    print_status "Domain: $DOMAIN_NAME"
}

# Validate environment variables
validate_env_vars() {
    print_header "Validating Environment Variables"
    
    local required_vars=(
        "DIGITALOCEAN_TOKEN"
        "CLOUDFLARE_API_TOKEN"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Missing required environment variables: ${missing_vars[*]}"
        print_status "Please set these variables before running the deployment"
        exit 1
    fi
    
    print_status "All required environment variables are set"
}

# Build Docker images
build_docker_images() {
    print_header "Building Docker Images"
    
    cd "$PROJECT_ROOT"
    
    # Build all service images
    print_status "Building service images..."
    ./scripts/build-containers.sh latest
    
    # Run security scan
    print_status "Running security scan..."
    ./scripts/security-scan.sh
    
    print_status "Docker images built and scanned successfully"
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    local env="$1"
    local auto_approve="$2"
    
    print_header "Deploying Infrastructure with Terraform"
    
    cd "$TERRAFORM_DIR"
    
    # Initialize Terraform
    print_status "Initializing Terraform..."
    ./scripts/terraform-manage.sh "$env" init
    
    # Validate configuration
    print_status "Validating configuration..."
    ./scripts/terraform-manage.sh "$env" validate
    
    # Plan deployment
    print_status "Planning deployment..."
    ./scripts/terraform-manage.sh "$env" plan
    
    # Apply changes
    local apply_args=()
    if [[ "$auto_approve" == "true" ]]; then
        apply_args+=("--auto-approve")
    fi
    
    print_status "Applying infrastructure changes..."
    ./scripts/terraform-manage.sh "$env" apply "${apply_args[@]}"
    
    print_status "Infrastructure deployed successfully"
}

# Get infrastructure outputs
get_infrastructure_outputs() {
    local env="$1"
    
    print_header "Retrieving Infrastructure Information"
    
    cd "$TERRAFORM_DIR"
    
    # Get outputs
    LOAD_BALANCER_IP=$(./scripts/terraform-manage.sh "$env" output -raw load_balancer_ip)
    DATABASE_URL=$(./scripts/terraform-manage.sh "$env" output -raw database_url)
    REDIS_URL=$(./scripts/terraform-manage.sh "$env" output -raw redis_url)
    
    print_status "Load Balancer IP: $LOAD_BALANCER_IP"
    print_status "Database and Redis connections retrieved"
}

# Deploy application
deploy_application() {
    local env="$1"
    
    print_header "Deploying Application"
    
    # Get server IPs
    local server_ips=($(cd "$TERRAFORM_DIR" && ./scripts/terraform-manage.sh "$env" output -json app_droplet_ips | jq -r '.[]'))
    
    for ip in "${server_ips[@]}"; do
        print_status "Deploying to server: $ip"
        
        # Copy application files
        rsync -avz --exclude='.git' --exclude='venv' --exclude='__pycache__' \
            "$PROJECT_ROOT/" "reddit-publisher@$ip:/opt/reddit-publisher/"
        
        # Create production environment file
        ssh "reddit-publisher@$ip" "cat > /opt/reddit-publisher/.env.production << EOF
ENVIRONMENT=production
DATABASE_URL=$DATABASE_URL
REDIS_URL=$REDIS_URL
CELERY_BROKER_URL=$REDIS_URL
CELERY_RESULT_BACKEND=$REDIS_URL
DOMAIN_NAME=$DOMAIN_NAME
EOF"
        
        # Deploy application
        ssh "reddit-publisher@$ip" "cd /opt/reddit-publisher && ./scripts/docker-manage.sh prod -d"
        
        # Wait for health check
        print_status "Waiting for application to start..."
        sleep 30
        
        # Health check
        if curl -f "http://$ip/health" > /dev/null 2>&1; then
            print_status "Application deployed successfully on $ip"
        else
            print_error "Health check failed on $ip"
            exit 1
        fi
    done
    
    print_status "Application deployed to all servers"
}

# Configure monitoring
setup_monitoring() {
    local env="$1"
    
    print_header "Setting Up Monitoring"
    
    cd "$TERRAFORM_DIR"
    
    # Get monitoring server IP
    local monitoring_ip=$(./scripts/terraform-manage.sh "$env" output -raw monitoring_server_ip)
    
    if [[ "$monitoring_ip" != "null" ]] && [[ -n "$monitoring_ip" ]]; then
        print_status "Configuring monitoring server: $monitoring_ip"
        
        # The monitoring server is configured via cloud-init
        # Just verify it's working
        sleep 60  # Wait for cloud-init to complete
        
        if curl -f "http://$monitoring_ip:3000" > /dev/null 2>&1; then
            print_status "Monitoring server is accessible"
            print_status "Grafana: http://monitoring.$DOMAIN_NAME"
            print_status "Prometheus: http://monitoring.$DOMAIN_NAME/prometheus"
        else
            print_warning "Monitoring server may still be initializing"
        fi
    else
        print_status "No monitoring server configured"
    fi
}

# Run post-deployment tests
run_tests() {
    local env="$1"
    
    print_header "Running Post-Deployment Tests"
    
    # Test main domain
    if curl -f "https://$DOMAIN_NAME/health" > /dev/null 2>&1; then
        print_status "Main domain health check passed"
    else
        print_error "Main domain health check failed"
        exit 1
    fi
    
    # Test API domain
    if curl -f "https://api.$DOMAIN_NAME/health" > /dev/null 2>&1; then
        print_status "API domain health check passed"
    else
        print_error "API domain health check failed"
        exit 1
    fi
    
    # Test SSL certificate
    local ssl_grade=$(curl -s "https://api.ssllabs.com/api/v3/analyze?host=$DOMAIN_NAME&publish=off&all=done" | jq -r '.endpoints[0].grade // "Unknown"')
    print_status "SSL Grade: $ssl_grade"
    
    print_status "All post-deployment tests passed"
}

# Destroy infrastructure
destroy_infrastructure() {
    local env="$1"
    local auto_approve="$2"
    
    print_header "Destroying Infrastructure"
    
    if [[ "$env" == "prod" ]]; then
        print_warning "You are about to destroy PRODUCTION infrastructure!"
        if [[ "$auto_approve" != "true" ]]; then
            read -p "Type 'destroy-production' to confirm: " confirm
            if [[ "$confirm" != "destroy-production" ]]; then
                print_status "Destroy cancelled"
                exit 0
            fi
        fi
    fi
    
    cd "$TERRAFORM_DIR"
    
    local destroy_args=()
    if [[ "$auto_approve" == "true" ]]; then
        destroy_args+=("--auto-approve")
    fi
    
    ./scripts/terraform-manage.sh "$env" destroy "${destroy_args[@]}"
    
    print_status "Infrastructure destroyed successfully"
}

# Generate deployment report
generate_report() {
    local env="$1"
    
    print_header "Generating Deployment Report"
    
    local report_file="deployment-report-$env-$(date +%Y%m%d-%H%M%S).md"
    
    cat > "$report_file" << EOF
# Deployment Report

**Environment:** $env
**Date:** $(date)
**Domain:** $DOMAIN_NAME

## Infrastructure

- **Load Balancer IP:** $LOAD_BALANCER_IP
- **Application Servers:** $(cd "$TERRAFORM_DIR" && ./scripts/terraform-manage.sh "$env" output -json app_droplet_ips | jq -r 'length')
- **Database:** PostgreSQL (managed)
- **Cache:** Redis (managed)
- **SSL Certificate:** Let's Encrypt
- **CDN:** CloudFlare

## Endpoints

- **Main Site:** https://$DOMAIN_NAME
- **API:** https://api.$DOMAIN_NAME
- **Health Check:** https://$DOMAIN_NAME/health
- **Metrics:** https://api.$DOMAIN_NAME/metrics

## Monitoring

- **Grafana:** http://monitoring.$DOMAIN_NAME
- **Prometheus:** http://monitoring.$DOMAIN_NAME/prometheus
- **Alertmanager:** http://monitoring.$DOMAIN_NAME/alertmanager

## Next Steps

1. Configure DNS records if not using CloudFlare
2. Set up monitoring alerts
3. Configure backup schedules
4. Review security settings
5. Set up CI/CD pipeline

## Support

For issues, check:
1. Application logs: \`docker-compose logs -f\`
2. Infrastructure status: \`terraform output\`
3. Health endpoints
4. Monitoring dashboards

EOF

    print_status "Deployment report generated: $report_file"
}

# Main deployment function
main() {
    local env=""
    local skip_terraform=false
    local skip_docker=false
    local skip_deploy=false
    local auto_approve=false
    local destroy=false
    local verbose=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            dev|prod)
                env="$1"
                shift
                ;;
            --skip-terraform)
                skip_terraform=true
                shift
                ;;
            --skip-docker)
                skip_docker=true
                shift
                ;;
            --skip-deploy)
                skip_deploy=true
                shift
                ;;
            --auto-approve)
                auto_approve=true
                shift
                ;;
            --destroy)
                destroy=true
                shift
                ;;
            --verbose|-v)
                verbose=true
                set -x
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    if [[ -z "$env" ]]; then
        print_error "Environment is required"
        usage
        exit 1
    fi
    
    # Start deployment
    print_header "Reddit Ghost Publisher Deployment"
    print_status "Environment: $env"
    print_status "Timestamp: $(date)"
    
    check_prerequisites
    load_environment "$env"
    validate_env_vars
    
    if [[ "$destroy" == "true" ]]; then
        destroy_infrastructure "$env" "$auto_approve"
        exit 0
    fi
    
    # Build phase
    if [[ "$skip_docker" != "true" ]]; then
        build_docker_images
    fi
    
    # Infrastructure phase
    if [[ "$skip_terraform" != "true" ]]; then
        deploy_infrastructure "$env" "$auto_approve"
        get_infrastructure_outputs "$env"
    fi
    
    # Application phase
    if [[ "$skip_deploy" != "true" ]]; then
        deploy_application "$env"
        setup_monitoring "$env"
        run_tests "$env"
    fi
    
    # Generate report
    generate_report "$env"
    
    print_header "Deployment Completed Successfully! 🎉"
    print_status "Your Reddit Ghost Publisher is now running at: https://$DOMAIN_NAME"
    print_status "API endpoint: https://api.$DOMAIN_NAME"
    print_status "Monitoring: http://monitoring.$DOMAIN_NAME"
}

# Run main function
main "$@"