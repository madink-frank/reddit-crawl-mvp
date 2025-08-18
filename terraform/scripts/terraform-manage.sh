#!/bin/bash

# Terraform management script for Reddit Ghost Publisher
# Provides easy commands for managing infrastructure

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENTS_DIR="$TERRAFORM_DIR/environments"

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
Usage: $0 <environment> <command> [options]

Environments:
  dev         Development environment
  prod        Production environment

Commands:
  init        Initialize Terraform
  plan        Show execution plan
  apply       Apply changes
  destroy     Destroy infrastructure
  output      Show outputs
  state       Manage Terraform state
  validate    Validate configuration
  fmt         Format Terraform files
  import      Import existing resources
  refresh     Refresh state
  show        Show current state

Options:
  --auto-approve    Auto approve apply/destroy
  --target=resource Target specific resource
  --var-file=file   Use specific variables file
  --verbose, -v     Verbose output

Examples:
  $0 dev init                    # Initialize development environment
  $0 prod plan                   # Plan production changes
  $0 dev apply --auto-approve    # Apply development changes
  $0 prod destroy                # Destroy production infrastructure
  $0 dev output                  # Show development outputs

EOF
}

# Check prerequisites
check_prerequisites() {
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed"
        print_status "Install from: https://www.terraform.io/downloads.html"
        exit 1
    fi
    
    local tf_version=$(terraform version -json | jq -r '.terraform_version')
    print_status "Using Terraform version: $tf_version"
}

# Validate environment
validate_environment() {
    local env="$1"
    
    if [[ ! "$env" =~ ^(dev|prod)$ ]]; then
        print_error "Invalid environment: $env"
        print_status "Valid environments: dev, prod"
        exit 1
    fi
    
    if [[ ! -f "$ENVIRONMENTS_DIR/$env/terraform.tfvars" ]]; then
        print_error "Environment configuration not found: $ENVIRONMENTS_DIR/$env/terraform.tfvars"
        exit 1
    fi
}

# Set up environment
setup_environment() {
    local env="$1"
    
    export TF_VAR_environment="$env"
    export TF_DATA_DIR="$TERRAFORM_DIR/.terraform-$env"
    
    # Load environment-specific variables
    if [[ -f "$ENVIRONMENTS_DIR/$env/.env" ]]; then
        source "$ENVIRONMENTS_DIR/$env/.env"
    fi
    
    print_status "Environment set to: $env"
    print_status "Terraform data directory: $TF_DATA_DIR"
}

# Initialize Terraform
terraform_init() {
    local env="$1"
    
    print_header "Initializing Terraform for $env"
    
    cd "$TERRAFORM_DIR"
    
    # Initialize with backend configuration
    terraform init \
        -backend-config="key=reddit-publisher/$env/terraform.tfstate" \
        -reconfigure
    
    print_status "Terraform initialized successfully"
}

# Plan changes
terraform_plan() {
    local env="$1"
    shift
    local args=("$@")
    
    print_header "Planning Terraform changes for $env"
    
    cd "$TERRAFORM_DIR"
    
    terraform plan \
        -var-file="$ENVIRONMENTS_DIR/$env/terraform.tfvars" \
        -out="$env.tfplan" \
        "${args[@]}"
    
    print_status "Plan saved to: $env.tfplan"
}

# Apply changes
terraform_apply() {
    local env="$1"
    shift
    local args=("$@")
    
    print_header "Applying Terraform changes for $env"
    
    cd "$TERRAFORM_DIR"
    
    # Check if plan file exists
    if [[ -f "$env.tfplan" ]]; then
        print_status "Applying saved plan: $env.tfplan"
        terraform apply "$env.tfplan"
        rm "$env.tfplan"
    else
        print_status "No saved plan found, creating new plan"
        terraform apply \
            -var-file="$ENVIRONMENTS_DIR/$env/terraform.tfvars" \
            "${args[@]}"
    fi
    
    print_status "Apply completed successfully"
}

# Destroy infrastructure
terraform_destroy() {
    local env="$1"
    shift
    local args=("$@")
    
    print_header "Destroying Terraform infrastructure for $env"
    
    if [[ "$env" == "prod" ]]; then
        print_warning "You are about to destroy PRODUCTION infrastructure!"
        read -p "Type 'yes' to confirm: " confirm
        if [[ "$confirm" != "yes" ]]; then
            print_status "Destroy cancelled"
            exit 0
        fi
    fi
    
    cd "$TERRAFORM_DIR"
    
    terraform destroy \
        -var-file="$ENVIRONMENTS_DIR/$env/terraform.tfvars" \
        "${args[@]}"
    
    print_status "Destroy completed successfully"
}

