#!/bin/bash

# Backup Restore Test Script for Reddit Ghost Publisher MVP
# Tests backup integrity by restoring to a test database and validating data

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

# Test database configuration
TEST_DB_NAME="${DB_NAME}_test_${TIMESTAMP}"

# Minimum validation thresholds
MIN_TABLES=4  # posts, media_files, processing_logs, token_usage
MIN_INDEXES=6  # Based on schema requirements
MIN_CONSTRAINTS=3  # UNIQUE constraints and checks

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    cleanup_test_db
    exit 1
}

# Cleanup function
cleanup_test_db() {
    if [[ -n "${TEST_DB_NAME:-}" ]]; then
        log "Cleaning up test database: $TEST_DB_NAME"
        export PGPASSWORD="$DB_PASSWORD"
        dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$TEST_DB_NAME" 2>/dev/null || true
    fi
}

# Trap cleanup on exit
trap cleanup_test_db EXIT

# Usage function
usage() {
    cat << EOF
Usage: $0 [BACKUP_FILE]

Test backup restore integrity by restoring to a temporary test database

ARGUMENTS:
    BACKUP_FILE     Path to backup file (default: latest backup)

OPTIONS:
    --min-tables N      Minimum number of tables expected (default: $MIN_TABLES)
    --min-indexes N     Minimum number of indexes expected (default: $MIN_INDEXES)
    --min-constraints N Minimum number of constraints expected (default: $MIN_CONSTRAINTS)
    -v, --verbose       Verbose output
    -h, --help          Show this help message

EXAMPLES:
    $0                                    # Test latest backup
    $0 backup_20240101_120000.sql        # Test specific backup
    $0 --min-tables 5 --verbose          # Test with custom thresholds

EOF
}

