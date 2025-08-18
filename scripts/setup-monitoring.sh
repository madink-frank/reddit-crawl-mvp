#!/bin/bash

# Setup monitoring and alerting for Reddit Publisher
# This script configures Grafana, Prometheus, and Alertmanager

set -e

echo "🚀 Setting up Reddit Publisher monitoring and alerting..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if required environment variables are set
check_env_vars() {
    echo "📋 Checking environment variables..."
    
    local required_vars=(
        "SLACK_WEBHOOK_URL"
        "GRAFANA_PASSWORD"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        echo -e "${RED}❌ Missing required environment variables:${NC}"
        for var in "${missing_vars[@]}"; do
            echo -e "${RED}  - $var${NC}"
        done
        echo ""
        echo "Please set these variables in your .env file or environment"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All required environment variables are set${NC}"
}

# Create necessary directories
create_directories() {
    echo "📁 Creating monitoring directories..."
    
    local dirs=(
        "docker/grafana/dashboards"
        "docker/grafana/provisioning/dashboards"
        "docker/grafana/provisioning/datasources"
        "docker/grafana/provisioning/alerting"
        "docker/prometheus/rules"
        "docker/alertmanager"
        "logs/grafana"
        "logs/prometheus"
        "logs/alertmanager"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
        echo "  Created: $dir"
    done
    
    echo -e "${GREEN}✅ Directories created${NC}"
}

# Set proper permissions
set_permissions() {
    echo "🔐 Setting proper permissions..."
    
    # Grafana needs specific permissions
    if [[ -d "docker/grafana" ]]; then
        chmod -R 755 docker/grafana/
        echo "  Set permissions for Grafana"
    fi
    
    # Prometheus rules directory
    if [[ -d "docker/prometheus/rules" ]]; then
        chmod -R 644 docker/prometheus/rules/*.yml 2>/dev/null || true
        echo "  Set permissions for Prometheus rules"
    fi
    
    # Make scripts executable
    chmod +x scripts/test-slack-webhook.py 2>/dev/null || true
    chmod +x scripts/setup-monitoring.sh 2>/dev/null || true
    
    echo -e "${GREEN}✅ Permissions set${NC}"
}

# Validate configuration files
validate_configs() {
    echo "🔍 Validating configuration files..."
    
    # Check if Prometheus config is valid
    if command -v promtool >/dev/null 2>&1; then
        if promtool check config docker/prometheus.yml >/dev/null 2>&1; then
            echo -e "${GREEN}  ✅ Prometheus config is valid${NC}"
        else
            echo -e "${YELLOW}  ⚠️  Prometheus config validation failed (promtool not available or config invalid)${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠️  promtool not available, skipping Prometheus config validation${NC}"
    fi
    
    # Check if Alertmanager config is valid
    if command -v amtool >/dev/null 2>&1; then
        if amtool check-config docker/alertmanager/alertmanager.yml >/dev/null 2>&1; then
            echo -e "${GREEN}  ✅ Alertmanager config is valid${NC}"
        else
            echo -e "${YELLOW}  ⚠️  Alertmanager config validation failed${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠️  amtool not available, skipping Alertmanager config validation${NC}"
    fi
    
    # Check if dashboard JSON files are valid
    local dashboard_files=(
        "docker/grafana/dashboards/system-overview.json"
        "docker/grafana/dashboards/application-metrics.json"
        "docker/grafana/dashboards/queue-monitoring.json"
        "docker/grafana/dashboards/business-metrics.json"
    )
    
    for file in "${dashboard_files[@]}"; do
        if [[ -f "$file" ]]; then
            if python3 -m json.tool "$file" >/dev/null 2>&1; then
                echo -e "${GREEN}  ✅ $(basename "$file") is valid JSON${NC}"
            else
                echo -e "${RED}  ❌ $(basename "$file") is invalid JSON${NC}"
                exit 1
            fi
        fi
    done
}

# Test Slack webhook
test_slack_webhook() {
    echo "🧪 Testing Slack webhook..."
    
    if python3 scripts/test-slack-webhook.py; then
        echo -e "${GREEN}✅ Slack webhook test passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Slack webhook test failed - please check your SLACK_WEBHOOK_URL${NC}"
    fi
}

# Start monitoring services
start_services() {
    echo "🚀 Starting monitoring services..."
    
    # Start monitoring stack
    docker-compose up -d prometheus grafana alertmanager
    
    echo "⏳ Waiting for services to start..."
    sleep 30
    
    # Check if services are running
    local services=("prometheus" "grafana" "alertmanager")
    
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            echo -e "${GREEN}  ✅ $service is running${NC}"
        else
            echo -e "${RED}  ❌ $service failed to start${NC}"
            docker-compose logs "$service"
            exit 1
        fi
    done
}

# Display access information
show_access_info() {
    echo ""
    echo "🎉 Monitoring setup complete!"
    echo ""
    echo "📊 Access URLs:"
    echo "  Grafana:      http://localhost:3000 (admin / ${GRAFANA_PASSWORD})"
    echo "  Prometheus:   http://localhost:9090"
    echo "  Alertmanager: http://localhost:9093"
    echo "  Flower:       http://localhost:5555"
    echo ""
    echo "📋 Available Dashboards:"
    echo "  - System Overview"
    echo "  - Application Metrics"
    echo "  - Queue Monitoring"
    echo "  - Business Metrics"
    echo ""
    echo "🔔 Alert Channels:"
    echo "  - #alerts-critical (Critical alerts)"
    echo "  - #alerts-warning (Warning alerts)"
    echo "  - #reddit-publisher-alerts (Service-specific alerts)"
    echo ""
    echo "💡 Next steps:"
    echo "  1. Configure your Slack channels"
    echo "  2. Review and adjust alert thresholds in docker/prometheus/rules/"
    echo "  3. Customize dashboards in Grafana"
    echo "  4. Test alerts with: docker-compose exec prometheus promtool query instant 'up'"
}

# Main execution
main() {
    echo "🔧 Reddit Publisher Monitoring Setup"
    echo "===================================="
    
    check_env_vars
    create_directories
    set_permissions
    validate_configs
    test_slack_webhook
    start_services
    show_access_info
    
    echo -e "${GREEN}✅ Setup completed successfully!${NC}"
}

# Run main function
main "$@"