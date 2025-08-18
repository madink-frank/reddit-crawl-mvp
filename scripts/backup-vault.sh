#!/bin/bash

# HashiCorp Vault Backup Script for Reddit Ghost Publisher
# This script creates backups of Vault data and configuration

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups/vault"
LOG_FILE="${BACKUP_DIR}/vault_backup.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=${VAULT_BACKUP_RETENTION_DAYS:-30}

# Load environment variables
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    source "${PROJECT_ROOT}/.env"
fi

# Vault configuration
VAULT_ADDR=${VAULT_URL:-http://localhost:8200}
VAULT_TOKEN=${VAULT_TOKEN:-}
VAULT_NAMESPACE=${VAULT_NAMESPACE:-}

# S3 configuration (DigitalOcean Spaces)
S3_ENDPOINT=${S3_ENDPOINT:-sgp1.digitaloceanspaces.com}
S3_BUCKET=${S3_BUCKET:-reddit-publisher-backups}
S3_ACCESS_KEY=${S3_ACCESS_KEY}
S3_SECRET_KEY=${S3_SECRET_KEY}

# Backup file names
VAULT_BACKUP_FILENAME="vault_backup_${TIMESTAMP}.json"
CONFIG_BACKUP_FILENAME="config_backup_${TIMESTAMP}.tar.gz"
VAULT_BACKUP_PATH="${BACKUP_DIR}/${VAULT_BACKUP_FILENAME}"
CONFIG_BACKUP_PATH="${BACKUP_DIR}/${CONFIG_BACKUP_FILENAME}"

# Logging function
log() {
    local level=$1
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR" "$1"
    exit 1
}

# Cleanup function
cleanup() {
    if [[ -f "$VAULT_BACKUP_PATH" ]]; then
        rm -f "$VAULT_BACKUP_PATH"
        log "INFO" "Cleaned up temporary vault backup file: $VAULT_BACKUP_PATH"
    fi
    if [[ -f "$CONFIG_BACKUP_PATH" ]]; then
        rm -f "$CONFIG_BACKUP_PATH"
        log "INFO" "Cleaned up temporary config backup file: $CONFIG_BACKUP_PATH"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Initialize log file
log "INFO" "Starting Vault and configuration backup process"
log "INFO" "Backup timestamp: $TIMESTAMP"
log "INFO" "Vault address: $VAULT_ADDR"

# Check if required tools are available
command -v vault >/dev/null 2>&1 || error_exit "vault CLI is not installed"
command -v jq >/dev/null 2>&1 || error_exit "jq is not installed"
command -v tar >/dev/null 2>&1 || error_exit "tar is not installed"

# Check Vault connectivity and authentication
log "INFO" "Testing Vault connectivity and authentication..."
export VAULT_ADDR="$VAULT_ADDR"
export VAULT_TOKEN="$VAULT_TOKEN"

if [[ -n "$VAULT_NAMESPACE" ]]; then
    export VAULT_NAMESPACE="$VAULT_NAMESPACE"
fi

if ! vault status >/dev/null 2>&1; then
    error_exit "Cannot connect to Vault at $VAULT_ADDR"
fi

if ! vault auth -method=token >/dev/null 2>&1; then
    error_exit "Vault authentication failed - check VAULT_TOKEN"
fi

log "INFO" "Vault connectivity and authentication confirmed"

# Create Vault secrets backup
log "INFO" "Creating Vault secrets backup..."

# Initialize backup structure
cat > "$VAULT_BACKUP_PATH" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "vault_address": "${VAULT_ADDR}",
    "backup_type": "secrets",
    "secrets": {}
}
EOF

# Define secret paths to backup
SECRET_PATHS=(
    "secret/reddit"
    "secret/openai" 
    "secret/ghost"
    "secret/database"
    "secret/s3"
    "secret/langsmith"
    "secret/monitoring"
)

# Backup each secret path
SECRETS_BACKED_UP=0
SECRETS_FAILED=0

for secret_path in "${SECRET_PATHS[@]}"; do
    log "INFO" "Backing up secret path: $secret_path"
    
    if vault kv get -format=json "$secret_path" >/dev/null 2>&1; then
        # Get secret data
        secret_data=$(vault kv get -format=json "$secret_path" 2>/dev/null)
        
        if [[ -n "$secret_data" ]]; then
            # Add to backup file
            temp_backup=$(mktemp)
            jq --arg path "$secret_path" --argjson data "$secret_data" \
               '.secrets[$path] = $data' "$VAULT_BACKUP_PATH" > "$temp_backup"
            mv "$temp_backup" "$VAULT_BACKUP_PATH"
            
            SECRETS_BACKED_UP=$((SECRETS_BACKED_UP + 1))
            log "INFO" "Successfully backed up secret: $secret_path"
        else
            log "WARN" "Secret path exists but no data found: $secret_path"
            SECRETS_FAILED=$((SECRETS_FAILED + 1))
        fi
    else
        log "WARN" "Secret path not found or inaccessible: $secret_path"
        SECRETS_FAILED=$((SECRETS_FAILED + 1))
    fi
done

# Update backup metadata
temp_backup=$(mktemp)
jq --arg count "$SECRETS_BACKED_UP" --arg failed "$SECRETS_FAILED" \
   '.secrets_backed_up = ($count | tonumber) | .secrets_failed = ($failed | tonumber)' \
   "$VAULT_BACKUP_PATH" > "$temp_backup"
mv "$temp_backup" "$VAULT_BACKUP_PATH"

log "INFO" "Vault secrets backup completed: $SECRETS_BACKED_UP backed up, $SECRETS_FAILED failed"

# Verify backup file was created and has content
if [[ ! -f "$VAULT_BACKUP_PATH" ]] || [[ ! -s "$VAULT_BACKUP_PATH" ]]; then
    error_exit "Vault backup file is empty or was not created"
fi

VAULT_BACKUP_SIZE=$(stat -f%z "$VAULT_BACKUP_PATH" 2>/dev/null || stat -c%s "$VAULT_BACKUP_PATH" 2>/dev/null)
log "INFO" "Vault backup created successfully (${VAULT_BACKUP_SIZE} bytes)"

# Create configuration backup
log "INFO" "Creating configuration backup..."

CONFIG_TEMP_DIR=$(mktemp -d)
CONFIG_BACKUP_NAME="config_backup_${TIMESTAMP}"
CONFIG_STAGING_DIR="${CONFIG_TEMP_DIR}/${CONFIG_BACKUP_NAME}"

mkdir -p "$CONFIG_STAGING_DIR"

# Backup configuration files
CONFIG_FILES=(
    ".env.example"
    ".env.production.example"
    "docker-compose.yml"
    "docker-compose.prod.yml"
    "docker-compose.test.yml"
    "requirements.txt"
    "requirements-dev.txt"
    "pyproject.toml"
    "alembic.ini"
)

CONFIG_DIRS=(
    "docker/"
    "terraform/"
    "scripts/"
    "templates/"
    ".kiro/"
    "migrations/"
)

# Copy configuration files
for config_file in "${CONFIG_FILES[@]}"; do
    if [[ -f "${PROJECT_ROOT}/${config_file}" ]]; then
        cp "${PROJECT_ROOT}/${config_file}" "${CONFIG_STAGING_DIR}/"
        log "INFO" "Backed up config file: $config_file"
    else
        log "WARN" "Config file not found: $config_file"
    fi
done

# Copy configuration directories
for config_dir in "${CONFIG_DIRS[@]}"; do
    if [[ -d "${PROJECT_ROOT}/${config_dir}" ]]; then
        cp -r "${PROJECT_ROOT}/${config_dir}" "${CONFIG_STAGING_DIR}/"
        log "INFO" "Backed up config directory: $config_dir"
    else
        log "WARN" "Config directory not found: $config_dir"
    fi
done

# Create metadata file
cat > "${CONFIG_STAGING_DIR}/backup_metadata.json" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "backup_type": "configuration",
    "project_root": "${PROJECT_ROOT}",
    "files_backed_up": $(find "${CONFIG_STAGING_DIR}" -type f | wc -l),
    "directories_backed_up": $(find "${CONFIG_STAGING_DIR}" -type d | wc -l)
}
EOF

