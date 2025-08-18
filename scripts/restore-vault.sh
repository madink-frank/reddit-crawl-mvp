#!/bin/bash

# HashiCorp Vault Restore Script for Reddit Ghost Publisher
# This script restores Vault secrets and configuration from backup files

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups/vault"
LOG_FILE="${BACKUP_DIR}/vault_restore.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Load environment variables
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    source "${PROJECT_ROOT}/.env"
fi

# Vault configuration
VAULT_ADDR=${VAULT_URL:-http://localhost:8200}
VAULT_TOKEN=${VAULT_TOKEN:-}
VAULT_NAMESPACE=${VAULT_NAMESPACE:-}

# S3 configuration
S3_ENDPOINT=${S3_ENDPOINT:-sgp1.digitaloceanspaces.com}
S3_BUCKET=${S3_BUCKET:-reddit-publisher-backups}
S3_ACCESS_KEY=${S3_ACCESS_KEY}
S3_SECRET_KEY=${S3_SECRET_KEY}

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

# Usage function
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Restore HashiCorp Vault secrets and configuration from backup

OPTIONS:
    -v, --vault-file FILE      Restore Vault secrets from local backup file
    -c, --config-file FILE     Restore configuration from local backup file
    -s, --s3-vault-key KEY     Restore Vault secrets from S3 backup key
    -S, --s3-config-key KEY    Restore configuration from S3 backup key
    -l, --list                 List available backups
    -t, --test                 Test restore (dry run)
    -y, --yes                  Skip confirmation prompts
    -h, --help                 Show this help message

EXAMPLES:
    $0 --list                                    # List available backups
    $0 --vault-file backups/vault/vault_backup_20240101_120000.json
    $0 --config-file backups/vault/config_backup_20240101_120000.tar.gz
    $0 --s3-vault-key vault-backups/2024/01/vault_backup_20240101_120000.json
    $0 --test --vault-file vault_backup.json    # Test restore without applying

EOF
}

# Parse command line arguments
VAULT_FILE=""
CONFIG_FILE=""
S3_VAULT_KEY=""
S3_CONFIG_KEY=""
LIST_BACKUPS=false
TEST_MODE=false
SKIP_CONFIRMATION=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--vault-file)
            VAULT_FILE="$2"
            shift 2
            ;;
        -c|--config-file)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -s|--s3-vault-key)
            S3_VAULT_KEY="$2"
            shift 2
            ;;
        -S|--s3-config-key)
            S3_CONFIG_KEY="$2"
            shift 2
            ;;
        -l|--list)
            LIST_BACKUPS=true
            shift
            ;;
        -t|--test)
            TEST_MODE=true
            shift
            ;;
        -y|--yes)
            SKIP_CONFIRMATION=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error_exit "Unknown option: $1"
            ;;
    esac
done

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Initialize log file
log "INFO" "Starting Vault and configuration restore process"

# Check if required tools are available
command -v vault >/dev/null 2>&1 || error_exit "vault CLI is not installed"
command -v jq >/dev/null 2>&1 || error_exit "jq is not installed"
command -v tar >/dev/null 2>&1 || error_exit "tar is not installed"

