#!/usr/bin/env python3
"""
Railway PostgreSQL Database Initialization Script
Creates the required schema and tables for Reddit Ghost Publisher
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.models.base import Base
from app.models.post import Post
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage
from app.models.media_file import MediaFile
from app.models.api_key import APIKey

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_railway_database():
    """Initialize Railway PostgreSQL database with required schema"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        logger.info("Connecting to Railway PostgreSQL database...")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"Connected to PostgreSQL: {version}")
        
        # Create all tables
        logger.info("Creating database schema...")
        Base.metadata.create_all(engine)
        
        # Create indexes and constraints
        with engine.connect() as conn:
            # Create unique index on reddit_post_id
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_reddit_post_id 
                ON posts(reddit_post_id)
            """))
            
            # Create index on created_ts for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_posts_created_ts 
                ON posts(created_ts)
            """))
            
            # Create index on subreddit for filtering
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_posts_subreddit 
                ON posts(subreddit)
            """))
            
            # Create index on ghost_url for published posts
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_posts_ghost_url 
                ON posts(ghost_url) WHERE ghost_url IS NOT NULL
            """))
            
            # Create index on processing_logs for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_processing_logs_post_id 
                ON processing_logs(post_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_processing_logs_created_at 
                ON processing_logs(created_at)
            """))
            
            # Create index on token_usage for cost tracking
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_created_at 
                ON token_usage(created_at)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_post_id 
                ON token_usage(post_id)
            """))
            
            # Create updated_at trigger for posts table
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql'
            """))
            
            conn.execute(text("""
                DROP TRIGGER IF EXISTS update_posts_updated_at ON posts
            """))
            
            conn.execute(text("""
                CREATE TRIGGER update_posts_updated_at 
                BEFORE UPDATE ON posts
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """))
            
            conn.commit()
        
        logger.info("Database schema created successfully!")
        
        # Verify tables exist
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"Created tables: {', '.join(tables)}")
            
            # Check if we have any existing data
            result = conn.execute(text("SELECT COUNT(*) FROM posts"))
            post_count = result.fetchone()[0]
            logger.info(f"Current posts in database: {post_count}")
        
        return True
        
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


def verify_database_schema():
    """Verify that the database schema is correctly set up"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        return False
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check required tables exist
            required_tables = ['posts', 'processing_logs', 'token_usage', 'media_files']
            
            for table in required_tables:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                    )
                """))
                
                exists = result.fetchone()[0]
                if not exists:
                    logger.error(f"Required table '{table}' does not exist")
                    return False
                else:
                    logger.info(f"✓ Table '{table}' exists")
            
            # Check required indexes exist
            required_indexes = [
                'idx_posts_reddit_post_id',
                'idx_posts_created_ts',
                'idx_posts_subreddit'
            ]
            
            for index in required_indexes:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM pg_indexes 
                        WHERE schemaname = 'public' 
                        AND indexname = '{index}'
                    )
                """))
                
                exists = result.fetchone()[0]
                if not exists:
                    logger.warning(f"Index '{index}' does not exist")
                else:
                    logger.info(f"✓ Index '{index}' exists")
            
            # Test basic operations
            result = conn.execute(text("SELECT COUNT(*) FROM posts"))
            post_count = result.fetchone()[0]
            
            result = conn.execute(text("SELECT COUNT(*) FROM processing_logs"))
            log_count = result.fetchone()[0]
            
            logger.info(f"Database verification successful!")
            logger.info(f"Posts: {post_count}, Logs: {log_count}")
            
        return True
        
    except Exception as e:
        logger.error(f"Database verification failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize Railway PostgreSQL database")
    parser.add_argument("--verify", action="store_true", help="Verify database schema instead of creating")
    
    args = parser.parse_args()
    
    if args.verify:
        success = verify_database_schema()
    else:
        success = init_railway_database()
    
    if success:
        logger.info("✅ Database operation completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Database operation failed!")
        sys.exit(1)