# Parse command line arguments
BACKUP_FILE=""
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --min-tables)
            MIN_TABLES="$2"
            shift 2
            ;;
        --min-indexes)
            MIN_INDEXES="$2"
            shift 2
            ;;
        --min-constraints)
            MIN_CONSTRAINTS="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            error_exit "Unknown option: $1"
            ;;
        *)
            if [[ -z "$BACKUP_FILE" ]]; then
                if [[ "$1" == /* ]]; then
                    BACKUP_FILE="$1"
                else
                    BACKUP_FILE="$BACKUP_DIR/$1"
                fi
            else
                error_exit "Multiple backup files specified"
            fi
            shift
            ;;
    esac
done

# Find latest backup if none specified
if [[ -z "$BACKUP_FILE" ]]; then
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/backup_*.sql 2>/dev/null | head -n1 || true)
    if [[ -z "$BACKUP_FILE" ]]; then
        error_exit "No backup files found in $BACKUP_DIR"
    fi
    log "Using latest backup: $(basename "$BACKUP_FILE")"
fi

# Validate backup file
if [[ ! -f "$BACKUP_FILE" ]]; then
    error_exit "Backup file not found: $BACKUP_FILE"
fi

if [[ ! -s "$BACKUP_FILE" ]]; then
    error_exit "Backup file is empty: $BACKUP_FILE"
fi

# Check if required tools are available
command -v psql >/dev/null 2>&1 || error_exit "psql is not installed"
command -v createdb >/dev/null 2>&1 || error_exit "createdb is not installed"
command -v dropdb >/dev/null 2>&1 || error_exit "dropdb is not installed"

# Check database connectivity
log "Testing database connectivity..."
export PGPASSWORD="$DB_PASSWORD"
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
    error_exit "Cannot connect to database server $DB_HOST:$DB_PORT"
fi
log "Database connectivity confirmed"

# Get backup file info
BACKUP_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)
log "Starting backup restore test"
log "Backup file: $(basename "$BACKUP_FILE")"
log "Backup size: $BACKUP_SIZE bytes"
log "Test database: $TEST_DB_NAME"
log "Validation thresholds: tables≥$MIN_TABLES, indexes≥$MIN_INDEXES, constraints≥$MIN_CONSTRAINTS"

# Create test database
log "Creating test database: $TEST_DB_NAME"
if ! createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$TEST_DB_NAME" 2>/dev/null; then
    error_exit "Failed to create test database: $TEST_DB_NAME"
fi

# Restore backup to test database
log "Restoring backup to test database..."
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -v ON_ERROR_STOP=1 -f "$BACKUP_FILE" >/dev/null 2>&1; then
    error_exit "Failed to restore backup to test database"
fi
log "Backup restored successfully to test database"

# Validate database connectivity
log "Validating test database connectivity..."
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
    error_exit "Cannot connect to restored test database"
fi

# Count and validate tables
log "Validating database schema..."
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT COUNT(*) 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
" 2>/dev/null | xargs || echo "0")

if [[ "$TABLE_COUNT" -lt "$MIN_TABLES" ]]; then
    error_exit "Insufficient tables found: $TABLE_COUNT < $MIN_TABLES (minimum required)"
fi
log "✓ Tables validation passed: $TABLE_COUNT tables found (≥$MIN_TABLES required)"

# Validate specific required tables exist
REQUIRED_TABLES=("posts" "media_files" "processing_logs" "token_usage")
for table in "${REQUIRED_TABLES[@]}"; do
    TABLE_EXISTS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = '$table';
    " 2>/dev/null | xargs || echo "0")
    
    if [[ "$TABLE_EXISTS" -eq 0 ]]; then
        error_exit "Required table '$table' not found in restored database"
    fi
    
    if [[ "$VERBOSE" == true ]]; then
        log "  ✓ Required table '$table' exists"
    fi
done

# Count and validate indexes
INDEX_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT COUNT(*) 
    FROM pg_indexes 
    WHERE schemaname = 'public';
" 2>/dev/null | xargs || echo "0")

if [[ "$INDEX_COUNT" -lt "$MIN_INDEXES" ]]; then
    error_exit "Insufficient indexes found: $INDEX_COUNT < $MIN_INDEXES (minimum required)"
fi
log "✓ Indexes validation passed: $INDEX_COUNT indexes found (≥$MIN_INDEXES required)"

# Validate specific required indexes exist
REQUIRED_INDEXES=("idx_posts_reddit_post_id" "idx_posts_created_ts" "idx_posts_subreddit")
for index in "${REQUIRED_INDEXES[@]}"; do
    INDEX_EXISTS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
        SELECT COUNT(*) 
        FROM pg_indexes 
        WHERE schemaname = 'public' AND indexname = '$index';
    " 2>/dev/null | xargs || echo "0")
    
    if [[ "$INDEX_EXISTS" -eq 0 ]]; then
        error_exit "Required index '$index' not found in restored database"
    fi
    
    if [[ "$VERBOSE" == true ]]; then
        log "  ✓ Required index '$index' exists"
    fi
done

# Count and validate constraints
CONSTRAINT_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT COUNT(*) 
    FROM information_schema.table_constraints 
    WHERE table_schema = 'public' AND constraint_type IN ('UNIQUE', 'CHECK', 'FOREIGN KEY');
" 2>/dev/null | xargs || echo "0")

if [[ "$CONSTRAINT_COUNT" -lt "$MIN_CONSTRAINTS" ]]; then
    error_exit "Insufficient constraints found: $CONSTRAINT_COUNT < $MIN_CONSTRAINTS (minimum required)"
fi
log "✓ Constraints validation passed: $CONSTRAINT_COUNT constraints found (≥$MIN_CONSTRAINTS required)"

# Validate specific required constraints
UNIQUE_CONSTRAINTS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT COUNT(*) 
    FROM information_schema.table_constraints 
    WHERE table_schema = 'public' 
    AND constraint_type = 'UNIQUE' 
    AND table_name = 'posts' 
    AND constraint_name LIKE '%reddit_post_id%';
" 2>/dev/null | xargs || echo "0")

if [[ "$UNIQUE_CONSTRAINTS" -eq 0 ]]; then
    error_exit "Required UNIQUE constraint on posts.reddit_post_id not found"
fi

if [[ "$VERBOSE" == true ]]; then
    log "  ✓ Required UNIQUE constraint on posts.reddit_post_id exists"
fi

# Test basic data operations
log "Testing basic database operations..."

# Test INSERT operation
TEST_INSERT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    INSERT INTO posts (reddit_post_id, title, subreddit, score, num_comments, created_ts) 
    VALUES ('test_restore_$(date +%s)', 'Test Post', 'test', 1, 0, NOW()) 
    RETURNING id;
" 2>/dev/null | xargs || echo "")

if [[ -z "$TEST_INSERT" ]]; then
    error_exit "Failed to perform test INSERT operation"
fi

# Test SELECT operation
TEST_SELECT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT COUNT(*) FROM posts WHERE id = '$TEST_INSERT';
" 2>/dev/null | xargs || echo "0")

if [[ "$TEST_SELECT" -ne 1 ]]; then
    error_exit "Failed to perform test SELECT operation"
fi

# Test DELETE operation
TEST_DELETE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    DELETE FROM posts WHERE id = '$TEST_INSERT';
" 2>/dev/null || echo "FAILED")

if [[ "$TEST_DELETE" == "FAILED" ]]; then
    error_exit "Failed to perform test DELETE operation"
fi

log "✓ Basic database operations test passed"

# Get final statistics
TOTAL_RECORDS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -t -c "
    SELECT 
        COALESCE(SUM(n_tup_ins), 0) as total_records
    FROM pg_stat_user_tables;
" 2>/dev/null | xargs || echo "0")

log "✓ Database statistics: $TOTAL_RECORDS total records across all tables"

# Verbose output
if [[ "$VERBOSE" == true ]]; then
    log "Detailed validation results:"
    log "  - Tables: $TABLE_COUNT (required: ≥$MIN_TABLES)"
    log "  - Indexes: $INDEX_COUNT (required: ≥$MIN_INDEXES)"
    log "  - Constraints: $CONSTRAINT_COUNT (required: ≥$MIN_CONSTRAINTS)"
    log "  - Total records: $TOTAL_RECORDS"
    
    # Show table sizes
    log "Table record counts:"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" -c "
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as records
        FROM pg_stat_user_tables 
        ORDER BY n_tup_ins DESC;
    " 2>/dev/null | while IFS= read -r line; do
        log "    $line"
    done
fi

# Cleanup test database (handled by trap)
log "Backup restore test completed successfully"
log "All validation checks passed:"
log "  ✓ Database connectivity"
log "  ✓ Schema integrity ($TABLE_COUNT tables, $INDEX_COUNT indexes, $CONSTRAINT_COUNT constraints)"
log "  ✓ Required tables and indexes present"
log "  ✓ Basic database operations functional"
log "  ✓ Data integrity maintained ($TOTAL_RECORDS records)"

exit 0