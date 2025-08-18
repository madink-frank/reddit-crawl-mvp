"""
Unit tests for FastAPI endpoints
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.api.routes.health import router as health_router
from app.api.routes.status import router as status_router
from app.api.routes.triggers import router as triggers_router


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_health_check_success(self, client):
        """Test successful health check"""
        with patch('app.api.routes.health.check_system_health') as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "timestamp": "2024-01-01T00:00:00Z",
                "services": {
                    "database": {"status": "healthy"},
                    "redis": {"status": "healthy"},
                    "vault": {"status": "healthy"}
                }
            }
            
            response = client.get("/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert "services" in data
    
    def test_health_check_unhealthy(self, client):
        """Test unhealthy system health check"""
        with patch('app.api.routes.health.check_system_health') as mock_health:
            mock_health.return_value = {
                "status": "unhealthy",
                "timestamp": "2024-01-01T00:00:00Z",
                "services": {
                    "database": {"status": "unhealthy", "error": "Connection failed"},
                    "redis": {"status": "healthy"},
                    "vault": {"status": "healthy"}
                }
            }
            
            response = client.get("/health")
            
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
    
    def test_readiness_check_success(self, client):
        """Test successful readiness check"""
        with patch('app.api.routes.health.check_readiness') as mock_readiness:
            mock_readiness.return_value = {
                "status": "ready",
                "timestamp": "2024-01-01T00:00:00Z",
                "checks": {
                    "database_migrations": {"status": "ready"},
                    "external_services": {"status": "ready"}
                }
            }
            
            response = client.get("/ready")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "ready"
    
    def test_liveness_check_success(self, client):
        """Test successful liveness check"""
        with patch('app.api.routes.health.check_liveness') as mock_liveness:
            mock_liveness.return_value = {
                "status": "alive",
                "timestamp": "2024-01-01T00:00:00Z",
                "uptime_seconds": 3600
            }
            
            response = client.get("/live")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "alive"


class TestStatusEndpoints:
    """Test status monitoring endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_queue_status_success(self, client):
        """Test successful queue status check"""
        with patch('app.api.routes.status.get_queue_status') as mock_status:
            mock_status.return_value = {
                "collect_pending": 5,
                "process_pending": 3,
                "publish_pending": 1,
                "collect_failed": 0,
                "process_failed": 1,
                "publish_failed": 0
            }
            
            response = client.get("/api/v1/status/queues")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["collect_pending"] == 5
            assert data["process_pending"] == 3
    
    def test_worker_status_success(self, client):
        """Test successful worker status check"""
        with patch('app.api.routes.status.get_worker_status') as mock_status:
            mock_status.return_value = {
                "active_workers": 6,
                "workers": {
                    "collector": {"active": 2, "total": 2},
                    "nlp": {"active": 2, "total": 2},
                    "publisher": {"active": 1, "total": 1}
                }
            }
            
            response = client.get("/api/v1/status/workers")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["active_workers"] == 6
            assert "workers" in data
    
    def test_system_metrics_success(self, client):
        """Test successful system metrics retrieval"""
        with patch('app.api.routes.status.get_system_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "disk_usage": 23.1,
                "network_io": {
                    "bytes_sent": 1024000,
                    "bytes_recv": 2048000
                }
            }
            
            response = client.get("/api/v1/status/metrics")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["cpu_usage"] == 45.2
            assert data["memory_usage"] == 67.8


