"""mvp_schema_update_uuid_reddit_post_id_takedown

Revision ID: df0754d14ef4
Revises: 9b1648a6a771
Create Date: 2025-08-09 21:10:47.666543

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'df0754d14ef4'
down_revision: Union[str, None] = '9b1648a6a771'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Add new columns to posts table
    op.add_column('posts', sa.Column('reddit_post_id', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('takedown_status', sa.Text(), nullable=False, server_default='active'))
    op.add_column('posts', sa.Column('ghost_post_id', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('ghost_slug', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('content_hash', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('num_comments', sa.Integer(), nullable=True))
    
    # Update existing data: copy comments to num_comments and set reddit_post_id = id
    op.execute('UPDATE posts SET num_comments = comments, reddit_post_id = id')
    
    # Make reddit_post_id and num_comments NOT NULL after data migration
    op.alter_column('posts', 'reddit_post_id', nullable=False)
    op.alter_column('posts', 'num_comments', nullable=False)
    
    # Add new UUID column
    op.add_column('posts', sa.Column('new_id', sa.dialects.postgresql.UUID(), nullable=True, server_default=sa.text('uuid_generate_v4()')))
    
    # Update foreign key references in related tables
    op.add_column('media_files', sa.Column('new_post_id', sa.dialects.postgresql.UUID(), nullable=True))
    op.add_column('processing_logs', sa.Column('new_post_id', sa.dialects.postgresql.UUID(), nullable=True))
    op.add_column('token_usage', sa.Column('new_post_id', sa.dialects.postgresql.UUID(), nullable=True))
    
    # Update foreign key values
    op.execute('''
        UPDATE media_files 
        SET new_post_id = posts.new_id 
        FROM posts 
        WHERE media_files.post_id = posts.id
    ''')
    
    op.execute('''
        UPDATE processing_logs 
        SET new_post_id = posts.new_id 
        FROM posts 
        WHERE processing_logs.post_id = posts.id
    ''')
    
    op.execute('''
        UPDATE token_usage 
        SET new_post_id = posts.new_id 
        FROM posts 
        WHERE token_usage.post_id = posts.id
    ''')
    
    # Drop old foreign key constraints
    op.drop_constraint('media_files_post_id_fkey', 'media_files', type_='foreignkey')
    op.drop_constraint('processing_logs_post_id_fkey', 'processing_logs', type_='foreignkey')
    op.drop_constraint('token_usage_post_id_fkey', 'token_usage', type_='foreignkey')
    
    # Drop old columns
    op.drop_column('media_files', 'post_id')
    op.drop_column('processing_logs', 'post_id')
    op.drop_column('token_usage', 'post_id')
    
    # Rename new columns
    op.alter_column('media_files', 'new_post_id', new_column_name='post_id', nullable=False)
    op.alter_column('processing_logs', 'new_post_id', new_column_name='post_id', nullable=False)
    op.alter_column('token_usage', 'new_post_id', new_column_name='post_id', nullable=False)
    
    # Drop old primary key and id column from posts
    op.drop_constraint('posts_pkey', 'posts', type_='primary')
    op.drop_column('posts', 'id')
    
    # Rename new_id to id and make it primary key
    op.alter_column('posts', 'new_id', new_column_name='id', nullable=False)
    op.create_primary_key('posts_pkey', 'posts', ['id'])
    
    # Add new foreign key constraints
    op.create_foreign_key('media_files_post_id_fkey', 'media_files', 'posts', ['post_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('processing_logs_post_id_fkey', 'processing_logs', 'posts', ['post_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('token_usage_post_id_fkey', 'token_usage', 'posts', ['post_id'], ['id'], ondelete='CASCADE')
    
    # Update tags column to JSONB
    op.alter_column('posts', 'topic_tag', new_column_name='tags', type_=sa.dialects.postgresql.JSONB())
    
    # Drop old comments column
    op.drop_column('posts', 'comments')
    
    # Add new unique constraints and indexes
    op.create_unique_constraint('uq_posts_reddit_post_id', 'posts', ['reddit_post_id'])
    op.create_unique_constraint('uq_posts_ghost_post_id', 'posts', ['ghost_post_id'])
    
    # Add check constraint for takedown_status
    op.create_check_constraint(
        'check_takedown_status',
        'posts',
        "takedown_status IN ('active', 'takedown_pending', 'removed')"
    )
    
    # Add model field to token_usage table
    op.add_column('token_usage', sa.Column('model', sa.Text(), nullable=True))
    
    # Create updated_at trigger function
    op.execute('''
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    ''')
    
    # Create trigger for posts table
    op.execute('''
        CREATE TRIGGER update_posts_updated_at 
        BEFORE UPDATE ON posts
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    ''')


def downgrade() -> None:
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS update_posts_updated_at ON posts')
    op.execute('DROP FUNCTION IF EXISTS update_updated_at_column()')
    
    # Drop new constraints
    op.drop_constraint('check_takedown_status', 'posts', type_='check')
    op.drop_constraint('uq_posts_ghost_post_id', 'posts', type_='unique')
    op.drop_constraint('uq_posts_reddit_post_id', 'posts', type_='unique')
    
    # Add back comments column
    op.add_column('posts', sa.Column('comments', sa.Integer(), nullable=True))
    op.execute('UPDATE posts SET comments = num_comments')
    op.alter_column('posts', 'comments', nullable=False)
    
    # Revert tags column
    op.alter_column('posts', 'tags', new_column_name='topic_tag', type_=sa.String(200))
    
    # Drop model column from token_usage
    op.drop_column('token_usage', 'model')
    
    # Add old string id column
    op.add_column('posts', sa.Column('old_id', sa.String(50), nullable=True))
    op.execute('UPDATE posts SET old_id = reddit_post_id')
    
    # Drop foreign key constraints
    op.drop_constraint('token_usage_post_id_fkey', 'token_usage', type_='foreignkey')
    op.drop_constraint('processing_logs_post_id_fkey', 'processing_logs', type_='foreignkey')
    op.drop_constraint('media_files_post_id_fkey', 'media_files', type_='foreignkey')
    
    # Add old foreign key columns
    op.add_column('token_usage', sa.Column('old_post_id', sa.String(50), nullable=True))
    op.add_column('processing_logs', sa.Column('old_post_id', sa.String(50), nullable=True))
    op.add_column('media_files', sa.Column('old_post_id', sa.String(50), nullable=True))
    
    # Update foreign key values
    op.execute('''
        UPDATE token_usage 
        SET old_post_id = posts.old_id 
        FROM posts 
        WHERE token_usage.post_id = posts.id
    ''')
    
    op.execute('''
        UPDATE processing_logs 
        SET old_post_id = posts.old_id 
        FROM posts 
        WHERE processing_logs.post_id = posts.id
    ''')
    
    op.execute('''
        UPDATE media_files 
        SET old_post_id = posts.old_id 
        FROM posts 
        WHERE media_files.post_id = posts.id
    ''')
    
    # Drop UUID columns
    op.drop_column('token_usage', 'post_id')
    op.drop_column('processing_logs', 'post_id')
    op.drop_column('media_files', 'post_id')
    
    # Rename old columns back
    op.alter_column('token_usage', 'old_post_id', new_column_name='post_id', nullable=False)
    op.alter_column('processing_logs', 'old_post_id', new_column_name='post_id', nullable=False)
    op.alter_column('media_files', 'old_post_id', new_column_name='post_id', nullable=False)
    
    # Drop UUID primary key
    op.drop_constraint('posts_pkey', 'posts', type_='primary')
    op.drop_column('posts', 'id')
    
    # Restore old primary key
    op.alter_column('posts', 'old_id', new_column_name='id', nullable=False)
    op.create_primary_key('posts_pkey', 'posts', ['id'])
    
    # Restore foreign key constraints
    op.create_foreign_key('media_files_post_id_fkey', 'media_files', 'posts', ['post_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('processing_logs_post_id_fkey', 'processing_logs', 'posts', ['post_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('token_usage_post_id_fkey', 'token_usage', 'posts', ['post_id'], ['id'], ondelete='CASCADE')
    
    # Drop new columns
    op.drop_column('posts', 'content_hash')
    op.drop_column('posts', 'ghost_slug')
    op.drop_column('posts', 'ghost_post_id')
    op.drop_column('posts', 'takedown_status')
    op.drop_column('posts', 'reddit_post_id')
    op.drop_column('posts', 'num_comments')