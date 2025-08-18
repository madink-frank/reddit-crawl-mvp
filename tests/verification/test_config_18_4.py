"""
Configuration for Task 18.4: Performance and UX Verification Tests
Requirements 11.34-11.40
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class PerformanceConfig:
    """Performance testing configuration"""
    # API Performance (Req 11.34)
    api_p95_target_ms: int = 300
    api_p95_alert_threshold_ms: int = 400
    k6_test_duration_minutes: int = 5
    k6_max_users: int = 100
    k6_ramp_up_duration: str = "30s"
    k6_sustained_duration: str = "2m"
    
    # E2E Processing (Req 11.35)
    e2e_target_seconds: int = 300  # 5 minutes
    e2e_test_posts: int = 10
    e2e_timeout_seconds: int = 600  # 10 minutes max
    
    # Throughput Stability (Req 11.36)
    throughput_target_posts_per_hour: int = 100
    throughput_failure_rate_threshold: float = 0.05  # 5%
    throughput_test_duration_minutes: int = 10  # Compressed for testing
    throughput_test_posts: int = 10  # Scaled down for testing
    retry_max_attempts: int = 3
    retry_backoff_seconds: int = 2

@dataclass
class UXConfig:
    """UX and template testing configuration"""
    # Template Consistency (Req 11.37)
    template_test_posts: int = 5
    required_sections: List[str] = None
    
    # Tag Formatting (Req 11.38)
    tag_test_posts: int = 20
    tag_min_count: int = 3
    tag_max_count: int = 5
    tag_formatting_rules: List[str] = None
    
    # Image Fallback (Req 11.39)
    default_og_image_url: str = "https://example.com/default-og-image.jpg"
    
    def __post_init__(self):
        if self.required_sections is None:
            self.required_sections = [
                "title",
                "summary", 
                "key_insights",
                "original_link",
                "source_attribution"
            ]
        
        if self.tag_formatting_rules is None:
            self.tag_formatting_rules = [
                "lowercase_or_korean",
                "no_special_characters",
                "consistent_spacing"
            ]

@dataclass
class ReleaseGateConfig:
    """Release gate criteria configuration (Req 11.40)"""
    # Functionality requirements
    functionality_core_endpoints: List[str] = None
    
    # Quality requirements
    unit_coverage_threshold: float = 0.70  # 70%
    smoke_test_pass_rate: float = 1.0  # 100%
    
    # Performance requirements
    performance_p95_threshold_ms: int = 300
    performance_e2e_threshold_seconds: int = 300
    performance_failure_rate_threshold: float = 0.05
    
    # Operations requirements
    required_env_vars: List[str] = None
    required_scripts: List[str] = None
    
    def __post_init__(self):
        if self.functionality_core_endpoints is None:
            self.functionality_core_endpoints = [
                "/health",
                "/metrics",
                "/api/v1/collect/trigger",
                "/api/v1/process/trigger",
                "/api/v1/publish/trigger",
                "/api/v1/status/queues",
                "/api/v1/status/workers"
            ]
        
        if self.required_env_vars is None:
            self.required_env_vars = [
                "REDDIT_CLIENT_ID",
                "REDDIT_CLIENT_SECRET",
                "OPENAI_API_KEY",
                "GHOST_ADMIN_KEY",
                "SLACK_WEBHOOK_URL"
            ]
        
        if self.required_scripts is None:
            self.required_scripts = [
                "scripts/backup-database.sh",
                "scripts/restore-database.sh",
                "docker-compose.yml",
                "Dockerfile"
            ]

@dataclass
class TestEnvironmentConfig:
    """Test environment configuration"""
    api_base_url: str = "http://localhost:8000"
    ghost_staging_url: str = "https://staging.example.ghost.io"
    slack_test_webhook_url: str = ""
    
    # Database configuration
    test_db_url: str = "postgresql://test:test@localhost:5432/reddit_publisher_test"
    
    # Redis configuration
    test_redis_url: str = "redis://localhost:6379/1"
    
    # Test data
    test_subreddits: List[str] = None
    test_batch_size: int = 5
    
    # Timeouts
    api_timeout_seconds: int = 30
    long_operation_timeout_seconds: int = 300
    
    def __post_init__(self):
        if self.test_subreddits is None:
            self.test_subreddits = [
                "technology",
                "programming", 
                "MachineLearning",
                "artificial",
                "datascience"
            ]

@dataclass
class Task18_4Config:
    """Complete configuration for Task 18.4 tests"""
    performance: PerformanceConfig
    ux: UXConfig
    release_gate: ReleaseGateConfig
    environment: TestEnvironmentConfig
    
    # Test execution settings
    stop_on_first_failure: bool = False
    parallel_execution: bool = False
    save_detailed_results: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

# Requirement to test method mapping for Task 18.4
REQUIREMENT_TEST_MAPPING_18_4 = {
    "11.34": {
        "name": "API p95 Performance Testing",
        "description": "Test that p95 response time ≤ 300ms with alert threshold at 400ms",
        "test_methods": ["test_api_p95_performance"],
        "requirements": ["Req 9.1"]
    },
    "11.35": {
        "name": "E2E Processing Time Testing", 
        "description": "Test that each post processes from collection to publishing in ≤ 5 minutes",
        "test_methods": ["test_e2e_processing_time"],
        "requirements": ["Req 9.2"]
    },
    "11.36": {
        "name": "Throughput Stability Testing",
        "description": "Test 100 posts/hour processing with <5% failure rate and retry recovery",
        "test_methods": ["test_throughput_stability"],
        "requirements": ["Req 9.3", "Req 9.4"]
    },
    "11.37": {
        "name": "Article Template Consistency Testing",
        "description": "Test that 5 random posts maintain consistent section order and styling",
        "test_methods": ["test_article_template_consistency"],
        "requirements": ["Req 10.1", "Req 10.2"]
    },
    "11.38": {
        "name": "Tag Limits and Formatting Testing",
        "description": "Test that recent 20 posts have 3-5 tags with consistent formatting",
        "test_methods": ["test_tag_limits_and_formatting"],
        "requirements": ["Req 10.3", "Req 10.4"]
    },
    "11.39": {
        "name": "Image Fallback Testing",
        "description": "Test that posts without media use default OG image",
        "test_methods": ["test_image_fallback"],
        "requirements": ["Req 10.5"]
    },
    "11.40": {
        "name": "Final Release Gate Criteria",
        "description": "Test all conditions: functionality, quality, performance, operations",
        "test_methods": ["test_final_release_gate_criteria"],
        "requirements": ["Req 1-10 (all)"]
    }
}

# Expected outcomes for each requirement
EXPECTED_OUTCOMES_18_4 = {
    "11.34": {
        "p95_duration_ms": {"operator": "<=", "value": 300},
        "alert_threshold_met": {"operator": "==", "value": True},
        "error_rate": {"operator": "<", "value": 0.05}
    },
    "11.35": {
        "average_processing_time_seconds": {"operator": "<=", "value": 300},
        "posts_within_limit_rate": {"operator": "==", "value": 1.0}
    },
    "11.36": {
        "failure_rate": {"operator": "<", "value": 0.05},
        "retry_recovery": {"operator": "==", "value": True},
        "throughput_stability": {"operator": "==", "value": True}
    },
    "11.37": {
        "template_consistency_rate": {"operator": "==", "value": 1.0},
        "section_order_consistent": {"operator": "==", "value": True}
    },
    "11.38": {
        "tag_compliance_rate": {"operator": "==", "value": 1.0},
        "formatting_violations": {"operator": "==", "value": 0}
    },
    "11.39": {
        "default_og_image_applied": {"operator": "==", "value": True}
    },
    "11.40": {
        "functionality_gate": {"operator": "==", "value": True},
        "quality_gate": {"operator": "==", "value": True},
        "performance_gate": {"operator": "==", "value": True},
        "operations_gate": {"operator": "==", "value": True}
    }
}

def get_task_18_4_config() -> Task18_4Config:
    """Get the complete Task 18.4 test configuration"""
    
    # Load from environment variables if available
    performance = PerformanceConfig(
        api_p95_target_ms=int(os.getenv('PERF_API_P95_TARGET_MS', '300')),
        api_p95_alert_threshold_ms=int(os.getenv('PERF_API_P95_ALERT_MS', '400')),
        k6_max_users=int(os.getenv('PERF_K6_MAX_USERS', '100')),
        e2e_test_posts=int(os.getenv('PERF_E2E_TEST_POSTS', '10')),
        throughput_test_posts=int(os.getenv('PERF_THROUGHPUT_TEST_POSTS', '10'))
    )
    
    ux = UXConfig(
        template_test_posts=int(os.getenv('UX_TEMPLATE_TEST_POSTS', '5')),
        tag_test_posts=int(os.getenv('UX_TAG_TEST_POSTS', '20')),
        default_og_image_url=os.getenv('UX_DEFAULT_OG_IMAGE_URL', 'https://example.com/default-og-image.jpg')
    )
    
    release_gate = ReleaseGateConfig(
        unit_coverage_threshold=float(os.getenv('GATE_COVERAGE_THRESHOLD', '0.70')),
        performance_p95_threshold_ms=int(os.getenv('GATE_P95_THRESHOLD_MS', '300'))
    )
    
    environment = TestEnvironmentConfig(
        api_base_url=os.getenv('TEST_API_BASE_URL', 'http://localhost:8000'),
        ghost_staging_url=os.getenv('TEST_GHOST_STAGING_URL', 'https://staging.example.ghost.io'),
        slack_test_webhook_url=os.getenv('TEST_SLACK_WEBHOOK_URL', ''),
        test_batch_size=int(os.getenv('TEST_BATCH_SIZE', '5'))
    )
    
    return Task18_4Config(
        performance=performance,
        ux=ux,
        release_gate=release_gate,
        environment=environment,
        stop_on_first_failure=os.getenv('TEST_STOP_ON_FAILURE', 'false').lower() == 'true',
        parallel_execution=os.getenv('TEST_PARALLEL', 'false').lower() == 'true',
        log_level=os.getenv('TEST_LOG_LEVEL', 'INFO')
    )

def list_all_requirements_18_4() -> List[str]:
    """List all requirements for Task 18.4"""
    return list(REQUIREMENT_TEST_MAPPING_18_4.keys())

def get_requirement_info_18_4(requirement_id: str) -> Dict[str, Any]:
    """Get information about a specific requirement"""
    return REQUIREMENT_TEST_MAPPING_18_4.get(requirement_id, {})

def validate_config(config: Task18_4Config) -> List[str]:
    """Validate the configuration and return any issues"""
    issues = []
    
    # Validate performance thresholds
    if config.performance.api_p95_target_ms <= 0:
        issues.append("API p95 target must be positive")
    
    if config.performance.api_p95_alert_threshold_ms <= config.performance.api_p95_target_ms:
        issues.append("Alert threshold must be higher than target threshold")
    
    # Validate UX settings
    if config.ux.tag_min_count >= config.ux.tag_max_count:
        issues.append("Tag min count must be less than max count")
    
    # Validate environment
    if not config.environment.api_base_url.startswith(('http://', 'https://')):
        issues.append("API base URL must start with http:// or https://")
    
    return issues

# Example usage and testing
if __name__ == "__main__":
    config = get_task_18_4_config()
    issues = validate_config(config)
    
    if issues:
        print("Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Configuration is valid")
    
    print(f"\nTask 18.4 Configuration:")
    print(f"  Performance - API p95 target: {config.performance.api_p95_target_ms}ms")
    print(f"  Performance - E2E target: {config.performance.e2e_target_seconds}s")
    print(f"  UX - Template test posts: {config.ux.template_test_posts}")
    print(f"  UX - Tag test posts: {config.ux.tag_test_posts}")
    print(f"  Environment - API URL: {config.environment.api_base_url}")
    
    print(f"\nAvailable requirements: {list_all_requirements_18_4()}")