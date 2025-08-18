"""
Unit tests for API routes
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check_success(self, client):
        """Test successful health check"""
        with patch('app.api.routes.health_mvp.check_database_health') as mock_db:
            with patch('app.api.routes.health_mvp.check_redis_health') as mock_redis:
                with patch('app.api.routes.health_mvp.check_external_apis_health') as mock_apis:
                    mock_db.return_value = {'status': 'healthy', 'response_time_ms': 10}
                    mock_redis.return_value = {'status': 'healthy', 'response_time_ms': 5}
                    mock_apis.return_value = {'reddit': 'healthy', 'openai': 'healthy', 'ghost': 'healthy'}
                    
                    response = client.get("/health")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data['status'] == 'healthy'
                    assert 'services' in data
                    assert data['services']['database']['status'] == 'healthy'
                    assert data['services']['redis']['status'] == 'healthy'
    
    def test_health_check_database_unhealthy(self, client):
        """Test health check with unhealthy database"""
        with patch('app.api.routes.health_mvp.check_database_health') as mock_db:
            with patch('app.api.routes.health_mvp.check_redis_health') as mock_redis:
                with patch('app.api.routes.health_mvp.check_external_apis_health') as mock_apis:
                    mock_db.return_value = {'status': 'unhealthy', 'error': 'Connection failed'}
                    mock_redis.return_value = {'status': 'healthy', 'response_time_ms': 5}
                    mock_apis.return_value = {'reddit': 'healthy', 'openai': 'healthy', 'ghost': 'healthy'}
                    
                    response = client.get("/health")
                    
                    assert response.status_code == 503
                    data = response.json()
                    assert data['status'] == 'unhealthy'
                    assert data['services']['database']['status'] == 'unhealthy'
    
    def test_health_check_redis_unhealthy(self, client):
        """Test health check with unhealthy Redis"""
        with patch('app.api.routes.health_mvp.check_database_health') as mock_db:
            with patch('app.api.routes.health_mvp.check_redis_health') as mock_redis:
                with patch('app.api.routes.health_mvp.check_external_apis_health') as mock_apis:
                    mock_db.return_value = {'status': 'healthy', 'response_time_ms': 10}
                    mock_redis.return_value = {'status': 'unhealthy', 'error': 'Redis connection failed'}
                    mock_apis.return_value = {'reddit': 'healthy', 'openai': 'healthy', 'ghost': 'healthy'}
                    
                    response = client.get("/health")
                    
                    assert response.status_code == 503
                    data = response.json()
                    assert data['status'] == 'unhealthy'
                    assert data['services']['redis']['status'] == 'unhealthy'


class TestMetricsEndpoints:
    """Test metrics endpoints"""
    
    def test_metrics_endpoint_success(self, client):
        """Test successful metrics retrieval"""
        with patch('app.api.routes.metrics_mvp.get_db_session') as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            
            # Mock database queries for metrics
            mock_session.query.return_value.filter.return_value.count.side_effect = [
                100,  # collected posts
                95,   # processed posts
                90,   # published posts
                5     # failed posts
            ]
            
            response = client.get("/metrics")
            
            assert response.status_code == 200
            assert response.headers['content-type'] == 'text/plain; charset=utf-8'
            
            content = response.text
            assert 'reddit_posts_collected_total 100' in content
            assert 'posts_processed_total 95' in content
            assert 'posts_published_total 90' in content
            assert 'processing_failures_total 5' in content
    
    def test_metrics_endpoint_database_error(self, client):
        """Test metrics endpoint with database error"""
        with patch('app.api.routes.metrics_mvp.get_db_session') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            response = client.get("/metrics")
            
            assert response.status_code == 500


class TestStatusEndpoints:
    """Test status monitoring endpoints"""
    
    def test_queue_status_success(self, client):
        """Test successful queue status retrieval"""
        with patch('app.api.routes.status_mvp.current_app') as mock_celery:
            with patch('app.api.routes.status_mvp.redis_client') as mock_redis:
                # Mock Celery inspect
                mock_inspect = Mock()
                mock_celery.control.inspect.return_value = mock_inspect
                mock_inspect.active.return_value = {'worker1': [{'name': 'task1'}]}
                mock_inspect.scheduled.return_value = {'worker1': []}
                
                # Mock Redis queue lengths
                mock_redis.llen.side_effect = [5, 3, 2]  # collect, process, publish queues
                
                response = client.get("/api/v1/status/queues")
                
                assert response.status_code == 200
                data = response.json()
                
                assert 'collect' in data
                assert 'process' in data
                assert 'publish' in data
                assert data['collect']['pending'] == 5
                assert data['process']['pending'] == 3
                assert data['publish']['pending'] == 2
    
    def test_worker_status_success(self, client):
        """Test successful worker status retrieval"""
        with patch('app.api.routes.status_mvp.current_app') as mock_celery:
            # Mock Celery inspect
            mock_inspect = Mock()
            mock_celery.control.inspect.return_value = mock_inspect
            mock_inspect.stats.return_value = {
                'worker1@hostname': {
                    'total': {'tasks.collector.collect_reddit_posts': 50},
                    'rusage': {'utime': 120.5}
                }
            }
            mock_inspect.active.return_value = {
                'worker1@hostname': [{'name': 'current_task'}]
            }
            
            response = client.get("/api/v1/status/workers")
            
            assert response.status_code == 200
            data = response.json()
            
            assert 'worker1@hostname' in data
            worker_data = data['worker1@hostname']
            assert worker_data['status'] == 'online'
            assert worker_data['active_tasks'] == 1
            assert worker_data['processed_tasks'] == 50
    
    def test_queue_status_celery_error(self, client):
        """Test queue status with Celery error"""
        with patch('app.api.routes.status_mvp.current_app') as mock_celery:
            mock_celery.control.inspect.side_effect = Exception("Celery connection failed")
            
            response = client.get("/api/v1/status/queues")
            
            assert response.status_code == 500


class TestTriggerEndpoints:
    """Test manual trigger endpoints"""
    
    def test_trigger_collect_success(self, client):
        """Test successful collection trigger"""
        with patch('app.api.routes.triggers_mvp.collect_reddit_posts') as mock_task:
            mock_task.delay.return_value = Mock(id='task-123')
            
            response = client.post("/api/v1/collect/trigger", json={
                "subreddits": ["technology", "programming"],
                "batch_size": 20
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'triggered'
            assert data['task_id'] == 'task-123'
            assert 'technology' in data['subreddits']
            assert 'programming' in data['subreddits']
    
    def test_trigger_collect_invalid_subreddits(self, client):
        """Test collection trigger with invalid subreddits"""
        response = client.post("/api/v1/collect/trigger", json={
            "subreddits": [],  # Empty list
            "batch_size": 20
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_trigger_process_success(self, client):
        """Test successful processing trigger"""
        with patch('app.api.routes.triggers_mvp.process_content_with_ai') as mock_task:
            mock_task.delay.return_value = Mock(id='task-456')
            
            response = client.post("/api/v1/process/trigger", json={
                "reddit_post_id": "test123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'triggered'
            assert data['task_id'] == 'task-456'
            assert data['reddit_post_id'] == 'test123'
    
    def test_trigger_publish_success(self, client):
        """Test successful publishing trigger"""
        with patch('app.api.routes.triggers_mvp.publish_to_ghost') as mock_task:
            mock_task.delay.return_value = Mock(id='task-789')
            
            response = client.post("/api/v1/publish/trigger", json={
                "reddit_post_id": "test123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'triggered'
            assert data['task_id'] == 'task-789'
            assert data['reddit_post_id'] == 'test123'
    
    def test_trigger_process_missing_post_id(self, client):
        """Test processing trigger with missing post ID"""
        response = client.post("/api/v1/process/trigger", json={})
        
        assert response.status_code == 422  # Validation error


class TestTakedownEndpoints:
    """Test takedown request endpoints"""
    
    def test_takedown_request_success(self, client):
        """Test successful takedown request"""
        with patch('app.api.routes.takedown_mvp.get_db_session') as mock_db:
            with patch('app.api.routes.takedown_mvp.get_ghost_client') as mock_ghost:
                with patch('app.api.routes.takedown_mvp.schedule_deletion') as mock_schedule:
                    # Mock database
                    mock_session = Mock()
                    mock_db.return_value.__enter__.return_value = mock_session
                    
                    mock_post = Mock()
                    mock_post.ghost_post_id = 'ghost-123'
                    mock_post.ghost_url = 'https://blog.example.com/post/'
                    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                    
                    # Mock Ghost client
                    mock_ghost_client = AsyncMock()
                    mock_ghost.return_value = mock_ghost_client
                    mock_ghost_client.unpublish_post.return_value = True
                    
                    # Mock scheduled task
                    mock_schedule.apply_async.return_value = Mock(id='schedule-task-123')
                    
                    response = client.post("/api/v1/takedown/test123", json={
                        "reason": "Copyright violation",
                        "contact_email": "user@example.com"
                    })
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data['status'] == 'unpublished'
                    assert 'deletion scheduled' in data['message']
                    
                    # Verify Ghost unpublish was called
                    mock_ghost_client.unpublish_post.assert_called_once_with('ghost-123')
                    
                    # Verify deletion was scheduled
                    mock_schedule.apply_async.assert_called_once()
    
    def test_takedown_request_post_not_found(self, client):
        """Test takedown request for non-existent post"""
        with patch('app.api.routes.takedown_mvp.get_db_session') as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            response = client.post("/api/v1/takedown/nonexistent", json={
                "reason": "Copyright violation",
                "contact_email": "user@example.com"
            })
            
            assert response.status_code == 404
            data = response.json()
            assert 'not found' in data['detail'].lower()
    
    def test_takedown_request_not_published(self, client):
        """Test takedown request for unpublished post"""
        with patch('app.api.routes.takedown_mvp.get_db_session') as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            
            mock_post = Mock()
            mock_post.ghost_post_id = None  # Not published
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
            
            response = client.post("/api/v1/takedown/test123", json={
                "reason": "Copyright violation",
                "contact_email": "user@example.com"
            })
            
            assert response.status_code == 400
            data = response.json()
            assert 'not published' in data['detail'].lower()
    
    def test_takedown_request_invalid_email(self, client):
        """Test takedown request with invalid email"""
        response = client.post("/api/v1/takedown/test123", json={
            "reason": "Copyright violation",
            "contact_email": "invalid-email"  # Invalid email format
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_takedown_request_ghost_error(self, client):
        """Test takedown request with Ghost API error"""
        with patch('app.api.routes.takedown_mvp.get_db_session') as mock_db:
            with patch('app.api.routes.takedown_mvp.get_ghost_client') as mock_ghost:
                # Mock database
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                
                mock_post = Mock()
                mock_post.ghost_post_id = 'ghost-123'
                mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                
                # Mock Ghost client to raise error
                mock_ghost_client = AsyncMock()
                mock_ghost.return_value = mock_ghost_client
                from workers.publisher.ghost_client import GhostAPIError
                mock_ghost_client.unpublish_post.side_effect = GhostAPIError("API Error")
                
                response = client.post("/api/v1/takedown/test123", json={
                    "reason": "Copyright violation",
                    "contact_email": "user@example.com"
                })
                
                assert response.status_code == 500


class TestErrorHandling:
    """Test API error handling"""
    
    def test_404_error_handling(self, client):
        """Test 404 error handling"""
        response = client.get("/nonexistent-endpoint")
        
        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data
    
    def test_method_not_allowed_error(self, client):
        """Test method not allowed error"""
        response = client.put("/health")  # Health endpoint only supports GET
        
        assert response.status_code == 405
    
    def test_validation_error_handling(self, client):
        """Test validation error handling"""
        response = client.post("/api/v1/collect/trigger", json={
            "subreddits": "not-a-list",  # Should be a list
            "batch_size": "not-a-number"  # Should be a number
        })
        
        assert response.status_code == 422
        data = response.json()
        assert 'detail' in data


class TestRateLimiting:
    """Test API rate limiting"""
    
    def test_rate_limit_not_exceeded(self, client):
        """Test normal request within rate limits"""
        with patch('app.api.middleware.rate_limit.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.return_value = True  # Within limits
            
            response = client.get("/health")
            
            assert response.status_code == 200
    
    def test_rate_limit_exceeded(self, client):
        """Test request exceeding rate limits"""
        with patch('app.api.middleware.rate_limit.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.return_value = False  # Rate limit exceeded
            
            response = client.get("/health")
            
            assert response.status_code == 429  # Too Many Requests


if __name__ == "__main__":
    pytest.main([__file__])