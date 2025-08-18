#!/usr/bin/env python3
"""
Schema validation script for Reddit Ghost Publisher MVP
Validates that the database schema matches the design requirements
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, inspect, text
from app.config import get_database_url


def validate_schema():
    """Validate that the database schema matches MVP requirements"""
    engine = create_engine(get_database_url())
    inspector = inspect(engine)
    
    print("🔍 Validating MVP Database Schema...")
    
    # Check if posts table exists
    tables = inspector.get_table_names()
    if 'posts' not in tables:
        print("❌ posts table not found")
        return False
    
    print("✅ posts table exists")
    
    # Check posts table columns
    posts_columns = {col['name']: col for col in inspector.get_columns('posts')}
    required_columns = [
        'id',  # UUID primary key
        'reddit_post_id',  # TEXT UNIQUE NOT NULL
        'title',  # TEXT NOT NULL
        'subreddit',  # TEXT NOT NULL
        'score',  # INTEGER DEFAULT 0
        'num_comments',  # INTEGER DEFAULT 0
        'created_ts',  # TIMESTAMPTZ NOT NULL
        'summary_ko',  # TEXT (nullable)
        'tags',  # JSONB (nullable)
        'pain_points',  # JSONB (nullable)
        'product_ideas',  # JSONB (nullable)
        'ghost_url',  # TEXT (nullable)
        'ghost_post_id',  # TEXT (nullable, unique)
        'ghost_slug',  # TEXT (nullable)
        'content_hash',  # TEXT (nullable)
        'takedown_status',  # TEXT DEFAULT 'active'
        'created_at',  # TIMESTAMPTZ DEFAULT NOW()
        'updated_at'  # TIMESTAMPTZ DEFAULT NOW()
    ]
    
    missing_columns = []
    for col in required_columns:
        if col not in posts_columns:
            missing_columns.append(col)
    
    if missing_columns:
        print(f"❌ Missing columns in posts table: {missing_columns}")
        return False
    
    print("✅ All required columns exist in posts table")
    
    # Check unique constraints
    unique_constraints = inspector.get_unique_constraints('posts')
    constraint_names = [const['name'] for const in unique_constraints]
    
    required_unique_constraints = [
        'uq_posts_reddit_post_id',
        'uq_posts_ghost_post_id'
    ]
    
    missing_constraints = []
    for constraint in required_unique_constraints:
        if constraint not in constraint_names:
            missing_constraints.append(constraint)
    
    if missing_constraints:
        print(f"❌ Missing unique constraints: {missing_constraints}")
        return False
    
    print("✅ All required unique constraints exist")
    
    # Check indexes
    indexes = inspector.get_indexes('posts')
    index_names = [idx['name'] for idx in indexes]
    
    required_indexes = [
        'idx_posts_created_ts',
        'idx_posts_subreddit'
    ]
    
    missing_indexes = []
    for index in required_indexes:
        if index not in index_names:
            missing_indexes.append(index)
    
    if missing_indexes:
        print(f"❌ Missing indexes: {missing_indexes}")
        return False
    
    print("✅ All required indexes exist")
    
    # Check other required tables
    required_tables = ['media_files', 'processing_logs', 'token_usage']
    missing_tables = []
    
    for table in required_tables:
        if table not in tables:
            missing_tables.append(table)
    
    if missing_tables:
        print(f"❌ Missing tables: {missing_tables}")
        return False
    
    print("✅ All required tables exist")
    
    # Check if updated_at trigger exists (PostgreSQL only)
    with engine.connect() as conn:
        if engine.dialect.name == 'postgresql':
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_trigger 
                    WHERE tgname = 'update_posts_updated_at'
                )
            """))
            
            if not result.scalar():
                print("❌ updated_at trigger not found")
                return False
            
            print("✅ updated_at trigger exists")
        else:
            print("⚠️  SQLite detected - trigger validation skipped (PostgreSQL required for production)")
    
    print("\n🎉 Schema validation passed! All MVP requirements are met.")
    return True


if __name__ == "__main__":
    if validate_schema():
        sys.exit(0)
    else:
        sys.exit(1)