# Show outputs
terraform_output() {
    local env="$1"
    shift
    local args=("$@")
    
    print_header "Terraform outputs for $env"
    
    cd "$TERRAFORM_DIR"
    
    terraform output "${args[@]}"
}

# Manage state
terraform_state() {
    local env="$1"
    shift
    local args=("$@")
    
    print_header "Managing Terraform state for $env"
    
    cd "$TERRAFORM_DIR"
    
    terraform state "${args[@]}"
}

# Validate configuration
terraform_validate() {
    local env="$1"
    
    print_header "Validating Terraform configuration for $env"
    
    cd "$TERRAFORM_DIR"
    
    terraform validate
    
    print_status "Configuration is valid"
}

# Format files
terraform_fmt() {
    print_header "Formatting Terraform files"
    
    cd "$TERRAFORM_DIR"
    
    terraform fmt -recursive
    
    print_status "Files formatted successfully"
}

# Import resource
terraform_import() {
    local env="$1"
    local resource="$2"
    local id="$3"
    
    if [[ -z "$resource" ]] || [[ -z "$id" ]]; then
        print_error "Usage: import <env> <resource> <id>"
        exit 1
    fi
    
    print_header "Importing resource for $env"
    
    cd "$TERRAFORM_DIR"
    
    terraform import \
        -var-file="$ENVIRONMENTS_DIR/$env/terraform.tfvars" \
        "$resource" "$id"
    
    print_status "Resource imported successfully"
}

# Refresh state
terraform_refresh() {
    local env="$1"
    
    print_header "Refreshing Terraform state for $env"
    
    cd "$TERRAFORM_DIR"
    
    terraform refresh \
        -var-file="$ENVIRONMENTS_DIR/$env/terraform.tfvars"
    
    print_status "State refreshed successfully"
}

# Show state
terraform_show() {
    local env="$1"
    
    print_header "Showing Terraform state for $env"
    
    cd "$TERRAFORM_DIR"
    
    terraform show
}

# Generate deployment summary
generate_summary() {
    local env="$1"
    
    print_header "Deployment Summary for $env"
    
    cd "$TERRAFORM_DIR"
    
    echo "Environment: $env"
    echo "Region: $(terraform output -raw region 2>/dev/null || echo 'N/A')"
    echo "Load Balancer IP: $(terraform output -raw load_balancer_ip 2>/dev/null || echo 'N/A')"
    echo "Domain: $(terraform output -raw domain_name 2>/dev/null || echo 'N/A')"
    echo "App Servers: $(terraform output -json app_droplet_ips 2>/dev/null | jq -r 'length' || echo 'N/A')"
    echo "Database Host: $(terraform output -raw postgres_host 2>/dev/null | sed 's/.*/[REDACTED]/' || echo 'N/A')"
    echo "Redis Host: $(terraform output -raw redis_host 2>/dev/null | sed 's/.*/[REDACTED]/' || echo 'N/A')"
    
    if [[ -f "$env.tfplan" ]]; then
        echo "Pending Plan: $env.tfplan"
    fi
}

# Main command handler
main() {
    check_prerequisites
    
    if [[ $# -lt 2 ]]; then
        usage
        exit 1
    fi
    
    local env="$1"
    local command="$2"
    shift 2
    
    validate_environment "$env"
    setup_environment "$env"
    
    case "$command" in
        "init")
            terraform_init "$env"
            ;;
        "plan")
            terraform_plan "$env" "$@"
            ;;
        "apply")
            terraform_apply "$env" "$@"
            ;;
        "destroy")
            terraform_destroy "$env" "$@"
            ;;
        "output")
            terraform_output "$env" "$@"
            ;;
        "state")
            terraform_state "$env" "$@"
            ;;
        "validate")
            terraform_validate "$env"
            ;;
        "fmt")
            terraform_fmt
            ;;
        "import")
            terraform_import "$env" "$@"
            ;;
        "refresh")
            terraform_refresh "$env"
            ;;
        "show")
            terraform_show "$env"
            ;;
        "summary")
            generate_summary "$env"
            ;;
        "--help"|"-h"|"help")
            usage
            ;;
        *)
            print_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"