# Create compressed archive
log "INFO" "Compressing configuration backup..."
cd "$CONFIG_TEMP_DIR"
if ! tar -czf "$CONFIG_BACKUP_PATH" "$CONFIG_BACKUP_NAME" 2>>"$LOG_FILE"; then
    rm -rf "$CONFIG_TEMP_DIR"
    error_exit "Failed to create configuration backup archive"
fi

# Clean up staging directory
rm -rf "$CONFIG_TEMP_DIR"

CONFIG_BACKUP_SIZE=$(stat -f%z "$CONFIG_BACKUP_PATH" 2>/dev/null || stat -c%s "$CONFIG_BACKUP_PATH" 2>/dev/null)
log "INFO" "Configuration backup created successfully (${CONFIG_BACKUP_SIZE} bytes)"

# Upload to S3 (DigitalOcean Spaces)
if [[ -n "${S3_ACCESS_KEY:-}" ]] && [[ -n "${S3_SECRET_KEY:-}" ]]; then
    log "INFO" "Uploading backups to S3..."
    
    # Configure AWS CLI for DigitalOcean Spaces
    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    
    # Upload Vault backup
    VAULT_S3_KEY="vault-backups/$(date +%Y)/$(date +%m)/${VAULT_BACKUP_FILENAME}"
    
    if aws s3 cp "$VAULT_BACKUP_PATH" "s3://${S3_BUCKET}/${VAULT_S3_KEY}" \
        --endpoint-url="https://${S3_ENDPOINT}" \
        --storage-class=STANDARD \
        --metadata="backup-type=vault,timestamp=${TIMESTAMP}" 2>>"$LOG_FILE"; then
        log "INFO" "Vault backup uploaded successfully to s3://${S3_BUCKET}/${VAULT_S3_KEY}"
    else
        log "ERROR" "Failed to upload Vault backup to S3"
    fi
    
    # Upload configuration backup
    CONFIG_S3_KEY="config-backups/$(date +%Y)/$(date +%m)/${CONFIG_BACKUP_FILENAME}"
    
    if aws s3 cp "$CONFIG_BACKUP_PATH" "s3://${S3_BUCKET}/${CONFIG_S3_KEY}" \
        --endpoint-url="https://${S3_ENDPOINT}" \
        --storage-class=STANDARD \
        --metadata="backup-type=configuration,timestamp=${TIMESTAMP}" 2>>"$LOG_FILE"; then
        log "INFO" "Configuration backup uploaded successfully to s3://${S3_BUCKET}/${CONFIG_S3_KEY}"
    else
        log "ERROR" "Failed to upload configuration backup to S3"
    fi