# List available backups
list_backups() {
    log "INFO" "Available local Vault backups:"
    if ls "$BACKUP_DIR"/vault_backup_*.json >/dev/null 2>&1; then
        for backup in "$BACKUP_DIR"/vault_backup_*.json; do
            local size=$(stat -f%z "$backup" 2>/dev/null || stat -c%s "$backup" 2>/dev/null)
            local date=$(stat -f%Sm -t "%Y-%m-%d %H:%M:%S" "$backup" 2>/dev/null || stat -c%y "$backup" 2>/dev/null | cut -d. -f1)
            printf "  %-50s %10s bytes  %s\n" "$(basename "$backup")" "$size" "$date"
        done
    else
        log "INFO" "No local Vault backups found"
    fi
    
    log "INFO" "Available local configuration backups:"
    if ls "$BACKUP_DIR"/config_backup_*.tar.gz >/dev/null 2>&1; then
        for backup in "$BACKUP_DIR"/config_backup_*.tar.gz; do
            local size=$(stat -f%z "$backup" 2>/dev/null || stat -c%s "$backup" 2>/dev/null)
            local date=$(stat -f%Sm -t "%Y-%m-%d %H:%M:%S" "$backup" 2>/dev/null || stat -c%y "$backup" 2>/dev/null | cut -d. -f1)
            printf "  %-50s %10s bytes  %s\n" "$(basename "$backup")" "$size" "$date"
        done
    else
        log "INFO" "No local configuration backups found"
    fi
    
    if [[ -n "${S3_ACCESS_KEY:-}" ]] && [[ -n "${S3_SECRET_KEY:-}" ]]; then
        log "INFO" "Available S3 Vault backups:"
        export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
        export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
        
        if aws s3 ls "s3://${S3_BUCKET}/vault-backups/" --recursive --endpoint-url="https://${S3_ENDPOINT}" 2>/dev/null; then
            true
        else
            log "INFO" "No S3 Vault backups found or unable to access S3"
        fi
        
        log "INFO" "Available S3 configuration backups:"
        if aws s3 ls "s3://${S3_BUCKET}/config-backups/" --recursive --endpoint-url="https://${S3_ENDPOINT}" 2>/dev/null; then
            true
        else
            log "INFO" "No S3 configuration backups found or unable to access S3"
        fi
    else
        log "INFO" "S3 credentials not configured"
    fi
}

# Handle list command
if [[ "$LIST_BACKUPS" == true ]]; then
    list_backups
    exit 0
fi

# Prepare backup files
VAULT_RESTORE_FILE=""
CONFIG_RESTORE_FILE=""
TEMP_VAULT_FILE=""
TEMP_CONFIG_FILE=""

# Handle Vault backup file
if [[ -n "$VAULT_FILE" ]]; then
    if [[ ! -f "$VAULT_FILE" ]]; then
        error_exit "Vault backup file not found: $VAULT_FILE"
    fi
    VAULT_RESTORE_FILE="$VAULT_FILE"
    log "INFO" "Using local Vault backup file: $VAULT_RESTORE_FILE"
    
elif [[ -n "$S3_VAULT_KEY" ]]; then
    if [[ -z "${S3_ACCESS_KEY:-}" ]] || [[ -z "${S3_SECRET_KEY:-}" ]]; then
        error_exit "S3 credentials not configured"
    fi
    
    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    
    TEMP_VAULT_FILE="${BACKUP_DIR}/temp_vault_restore_${TIMESTAMP}.json"
    
    log "INFO" "Downloading Vault backup from S3: $S3_VAULT_KEY"
    if ! aws s3 cp "s3://${S3_BUCKET}/${S3_VAULT_KEY}" "$TEMP_VAULT_FILE" --endpoint-url="https://${S3_ENDPOINT}" 2>>"$LOG_FILE"; then
        error_exit "Failed to download Vault backup from S3"
    fi
    
    VAULT_RESTORE_FILE="$TEMP_VAULT_FILE"
    log "INFO" "Downloaded Vault backup to: $VAULT_RESTORE_FILE"
fi

# Handle configuration backup file
if [[ -n "$CONFIG_FILE" ]]; then
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error_exit "Configuration backup file not found: $CONFIG_FILE"
    fi
    CONFIG_RESTORE_FILE="$CONFIG_FILE"
    log "INFO" "Using local configuration backup file: $CONFIG_RESTORE_FILE"
    
elif [[ -n "$S3_CONFIG_KEY" ]]; then
    if [[ -z "${S3_ACCESS_KEY:-}" ]] || [[ -z "${S3_SECRET_KEY:-}" ]]; then
        error_exit "S3 credentials not configured"
    fi
    
    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    
    TEMP_CONFIG_FILE="${BACKUP_DIR}/temp_config_restore_${TIMESTAMP}.tar.gz"
    
    log "INFO" "Downloading configuration backup from S3: $S3_CONFIG_KEY"
    if ! aws s3 cp "s3://${S3_BUCKET}/${S3_CONFIG_KEY}" "$TEMP_CONFIG_FILE" --endpoint-url="https://${S3_ENDPOINT}" 2>>"$LOG_FILE"; then
        error_exit "Failed to download configuration backup from S3"
    fi
    
    CONFIG_RESTORE_FILE="$TEMP_CONFIG_FILE"
    log "INFO" "Downloaded configuration backup to: $CONFIG_RESTORE_FILE"
