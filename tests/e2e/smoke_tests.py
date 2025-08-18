"""
Post-deployment smoke tests for Reddit Publisher
These tests verify critical functionality after deployment
"""

import os
import time
import pytest
import requests
from typing import Dict, Any


class TestSmokeTests:
    """Smoke tests for critical application functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test configuration"""
        self.api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.api_key = os.getenv('API_KEY', '')
        self.timeout = 30
        
        # Headers for authenticated requests
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        } if self.api_key else {'Content-Type': 'application/json'}
    
    def test_health_endpoint(self):
        """Test that the health endpoint is accessible and returns healthy status"""
        response = requests.get(
            f'{self.api_base_url}/health',
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        
        health_data = response.json()
        assert 'status' in health_data
        assert health_data['status'] == 'healthy'
        
        # Check that all required components are healthy
        required_components = ['database', 'redis', 'celery']
        if 'components' in health_data:
            for component in required_components:
                if component in health_data['components']:
                    assert health_data['components'][component]['status'] == 'healthy'
    
    def test_api_authentication(self):
        """Test API authentication mechanism"""
        if not self.api_key:
            pytest.skip("No API key provided, skipping authentication test")
        
        # Test with valid API key
        response = requests.get(
            f'{self.api_base_url}/api/v1/status/queues',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        
        # Test with invalid API key
        invalid_headers = {
            'Authorization': 'Bearer invalid_key',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'{self.api_base_url}/api/v1/status/queues',
            headers=invalid_headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 401
    
    def test_queue_status_endpoint(self):
        """Test queue status monitoring endpoint"""
        response = requests.get(
            f'{self.api_base_url}/api/v1/status/queues',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        
        queue_data = response.json()
        assert 'queues' in queue_data
        
        # Check that expected queues are present
        expected_queues = ['collect', 'process', 'publish']
        for queue_name in expected_queues:
            assert queue_name in queue_data['queues']
            queue_info = queue_data['queues'][queue_name]
            assert 'pending' in queue_info
            assert 'active' in queue_info
            assert isinstance(queue_info['pending'], int)
            assert isinstance(queue_info['active'], int)
    
    def test_worker_status_endpoint(self):
        """Test worker status monitoring endpoint"""
        response = requests.get(
            f'{self.api_base_url}/api/v1/status/workers',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        
        worker_data = response.json()
        assert 'workers' in worker_data
        assert 'total_workers' in worker_data
        assert isinstance(worker_data['total_workers'], int)
        assert worker_data['total_workers'] > 0
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        response = requests.get(
            f'{self.api_base_url}/metrics',
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        assert 'text/plain' in response.headers.get('content-type', '')
        
        metrics_text = response.text
        
        # Check for expected metrics
        expected_metrics = [
            'reddit_api_calls_total',
            'openai_tokens_used',
            'celery_task_duration_seconds',
            'ghost_publish_success_total'
        ]
        
        for metric in expected_metrics:
            assert metric in metrics_text, f"Metric {metric} not found in response"
    
    def test_manual_trigger_endpoints(self):
        """Test manual trigger endpoints for each service"""
        if not self.api_key:
            pytest.skip("No API key provided, skipping trigger tests")
        
        # Test collect trigger
        response = requests.post(
            f'{self.api_base_url}/api/v1/collect/trigger',
            headers=self.headers,
            json={'subreddits': ['test'], 'limit': 1},
            timeout=self.timeout
        )
        
        assert response.status_code in [200, 202]  # Accept both OK and Accepted
        
        trigger_data = response.json()
        assert 'task_id' in trigger_data or 'message' in trigger_data
    
    def test_database_connectivity(self):
        """Test database connectivity through API"""
        # This test assumes there's an endpoint that requires DB access
        response = requests.get(
            f'{self.api_base_url}/api/v1/status/queues',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        # If we get a successful response, database connectivity is working
    
    def test_redis_connectivity(self):
        """Test Redis connectivity through queue status"""
        response = requests.get(
            f'{self.api_base_url}/api/v1/status/queues',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        
        queue_data = response.json()
        # If we can get queue status, Redis is working
        assert 'queues' in queue_data
    
    def test_api_response_time(self):
        """Test that API response times are acceptable"""
        start_time = time.time()
        
        response = requests.get(
            f'{self.api_base_url}/health',
            timeout=self.timeout
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 5.0, f"Health endpoint took {response_time:.2f}s (should be < 5s)"
    
    def test_error_handling(self):
        """Test that API handles errors gracefully"""
        # Test 404 endpoint
        response = requests.get(
            f'{self.api_base_url}/api/v1/nonexistent',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 404
        
        error_data = response.json()
        assert 'error' in error_data or 'detail' in error_data
    
    def test_cors_headers(self):
        """Test that CORS headers are properly configured"""
        response = requests.options(
            f'{self.api_base_url}/health',
            headers={'Origin': 'https://example.com'},
            timeout=self.timeout
        )
        
        # Should not fail with CORS error
        assert response.status_code in [200, 204]
    
    def test_security_headers(self):
        """Test that security headers are present"""
        response = requests.get(
            f'{self.api_base_url}/health',
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        
        # Check for important security headers
        headers = response.headers
        
        # These headers should be present for security
        expected_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
        ]
        
        for header in expected_headers:
            assert header in headers, f"Security header {header} is missing"


class TestIntegrationSmokeTests:
    """Integration smoke tests that verify end-to-end functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test configuration"""
        self.api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.api_key = os.getenv('API_KEY', '')
        self.timeout = 60  # Longer timeout for integration tests
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        } if self.api_key else {'Content-Type': 'application/json'}
    
    @pytest.mark.slow
    def test_full_pipeline_trigger(self):
        """Test triggering the full pipeline (collect -> process -> publish)"""
        if not self.api_key:
            pytest.skip("No API key provided, skipping pipeline test")
        
        # Trigger collection
        collect_response = requests.post(
            f'{self.api_base_url}/api/v1/collect/trigger',
            headers=self.headers,
            json={'subreddits': ['test'], 'limit': 1},
            timeout=self.timeout
        )
        
        assert collect_response.status_code in [200, 202]
        
        # Wait a bit for processing
        time.sleep(5)
        
        # Check queue status to see if tasks are being processed
        queue_response = requests.get(
            f'{self.api_base_url}/api/v1/status/queues',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert queue_response.status_code == 200
        
        queue_data = queue_response.json()
        
        # Verify that queues are functioning
        assert 'queues' in queue_data
        for queue_name in ['collect', 'process', 'publish']:
            assert queue_name in queue_data['queues']
    
    @pytest.mark.slow
    def test_service_recovery(self):
        """Test that services can recover from temporary failures"""
        # This test would typically involve stopping and starting services
        # For now, we'll just verify that all services are running
        
        response = requests.get(
            f'{self.api_base_url}/api/v1/status/workers',
            headers=self.headers,
            timeout=self.timeout
        )
        
        assert response.status_code == 200
        
        worker_data = response.json()
        assert worker_data['total_workers'] > 0
    
    def test_load_balancer_health(self):
        """Test that load balancer is properly routing requests"""
        # Make multiple requests to ensure consistent responses
        for _ in range(5):
            response = requests.get(
                f'{self.api_base_url}/health',
                timeout=self.timeout
            )
            
            assert response.status_code == 200
            
            health_data = response.json()
            assert health_data['status'] == 'healthy'
            
            # Small delay between requests
            time.sleep(0.1)


if __name__ == '__main__':
    # Run smoke tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--maxfail=5',  # Stop after 5 failures
        '-x',  # Stop on first failure for critical tests
    ])