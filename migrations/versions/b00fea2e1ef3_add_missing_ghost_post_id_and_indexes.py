"""add_missing_ghost_post_id_and_indexes

Revision ID: b00fea2e1ef3
Revises: add_missing_columns
Create Date: 2025-08-13 04:36:49.297143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b00fea2e1ef3'
down_revision: Union[str, None] = 'add_missing_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if ghost_post_id column exists, if not add it
    # This handles cases where the previous migration might not have included it
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('posts')]
    
    if 'ghost_post_id' not in columns:
        op.add_column('posts', sa.Column('ghost_post_id', sa.Text(), nullable=True))
        op.create_unique_constraint('uq_posts_ghost_post_id', 'posts', ['ghost_post_id'])
    
    # Ensure all required indexes exist
    indexes = [idx['name'] for idx in inspector.get_indexes('posts')]
    
    if 'idx_posts_reddit_post_id' not in indexes:
        op.create_index('idx_posts_reddit_post_id', 'posts', ['reddit_post_id'], unique=True)
    
    if 'idx_posts_created_ts' not in indexes:
        op.create_index('idx_posts_created_ts', 'posts', ['created_ts'])
    
    if 'idx_posts_subreddit' not in indexes:
        op.create_index('idx_posts_subreddit', 'posts', ['subreddit'])
    
    # Ensure processing_logs has required index
    processing_logs_indexes = [idx['name'] for idx in inspector.get_indexes('processing_logs')]
    if 'idx_processing_logs_post_id' not in processing_logs_indexes:
        op.create_index('idx_processing_logs_post_id', 'processing_logs', ['post_id'])
    
    # Ensure token_usage has required index
    token_usage_indexes = [idx['name'] for idx in inspector.get_indexes('token_usage')]
    if 'idx_token_usage_created_at' not in token_usage_indexes:
        op.create_index('idx_token_usage_created_at', 'token_usage', ['created_at'])


def downgrade() -> None:
    # Drop indexes if they exist
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    indexes = [idx['name'] for idx in inspector.get_indexes('posts')]
    if 'idx_posts_subreddit' in indexes:
        op.drop_index('idx_posts_subreddit', table_name='posts')
    if 'idx_posts_created_ts' in indexes:
        op.drop_index('idx_posts_created_ts', table_name='posts')
    if 'idx_posts_reddit_post_id' in indexes:
        op.drop_index('idx_posts_reddit_post_id', table_name='posts')
    
    processing_logs_indexes = [idx['name'] for idx in inspector.get_indexes('processing_logs')]
    if 'idx_processing_logs_post_id' in processing_logs_indexes:
        op.drop_index('idx_processing_logs_post_id', table_name='processing_logs')
    
    token_usage_indexes = [idx['name'] for idx in inspector.get_indexes('token_usage')]
    if 'idx_token_usage_created_at' in token_usage_indexes:
        op.drop_index('idx_token_usage_created_at', table_name='token_usage')
    
    # Drop ghost_post_id column and constraint if they exist
    constraints = [const['name'] for const in inspector.get_unique_constraints('posts')]
    if 'uq_posts_ghost_post_id' in constraints:
        op.drop_constraint('uq_posts_ghost_post_id', 'posts', type_='unique')
    
    columns = [col['name'] for col in inspector.get_columns('posts')]
    if 'ghost_post_id' in columns:
        op.drop_column('posts', 'ghost_post_id')