fi

# Cleanup function for temporary files
cleanup() {
    if [[ -n "$TEMP_VAULT_FILE" ]] && [[ -f "$TEMP_VAULT_FILE" ]]; then
        rm -f "$TEMP_VAULT_FILE"
        log "INFO" "Cleaned up temporary Vault file: $TEMP_VAULT_FILE"
    fi
    if [[ -n "$TEMP_CONFIG_FILE" ]] && [[ -f "$TEMP_CONFIG_FILE" ]]; then
        rm -f "$TEMP_CONFIG_FILE"
        log "INFO" "Cleaned up temporary configuration file: $TEMP_CONFIG_FILE"
    fi
}
trap cleanup EXIT

# Restore Vault secrets
if [[ -n "$VAULT_RESTORE_FILE" ]]; then
    log "INFO" "Restoring Vault secrets from: $VAULT_RESTORE_FILE"
    
    # Verify backup file
    if [[ ! -f "$VAULT_RESTORE_FILE" ]] || [[ ! -s "$VAULT_RESTORE_FILE" ]]; then
        error_exit "Vault backup file is empty or does not exist: $VAULT_RESTORE_FILE"
    fi
    
    # Validate JSON format
    if ! jq empty "$VAULT_RESTORE_FILE" 2>/dev/null; then
        error_exit "Vault backup file is not valid JSON: $VAULT_RESTORE_FILE"
    fi
    
    # Check Vault connectivity
    log "INFO" "Testing Vault connectivity..."
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
    
    log "INFO" "Vault connectivity confirmed"
    
    # Confirmation prompt for Vault restore
    if [[ "$SKIP_CONFIRMATION" != true ]] && [[ "$TEST_MODE" != true ]]; then
        echo
        echo "WARNING: This will overwrite existing secrets in Vault"
        echo "Vault address: $VAULT_ADDR"
        echo "Backup file: $VAULT_RESTORE_FILE"
        echo
        read -p "Are you sure you want to continue? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log "INFO" "Vault restore cancelled by user"
            exit 0
        fi
    fi
    
    # Extract and restore secrets
    SECRETS_RESTORED=0
    SECRETS_FAILED=0
    
    # Get list of secret paths from backup
    secret_paths=$(jq -r '.secrets | keys[]' "$VAULT_RESTORE_FILE")
    
    for secret_path in $secret_paths; do
        log "INFO" "Restoring secret: $secret_path"
        
        if [[ "$TEST_MODE" == true ]]; then
            log "INFO" "TEST MODE: Would restore secret $secret_path"
            SECRETS_RESTORED=$((SECRETS_RESTORED + 1))
            continue
        fi
        
        # Extract secret data
        secret_data=$(jq -r --arg path "$secret_path" '.secrets[$path].data.data' "$VAULT_RESTORE_FILE")
        
        if [[ "$secret_data" != "null" ]] && [[ -n "$secret_data" ]]; then
            # Create temporary file with secret data
            temp_secret=$(mktemp)
            echo "$secret_data" > "$temp_secret"
            
            # Restore secret to Vault
            if vault kv put "$secret_path" @"$temp_secret" >/dev/null 2>&1; then
                SECRETS_RESTORED=$((SECRETS_RESTORED + 1))
                log "INFO" "Successfully restored secret: $secret_path"
            else
                SECRETS_FAILED=$((SECRETS_FAILED + 1))
                log "ERROR" "Failed to restore secret: $secret_path"
            fi
            
            # Clean up temp file
            rm -f "$temp_secret"
        else
            SECRETS_FAILED=$((SECRETS_FAILED + 1))
            log "ERROR" "No data found for secret: $secret_path"
        fi
    done
    
    log "INFO" "Vault secrets restore completed: $SECRETS_RESTORED restored, $SECRETS_FAILED failed"
fi

