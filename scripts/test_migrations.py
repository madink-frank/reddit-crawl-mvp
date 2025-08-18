#!/usr/bin/env python3
"""
Test migration files for Reddit Ghost Publisher MVP
Validates migration structure without requiring database connection
"""

import os
import sys
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_migration_files():
    """Test that migration files contain required schema elements"""
    print("🔍 Testing Migration Files...")
    
    migrations_dir = Path("migrations/versions")
    if not migrations_dir.exists():
        print("❌ migrations/versions directory not found")
        return False
    
    # Find the latest MVP migration
    mvp_migration = None
    for migration_file in migrations_dir.glob("*.py"):
        if "complete_mvp_schema_postgresql_only" in migration_file.name:
            mvp_migration = migration_file
            break
    
    if not mvp_migration:
        print("❌ MVP schema migration not found")
        return False
    
    print(f"✅ Found MVP migration: {mvp_migration.name}")
    
    # Read migration content
    with open(mvp_migration, 'r') as f:
        content = f.read()
    
    # Check for required elements
    required_elements = [
        'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',  # UUID extension
        'ghost_post_id',  # ghost_post_id column
        'ghost_slug',  # ghost_slug column
        'uq_posts_ghost_post_id',  # unique constraint
        'idx_posts_reddit_post_id',  # reddit_post_id index
        'idx_posts_created_ts',  # created_ts index
        'idx_posts_subreddit',  # subreddit index
        'idx_processing_logs_post_id',  # processing_logs index
        'idx_token_usage_created_at',  # token_usage index
        'update_updated_at_column',  # trigger function
        'update_posts_updated_at'  # trigger
    ]
    
    missing_elements = []
    for element in required_elements:
        if element not in content:
            missing_elements.append(element)
    
    if missing_elements:
        print(f"❌ Missing elements in migration: {missing_elements}")
        return False
    
    print("✅ All required elements found in migration")
    
    # Check that PostgreSQL-specific features are used
    postgresql_features = [
        'postgresql',  # PostgreSQL dialect check
        'UUID',  # UUID type
        'JSONB',  # JSONB type (should be in earlier migrations)
        'TIMESTAMPTZ'  # TIMESTAMPTZ type (should be in earlier migrations)
    ]
    
    found_postgresql_features = []
    for feature in postgresql_features:
        if feature.lower() in content.lower():
            found_postgresql_features.append(feature)
    
    if len(found_postgresql_features) < 2:  # At least PostgreSQL and UUID
        print(f"⚠️  Limited PostgreSQL-specific features found: {found_postgresql_features}")
    else:
        print(f"✅ PostgreSQL-specific features found: {found_postgresql_features}")
    
    # Check env.py for sync engine usage
    env_py = Path("migrations/env.py")
    if env_py.exists():
        with open(env_py, 'r') as f:
            env_content = f.read()
        
        if 'create_engine(url)' in env_content and 'async' not in env_content.split('create_engine(url)')[1].split('\n')[0]:
            print("✅ env.py uses sync engine as required")
        else:
            print("⚠️  env.py engine configuration may need review")
    
    return True


def test_schema_documentation():
    """Test that schema documentation exists and is complete"""
    print("\n🔍 Testing Schema Documentation...")
    
    doc_file = Path("docs/database-schema.md")
    if not doc_file.exists():
        print("❌ database-schema.md documentation not found")
        return False
    
    print("✅ Schema documentation exists")
    
    with open(doc_file, 'r') as f:
        doc_content = f.read()
    
    # Check for required documentation sections
    required_sections = [
        'PostgreSQL 15',
        'posts',  # posts table section
        'media_files',
        'processing_logs',
        'token_usage',
        'Indexes',
        'Triggers',
        'Migration Strategy',
        'Backup and Recovery'
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in doc_content:
            missing_sections.append(section)
    
    if missing_sections:
        print(f"❌ Missing documentation sections: {missing_sections}")
        return False
    
    print("✅ All required documentation sections found")
    return True


def test_env_example():
    """Test that .env.example shows PostgreSQL configuration"""
    print("\n🔍 Testing Environment Configuration...")
    
    env_example = Path(".env.example")
    if not env_example.exists():
        print("❌ .env.example not found")
        return False
    
    with open(env_example, 'r') as f:
        env_content = f.read()
    
    # Check for PostgreSQL configuration
    if 'postgresql://' not in env_content:
        print("❌ .env.example does not show PostgreSQL configuration")
        return False
    
    if 'sqlite' in env_content.lower():
        print("⚠️  .env.example contains SQLite references (should be PostgreSQL only)")
    
    print("✅ .env.example shows PostgreSQL configuration")
    
    # Check for required environment variables
    required_vars = [
        'DATABASE_URL',
        'POSTGRES_DB',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'REDDIT_CLIENT_ID',
        'OPENAI_API_KEY',
        'GHOST_ADMIN_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if var not in env_content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables in .env.example: {missing_vars}")
        return False
    
    print("✅ All required environment variables documented")
    return True


def main():
    """Run all migration tests"""
    print("🚀 Testing MVP Database Schema Implementation\n")
    
    tests = [
        test_migration_files,
        test_schema_documentation,
        test_env_example
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)
    
    print(f"\n📊 Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed! MVP schema implementation is complete.")
        return True
    else:
        print("❌ Some tests failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)