#!/bin/bash

# Simplified PostgreSQL Database Restore Script for Reddit Ghost Publisher MVP
# Restores database from local backup files

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Database configuration from environment variables
DB_HOST=${PGHOST:-postgres}
DB_PORT=${PGPORT:-5432}
DB_NAME=${PGDATABASE:-reddit_publisher}
DB_USER=${PGUSER:-postgres}
DB_PASSWORD=${PGPASSWORD:-postgres}

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Usage function
usage() {
    cat << EOF
Usage: $0 [BACKUP_FILE]

Restore PostgreSQL database from backup file

ARGUMENTS:
    BACKUP_FILE     Path to backup file (default: latest backup)

OPTIONS:
    -l, --list      List available backups
    -h, --help      Show this help message

EXAMPLES:
    $0                                    # Restore from latest backup
    $0 backup_20240101_120000.sql        # Restore from specific backup
    $0 --list                            # List available backups

EOF
}

# List available backups
list_backups() {
    log "Available backups in $BACKUP_DIR:"
    if ls "$BACKUP_DIR"/backup_*.sql >/dev/null 2>&1; then
        for backup in "$BACKUP_DIR"/backup_*.sql; do
            local size=$(stat -c%s "$backup" 2>/dev/null || stat -f%z "$backup" 2>/dev/null)
            local date=$(stat -c%y "$backup" 2>/dev/null | cut -d. -f1 || stat -f%Sm -t "%Y-%m-%d %H:%M:%S" "$backup" 2>/dev/null)
            printf "  %-40s %10s bytes  %s\n" "$(basename "$backup")" "$size" "$date"
        done
    else
        log "No backups found in $BACKUP_DIR"
    fi
}

# Parse command line arguments
BACKUP_FILE=""

case "${1:-}" in
    -l|--list)
        list_backups
        exit 0
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    "")
        # Find latest backup
        BACKUP_FILE=$(ls -t "$BACKUP_DIR"/backup_*.sql 2>/dev/null | head -n1 || true)
        if [[ -z "$BACKUP_FILE" ]]; then
            error_exit "No backup files found in $BACKUP_DIR"
        fi
        log "Using latest backup: $(basename "$BACKUP_FILE")"
        ;;
    *)
        if [[ "$1" == /* ]]; then
            BACKUP_FILE="$1"
        else
            BACKUP_FILE="$BACKUP_DIR/$1"
        fi
        ;;
esac

# Validate backup file
if [[ ! -f "$BACKUP_FILE" ]]; then
    error_exit "Backup file not found: $BACKUP_FILE"
fi

if [[ ! -s "$BACKUP_FILE" ]]; then
    error_exit "Backup file is empty: $BACKUP_FILE"
fi

# Check if required tools are available
command -v psql >/dev/null 2>&1 || error_exit "psql is not installed"

# Check database connectivity
log "Testing database connectivity..."
export PGPASSWORD="$DB_PASSWORD"
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
    error_exit "Cannot connect to database server $DB_HOST:$DB_PORT"
fi
log "Database connectivity confirmed"

# Get backup file info
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)
log "Backup file: $BACKUP_FILE"
log "Backup size: $BACKUP_SIZE bytes"

# Confirmation prompt
echo
echo "WARNING: This will completely replace the existing database '$DB_NAME'"
echo "Database: $DB_NAME@$DB_HOST:$DB_PORT"
echo "Backup file: $BACKUP_FILE"
echo "Backup size: $BACKUP_SIZE bytes"
echo
read -p "Are you sure you want to continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    log "Restore cancelled by user"
    exit 0
fi

# Create backup of current database before restore
CURRENT_BACKUP="$BACKUP_DIR/pre_restore_backup_${TIMESTAMP}.sql"
log "Creating backup of current database before restore..."
if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --create -f "$CURRENT_BACKUP" 2>/dev/null; then
    log "Pre-restore backup created: $(basename "$CURRENT_BACKUP")"
else
    log "WARNING: Failed to create pre-restore backup, continuing anyway..."
fi

# Restore database
log "Restoring database from backup..."
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 -f "$BACKUP_FILE" >/dev/null 2>&1; then
    log "Database restore completed successfully"
else
    error_exit "Failed to restore database from backup"
fi

# Verify restore
log "Verifying database restore..."
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
    error_exit "Database restore verification failed - cannot connect to restored database"
fi

# Count tables to verify restore
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | xargs || echo "0")
log "Database restore verified - found $TABLE_COUNT tables"

if [[ "$TABLE_COUNT" -eq 0 ]]; then
    log "WARNING: No tables found in restored database"
fi

log "Database restore process completed successfully"

exit 0