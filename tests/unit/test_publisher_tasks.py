"""
Unit tests for Publisher Tasks
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

from workers.publisher.tasks import (
    publish_to_ghost,
    republish_to_ghost,
    batch_publish_to_ghost,
    _publish_to_ghost_async,
    _republish_to_ghost_async,
    _batch_publish_to_ghost_async,
    update_post_status,
    log_processing_step,
    rollback_ghost_post,
    PublishingError,
    PublishingRollbackError
)


class TestPublisherTasks:
    """Test publisher task functionality"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database"""
        database = Mock()
        session = AsyncMock()
        
        # Mock the async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        database.session.return_value = async_context
        
        return database, session
    
    @pytest.fixture
    def mock_ghost_client(self):
        """Mock Ghost client"""
        client = AsyncMock()
        client.create_post.return_value = {
            'id': 'ghost_123',
            'url': 'https://blog.example.com/test-post/'
        }
        client.delete_post.return_value = True
        client.close.return_value = None
        return client
    
    @pytest.fixture
    def mock_template_engine(self):
        """Mock template engine"""
        engine = Mock()
        engine.validate_template_data.return_value = {'errors': [], 'warnings': []}
        engine.render_template.return_value = '<article><h1>Test Post</h1><p>Content</p></article>'
        engine._detect_template_type.return_value = Mock(value='article')
        return engine
    
    @pytest.fixture
    def mock_image_handler(self):
        """Mock image handler"""
        handler = AsyncMock()
        handler.process_content_images.return_value = (
            'Updated content with CDN URLs',
            {'https://reddit.com/img1.jpg': 'https://cdn.ghost.io/img1.jpg'}
        )
        handler.get_feature_image.return_value = 'https://cdn.ghost.io/feature.jpg'
        handler.close.return_value = None
        return handler
    
    @pytest.fixture
    def mock_metadata_processor(self):
        """Mock metadata processor"""
        processor = AsyncMock()
        processor.process_post_metadata.return_value = {
            'tags': ['ai', 'tech', 'reddit'],
            'meta_title': 'Test Post',
            'meta_description': 'Test description',
            'og_title': 'Test Post',
            'og_description': 'Test description',
            'twitter_title': 'Test Post',
            'twitter_description': 'Test description',
            'activitypub': {
                'activitypub_content': 'Test content for ActivityPub',
                'hashtags': ['#ai', '#tech'],
                'visibility': 'public'
            }
        }
        processor.validate_metadata.return_value = {'errors': [], 'warnings': []}
        return processor
    
    @pytest.fixture
    def sample_post_data(self):
        """Sample post data"""
        return {
            'id': 'test_post_123',
            'title': 'Test Reddit Post',
            'content': 'This is test content with ![image](https://reddit.com/img1.jpg)',
            'summary_ko': '테스트 게시글입니다',
            'subreddit': 'technology',
            'status': 'processed',
            'url': 'https://reddit.com/r/technology/test',
            'score': 150,
            'comments': 25,
            'author': 'test_user'
        }
    
    @pytest.mark.asyncio
    async def test_log_processing_step(self, mock_database):
        """Test logging processing step"""
        database, session = mock_database
        
        with patch('workers.publisher.tasks.get_database', return_value=database):
            await log_processing_step(
                post_id='test_123',
                service_name='ghost_publisher',
                status='completed',
                processing_time_ms=1500
            )
            
            session.add.assert_called_once()
            session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_post_status(self, mock_database, sample_post_data):
        """Test updating post status"""
        database, session = mock_database
        
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchone.return_value = Mock(_mapping=sample_post_data)
        session.execute.return_value = mock_result
        
        with patch('workers.publisher.tasks.get_database', return_value=database):
            await update_post_status('test_123', 'publishing', ghost_id='ghost_123')
            
            # Should execute SELECT and UPDATE queries
            assert session.execute.call_count == 2
            session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_post_status_not_found(self, mock_database):
        """Test updating post status when post not found"""
        database, session = mock_database
        
        # Mock empty result
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        session.execute.return_value = mock_result
        
        with patch('workers.publisher.tasks.get_database', return_value=database):
            with pytest.raises(PublishingError, match="Post test_123 not found"):
                await update_post_status('test_123', 'publishing')
    
    @pytest.mark.asyncio
    async def test_rollback_ghost_post_success(self, mock_ghost_client):
        """Test successful Ghost post rollback"""
        await rollback_ghost_post(mock_ghost_client, 'ghost_123', 'post_123')
        
        mock_ghost_client.delete_post.assert_called_once_with('ghost_123')
    
    @pytest.mark.asyncio
    async def test_rollback_ghost_post_failure(self, mock_ghost_client):
        """Test Ghost post rollback failure"""
        mock_ghost_client.delete_post.side_effect = Exception("Delete failed")
        
        with pytest.raises(PublishingRollbackError, match="Failed to rollback Ghost post"):
            await rollback_ghost_post(mock_ghost_client, 'ghost_123', 'post_123')
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_async_success(
        self, 
        mock_database, 
        mock_ghost_client,
        mock_template_engine,
        mock_image_handler,
        mock_metadata_processor,
        sample_post_data
    ):
        """Test successful async Ghost publishing"""
        database, session = mock_database
        
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchone.return_value = Mock(_mapping=sample_post_data)
        session.execute.return_value = mock_result
        
        with patch('workers.publisher.tasks.get_database', return_value=database), \
             patch('workers.publisher.tasks.get_ghost_client', return_value=mock_ghost_client), \
             patch('workers.publisher.tasks.get_template_engine', return_value=mock_template_engine), \
             patch('workers.publisher.tasks.get_image_handler', return_value=mock_image_handler), \
             patch('workers.publisher.tasks.get_metadata_processor', return_value=mock_metadata_processor):
            
            result = await _publish_to_ghost_async('test_123', None)
            
            # Verify result structure
            assert result['post_id'] == 'test_123'
            assert result['ghost_id'] == 'ghost_123'
            assert result['ghost_url'] == 'https://blog.example.com/test-post/'
            assert result['images_processed'] == 1
            assert result['tags_applied'] == 3
            assert result['template_used'] == 'article'
            assert 'published_at' in result
            
            # Verify all components were called
            mock_image_handler.process_content_images.assert_called_once()
            mock_image_handler.get_feature_image.assert_called_once()
            mock_metadata_processor.process_post_metadata.assert_called_once()
            mock_template_engine.render_template.assert_called_once()
            mock_ghost_client.create_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_async_post_not_found(self, mock_database):
        """Test async publishing with post not found"""
        database, session = mock_database
        
        # Mock empty result
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        session.execute.return_value = mock_result
        
        with patch('workers.publisher.tasks.get_database', return_value=database):
            with pytest.raises(PublishingError, match="Post test_123 not found"):
                await _publish_to_ghost_async('test_123', None)
    
    @pytest.mark.asyncio
    async def test_publish_to_ghost_async_with_rollback(
        self,
        mock_database,
        mock_ghost_client,
        mock_template_engine,
        mock_image_handler,
        mock_metadata_processor,
        sample_post_data
    ):
        """Test async publishing with error and rollback"""
        database, session = mock_database
        
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchone.return_value = Mock(_mapping=sample_post_data)
        session.execute.return_value = mock_result
        
        # Make Ghost client fail after post creation
        mock_ghost_client.create_post.return_value = {
            'id': 'ghost_123',
            'url': 'https://blog.example.com/test-post/'
        }
        
        # Mock a failure during database update
        session.execute.side_effect = [
            mock_result,  # First call succeeds (fetch post)
            None,         # Second call succeeds (update to publishing)
            Exception("Database error")  # Third call fails (final update)
        ]
        
        with patch('workers.publisher.tasks.get_database', return_value=database), \
             patch('workers.publisher.tasks.get_ghost_client', return_value=mock_ghost_client), \
             patch('workers.publisher.tasks.get_template_engine', return_value=mock_template_engine), \
             patch('workers.publisher.tasks.get_image_handler', return_value=mock_image_handler), \
             patch('workers.publisher.tasks.get_metadata_processor', return_value=mock_metadata_processor):
            
            with pytest.raises(Exception, match="Database error"):
                await _publish_to_ghost_async('test_123', None)
            
            # Verify rollback was attempted (Ghost post should be deleted)
            mock_ghost_client.delete_post.assert_called_once_with('ghost_123')
    
    @pytest.mark.asyncio
    async def test_republish_to_ghost_async_not_published(self, mock_database, sample_post_data):
        """Test republishing post that's not published"""
        database, session = mock_database
        
        # Mock post that's not published
        unpublished_post = sample_post_data.copy()
        unpublished_post['status'] = 'processed'
        unpublished_post['ghost_id'] = None
        
        mock_result = Mock()
        mock_result.fetchone.return_value = Mock(_mapping=unpublished_post)
        session.execute.return_value = mock_result
        
        with patch('workers.publisher.tasks.get_database', return_value=database), \
             patch('workers.publisher.tasks._publish_to_ghost_async') as mock_publish:
            
            mock_publish.return_value = {'post_id': 'test_123', 'status': 'published'}
            
            result = await _republish_to_ghost_async('test_123', False)
            
            # Should call regular publish function
            mock_publish.assert_called_once_with('test_123', None)
    
    @pytest.mark.asyncio
    async def test_republish_to_ghost_async_already_published_no_force(self, mock_database, sample_post_data):
        """Test republishing already published post without force"""
        database, session = mock_database
        
        # Mock published post
        published_post = sample_post_data.copy()
        published_post['status'] = 'published'
        published_post['ghost_id'] = 'ghost_123'
        
        mock_result = Mock()
        mock_result.fetchone.return_value = Mock(_mapping=published_post)
        session.execute.return_value = mock_result
        
        with patch('workers.publisher.tasks.get_database', return_value=database):
            result = await _republish_to_ghost_async('test_123', False)
            
            assert result['action'] == 'skipped'
            assert 'Already published' in result['reason']
    
    @pytest.mark.asyncio
    async def test_republish_to_ghost_async_force_republish(
        self, 
        mock_database, 
        mock_ghost_client,
        sample_post_data
    ):
        """Test force republishing already published post"""
        database, session = mock_database
        
        # Mock published post
        published_post = sample_post_data.copy()
        published_post['status'] = 'published'
        published_post['ghost_id'] = 'ghost_123'
        
        mock_result = Mock()
        mock_result.fetchone.return_value = Mock(_mapping=published_post)
        session.execute.return_value = mock_result
        
        with patch('workers.publisher.tasks.get_database', return_value=database), \
             patch('workers.publisher.tasks.get_ghost_client', return_value=mock_ghost_client), \
             patch('workers.publisher.tasks.update_post_status') as mock_update, \
             patch('workers.publisher.tasks._publish_to_ghost_async') as mock_publish:
            
            mock_publish.return_value = {'post_id': 'test_123', 'status': 'published'}
            
            result = await _republish_to_ghost_async('test_123', True)
            
            # Should delete existing Ghost post
            mock_ghost_client.delete_post.assert_called_once_with('ghost_123')
            
            # Should reset post status
            mock_update.assert_called_once_with('test_123', 'processed', ghost_id=None, ghost_url=None)
            
            # Should call regular publish function
            mock_publish.assert_called_once_with('test_123', None)
    
    @pytest.mark.asyncio
    async def test_batch_publish_to_ghost_async_success(self):
        """Test successful batch publishing"""
        post_ids = ['post_1', 'post_2', 'post_3']
        
        # Mock successful publishing for all posts
        async def mock_publish(post_id, task_instance):
            return {
                'post_id': post_id,
                'ghost_id': f'ghost_{post_id}',
                'ghost_url': f'https://blog.example.com/{post_id}/'
            }
        
        with patch('workers.publisher.tasks._publish_to_ghost_async', side_effect=mock_publish):
            result = await _batch_publish_to_ghost_async(post_ids, 2, None)
            
            assert result['total_posts'] == 3
            assert result['successful_count'] == 3
            assert result['failed_count'] == 0
            assert len(result['successful_posts']) == 3
            assert len(result['failed_posts']) == 0
    
    @pytest.mark.asyncio
    async def test_batch_publish_to_ghost_async_partial_failure(self):
        """Test batch publishing with some failures"""
        post_ids = ['post_1', 'post_2', 'post_3']
        
        # Mock mixed success/failure
        async def mock_publish(post_id, task_instance):
            if post_id == 'post_2':
                raise Exception(f"Failed to publish {post_id}")
            return {
                'post_id': post_id,
                'ghost_id': f'ghost_{post_id}',
                'ghost_url': f'https://blog.example.com/{post_id}/'
            }
        
        with patch('workers.publisher.tasks._publish_to_ghost_async', side_effect=mock_publish):
            result = await _batch_publish_to_ghost_async(post_ids, 2, None)
            
            assert result['total_posts'] == 3
            assert result['successful_count'] == 2
            assert result['failed_count'] == 1
            assert len(result['successful_posts']) == 2
            assert len(result['failed_posts']) == 1
            assert result['failed_posts'][0]['post_id'] == 'post_2'
    
    def test_publish_to_ghost_task_success(self):
        """Test Celery task wrapper for publishing"""
        expected_result = {
            'post_id': 'test_123',
            'ghost_id': 'ghost_123',
            'ghost_url': 'https://blog.example.com/test-post/'
        }
        
        with patch('workers.publisher.tasks.asyncio.run') as mock_run:
            mock_run.return_value = expected_result
            
            # Call the task function directly (not as Celery task)
            from workers.publisher.tasks import publish_to_ghost as publish_func
            
            # Create a mock task instance
            mock_task = Mock()
            mock_task.request.id = 'task_123'
            mock_task.request.retries = 0
            mock_task.max_retries = 5
            mock_task.default_retry_delay = 60
            
            result = publish_func.__wrapped__(mock_task, 'test_123')
            
            assert result == expected_result
            mock_run.assert_called()
    
    def test_publish_to_ghost_task_retry(self):
        """Test Celery task retry logic"""
        from workers.publisher.ghost_client import GhostAPIError
        from workers.publisher.tasks import publish_to_ghost as publish_func
        
        mock_task = Mock()
        mock_task.request.id = 'task_123'
        mock_task.request.retries = 2
        mock_task.max_retries = 5
        mock_task.default_retry_delay = 60
        
        with patch('workers.publisher.tasks.asyncio.run') as mock_run:
            mock_run.side_effect = GhostAPIError("API Error")
            
            # Should raise retry
            mock_task.retry.side_effect = Exception("Retry called")
            
            with pytest.raises(Exception, match="Retry called"):
                publish_func.__wrapped__(mock_task, 'test_123')
            
            mock_task.retry.assert_called_once()
    
    def test_publish_to_ghost_task_max_retries_exceeded(self):
        """Test Celery task when max retries exceeded"""
        from workers.publisher.ghost_client import GhostAPIError
        from workers.publisher.tasks import publish_to_ghost as publish_func
        
        mock_task = Mock()
        mock_task.request.id = 'task_123'
        mock_task.request.retries = 5
        mock_task.max_retries = 5
        mock_task.default_retry_delay = 60
        
        with patch('workers.publisher.tasks.asyncio.run') as mock_run:
            mock_run.side_effect = GhostAPIError("API Error")
            
            with pytest.raises(PublishingError, match="Failed to publish to Ghost"):
                publish_func.__wrapped__(mock_task, 'test_123')
    
    def test_republish_to_ghost_task(self):
        """Test Celery task wrapper for republishing"""
        from workers.publisher.tasks import republish_to_ghost as republish_func
        
        expected_result = {
            'post_id': 'test_123',
            'action': 'republished'
        }
        
        with patch('workers.publisher.tasks.asyncio.run') as mock_run:
            mock_run.return_value = expected_result
            
            mock_task = Mock()
            result = republish_func.__wrapped__(mock_task, 'test_123', force=True)
            
            assert result == expected_result
    
    def test_batch_publish_to_ghost_task(self):
        """Test Celery task wrapper for batch publishing"""
        from workers.publisher.tasks import batch_publish_to_ghost as batch_func
        
        post_ids = ['post_1', 'post_2']
        expected_result = {
            'total_posts': 2,
            'successful_count': 2,
            'failed_count': 0
        }
        
        with patch('workers.publisher.tasks.asyncio.run') as mock_run:
            mock_run.return_value = expected_result
            
            mock_task = Mock()
            result = batch_func.__wrapped__(mock_task, post_ids, max_concurrent=2)
            
            assert result == expected_result