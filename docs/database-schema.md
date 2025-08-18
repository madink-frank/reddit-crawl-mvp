# Database Schema Documentation

## Overview

The Reddit Ghost Publisher MVP uses PostgreSQL 15 as the primary database for both development and production environments. SQLite is not supported in the MVP to ensure consistency and leverage PostgreSQL-specific features.

## Schema Design

### Core Tables

#### posts
The main table storing Reddit posts and their processing status.

```sql
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reddit_post_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    subreddit TEXT NOT NULL,
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    created_ts TIMESTAMPTZ NOT NULL,
    
    -- AI processing results
    summary_ko TEXT,
    tags JSONB,
    pain_points JSONB,
    product_ideas JSONB,
    
    -- Ghost publishing info
    ghost_url TEXT,
    ghost_post_id TEXT,
    ghost_slug TEXT,
    
    -- Metadata
    content_hash TEXT,
    takedown_status TEXT DEFAULT 'active' CHECK (takedown_status IN ('active', 'takedown_pending', 'removed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Key Features:**
- UUID primary key for better distribution and security
- `reddit_post_id` unique constraint prevents duplicate collection
- `ghost_post_id` unique constraint prevents duplicate publishing (nullable)
- `takedown_status` supports the 2-stage takedown workflow
- JSONB fields for structured AI analysis results
- Automatic `updated_at` timestamp via trigger

#### media_files
Stores media file information and processing status.

```sql
CREATE TABLE media_files (
    id SERIAL PRIMARY KEY,
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    original_url TEXT NOT NULL,
    ghost_url TEXT,
    file_type TEXT,
    file_size INTEGER,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### processing_logs
Tracks processing attempts and results for monitoring.

```sql
CREATE TABLE processing_logs (
    id SERIAL PRIMARY KEY,
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    service_name TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### token_usage
Tracks AI token usage for budget management.

```sql
CREATE TABLE token_usage (
    id SERIAL PRIMARY KEY,
    post_id UUID REFERENCES posts(id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Indexes

Performance-critical indexes as specified in the design:

```sql
-- Unique indexes
CREATE UNIQUE INDEX idx_posts_reddit_post_id ON posts(reddit_post_id);
CREATE UNIQUE CONSTRAINT uq_posts_ghost_post_id ON posts(ghost_post_id);

-- Query optimization indexes
CREATE INDEX idx_posts_created_ts ON posts(created_ts);
CREATE INDEX idx_posts_subreddit ON posts(subreddit);
CREATE INDEX idx_processing_logs_post_id ON processing_logs(post_id);
CREATE INDEX idx_token_usage_created_at ON token_usage(created_at);
```

### Triggers

Automatic timestamp management:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$ language 'plpgsql';

CREATE TRIGGER update_posts_updated_at 
BEFORE UPDATE ON posts
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

## Migration Strategy

### Development to Production Consistency

Both development and production environments use PostgreSQL 15 to ensure:
- Consistent behavior across environments
- Proper testing of PostgreSQL-specific features
- No SQLite-specific issues in production

### Migration Files

The schema is managed through Alembic migrations:

1. `8d1ab4a331e1_initial_database_schema_with_posts_.py` - Initial schema
2. `df0754d14ef4_mvp_schema_update_uuid_reddit_post_id_.py` - MVP updates
3. `add_missing_columns.py` - Additional columns
4. `b00fea2e1ef3_add_missing_ghost_post_id_and_indexes.py` - Index fixes
5. `9f47a4c1b294_complete_mvp_schema_postgresql_only.py` - Final MVP schema

### Running Migrations

```bash
# Apply all migrations
python -m alembic upgrade head

# Validate schema
python scripts/validate_schema.py
```

## Configuration

### Environment Variables

```bash
# PostgreSQL connection
DATABASE_URL=postgresql://user:password@localhost:5432/reddit_publisher
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Docker Compose variables
POSTGRES_DB=reddit_publisher
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_PORT=5432
```

### Docker Compose Setup

```yaml
postgres:
  image: postgres:15
  environment:
    - POSTGRES_DB=reddit_publisher
    - POSTGRES_USER=${POSTGRES_USER}
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./backups:/backups
  ports:
    - "5432:5432"
  restart: unless-stopped
```

## Backup and Recovery

### Automated Backups

Daily backups using pg_dump:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="reddit_publisher"

pg_dump -h postgres -U ${DB_USER} -d ${DB_NAME} > ${BACKUP_DIR}/backup_${DATE}.sql
find ${BACKUP_DIR} -name "backup_*.sql" -mtime +7 -delete
```

### Recovery Testing

Weekly automated recovery tests validate backup integrity:

```bash
# Create test database
createdb -h postgres -U ${DB_USER} reddit_publisher_test

# Restore from backup
psql -h postgres -U ${DB_USER} -d reddit_publisher_test < backup_file.sql

# Validate data
psql -h postgres -U ${DB_USER} -d reddit_publisher_test -c "SELECT COUNT(*) FROM posts;"

# Cleanup
dropdb -h postgres -U ${DB_USER} reddit_publisher_test
```

## Monitoring

### Schema Validation

The `scripts/validate_schema.py` script ensures:
- All required tables exist
- All required columns are present
- Unique constraints are properly configured
- Indexes are created for performance
- Triggers are functioning

### Performance Monitoring

Key metrics to monitor:
- Query performance on indexed columns
- Table sizes and growth rates
- Index usage statistics
- Connection pool utilization

## Security Considerations

### Data Protection

- UUID primary keys prevent enumeration attacks
- Foreign key constraints ensure referential integrity
- Check constraints validate data integrity
- Cascade deletes maintain consistency

### Access Control

- Database credentials stored in environment variables
- Connection pooling limits resource usage
- Backup files secured with appropriate permissions

## Troubleshooting

### Common Issues

1. **Migration Failures**: Check PostgreSQL version compatibility
2. **Index Conflicts**: Verify unique constraints before migration
3. **Trigger Issues**: Ensure PostgreSQL extensions are enabled
4. **Connection Issues**: Validate DATABASE_URL format

### Validation Commands

```bash
# Check current migration status
python -m alembic current

# Validate schema compliance
python scripts/validate_schema.py

# Test database connection
python -c "from app.config import get_database_url; from sqlalchemy import create_engine; print(create_engine(get_database_url()).execute('SELECT 1').scalar())"
```