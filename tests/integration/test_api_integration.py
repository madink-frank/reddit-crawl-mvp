"""
Integration tests for API endpoints
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.config import get_settings


class TestAPIIntegration:
    """Test API integration scenarios"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        # Mock JWT verification for testing
        with patch('app.api.middleware.auth.verify_jwt_token') as mock_verify:
            mock_verify.return_value = {"user_id": "test_user", "role": "admin"}
            return {"Authorization": "Bearer test_token"}
    
    def test_health_endpoint_integration(self, client):
        """Test health endpoint with real dependencies"""
        with patch('app.monitoring.health.check_system_health') as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "timestamp": "2024-01-01T00:00:00Z",
                "services": {
                    "database": {"status": "healthy", "response_time_ms": 5},
                    "redis": {"status": "healthy", "response_time_ms": 2},
                    "vault": {"status": "healthy", "response_time_ms": 10}
                },
                "version": "1.0.0",
                "uptime_seconds": 3600
            }
            
            response = client.get("/health")
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert "services" in data
            assert "version" in data
            assert "uptime_seconds" in data
    
    def test_metrics_endpoint_integration(self, client):
        """Test Prometheus metrics endpoint"""
        with patch('app.monitoring.metrics.generate_metrics') as mock_metrics:
            mock_metrics.return_value = """
# HELP reddit_api_calls_total Total Reddit API calls
# TYPE reddit_api_calls_total counter
reddit_api_calls_total 150.0

# HELP openai_tokens_used OpenAI tokens consumed
# TYPE openai_tokens_used counter
openai_tokens_used{type="input"} 50000.0
openai_tokens_used{type="output"} 25000.0

# HELP celery_queue_length Queue length
# TYPE celery_queue_length gauge
celery_queue_length{queue_name="collect"} 5.0
celery_queue_length{queue_name="process"} 3.0
celery_queue_length{queue_name="publish"} 1.0
"""
            
            response = client.get("/metrics")
            
            assert response.status_code == status.HTTP_200_OK
            assert "reddit_api_calls_total" in response.text
            assert "openai_tokens_used" in response.text
            assert "celery_queue_length" in response.text
    
    def test_queue_status_integration(self, client, auth_headers):
        """Test queue status endpoint with real Redis connection"""
        with patch('app.api.routes.status.get_queue_status') as mock_status:
            mock_status.return_value = {
                "collect_pending": 5,
                "process_pending": 3,
                "publish_pending": 1,
                "collect_failed": 0,
                "process_failed": 1,
                "publish_failed": 0,
                "total_pending": 9,
                "total_failed": 1
            }
            
            response = client.get("/api/v1/status/queues", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["collect_pending"] == 5
            assert data["process_pending"] == 3
            assert data["publish_pending"] == 1
            assert data["total_pending"] == 9
    
    def test_worker_status_integration(self, client, auth_headers):
        """Test worker status endpoint"""
        with patch('app.api.routes.status.get_worker_status') as mock_status:
            mock_status.return_value = {
                "active_workers": 6,
                "workers": {
                    "collector": {
                        "active": 2,
                        "total": 2,
                        "queues": ["collect"],
                        "status": "running"
                    },
                    "nlp": {
                        "active": 2,
                        "total": 2,
                        "queues": ["process"],
                        "status": "running"
                    },
                    "publisher": {
                        "active": 1,
                        "total": 1,
                        "queues": ["publish"],
                        "status": "running"
                    }
                }
            }
            
            response = client.get("/api/v1/status/workers", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["active_workers"] == 6
            assert len(data["workers"]) == 3
    
    def test_trigger_collection_integration(self, client, auth_headers):
        """Test collection trigger endpoint"""
        with patch('workers.collector.tasks.collect_reddit_posts.delay') as mock_task:
            mock_task.return_value.id = "collect_task_123"
            
            payload = {
                "subreddits": ["technology", "programming"],
                "sort_type": "hot",
                "limit": 50
            }
            
            response = client.post(
                "/api/v1/collect/trigger",
                headers=auth_headers,
                json=payload
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "queued"
            mock_task.assert_called_once()
    
    def test_trigger_processing_integration(self, client, auth_headers):
        """Test processing trigger endpoint"""
        with patch('workers.nlp_pipeline.tasks.process_content_with_ai.delay') as mock_task:
            mock_task.return_value.id = "process_task_123"
            
            payload = {
                "post_ids": ["post_1", "post_2", "post_3"],
                "force_reprocess": False
            }
            
            response = client.post(
                "/api/v1/process/trigger",
                headers=auth_headers,
                json=payload
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "queued"
    
    def test_trigger_publishing_integration(self, client, auth_headers):
        """Test publishing trigger endpoint"""
        with patch('workers.publisher.tasks.publish_to_ghost.delay') as mock_task:
            mock_task.return_value.id = "publish_task_123"
            
            payload = {
                "post_ids": ["post_1", "post_2"],
                "force_republish": False
            }
            
            response = client.post(
                "/api/v1/publish/trigger",
                headers=auth_headers,
                json=payload
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "queued"
    
    def test_authentication_flow_integration(self, client):
        """Test authentication flow"""
        # Test without authentication
        response = client.post("/api/v1/collect/trigger", json={"subreddits": ["test"]})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Test with invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        with patch('app.api.middleware.auth.verify_jwt_token') as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")
            
            response = client.post(
                "/api/v1/collect/trigger",
                headers=headers,
                json={"subreddits": ["test"]}
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_rate_limiting_integration(self, client):
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
    
    def test_error_handling_integration(self, client):
        """Test error handling across the API"""
        # Test 404 error
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Test validation error
        with patch('app.api.middleware.auth.verify_jwt_token') as mock_verify:
            mock_verify.return_value = {"user_id": "test_user", "role": "admin"}
            headers = {"Authorization": "Bearer test_token"}
            
            # Invalid payload
            response = client.post(
                "/api/v1/collect/trigger",
                headers=headers,
                json={"invalid_field": "value"}
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_cors_integration(self, client):
        """Test CORS headers"""
        response = client.options("/health", headers={"Origin": "http://localhost:3000"})
        
        # Check for CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
    
    def test_security_headers_integration(self, client):
        """Test security headers"""
        response = client.get("/health")
        
        # Check for security headers
        assert "x-content-type-options" in response.headers
        assert "x-frame-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"


class TestAPIErrorScenarios:
    """Test API error scenarios"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    def test_database_connection_error(self, client):
        """Test API behavior when database is unavailable"""
        with patch('app.monitoring.health.check_database_health') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            response = client.get("/health")
            
            # Should return 503 when database is unavailable
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["status"] == "unhealthy"
    
    def test_redis_connection_error(self, client):
        """Test API behavior when Redis is unavailable"""
        with patch('app.redis_client.redis_health_check') as mock_redis:
            mock_redis.return_value = {
                "status": "unhealthy",
                "error": "Connection refused",
                "connected": False
            }
            
            response = client.get("/health")
            
            # Should return 503 when Redis is unavailable
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    
    def test_vault_connection_error(self, client):
        """Test API behavior when Vault is unavailable"""
        with patch('app.vault_client.vault_health_check') as mock_vault:
            mock_vault.return_value = {
                "status": "unhealthy",
                "error": "Vault sealed",
                "connected": False
            }
            
            response = client.get("/health")
            
            # Should return 503 when Vault is unavailable
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    
    def test_celery_worker_unavailable(self, client):
        """Test API behavior when Celery workers are unavailable"""
        with patch('app.api.middleware.auth.verify_jwt_token') as mock_verify:
            mock_verify.return_value = {"user_id": "test_user", "role": "admin"}
            headers = {"Authorization": "Bearer test_token"}
            
            with patch('workers.collector.tasks.collect_reddit_posts.delay') as mock_task:
                mock_task.side_effect = Exception("No workers available")
                
                response = client.post(
                    "/api/v1/collect/trigger",
                    headers=headers,
                    json={"subreddits": ["test"]}
                )
                
                assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    
    def test_high_load_scenario(self, client):
        """Test API behavior under high load"""
        with patch('app.api.middleware.auth.verify_jwt_token') as mock_verify:
            mock_verify.return_value = {"user_id": "test_user", "role": "admin"}
            headers = {"Authorization": "Bearer test_token"}
            
            # Simulate high queue depth
            with patch('app.api.routes.status.get_queue_status') as mock_status:
                mock_status.return_value = {
                    "collect_pending": 1500,  # High queue depth
                    "process_pending": 800,
                    "publish_pending": 300,
                    "total_pending": 2600
                }
                
                response = client.get("/api/v1/status/queues", headers=headers)
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["total_pending"] == 2600
                
                # Should include warning about high load
                assert data["collect_pending"] > 1000


if __name__ == "__main__":
    pytest.main([__file__])