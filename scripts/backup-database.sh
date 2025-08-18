#!/bin/bash

# Simplified PostgreSQL Database Backup Script for Reddit Ghost Publisher MVP
# Creates local backups with 7-day retention as per requirements

set -euo pipefail

# Configuration
BACKUP_DIR="/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=7

# Database configuration from environment variables
DB_HOST=${PGHOST:-postgres}
DB_PORT=${PGPORT:-5432}
DB_NAME=${PGDATABASE:-reddit_publisher}
DB_USER=${PGUSER:-postgres}
DB_PASSWORD=${PGPASSWORD:-postgres}

# Backup file names
BACKUP_FILENAME="backup_${TIMESTAMP}.sql"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log "Starting database backup process"
log "Backup timestamp: $TIMESTAMP"
log "Database: $DB_NAME@$DB_HOST:$DB_PORT"

# Check if pg_dump is available
command -v pg_dump >/dev/null 2>&1 || error_exit "pg_dump is not installed"

# Check database connectivity
log "Testing database connectivity..."
export PGPASSWORD="$DB_PASSWORD"
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    error_exit "Cannot connect to database $DB_NAME@$DB_HOST:$DB_PORT"
fi
log "Database connectivity confirmed"

# Create database backup
log "Creating database backup..."
if ! pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --clean \
    --if-exists \
    --create \
    --format=plain \
    --no-password \
    --file="$BACKUP_PATH"; then
    error_exit "Failed to create database backup"
fi

# Verify backup file was created and has content
if [[ ! -f "$BACKUP_PATH" ]] || [[ ! -s "$BACKUP_PATH" ]]; then
    error_exit "Backup file is empty or was not created"
fi

# Get backup size
if command -v stat >/dev/null 2>&1; then
    BACKUP_SIZE=$(stat -c%s "$BACKUP_PATH" 2>/dev/null || stat -f%z "$BACKUP_PATH" 2>/dev/null)
    log "Database backup created successfully (${BACKUP_SIZE} bytes)"
else
    log "Database backup created successfully"
fi

# Clean up old local backups (keep last 7 days as per requirements)
log "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "$BACKUP_DIR" -name "backup_*.sql" -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true

# Count remaining backups
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "backup_*.sql" -type f | wc -l)
log "Backup cleanup completed. Total backups: ${BACKUP_COUNT}"

log "Database backup process completed successfully"
log "Backup saved as: $BACKUP_PATH"

exit 0