# Restore configuration
if [[ -n "$CONFIG_RESTORE_FILE" ]]; then
    log "INFO" "Restoring configuration from: $CONFIG_RESTORE_FILE"
    
    # Verify backup file
    if [[ ! -f "$CONFIG_RESTORE_FILE" ]] || [[ ! -s "$CONFIG_RESTORE_FILE" ]]; then
        error_exit "Configuration backup file is empty or does not exist: $CONFIG_RESTORE_FILE"
    fi
    
    # Test archive integrity
    if ! tar -tzf "$CONFIG_RESTORE_FILE" >/dev/null 2>&1; then
        error_exit "Configuration backup file is corrupted or not a valid tar.gz file"
    fi
    
    # Confirmation prompt for configuration restore
    if [[ "$SKIP_CONFIRMATION" != true ]] && [[ "$TEST_MODE" != true ]]; then
        echo
        echo "WARNING: This will overwrite existing configuration files"
        echo "Project root: $PROJECT_ROOT"
        echo "Backup file: $CONFIG_RESTORE_FILE"
        echo
        read -p "Are you sure you want to continue? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log "INFO" "Configuration restore cancelled by user"
            exit 0
        fi
    fi
    
    if [[ "$TEST_MODE" == true ]]; then
        log "INFO" "TEST MODE: Would extract configuration to $PROJECT_ROOT"
        log "INFO" "Archive contents:"
        tar -tzf "$CONFIG_RESTORE_FILE" | head -20
        if [[ $(tar -tzf "$CONFIG_RESTORE_FILE" | wc -l) -gt 20 ]]; then
            log "INFO" "... and $(( $(tar -tzf "$CONFIG_RESTORE_FILE" | wc -l) - 20 )) more files"
        fi
    else
        # Create backup of current configuration
        CURRENT_CONFIG_BACKUP="${BACKUP_DIR}/pre_restore_config_${TIMESTAMP}.tar.gz"
        log "INFO" "Creating backup of current configuration before restore..."
        
        cd "$PROJECT_ROOT"
        if tar -czf "$CURRENT_CONFIG_BACKUP" \
            --exclude='backups' \
            --exclude='logs' \
            --exclude='venv' \
            --exclude='__pycache__' \
            --exclude='.git' \
            --exclude='node_modules' \
            . 2>>"$LOG_FILE"; then
            log "INFO" "Pre-restore configuration backup created: $CURRENT_CONFIG_BACKUP"
        else
            log "WARN" "Failed to create pre-restore configuration backup"
        fi
        
        # Extract configuration
        log "INFO" "Extracting configuration files..."
        
        # Create temporary extraction directory
        EXTRACT_TEMP_DIR=$(mktemp -d)
        
        cd "$EXTRACT_TEMP_DIR"
        if tar -xzf "$CONFIG_RESTORE_FILE" 2>>"$LOG_FILE"; then
            # Find the extracted directory
            EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name "config_backup_*" | head -1)
            
            if [[ -n "$EXTRACTED_DIR" ]] && [[ -d "$EXTRACTED_DIR" ]]; then
                # Copy files to project root
                cd "$EXTRACTED_DIR"
                cp -r . "$PROJECT_ROOT/" 2>>"$LOG_FILE"
                
                FILES_RESTORED=$(find . -type f | wc -l)
                log "INFO" "Configuration restore completed: $FILES_RESTORED files restored"
            else
                error_exit "Could not find extracted configuration directory"
            fi
        else
            error_exit "Failed to extract configuration backup"
        fi
        
        # Clean up extraction directory
        rm -rf "$EXTRACT_TEMP_DIR"
    fi
fi

# Generate restore report
RESTORE_REPORT="${BACKUP_DIR}/vault_restore_report_${TIMESTAMP}.json"
cat > "$RESTORE_REPORT" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "vault_restore": {
        "performed": $(if [[ -n "$VAULT_RESTORE_FILE" ]]; then echo "true"; else echo "false"; fi),
        "source_file": "${VAULT_RESTORE_FILE}",
        "secrets_restored": ${SECRETS_RESTORED:-0},
        "secrets_failed": ${SECRETS_FAILED:-0}
    },
    "config_restore": {
        "performed": $(if [[ -n "$CONFIG_RESTORE_FILE" ]]; then echo "true"; else echo "false"; fi),
        "source_file": "${CONFIG_RESTORE_FILE}",
        "files_restored": ${FILES_RESTORED:-0}
    },
    "test_mode": $(if [[ "$TEST_MODE" == true ]]; then echo "true"; else echo "false"; fi),
    "status": "success"
}
EOF

log "INFO" "Restore report generated: $RESTORE_REPORT"
log "INFO" "Vault and configuration restore process completed successfully"

exit 0