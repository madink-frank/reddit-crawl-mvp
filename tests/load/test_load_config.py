"""
Unit tests for load test configuration
"""
import pytest
import os
import json
import tempfile
from load_test_config import LoadTestConfig, LoadTestRunner, PerformanceMonitor


class TestLoadTestConfig:
    """Test LoadTestConfig class"""
    
    def test_load_test_config_creation(self):
        """Test creating a LoadTestConfig"""
        config = LoadTestConfig(
            name="test_config",
            description="Test configuration",
            host="http://localhost:8000",
            users=10,
            spawn_rate=2,
            run_time="5m",
            user_classes=["RedditPublisherUser"],
            expected_rps=10.0,
            max_avg_response_time=250.0,
            max_p95_response_time=300.0,
            max_failure_rate=1.0
        )
        
        assert config.name == "test_config"
        assert config.users == 10
        assert config.spawn_rate == 2
        assert config.run_time == "5m"
        assert config.expected_rps == 10.0


class TestLoadTestRunner:
    """Test LoadTestRunner class"""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                "test_config": {
                    "name": "test_config",
                    "description": "Test configuration",
                    "host": "http://localhost:8000",
                    "users": 5,
                    "spawn_rate": 1,
                    "run_time": "1m",
                    "user_classes": ["RedditPublisherUser"],
                    "expected_rps": 5.0,
                    "max_avg_response_time": 250.0,
                    "max_p95_response_time": 300.0,
                    "max_failure_rate": 1.0
                }
            }
            json.dump(config_data, f)
            temp_file = f.name
        
        yield temp_file
        os.unlink(temp_file)
    
    def test_load_configs_from_file(self, temp_config_file):
        """Test loading configurations from file"""
        runner = LoadTestRunner(temp_config_file)
        configs = runner.load_configs()
        
        assert "test_config" in configs
        config = configs["test_config"]
        assert config.name == "test_config"
        assert config.users == 5
        assert config.spawn_rate == 1
    
    def test_get_default_configs(self):
        """Test getting default configurations"""
        runner = LoadTestRunner()
        configs = runner.get_default_configs()
        
        assert "smoke_test" in configs
        assert "normal_load" in configs
        assert "high_load" in configs
        assert "stress_test" in configs
        assert "spike_test" in configs
        assert "endurance_test" in configs
        
        # Check smoke test config
        smoke_config = configs["smoke_test"]
        assert smoke_config.users == 1
        assert smoke_config.run_time == "1m"
    
    def test_generate_locust_command(self):
        """Test generating Locust command"""
        runner = LoadTestRunner()
        config = LoadTestConfig(
            name="test_cmd",
            description="Test command generation",
            host="http://localhost:8000",
            users=10,
            spawn_rate=2,
            run_time="5m",
            user_classes=["RedditPublisherUser"],
            expected_rps=10.0,
            max_avg_response_time=250.0,
            max_p95_response_time=300.0,
            max_failure_rate=1.0
        )
        
        command = runner.generate_locust_command(config)
        
        assert "locust" in command
        assert "-f tests/load/locustfile.py" in command
        assert "--host=http://localhost:8000" in command
        assert "--users=10" in command
        assert "--spawn-rate=2" in command
        assert "--run-time=5m" in command
        assert "--headless" in command
    
    def test_analyze_results(self):
        """Test analyzing results (mock)"""
        runner = LoadTestRunner()
        
        # Test with non-existent file
        with pytest.raises(FileNotFoundError):
            runner.analyze_results("nonexistent_file.csv")
        
        # Create a temporary mock file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("timestamp,requests,failures,avg_response_time\n")
            f.write("2024-01-01 10:00:00,100,1,245.5\n")
            temp_file = f.name
        
        try:
            # Test with mock results
            results = runner.analyze_results(temp_file)  # This returns mock data
            
            assert "total_requests" in results
            assert "avg_response_time" in results
            assert "p95_response_time" in results
            assert "failure_rate" in results
        finally:
            os.unlink(temp_file)
    
    def test_check_performance_requirements(self):
        """Test checking performance requirements"""
        runner = LoadTestRunner()
        
        config = LoadTestConfig(
            name="test_perf",
            description="Test performance check",
            host="http://localhost:8000",
            users=10,
            spawn_rate=2,
            run_time="5m",
            user_classes=["RedditPublisherUser"],
            expected_rps=10.0,
            max_avg_response_time=250.0,
            max_p95_response_time=300.0,
            max_failure_rate=1.0
        )
        
        # Test passing results
        good_results = {
            "avg_response_time": 200.0,
            "p95_response_time": 280.0,
            "failure_rate": 0.5,
            "requests_per_second": 12.0
        }
        
        checks = runner.check_performance_requirements(config, good_results)
        
        assert checks["avg_response_time"] is True
        assert checks["p95_response_time"] is True
        assert checks["failure_rate"] is True
        assert checks["requests_per_second"] is True
        
        # Test failing results
        bad_results = {
            "avg_response_time": 300.0,  # Too high
            "p95_response_time": 400.0,  # Too high
            "failure_rate": 2.0,         # Too high
            "requests_per_second": 5.0   # Too low
        }
        
        checks = runner.check_performance_requirements(config, bad_results)
        
        assert checks["avg_response_time"] is False
        assert checks["p95_response_time"] is False
        assert checks["failure_rate"] is False
        assert checks["requests_per_second"] is False
    
    def test_generate_report(self):
        """Test generating performance report"""
        runner = LoadTestRunner()
        
        config = LoadTestConfig(
            name="test_report",
            description="Test report generation",
            host="http://localhost:8000",
            users=10,
            spawn_rate=2,
            run_time="5m",
            user_classes=["RedditPublisherUser"],
            expected_rps=10.0,
            max_avg_response_time=250.0,
            max_p95_response_time=300.0,
            max_failure_rate=1.0
        )
        
        results = {
            "total_requests": 1000,
            "total_failures": 5,
            "avg_response_time": 200.0,
            "p95_response_time": 280.0,
            "p99_response_time": 350.0,
            "requests_per_second": 12.0,
            "failure_rate": 0.5
        }
        
        checks = {
            "avg_response_time": True,
            "p95_response_time": True,
            "failure_rate": True,
            "requests_per_second": True
        }
        
        report = runner.generate_report(config, results, checks)
        
        assert "Load Test Report: test_report" in report
        assert "Test Configuration" in report
        assert "Performance Requirements" in report
        assert "Test Results" in report
        assert "Performance Check Results" in report
        assert "✅ PASS" in report


class TestPerformanceMonitor:
    """Test PerformanceMonitor class"""
    
    def test_collect_metrics(self):
        """Test collecting system metrics"""
        monitor = PerformanceMonitor()
        metrics = monitor.collect_metrics()
        
        assert "timestamp" in metrics
        assert "cpu_usage" in metrics
        assert "memory_usage" in metrics
        assert "disk_usage" in metrics
        assert "network_io" in metrics
        assert "queue_depths" in metrics
        assert "active_workers" in metrics
        assert "database_connections" in metrics
    
    def test_get_metrics_summary(self):
        """Test getting metrics summary"""
        monitor = PerformanceMonitor()
        
        # Test with no metrics
        summary = monitor.get_metrics_summary()
        assert summary == {}
        
        # Test with mock metrics
        monitor.metrics = [{"cpu_usage": 45.0}, {"cpu_usage": 50.0}]
        summary = monitor.get_metrics_summary()
        
        assert "avg_cpu_usage" in summary
        assert "peak_cpu_usage" in summary


if __name__ == "__main__":
    pytest.main([__file__])