"""
Load test configuration and utilities for Reddit Ghost Publisher
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class LoadTestConfig:
    """Load test configuration"""
    name: str
    description: str
    host: str
    users: int
    spawn_rate: int
    run_time: str
    user_classes: List[str]
    expected_rps: float
    max_avg_response_time: float
    max_p95_response_time: float
    max_failure_rate: float


class LoadTestRunner:
    """Load test runner and results analyzer"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or "tests/load/test_configs.json"
        self.results_dir = "tests/load/results"
        self.ensure_results_dir()
    
    def ensure_results_dir(self):
        """Ensure results directory exists"""
        os.makedirs(self.results_dir, exist_ok=True)
    
    def load_configs(self) -> Dict[str, LoadTestConfig]:
        """Load test configurations from JSON file"""
        if not os.path.exists(self.config_file):
            return self.get_default_configs()
        
        with open(self.config_file, 'r') as f:
            configs_data = json.load(f)
        
        configs = {}
        for name, data in configs_data.items():
            configs[name] = LoadTestConfig(**data)
        
        return configs
    
    def get_default_configs(self) -> Dict[str, LoadTestConfig]:
        """Get default load test configurations"""
        return {
            "smoke_test": LoadTestConfig(
                name="smoke_test",
                description="Quick smoke test to verify basic functionality",
                host="http://localhost:8000",
                users=1,
                spawn_rate=1,
                run_time="1m",
                user_classes=["RedditPublisherUser"],
                expected_rps=1.0,
                max_avg_response_time=250.0,
                max_p95_response_time=300.0,
                max_failure_rate=1.0
            ),
            "normal_load": LoadTestConfig(
                name="normal_load",
                description="Normal operational load test",
                host="http://localhost:8000",
                users=10,
                spawn_rate=2,
                run_time="5m",
                user_classes=["RedditPublisherUser"],
                expected_rps=10.0,
                max_avg_response_time=250.0,
                max_p95_response_time=300.0,
                max_failure_rate=1.0
            ),
            "high_load": LoadTestConfig(
                name="high_load",
                description="High load test to verify performance under stress",
                host="http://localhost:8000",
                users=50,
                spawn_rate=5,
                run_time="10m",
                user_classes=["RedditPublisherUser", "HighLoadUser"],
                expected_rps=50.0,
                max_avg_response_time=300.0,
                max_p95_response_time=500.0,
                max_failure_rate=2.0
            ),
            "stress_test": LoadTestConfig(
                name="stress_test",
                description="Stress test to find system breaking point",
                host="http://localhost:8000",
                users=100,
                spawn_rate=10,
                run_time="30m",
                user_classes=["RedditPublisherUser", "HighLoadUser", "BurstUser"],
                expected_rps=100.0,
                max_avg_response_time=500.0,
                max_p95_response_time=1000.0,
                max_failure_rate=5.0
            ),
            "spike_test": LoadTestConfig(
                name="spike_test",
                description="Spike test to verify system handles sudden load increases",
                host="http://localhost:8000",
                users=200,
                spawn_rate=50,
                run_time="2m",
                user_classes=["BurstUser"],
                expected_rps=200.0,
                max_avg_response_time=1000.0,
                max_p95_response_time=2000.0,
                max_failure_rate=10.0
            ),
            "endurance_test": LoadTestConfig(
                name="endurance_test",
                description="Long-running test to verify system stability",
                host="http://localhost:8000",
                users=20,
                spawn_rate=2,
                run_time="60m",
                user_classes=["RedditPublisherUser"],
                expected_rps=20.0,
                max_avg_response_time=250.0,
                max_p95_response_time=300.0,
                max_failure_rate=1.0
            )
        }
    
    def save_configs(self, configs: Dict[str, LoadTestConfig]):
        """Save configurations to JSON file"""
        configs_data = {}
        for name, config in configs.items():
            configs_data[name] = asdict(config)
        
        with open(self.config_file, 'w') as f:
            json.dump(configs_data, f, indent=2)
    
    def generate_locust_command(self, config: LoadTestConfig) -> str:
        """Generate Locust command for given configuration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_report = f"{self.results_dir}/{config.name}_{timestamp}.html"
        csv_prefix = f"{self.results_dir}/{config.name}_{timestamp}"
        
        command = [
            "locust",
            "-f tests/load/locustfile.py",
            f"--host={config.host}",
            f"--users={config.users}",
            f"--spawn-rate={config.spawn_rate}",
            f"--run-time={config.run_time}",
            f"--html={html_report}",
            f"--csv={csv_prefix}",
            "--headless"
        ]
        
        return " ".join(command)
    
    def analyze_results(self, results_file: str) -> Dict[str, Any]:
        """Analyze load test results"""
        if not os.path.exists(results_file):
            raise FileNotFoundError(f"Results file not found: {results_file}")
        
        # This would parse CSV results from Locust
        # For now, return a mock analysis
        return {
            "total_requests": 1000,
            "total_failures": 5,
            "avg_response_time": 245.5,
            "p95_response_time": 298.2,
            "p99_response_time": 456.7,
            "requests_per_second": 33.3,
            "failure_rate": 0.5
        }
    
    def check_performance_requirements(self, 
                                     config: LoadTestConfig, 
                                     results: Dict[str, Any]) -> Dict[str, bool]:
        """Check if results meet performance requirements"""
        checks = {}
        
        # Average response time check
        checks["avg_response_time"] = results["avg_response_time"] <= config.max_avg_response_time
        
        # 95th percentile response time check
        checks["p95_response_time"] = results["p95_response_time"] <= config.max_p95_response_time
        
        # Failure rate check
        checks["failure_rate"] = results["failure_rate"] <= config.max_failure_rate
        
        # RPS check (should be at least 80% of expected)
        min_expected_rps = config.expected_rps * 0.8
        checks["requests_per_second"] = results["requests_per_second"] >= min_expected_rps
        
        return checks
    
    def generate_report(self, 
                       config: LoadTestConfig, 
                       results: Dict[str, Any], 
                       checks: Dict[str, bool]) -> str:
        """Generate performance test report"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        report = f"""