else
    log "WARN" "S3 credentials not provided, skipping upload"
fi

# Clean up old local backups
log "INFO" "Cleaning up old local backups (older than ${RETENTION_DAYS} days)..."
find "$BACKUP_DIR" -name "vault_backup_*.json" -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

# Clean up old S3 backups
if [[ -n "${S3_ACCESS_KEY:-}" ]] && [[ -n "${S3_SECRET_KEY:-}" ]]; then
    log "INFO" "Cleaning up old S3 backups (older than ${RETENTION_DAYS} days)..."
    
    CUTOFF_DATE=$(date -d "${RETENTION_DAYS} days ago" +%Y-%m-%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y-%m-%d 2>/dev/null)
    
    # Clean up vault backups
    aws s3 ls "s3://${S3_BUCKET}/vault-backups/" --recursive --endpoint-url="https://${S3_ENDPOINT}" | \
    while read -r line; do
        BACKUP_DATE=$(echo "$line" | awk '{print $1}')
        BACKUP_KEY=$(echo "$line" | awk '{print $4}')
        
        if [[ "$BACKUP_DATE" < "$CUTOFF_DATE" ]]; then
            log "INFO" "Deleting old vault backup: $BACKUP_KEY"
            aws s3 rm "s3://${S3_BUCKET}/${BACKUP_KEY}" --endpoint-url="https://${S3_ENDPOINT}" 2>>"$LOG_FILE" || true
        fi
    done
    
    # Clean up config backups
    aws s3 ls "s3://${S3_BUCKET}/config-backups/" --recursive --endpoint-url="https://${S3_ENDPOINT}" | \
    while read -r line; do
        BACKUP_DATE=$(echo "$line" | awk '{print $1}')
        BACKUP_KEY=$(echo "$line" | awk '{print $4}')
        
        if [[ "$BACKUP_DATE" < "$CUTOFF_DATE" ]]; then
            log "INFO" "Deleting old config backup: $BACKUP_KEY"
            aws s3 rm "s3://${S3_BUCKET}/${BACKUP_KEY}" --endpoint-url="https://${S3_ENDPOINT}" 2>>"$LOG_FILE" || true
        fi
    done
fi

# Generate backup report
BACKUP_REPORT="${BACKUP_DIR}/vault_backup_report_${TIMESTAMP}.json"
cat > "$BACKUP_REPORT" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "vault": {
        "address": "${VAULT_ADDR}",
        "secrets_backed_up": ${SECRETS_BACKED_UP},
        "secrets_failed": ${SECRETS_FAILED},
        "backup_file": "${VAULT_BACKUP_FILENAME}",
        "backup_size": ${VAULT_BACKUP_SIZE}
    },
    "configuration": {
        "backup_file": "${CONFIG_BACKUP_FILENAME}",
        "backup_size": ${CONFIG_BACKUP_SIZE}
    },
    "s3": {
        "uploaded": $(if [[ -n "${S3_ACCESS_KEY:-}" ]]; then echo "true"; else echo "false"; fi),
        "bucket": "${S3_BUCKET}",
        "vault_key": "${VAULT_S3_KEY:-}",
        "config_key": "${CONFIG_S3_KEY:-}",
        "endpoint": "${S3_ENDPOINT}"
    },
    "status": "success"
}
EOF

log "INFO" "Backup report generated: $BACKUP_REPORT"
log "INFO" "Vault and configuration backup process completed successfully"

# Send metrics to monitoring system (if configured)
if command -v curl >/dev/null 2>&1 && [[ -n "${PROMETHEUS_PUSHGATEWAY_URL:-}" ]]; then
    cat << EOF | curl -X POST --data-binary @- "${PROMETHEUS_PUSHGATEWAY_URL}/metrics/job/vault_backup/instance/${HOSTNAME}"
# HELP vault_backup_size_bytes Size of vault backup in bytes
# TYPE vault_backup_size_bytes gauge
vault_backup_size_bytes{type="vault"} ${VAULT_BACKUP_SIZE}
vault_backup_size_bytes{type="config"} ${CONFIG_BACKUP_SIZE}

# HELP vault_secrets_backed_up Number of vault secrets backed up
# TYPE vault_secrets_backed_up gauge
vault_secrets_backed_up ${SECRETS_BACKED_UP}

# HELP vault_backup_success Success status of vault backup (1=success, 0=failure)
# TYPE vault_backup_success gauge
vault_backup_success 1
EOF
fi

exit 0