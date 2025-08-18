"""
Load testing for Reddit Ghost Publisher using Locust

This file contains load test scenarios for testing the system under various loads.
Run with: locust -f tests/load/locustfile.py --host=http://localhost:8000
"""
import json
import random
import time
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask


class RedditPublisherUser(HttpUser):
    """Base user class for Reddit Publisher load testing"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    def on_start(self):
        """Called when a user starts"""
        self.auth_token = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate user and get JWT token"""
        # In a real scenario, you would authenticate here
        # For testing, we'll use a mock token
        self.auth_token = "mock_jwt_token_for_load_testing"
        self.client.headers.update({
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        })
    
    @task(10)
    def health_check(self):
        """Test health endpoint - most frequent request"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 503:
                # Service unavailable is acceptable during load testing
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(5)
    def metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code == 200:
                if "reddit_api_calls_total" in response.text:
                    response.success()
                else:
                    response.failure("Metrics response missing expected content")
            else:
                response.failure(f"Metrics endpoint failed: {response.status_code}")
    
    @task(3)
    def queue_status(self):
        """Test queue status endpoint"""
        with self.client.get("/api/v1/status/queues", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "collect_pending" in data and "process_pending" in data:
                        response.success()
                    else:
                        response.failure("Queue status missing expected fields")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Authentication failed")
            else:
                response.failure(f"Queue status failed: {response.status_code}")
    
    @task(3)
    def worker_status(self):
        """Test worker status endpoint"""
        with self.client.get("/api/v1/status/workers", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "active_workers" in data and "workers" in data:
                        response.success()
                    else:
                        response.failure("Worker status missing expected fields")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Authentication failed")
            else:
                response.failure(f"Worker status failed: {response.status_code}")
    
    @task(2)
    def trigger_collection(self):
        """Test collection trigger endpoint"""
        subreddits = ["technology", "programming", "python", "javascript", "datascience"]
        payload = {
            "subreddits": random.sample(subreddits, random.randint(1, 3)),
            "sort_type": random.choice(["hot", "new", "rising"]),
            "limit": random.randint(10, 50)
        }
        
        with self.client.post("/api/v1/collect/trigger", 
                             json=payload, 
                             catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "task_id" in data and "status" in data:
                        response.success()
                    else:
                        response.failure("Collection trigger missing expected fields")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Authentication failed")
            elif response.status_code == 503:
                # Service unavailable during high load is acceptable
                response.success()
            else:
                response.failure(f"Collection trigger failed: {response.status_code}")
    
    @task(1)
    def trigger_processing(self):
        """Test processing trigger endpoint"""
        # Generate mock post IDs
        post_ids = [f"load_test_post_{random.randint(1, 1000)}" for _ in range(random.randint(1, 5))]
        payload = {
            "post_ids": post_ids,
            "force_reprocess": random.choice([True, False])
        }
        
        with self.client.post("/api/v1/process/trigger", 
                             json=payload, 
                             catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "task_id" in data:
                        response.success()
                    else:
                        response.failure("Processing trigger missing task_id")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Authentication failed")
            elif response.status_code == 503:
                response.success()  # Acceptable during load
            else:
                response.failure(f"Processing trigger failed: {response.status_code}")
    
    @task(1)
    def trigger_publishing(self):
        """Test publishing trigger endpoint"""
        post_ids = [f"processed_post_{random.randint(1, 500)}" for _ in range(random.randint(1, 3))]
        payload = {
            "post_ids": post_ids,
            "force_republish": random.choice([True, False])
        }
        
        with self.client.post("/api/v1/publish/trigger", 
                             json=payload, 
                             catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "task_id" in data:
                        response.success()
                    else:
                        response.failure("Publishing trigger missing task_id")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Authentication failed")
            elif response.status_code == 503:
                response.success()  # Acceptable during load
            else:
                response.failure(f"Publishing trigger failed: {response.status_code}")


class HighLoadUser(RedditPublisherUser):
    """User class for high-load scenarios"""
    
    wait_time = between(0.1, 0.5)  # Much faster requests
    
    @task(20)
    def rapid_health_checks(self):
        """Rapid health check requests"""
        self.health_check()
    
    @task(5)
    def rapid_queue_status(self):
        """Rapid queue status checks"""
        self.queue_status()


class BurstUser(RedditPublisherUser):
    """User class for burst load scenarios"""
    
    wait_time = between(0, 0.1)  # Very fast requests
    
    def on_start(self):
        super().on_start()
        self.burst_count = 0
    
    @task
    def burst_requests(self):
        """Send burst of requests then pause"""
        if self.burst_count < 10:
            self.health_check()
            self.burst_count += 1
        else:
            # Pause for a longer time after burst
            time.sleep(random.uniform(5, 10))
            self.burst_count = 0


class AdminUser(RedditPublisherUser):
    """Admin user with access to all endpoints"""
    
    wait_time = between(2, 5)  # Slower, more deliberate requests
    
    @task(5)
    def admin_health_check(self):
        """Admin health check"""
        self.health_check()
    
    @task(3)
    def admin_queue_management(self):
        """Admin queue status checks"""
        self.queue_status()
        self.worker_status()
    
    @task(2)
    def admin_trigger_operations(self):
        """Admin trigger operations"""
        self.trigger_collection()
        time.sleep(1)  # Wait between operations
        self.trigger_processing()
        time.sleep(1)
        self.trigger_publishing()


# Custom events for detailed metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Custom request event handler for detailed metrics"""
    if exception:
        print(f"Request failed: {request_type} {name} - {exception}")
    elif response_time > 1000:  # Log slow requests (>1s)
        print(f"Slow request: {request_type} {name} - {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("Starting Reddit Publisher load test...")
    print(f"Target host: {environment.host}")
    print(f"User classes: {[cls.__name__ for cls in environment.user_classes]}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("Reddit Publisher load test completed.")
    
    # Print summary statistics
    stats = environment.stats
    print(f"\nTest Summary:")
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print(f"Requests per second: {stats.total.current_rps:.2f}")
    
    # Check if performance requirements are met
    avg_response_time = stats.total.avg_response_time
    p95_response_time = stats.total.get_response_time_percentile(0.95)
    failure_rate = (stats.total.num_failures / stats.total.num_requests) * 100 if stats.total.num_requests > 0 else 0
    
    print(f"\nPerformance Requirements Check:")
    print(f"Average response time: {avg_response_time:.2f}ms (target: <250ms) - {'✓' if avg_response_time < 250 else '✗'}")
    print(f"95th percentile: {p95_response_time:.2f}ms (target: <300ms) - {'✓' if p95_response_time < 300 else '✗'}")
    print(f"Failure rate: {failure_rate:.2f}% (target: <1%) - {'✓' if failure_rate < 1 else '✗'}")


# Load test scenarios
class LoadTestScenarios:
    """Predefined load test scenarios"""
    
    @staticmethod
    def normal_load():
        """Normal operational load"""
        return {
            "user_classes": [RedditPublisherUser],
            "users": 10,
            "spawn_rate": 2,
            "run_time": "5m"
        }
    
    @staticmethod
    def high_load():
        """High load scenario"""
        return {
            "user_classes": [RedditPublisherUser, HighLoadUser],
            "users": 50,
            "spawn_rate": 5,
            "run_time": "10m"
        }
    
    @staticmethod
    def stress_test():
        """Stress test scenario"""
        return {
            "user_classes": [RedditPublisherUser, HighLoadUser, BurstUser],
            "users": 100,
            "spawn_rate": 10,
            "run_time": "30m"
        }
    
    @staticmethod
    def spike_test():
        """Spike test scenario"""
        return {
            "user_classes": [BurstUser],
            "users": 200,
            "spawn_rate": 50,
            "run_time": "2m"
        }


# Example usage:
# locust -f tests/load/locustfile.py --host=http://localhost:8000 --users=10 --spawn-rate=2 --run-time=5m
# locust -f tests/load/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10 --run-time=30m --html=load_test_report.html