# Load Test Report: {config.name}

**Test Date:** {timestamp}
**Description:** {config.description}

## Test Configuration
- **Host:** {config.host}
- **Users:** {config.users}
- **Spawn Rate:** {config.spawn_rate}
- **Run Time:** {config.run_time}
- **User Classes:** {', '.join(config.user_classes)}

## Performance Requirements
- **Max Average Response Time:** {config.max_avg_response_time}ms
- **Max 95th Percentile:** {config.max_p95_response_time}ms
- **Max Failure Rate:** {config.max_failure_rate}%
- **Expected RPS:** {config.expected_rps}

## Test Results
- **Total Requests:** {results['total_requests']:,}
- **Total Failures:** {results['total_failures']:,}
- **Average Response Time:** {results['avg_response_time']:.2f}ms
- **95th Percentile:** {results['p95_response_time']:.2f}ms
- **99th Percentile:** {results['p99_response_time']:.2f}ms
- **Requests per Second:** {results['requests_per_second']:.2f}
- **Failure Rate:** {results['failure_rate']:.2f}%

## Performance Check Results
"""
        
        for check_name, passed in checks.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            report += f"- **{check_name.replace('_', ' ').title()}:** {status}\n"
        
        overall_pass = all(checks.values())
        report += f"\n## Overall Result: {'✅ PASS' if overall_pass else '❌ FAIL'}\n"
        
        if not overall_pass:
            report += "\n## Recommendations\n"
            if not checks.get("avg_response_time", True):
                report += "- Average response time exceeds target. Consider optimizing application performance.\n"
            if not checks.get("p95_response_time", True):
                report += "- 95th percentile response time is too high. Check for performance bottlenecks.\n"
            if not checks.get("failure_rate", True):
                report += "- Failure rate is above acceptable threshold. Investigate error causes.\n"
            if not checks.get("requests_per_second", True):
                report += "- Request throughput is below expected. Consider scaling resources.\n"
        
        return report


class PerformanceMonitor:
    """Monitor system performance during load tests"""
    
    def __init__(self):
        self.metrics = []
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect system metrics"""
        # In a real implementation, this would collect actual system metrics
        # For now, return mock metrics
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_usage": 23.1,
            "network_io": {
                "bytes_sent": 1024000,
                "bytes_recv": 2048000
            },
            "queue_depths": {
                "collect": 5,
                "process": 3,
                "publish": 1
            },
            "active_workers": 6,
            "database_connections": 8
        }
    
    def start_monitoring(self, interval: int = 30):
        """Start collecting metrics at regular intervals"""
        # This would run in a separate thread/process
        pass
    
    def stop_monitoring(self):
        """Stop collecting metrics"""
        pass
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics"""
        if not self.metrics:
            return {}
        
        # Calculate averages, peaks, etc.
        return {
            "avg_cpu_usage": 45.2,
            "peak_cpu_usage": 78.5,
            "avg_memory_usage": 67.8,
            "peak_memory_usage": 89.2,
            "max_queue_depth": 15,
            "avg_active_workers": 6
        }


if __name__ == "__main__":
    # Example usage
    runner = LoadTestRunner()
    configs = runner.load_configs()
    
    # Generate commands for all test configurations
    print("Available Load Test Configurations:")
    print("=" * 50)
    
    for name, config in configs.items():
        print(f"\n{name.upper()}:")
        print(f"Description: {config.description}")
        print(f"Command: {runner.generate_locust_command(config)}")
    
    # Save default configurations
    runner.save_configs(configs)
    print(f"\nConfigurations saved to: {runner.config_file}")