class TestTriggerEndpoints:
    """Test manual trigger endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        with patch('app.api.middleware.auth.verify_jwt_token') as mock_verify:
            mock_verify.return_value = {"user_id": "test_user", "role": "admin"}
            return {"Authorization": "Bearer test_token"}
    
    def test_trigger_collection_success(self, client, auth_headers):
        """Test successful collection trigger"""
        with patch('app.api.routes.triggers.trigger_collection') as mock_trigger:
            mock_trigger.return_value = {
                "task_id": "collect_123",
                "status": "queued",
                "message": "Collection task queued successfully"
            }
            
            response = client.post(
                "/api/v1/collect/trigger",
                headers=auth_headers,
                json={"subreddits": ["technology", "programming"]}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["task_id"] == "collect_123"
            assert data["status"] == "queued"
    
    def test_trigger_processing_success(self, client, auth_headers):
        """Test successful processing trigger"""
        with patch('app.api.routes.triggers.trigger_processing') as mock_trigger:
            mock_trigger.return_value = {
                "task_id": "process_123",
                "status": "queued",
                "message": "Processing task queued successfully"
            }
            
            response = client.post(
                "/api/v1/process/trigger",
                headers=auth_headers,
                json={"post_ids": ["post_1", "post_2"]}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["task_id"] == "process_123"
    
    def test_trigger_publishing_success(self, client, auth_headers):
        """Test successful publishing trigger"""
        with patch('app.api.routes.triggers.trigger_publishing') as mock_trigger:
            mock_trigger.return_value = {
                "task_id": "publish_123",
                "status": "queued",
                "message": "Publishing task queued successfully"
            }
            
            response = client.post(
                "/api/v1/publish/trigger",
                headers=auth_headers,
                json={"post_ids": ["post_1", "post_2"]}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["task_id"] == "publish_123"
    
    def test_trigger_unauthorized(self, client):
        """Test unauthorized trigger request"""
        response = client.post(
            "/api/v1/collect/trigger",
            json={"subreddits": ["technology"]}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_trigger_invalid_payload(self, client, auth_headers):
        """Test trigger with invalid payload"""
        response = client.post(
            "/api/v1/collect/trigger",
            headers=auth_headers,
            json={"invalid_field": "value"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestMetricsEndpoint:
    """Test Prometheus metrics endpoint"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_metrics_endpoint_success(self, client):
        """Test successful metrics retrieval"""
        with patch('app.monitoring.metrics.generate_metrics') as mock_metrics:
            mock_metrics.return_value = """
# HELP reddit_api_calls_total Total Reddit API calls
# TYPE reddit_api_calls_total counter
reddit_api_calls_total 150.0

# HELP openai_tokens_used OpenAI tokens consumed
# TYPE openai_tokens_used counter
openai_tokens_used{type="input"} 50000.0
openai_tokens_used{type="output"} 25000.0

# HELP celery_task_duration_seconds Task execution time
# TYPE celery_task_duration_seconds histogram
celery_task_duration_seconds_bucket{task_name="collect_reddit_posts",le="1.0"} 10.0
celery_task_duration_seconds_bucket{task_name="collect_reddit_posts",le="5.0"} 25.0
celery_task_duration_seconds_bucket{task_name="collect_reddit_posts",le="+Inf"} 30.0
celery_task_duration_seconds_count{task_name="collect_reddit_posts"} 30.0
celery_task_duration_seconds_sum{task_name="collect_reddit_posts"} 45.5
"""
            
            response = client.get("/metrics")
            
            assert response.status_code == status.HTTP_200_OK
            assert "reddit_api_calls_total" in response.text
            assert "openai_tokens_used" in response.text
            assert "celery_task_duration_seconds" in response.text
    
    def test_metrics_endpoint_error(self, client):
        """Test metrics endpoint error handling"""
        with patch('app.monitoring.metrics.generate_metrics') as mock_metrics:
            mock_metrics.side_effect = Exception("Metrics generation failed")
            
            response = client.get("/metrics")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestErrorHandling:
    """Test API error handling"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_404_not_found(self, client):
        """Test 404 error handling"""
        response = client.get("/nonexistent-endpoint")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
    
    def test_method_not_allowed(self, client):
        """Test 405 error handling"""
        response = client.put("/health")  # Health endpoint only supports GET
        
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    
    def test_internal_server_error(self, client):
        """Test 500 error handling"""
        with patch('app.api.routes.health.check_system_health') as mock_health:
            mock_health.side_effect = Exception("Internal error")
            
            response = client.get("/health")
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "error" in data


class TestMiddleware:
    """Test middleware functionality"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options("/health")
        
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_security_headers(self, client):
        """Test security headers are present"""
        response = client.get("/health")
        
        # Check for security headers
        assert "x-content-type-options" in response.headers
        assert "x-frame-options" in response.headers
        assert "x-xss-protection" in response.headers
    
    def test_rate_limiting(self, client):
        """Test rate limiting middleware"""
        with patch('app.api.middleware.rate_limit.check_rate_limit') as mock_rate_limit:
            # First request should pass
            mock_rate_limit.return_value = (True, 99, 60)
            response = client.get("/health")
            assert response.status_code == status.HTTP_200_OK
            
            # Subsequent request should be rate limited
            mock_rate_limit.return_value = (False, 0, 60)
            response = client.get("/health")
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


if __name__ == "__main__":
    pytest.main([__file__])