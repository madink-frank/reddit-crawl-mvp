#!/bin/bash

# Database Backup Verification Script for Reddit Ghost Publisher
# This script verifies the integrity and completeness of database backups

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups"
LOG_FILE="${BACKUP_DIR}/verification.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Load environment variables
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    source "${PROJECT_ROOT}/.env"
fi

# Database configuration
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}
DB_NAME=${POSTGRES_DB:-reddit_publisher}
DB_USER=${POSTGRES_USER:-postgres}
DB_PASSWORD=${POSTGRES_PASSWORD:-postgres}

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

Verify database backup integrity and completeness

OPTIONS:
    -f, --file FILE         Verify specific backup file
    -a, --all              Verify all local backup files
    -s, --s3               Verify S3 backups
    -r, --report           Generate detailed verification report
    -h, --help             Show this help message

EXAMPLES:
    $0 --all                                     # Verify all local backups
    $0 --file backups/reddit_publisher_20240101_120000.sql.gz
    $0 --s3 --report                            # Verify S3 backups with report

EOF
}

# Parse command line arguments
BACKUP_FILE=""
VERIFY_ALL=false
VERIFY_S3=false
GENERATE_REPORT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--file)
            BACKUP_FILE="$2"
            shift 2
            ;;
        -a|--all)
            VERIFY_ALL=true
            shift
            ;;
        -s|--s3)
            VERIFY_S3=true
            shift
            ;;
        -r|--report)
            GENERATE_REPORT=true
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
log "INFO" "Starting backup verification process"

# Check if required tools are available
command -v gunzip >/dev/null 2>&1 || error_exit "gunzip is not installed"
command -v psql >/dev/null 2>&1 || error_exit "psql is not installed"

# Verification results
declare -A VERIFICATION_RESULTS
TOTAL_VERIFIED=0
TOTAL_PASSED=0
TOTAL_FAILED=0

