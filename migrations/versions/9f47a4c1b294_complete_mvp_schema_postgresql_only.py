"""complete_mvp_schema_postgresql_only

Revision ID: 9f47a4c1b294
Revises: b00fea2e1ef3
Create Date: 2025-08-13 04:37:54.163580

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f47a4c1b294'
down_revision: Union[str, None] = 'b00fea2e1ef3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Complete MVP schema for PostgreSQL only
    Ensures all required fields, indexes, and constraints are present
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Enable UUID extension for PostgreSQL
    if connection.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Check existing columns and add missing ones
    columns = [col['name'] for col in inspector.get_columns('posts')]
    
    # Ensure ghost_post_id exists (should be unique and nullable)
    if 'ghost_post_id' not in columns:
        op.add_column('posts', sa.Column('ghost_post_id', sa.Text(), nullable=True))
    
    # Ensure ghost_slug exists (for takedown workflow)
    if 'ghost_slug' not in columns:
        op.add_column('posts', sa.Column('ghost_slug', sa.Text(), nullable=True))
    
    # Check and create unique constraints
    constraints = [const['name'] for const in inspector.get_unique_constraints('posts')]
    
    if 'uq_posts_ghost_post_id' not in constraints:
        # Create unique constraint for ghost_post_id (nullable unique)
        op.create_unique_constraint('uq_posts_ghost_post_id', 'posts', ['ghost_post_id'])
    
    # Ensure all required indexes exist as per design document
    indexes = [idx['name'] for idx in inspector.get_indexes('posts')]
    
    # idx_posts_reddit_post_id (unique)
    if 'idx_posts_reddit_post_id' not in indexes:
        op.create_index('idx_posts_reddit_post_id', 'posts', ['reddit_post_id'], unique=True)
    
    # idx_posts_created_ts
    if 'idx_posts_created_ts' not in indexes:
        op.create_index('idx_posts_created_ts', 'posts', ['created_ts'])
    
    # idx_posts_subreddit
    if 'idx_posts_subreddit' not in indexes:
        op.create_index('idx_posts_subreddit', 'posts', ['subreddit'])
    
    # Ensure processing_logs has required index
    try:
        processing_logs_indexes = [idx['name'] for idx in inspector.get_indexes('processing_logs')]
        if 'idx_processing_logs_post_id' not in processing_logs_indexes:
            op.create_index('idx_processing_logs_post_id', 'processing_logs', ['post_id'])
    except Exception:
        # Table might not exist yet, skip
        pass
    
    # Ensure token_usage has required index
    try:
        token_usage_indexes = [idx['name'] for idx in inspector.get_indexes('token_usage')]
        if 'idx_token_usage_created_at' not in token_usage_indexes:
            op.create_index('idx_token_usage_created_at', 'token_usage', ['created_at'])
    except Exception:
        # Table might not exist yet, skip
        pass
    
    # Ensure updated_at trigger exists
    if connection.dialect.name == 'postgresql':
        # Check if trigger function exists
        result = connection.execute(sa.text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_proc 
                WHERE proname = 'update_updated_at_column'
            )
        """))
        
        if not result.scalar():
            # Create trigger function
            op.execute('''
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $ language 'plpgsql';
            ''')
        
        # Check if trigger exists
        result = connection.execute(sa.text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger 
                WHERE tgname = 'update_posts_updated_at'
            )
        """))
        
        if not result.scalar():
            # Create trigger
            op.execute('''
                CREATE TRIGGER update_posts_updated_at 
                BEFORE UPDATE ON posts
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            ''')


def downgrade() -> None:
    """
    Downgrade MVP schema changes
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Drop trigger and function for PostgreSQL
    if connection.dialect.name == 'postgresql':
        op.execute('DROP TRIGGER IF EXISTS update_posts_updated_at ON posts')
        op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')
    
    # Drop indexes
    indexes = [idx['name'] for idx in inspector.get_indexes('posts')]
    
    if 'idx_posts_subreddit' in indexes:
        op.drop_index('idx_posts_subreddit', table_name='posts')
    if 'idx_posts_created_ts' in indexes:
        op.drop_index('idx_posts_created_ts', table_name='posts')
    if 'idx_posts_reddit_post_id' in indexes:
        op.drop_index('idx_posts_reddit_post_id', table_name='posts')
    
    # Drop processing_logs index
    try:
        processing_logs_indexes = [idx['name'] for idx in inspector.get_indexes('processing_logs')]
        if 'idx_processing_logs_post_id' in processing_logs_indexes:
            op.drop_index('idx_processing_logs_post_id', table_name='processing_logs')
    except Exception:
        pass
    
    # Drop token_usage index
    try:
        token_usage_indexes = [idx['name'] for idx in inspector.get_indexes('token_usage')]
        if 'idx_token_usage_created_at' in token_usage_indexes:
            op.drop_index('idx_token_usage_created_at', table_name='token_usage')
    except Exception:
        pass
    
    # Drop unique constraints
    constraints = [const['name'] for const in inspector.get_unique_constraints('posts')]
    if 'uq_posts_ghost_post_id' in constraints:
        op.drop_constraint('uq_posts_ghost_post_id', 'posts', type_='unique')
    
    # Drop columns
    columns = [col['name'] for col in inspector.get_columns('posts')]
    if 'ghost_slug' in columns:
        op.drop_column('posts', 'ghost_slug')
    if 'ghost_post_id' in columns:
        op.drop_column('posts', 'ghost_post_id')