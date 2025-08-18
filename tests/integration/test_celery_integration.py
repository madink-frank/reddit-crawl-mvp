"""
Integration tests for Celery tasks
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, Mock
from datetime import datetime, timedelta
from celery import Celery
from celery.result import AsyncResult

from app.celery_app import celery_app
from workers.collector.tasks import collect_reddit_posts
from workers.nlp_pipeline.tasks import process_content_with_ai
from workers.publisher.tasks import publish_to_ghost


class TestCeleryIntegration:
    """Test Celery task integration"""
    
    @pytest.fixture
    def celery_test_app(self):
        """Create test Celery app"""
        test_app = Celery('test_app')
        test_app.config_from_object({
            'broker_url': 'memory://',
            'result_backend': 'cache+memory://',
            'task_always_eager': True,
            'task_eager_propagates': True,
        })
        return test_app
    
    def test_collect_reddit_posts_task(self):
        """Test Reddit collection task"""
        with patch('workers.collector.reddit_client.RedditClient') as mock_client:
            with patch('workers.collector.tasks.get_db_session') as mock_db:
                # Mock Reddit client
                mock_reddit = Mock()
                mock_reddit.authenticate.return_value = True
                mock_reddit.collect_posts.return_value = [
                    {
                        'id': 'test_post_1',
                        'title': 'Test Post 1',
                        'subreddit': 'technology',
                        'score': 150,
                        'comments': 45,
                        'created_utc': datetime.utcnow().timestamp(),
                        'url': 'https://reddit.com/test1',
                        'content': 'Test content 1',
                        'author': 'test_author_1'
                    },
                    {
                        'id': 'test_post_2',
                        'title': 'Test Post 2',
                        'subreddit': 'technology',
                        'score': 200,
                        'comments': 60,
                        'created_utc': datetime.utcnow().timestamp(),
                        'url': 'https://reddit.com/test2',
                        'content': 'Test content 2',
                        'author': 'test_author_2'
                    }
                ]
                mock_client.return_value = mock_reddit
                
                # Mock database session
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                
                # Execute task
                result = collect_reddit_posts.apply(
                    args=[['technology'], 'hot', 50]
                )
                
                # Verify task completed successfully
                assert result.successful()
                task_result = result.get()
                
                assert task_result['status'] == 'completed'
                assert task_result['posts_collected'] == 2
                assert len(task_result['post_ids']) == 2
                
                # Verify Reddit client was called
                mock_reddit.authenticate.assert_called_once()
                mock_reddit.collect_posts.assert_called_once_with(
                    subreddits=['technology'],
                    sort_type='hot',
                    limit=50
                )
                
                # Verify database operations
                assert mock_session.add_all.called
                assert mock_session.commit.called
    
    def test_process_content_with_ai_task(self):
        """Test AI content processing task"""
        with patch('workers.nlp_pipeline.openai_client.OpenAIClient') as mock_openai:
            with patch('workers.nlp_pipeline.bertopic_client.BERTopicClient') as mock_bertopic:
                with patch('workers.nlp_pipeline.tasks.get_db_session') as mock_db:
                    # Mock OpenAI client
                    mock_openai_instance = Mock()
                    mock_openai_instance.generate_summary.return_value = {
                        'summary': '이것은 테스트 요약입니다.',
                        'input_tokens': 100,
                        'output_tokens': 50,
                        'cost_usd': 0.001
                    }
                    mock_openai_instance.analyze_content.return_value = {
                        'analysis': {
                            'pain_points': [{'issue': '느린 성능', 'severity': 'high'}],
                            'product_ideas': [{'idea': '모바일 앱', 'priority': 'medium'}]
                        },
                        'input_tokens': 200,
                        'output_tokens': 100,
                        'cost_usd': 0.002
                    }
                    mock_openai.return_value = mock_openai_instance
                    
                    # Mock BERTopic client
                    mock_bertopic_instance = Mock()
                    mock_bertopic_instance.extract_keywords.return_value = {
                        'keywords': [
                            {'word': 'technology', 'score': 0.9},
                            {'word': 'performance', 'score': 0.8}
                        ]
                    }
                    mock_bertopic.return_value = mock_bertopic_instance
                    
                    # Mock database session and post
                    mock_session = Mock()
                    mock_post = Mock()
                    mock_post.id = 'test_post_1'
                    mock_post.title = 'Test Post'
                    mock_post.content = 'Test content about technology and performance'
                    mock_post.subreddit = 'technology'
                    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                    mock_db.return_value.__enter__.return_value = mock_session
                    
                    # Execute task
                    result = process_content_with_ai.apply(
                        args=['test_post_1']
                    )
                    
                    # Verify task completed successfully
                    assert result.successful()
                    task_result = result.get()
                    
                    assert task_result['status'] == 'completed'
                    assert task_result['post_id'] == 'test_post_1'
                    assert 'summary_ko' in task_result
                    assert 'topic_tags' in task_result
                    assert 'pain_points' in task_result
                    assert 'product_ideas' in task_result
                    
                    # Verify AI clients were called
                    mock_openai_instance.generate_summary.assert_called_once()
                    mock_openai_instance.analyze_content.assert_called_once()
                    mock_bertopic_instance.extract_keywords.assert_called_once()
                    
                    # Verify database updates
                    assert mock_session.commit.called
    
    def test_publish_to_ghost_task(self):
        """Test Ghost publishing task"""
        with patch('workers.publisher.ghost_client.GhostClient') as mock_ghost:
            with patch('workers.publisher.template_engine.TemplateEngine') as mock_template:
                with patch('workers.publisher.tasks.get_db_session') as mock_db:
                    # Mock Ghost client
                    mock_ghost_instance = Mock()
                    mock_ghost_instance.create_post.return_value = {
                        'id': 'ghost_post_123',
                        'title': 'Test Post',
                        'url': 'https://ghost.example.com/test-post/',
                        'status': 'published'
                    }
                    mock_ghost.return_value = mock_ghost_instance
                    
                    # Mock template engine
                    mock_template_instance = Mock()
                    mock_template_instance.render_article.return_value = '<h1>Test Post</h1><p>Content</p>'
                    mock_template.return_value = mock_template_instance
                    
                    # Mock database session and post
                    mock_session = Mock()
                    mock_post = Mock()
                    mock_post.id = 'test_post_1'
                    mock_post.title = 'Test Post'
                    mock_post.summary_ko = '테스트 요약'
                    mock_post.topic_tag = 'technology,ai'
                    mock_post.pain_points = {'main_issues': ['slow performance']}
                    mock_post.product_ideas = {'suggestions': ['mobile app']}
                    mock_post.status = 'processed'
                    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                    mock_db.return_value.__enter__.return_value = mock_session
                    
                    # Execute task
                    result = publish_to_ghost.apply(
                        args=['test_post_1']
                    )
                    
                    # Verify task completed successfully
                    assert result.successful()
                    task_result = result.get()
                    
                    assert task_result['status'] == 'completed'
                    assert task_result['post_id'] == 'test_post_1'
                    assert task_result['ghost_id'] == 'ghost_post_123'
                    assert task_result['ghost_url'] == 'https://ghost.example.com/test-post/'
                    
                    # Verify Ghost client was called
                    mock_ghost_instance.create_post.assert_called_once()
                    
                    # Verify template engine was called
                    mock_template_instance.render_article.assert_called_once()
                    
                    # Verify database updates
                    assert mock_session.commit.called
    
    def test_task_chain_integration(self):
        """Test chaining tasks together"""
        with patch('workers.collector.reddit_client.RedditClient') as mock_reddit_client:
            with patch('workers.nlp_pipeline.openai_client.OpenAIClient') as mock_openai:
                with patch('workers.nlp_pipeline.bertopic_client.BERTopicClient') as mock_bertopic:
                    with patch('workers.publisher.ghost_client.GhostClient') as mock_ghost:
                        with patch('workers.collector.tasks.get_db_session') as mock_db1:
                            with patch('workers.nlp_pipeline.tasks.get_db_session') as mock_db2:
                                with patch('workers.publisher.tasks.get_db_session') as mock_db3:
                                    # Setup mocks for collection
                                    mock_reddit = Mock()
                                    mock_reddit.authenticate.return_value = True
                                    mock_reddit.collect_posts.return_value = [{
                                        'id': 'chain_test_1',
                                        'title': 'Chain Test Post',
                                        'subreddit': 'technology',
                                        'score': 150,
                                        'comments': 45,
                                        'created_utc': datetime.utcnow().timestamp(),
                                        'url': 'https://reddit.com/chain_test',
                                        'content': 'Chain test content',
                                        'author': 'chain_author'
                                    }]
                                    mock_reddit_client.return_value = mock_reddit
                                    
                                    # Setup mocks for processing
                                    mock_openai_instance = Mock()
                                    mock_openai_instance.generate_summary.return_value = {
                                        'summary': '체인 테스트 요약',
                                        'input_tokens': 100,
                                        'output_tokens': 50,
                                        'cost_usd': 0.001
                                    }
                                    mock_openai_instance.analyze_content.return_value = {
                                        'analysis': {
                                            'pain_points': [{'issue': '체인 문제', 'severity': 'medium'}],
                                            'product_ideas': [{'idea': '체인 솔루션', 'priority': 'high'}]
                                        },
                                        'input_tokens': 200,
                                        'output_tokens': 100,
                                        'cost_usd': 0.002
                                    }
                                    mock_openai.return_value = mock_openai_instance
                                    
                                    mock_bertopic_instance = Mock()
                                    mock_bertopic_instance.extract_keywords.return_value = {
                                        'keywords': [{'word': 'chain', 'score': 0.9}]
                                    }
                                    mock_bertopic.return_value = mock_bertopic_instance
                                    
                                    # Setup mocks for publishing
                                    mock_ghost_instance = Mock()
                                    mock_ghost_instance.create_post.return_value = {
                                        'id': 'ghost_chain_123',
                                        'title': 'Chain Test Post',
                                        'url': 'https://ghost.example.com/chain-test/',
                                        'status': 'published'
                                    }
                                    mock_ghost.return_value = mock_ghost_instance
                                    
                                    # Setup database mocks
                                    mock_session1 = Mock()
                                    mock_session2 = Mock()
                                    mock_session3 = Mock()
                                    
                                    mock_db1.return_value.__enter__.return_value = mock_session1
                                    mock_db2.return_value.__enter__.return_value = mock_session2
                                    mock_db3.return_value.__enter__.return_value = mock_session3
                                    
                                    # Mock post for processing and publishing
                                    mock_post = Mock()
                                    mock_post.id = 'chain_test_1'
                                    mock_post.title = 'Chain Test Post'
                                    mock_post.content = 'Chain test content'
                                    mock_post.subreddit = 'technology'
                                    mock_post.status = 'processed'
                                    mock_post.summary_ko = '체인 테스트 요약'
                                    mock_post.topic_tag = 'chain,technology'
                                    
                                    mock_session2.query.return_value.filter_by.return_value.first.return_value = mock_post
                                    mock_session3.query.return_value.filter_by.return_value.first.return_value = mock_post
                                    
                                    # Execute task chain
                                    # 1. Collect posts
                                    collect_result = collect_reddit_posts.apply(
                                        args=[['technology'], 'hot', 10]
                                    )
                                    
                                    assert collect_result.successful()
                                    collect_data = collect_result.get()
                                    assert collect_data['posts_collected'] == 1
                                    
                                    # 2. Process content
                                    process_result = process_content_with_ai.apply(
                                        args=['chain_test_1']
                                    )
                                    
                                    assert process_result.successful()
                                    process_data = process_result.get()
                                    assert process_data['post_id'] == 'chain_test_1'
                                    
                                    # 3. Publish to Ghost
                                    publish_result = publish_to_ghost.apply(
                                        args=['chain_test_1']
                                    )
                                    
                                    assert publish_result.successful()
                                    publish_data = publish_result.get()
                                    assert publish_data['ghost_id'] == 'ghost_chain_123'
    
    def test_task_error_handling(self):
        """Test task error handling and retries"""
        with patch('workers.collector.reddit_client.RedditClient') as mock_client:
            with patch('workers.collector.tasks.get_db_session') as mock_db:
                # Mock Reddit client to raise an exception
                mock_reddit = Mock()
                mock_reddit.authenticate.side_effect = Exception("Reddit API error")
                mock_client.return_value = mock_reddit
                
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                
                # Execute task (should fail)
                result = collect_reddit_posts.apply(
                    args=[['technology'], 'hot', 50]
                )
                
                # Verify task failed
                assert result.failed()
                
                # Verify error information
                with pytest.raises(Exception) as exc_info:
                    result.get(propagate=True)
                
                assert "Reddit API error" in str(exc_info.value)
    
    def test_task_timeout_handling(self):
        """Test task timeout handling"""
        with patch('workers.nlp_pipeline.openai_client.OpenAIClient') as mock_openai:
            with patch('workers.nlp_pipeline.tasks.get_db_session') as mock_db:
                # Mock OpenAI client to simulate timeout
                mock_openai_instance = Mock()
                mock_openai_instance.generate_summary.side_effect = TimeoutError("Request timeout")
                mock_openai.return_value = mock_openai_instance
                
                # Mock database session and post
                mock_session = Mock()
                mock_post = Mock()
                mock_post.id = 'timeout_test_1'
                mock_post.title = 'Timeout Test Post'
                mock_post.content = 'Test content'
                mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                mock_db.return_value.__enter__.return_value = mock_session
                
                # Execute task (should handle timeout)
                result = process_content_with_ai.apply(
                    args=['timeout_test_1']
                )
                
                # Verify task failed due to timeout
                assert result.failed()
                
                with pytest.raises(TimeoutError):
                    result.get(propagate=True)
    
    def test_task_progress_tracking(self):
        """Test task progress tracking"""
        with patch('workers.collector.reddit_client.RedditClient') as mock_client:
            with patch('workers.collector.tasks.get_db_session') as mock_db:
                # Mock Reddit client with progress updates
                mock_reddit = Mock()
                mock_reddit.authenticate.return_value = True
                
                # Simulate collecting multiple posts with progress
                posts_data = []
                for i in range(5):
                    posts_data.append({
                        'id': f'progress_test_{i}',
                        'title': f'Progress Test Post {i}',
                        'subreddit': 'technology',
                        'score': 100 + i * 10,
                        'comments': 20 + i * 5,
                        'created_utc': datetime.utcnow().timestamp(),
                        'url': f'https://reddit.com/progress_test_{i}',
                        'content': f'Progress test content {i}',
                        'author': f'progress_author_{i}'
                    })
                
                mock_reddit.collect_posts.return_value = posts_data
                mock_client.return_value = mock_reddit
                
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                
                # Execute task
                result = collect_reddit_posts.apply(
                    args=[['technology'], 'hot', 50]
                )
                
                # Verify task completed with progress information
                assert result.successful()
                task_result = result.get()
                
                assert task_result['status'] == 'completed'
                assert task_result['posts_collected'] == 5
                assert len(task_result['post_ids']) == 5
                
                # Verify all posts were processed
                for i in range(5):
                    assert f'progress_test_{i}' in task_result['post_ids']


if __name__ == "__main__":
    pytest.main([__file__])