# Verify single backup file
verify_backup_file() {
    local backup_file="$1"
    local file_name=$(basename "$backup_file")
    
    log "INFO" "Verifying backup file: $file_name"
    
    # Check if file exists and is not empty
    if [[ ! -f "$backup_file" ]]; then
        log "ERROR" "Backup file not found: $backup_file"
        VERIFICATION_RESULTS["$file_name"]="FAILED - File not found"
        return 1
    fi
    
    if [[ ! -s "$backup_file" ]]; then
        log "ERROR" "Backup file is empty: $backup_file"
        VERIFICATION_RESULTS["$file_name"]="FAILED - Empty file"
        return 1
    fi
    
    local file_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null)
    log "INFO" "File size: $file_size bytes"
    
    # Check file integrity (if compressed)
    if [[ "$backup_file" == *.gz ]]; then
        log "INFO" "Testing gzip integrity..."
        if ! gunzip -t "$backup_file" 2>/dev/null; then
            log "ERROR" "Gzip integrity check failed"
            VERIFICATION_RESULTS["$file_name"]="FAILED - Corrupted gzip"
            return 1
        fi
        log "INFO" "Gzip integrity check passed"
    fi
    
    # Verify SQL content structure
    log "INFO" "Verifying SQL content structure..."
    local temp_sql="/tmp/verify_${TIMESTAMP}_$(basename "$backup_file" .gz)"
    
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" > "$temp_sql" 2>/dev/null
    else
        cp "$backup_file" "$temp_sql"
    fi
    
    # Check for essential SQL elements
    local has_create_db=false
    local has_tables=false
    local has_data=false
    local table_count=0
    
    if grep -q "CREATE DATABASE" "$temp_sql" 2>/dev/null; then
        has_create_db=true
        log "INFO" "Found database creation statement"
    fi
    
    table_count=$(grep -c "CREATE TABLE" "$temp_sql" 2>/dev/null || echo "0")
    if [[ "$table_count" -gt 0 ]]; then
        has_tables=true
        log "INFO" "Found $table_count table creation statements"
    fi
    
    if grep -q "INSERT INTO\|COPY.*FROM" "$temp_sql" 2>/dev/null; then
        has_data=true
        log "INFO" "Found data insertion statements"
    fi
    
    # Clean up temp file
    rm -f "$temp_sql"
    
    # Evaluate verification results
    local verification_status="PASSED"
    local issues=()
    
    if [[ "$has_create_db" != true ]]; then
        issues+=("No database creation")
    fi
    
    if [[ "$has_tables" != true ]]; then
        issues+=("No table definitions")
        verification_status="FAILED"
    fi
    
    if [[ "$table_count" -lt 4 ]]; then  # Expecting at least posts, media_files, processing_logs, token_usage
        issues+=("Insufficient tables ($table_count < 4)")
        verification_status="FAILED"
    fi
    
    if [[ "$has_data" != true ]]; then
        issues+=("No data found")
        # This might be OK for empty databases, so just warn
        log "WARN" "No data insertion statements found in backup"
    fi
    
    if [[ ${#issues[@]} -gt 0 ]]; then
        local issue_list=$(IFS=", "; echo "${issues[*]}")
        VERIFICATION_RESULTS["$file_name"]="$verification_status - Issues: $issue_list"
        if [[ "$verification_status" == "FAILED" ]]; then
            log "ERROR" "Verification failed: $issue_list"
            return 1
        else
            log "WARN" "Verification passed with warnings: $issue_list"
        fi
    else
        VERIFICATION_RESULTS["$file_name"]="PASSED - All checks successful"
        log "INFO" "All verification checks passed"
    fi
    
    return 0
}

# Verify all local backup files
if [[ "$VERIFY_ALL" == true ]]; then
    log "INFO" "Verifying all local backup files..."
    
    local backup_files=("$BACKUP_DIR"/reddit_publisher_*.sql.gz "$BACKUP_DIR"/reddit_publisher_*.sql)
    local found_files=false
    
    for backup_file in "${backup_files[@]}"; do
        if [[ -f "$backup_file" ]]; then
            found_files=true
            TOTAL_VERIFIED=$((TOTAL_VERIFIED + 1))
            
            if verify_backup_file "$backup_file"; then
                TOTAL_PASSED=$((TOTAL_PASSED + 1))
            else
                TOTAL_FAILED=$((TOTAL_FAILED + 1))
            fi
        fi
    done
    
    if [[ "$found_files" != true ]]; then
        log "WARN" "No local backup files found to verify"
    fi
fi

# Verify specific backup file
if [[ -n "$BACKUP_FILE" ]]; then
    TOTAL_VERIFIED=$((TOTAL_VERIFIED + 1))
    
    if verify_backup_file "$BACKUP_FILE"; then
        TOTAL_PASSED=$((TOTAL_PASSED + 1))
    else
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi
fi

# Verify S3 backups
if [[ "$VERIFY_S3" == true ]]; then
    if [[ -z "${S3_ACCESS_KEY:-}" ]] || [[ -z "${S3_SECRET_KEY:-}" ]]; then
        log "WARN" "S3 credentials not configured, skipping S3 verification"
    else
        log "INFO" "Verifying S3 backups..."
        
        export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
        export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
        
        # List S3 backups
        local s3_backups
        if s3_backups=$(aws s3 ls "s3://${S3_BUCKET}/database-backups/" --recursive --endpoint-url="https://${S3_ENDPOINT}" 2>/dev/null); then
            
            echo "$s3_backups" | while read -r line; do
                if [[ -n "$line" ]]; then
                    local s3_key=$(echo "$line" | awk '{print $4}')
                    local s3_size=$(echo "$line" | awk '{print $3}')
                    local file_name=$(basename "$s3_key")
                    
                    log "INFO" "Verifying S3 backup: $s3_key (${s3_size} bytes)"
                    
                    # Download and verify
                    local temp_file="${BACKUP_DIR}/temp_s3_verify_${TIMESTAMP}_${file_name}"
                    
                    if aws s3 cp "s3://${S3_BUCKET}/${s3_key}" "$temp_file" --endpoint-url="https://${S3_ENDPOINT}" 2>>"$LOG_FILE"; then
                        TOTAL_VERIFIED=$((TOTAL_VERIFIED + 1))
                        
                        if verify_backup_file "$temp_file"; then
                            TOTAL_PASSED=$((TOTAL_PASSED + 1))
                        else
                            TOTAL_FAILED=$((TOTAL_FAILED + 1))
                        fi
                        
                        # Clean up temp file
                        rm -f "$temp_file"
                    else
                        log "ERROR" "Failed to download S3 backup: $s3_key"
                        VERIFICATION_RESULTS["$file_name"]="FAILED - Download error"
                        TOTAL_VERIFIED=$((TOTAL_VERIFIED + 1))
                        TOTAL_FAILED=$((TOTAL_FAILED + 1))
                    fi
                fi
            done
        else
            log "WARN" "No S3 backups found or unable to access S3"
        fi
    fi
fi

# Generate verification report
if [[ "$GENERATE_REPORT" == true ]] || [[ "$TOTAL_VERIFIED" -gt 0 ]]; then
    local report_file="${BACKUP_DIR}/verification_report_${TIMESTAMP}.json"
    
    log "INFO" "Generating verification report..."
    
    # Build JSON report
    cat > "$report_file" << EOF
{
    "timestamp": "${TIMESTAMP}",
    "verification_summary": {
        "total_verified": ${TOTAL_VERIFIED},
        "total_passed": ${TOTAL_PASSED},
        "total_failed": ${TOTAL_FAILED},
        "success_rate": "$(echo "scale=2; $TOTAL_PASSED * 100 / $TOTAL_VERIFIED" | bc 2>/dev/null || echo "0")%"
    },
    "results": {
EOF
    
    # Add individual results
    local first=true
    for file_name in "${!VERIFICATION_RESULTS[@]}"; do
        if [[ "$first" != true ]]; then
            echo "," >> "$report_file"
        fi
        echo "        \"$file_name\": \"${VERIFICATION_RESULTS[$file_name]}\"" >> "$report_file"
        first=false
    done
    
    cat >> "$report_file" << EOF
    },
    "recommendations": [
EOF
    
    # Add recommendations based on results
    local recommendations=()
    
    if [[ "$TOTAL_FAILED" -gt 0 ]]; then
        recommendations+=("\"Investigate and fix failed backup verifications\"")
    fi
    
    if [[ "$TOTAL_VERIFIED" -eq 0 ]]; then
        recommendations+=("\"No backups found - ensure backup process is running\"")
    fi
    
    if [[ "$VERIFY_S3" != true ]] && [[ -n "${S3_ACCESS_KEY:-}" ]]; then
        recommendations+=("\"Consider verifying S3 backups regularly\"")
    fi
    
    if [[ ${#recommendations[@]} -eq 0 ]]; then
        recommendations+=("\"All backups verified successfully - no action needed\"")
    fi
    
    local first=true
    for rec in "${recommendations[@]}"; do
        if [[ "$first" != true ]]; then
            echo "," >> "$report_file"
        fi
        echo "        $rec" >> "$report_file"
        first=false
    done
    
    cat >> "$report_file" << EOF
    ]
}
EOF
    
    log "INFO" "Verification report generated: $report_file"
fi

# Print summary
log "INFO" "Verification Summary:"
log "INFO" "  Total verified: $TOTAL_VERIFIED"
log "INFO" "  Passed: $TOTAL_PASSED"
log "INFO" "  Failed: $TOTAL_FAILED"

if [[ "$TOTAL_VERIFIED" -gt 0 ]]; then
    local success_rate=$(echo "scale=1; $TOTAL_PASSED * 100 / $TOTAL_VERIFIED" | bc 2>/dev/null || echo "0")
    log "INFO" "  Success rate: ${success_rate}%"
fi

# Exit with appropriate code
if [[ "$TOTAL_FAILED" -gt 0 ]]; then
    log "ERROR" "Some backup verifications failed"
    exit 1
else
    log "INFO" "All backup verifications passed"
    exit 0
fi