#!/bin/bash

# Security scan script using Trivy for Docker images
# Requirement: High+ vulnerabilities cause CI failure

set -e

IMAGE_NAME=${1:-"reddit-publisher:latest"}
SEVERITY_THRESHOLD="HIGH,CRITICAL"
EXIT_CODE=0

echo "🔍 Starting security scan for image: $IMAGE_NAME"
echo "📊 Scanning for vulnerabilities with severity: $SEVERITY_THRESHOLD"

# Check if Trivy is installed
if ! command -v trivy &> /dev/null; then
    echo "❌ Trivy is not installed. Installing..."
    
    # Install Trivy based on OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux installation
        sudo apt-get update
        sudo apt-get install wget apt-transport-https gnupg lsb-release
        wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
        echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
        sudo apt-get update
        sudo apt-get install trivy
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS installation
        if command -v brew &> /dev/null; then
            brew install aquasecurity/trivy/trivy
        else
            echo "❌ Homebrew not found. Please install Trivy manually."
            exit 1
        fi
    else
        echo "❌ Unsupported OS. Please install Trivy manually."
        exit 1
    fi
fi

# Update Trivy database
echo "📥 Updating Trivy vulnerability database..."
trivy image --download-db-only

# Create results directory
mkdir -p security-reports

# Run Trivy scan with JSON output for detailed analysis
echo "🔍 Running comprehensive security scan..."
trivy image \
    --format json \
    --output security-reports/trivy-report-$(date +%Y%m%d-%H%M%S).json \
    --severity $SEVERITY_THRESHOLD \
    $IMAGE_NAME

# Run Trivy scan with table output for human-readable results
echo "📋 Generating human-readable report..."
trivy image \
    --format table \
    --output security-reports/trivy-summary-$(date +%Y%m%d-%H%M%S).txt \
    --severity $SEVERITY_THRESHOLD \
    $IMAGE_NAME

# Check for HIGH and CRITICAL vulnerabilities
echo "🔍 Checking for HIGH and CRITICAL vulnerabilities..."
HIGH_CRITICAL_COUNT=$(trivy image --format json --severity $SEVERITY_THRESHOLD $IMAGE_NAME | jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH" or .Severity == "CRITICAL")] | length')

if [ "$HIGH_CRITICAL_COUNT" -gt 0 ]; then
    echo "❌ Found $HIGH_CRITICAL_COUNT HIGH or CRITICAL vulnerabilities!"
    echo "📊 Vulnerability breakdown:"
    
    # Show detailed breakdown
    trivy image --format table --severity $SEVERITY_THRESHOLD $IMAGE_NAME
    
    echo ""
    echo "🚨 Security scan FAILED - HIGH or CRITICAL vulnerabilities detected"
    echo "📋 Detailed reports saved in security-reports/ directory"
    echo "🔧 Please fix these vulnerabilities before proceeding with deployment"
    
    EXIT_CODE=1
else
    echo "✅ No HIGH or CRITICAL vulnerabilities found!"
    echo "🎉 Security scan PASSED"
fi

# Additional checks for best practices
echo ""
echo "🔍 Running additional security checks..."

# Check if running as root
ROOT_CHECK=$(trivy image --format json $IMAGE_NAME | jq -r '.Results[]?.Misconfigurations[]? | select(.ID == "DS002") | .Status' 2>/dev/null || echo "")
if [ "$ROOT_CHECK" = "FAIL" ]; then
    echo "⚠️  WARNING: Container may be running as root user"
fi

# Check for secrets in image
echo "🔐 Scanning for exposed secrets..."
trivy image --format table --scanners secret $IMAGE_NAME

echo ""
echo "📊 Security scan completed"
echo "📁 Reports saved in security-reports/ directory"

exit $EXIT_CODE