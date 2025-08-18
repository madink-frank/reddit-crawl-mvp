"""add missing post columns url selftext

Revision ID: add_missing_columns
Revises: df0754d14ef4
Create Date: 2025-08-13 04:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_missing_columns'
down_revision: Union[str, None] = 'df0754d14ef4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to posts table
    op.add_column('posts', sa.Column('url', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('selftext', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('content', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('author', sa.String(100), nullable=True))
    op.add_column('posts', sa.Column('status', sa.String(20), nullable=False, server_default='collected'))
    op.add_column('posts', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('processing_attempts', sa.Integer(), nullable=False, server_default='0'))
    
    # Add check constraint for status
    op.create_check_constraint(
        'check_post_status',
        'posts',
        "status IN ('collected', 'processing', 'processed', 'published', 'failed')"
    )
    
    # Add check constraint for processing attempts
    op.create_check_constraint(
        'check_processing_attempts_positive',
        'posts',
        "processing_attempts >= 0"
    )
    
    # Add indexes for new columns
    op.create_index('idx_posts_status', 'posts', ['status'])
    op.create_index('idx_posts_published_at', 'posts', ['published_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_posts_published_at', 'posts')
    op.drop_index('idx_posts_status', 'posts')
    
    # Drop check constraints
    op.drop_constraint('check_processing_attempts_positive', 'posts', type_='check')
    op.drop_constraint('check_post_status', 'posts', type_='check')
    
    # Drop columns
    op.drop_column('posts', 'processing_attempts')
    op.drop_column('posts', 'published_at')
    op.drop_column('posts', 'status')
    op.drop_column('posts', 'author')
    op.drop_column('posts', 'content')
    op.drop_column('posts', 'selftext')
    op.drop_column('posts', 'url')