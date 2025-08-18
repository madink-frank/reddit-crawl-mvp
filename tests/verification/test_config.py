"""
Test configuration for MVP system verification tests
Defines test parameters, thresholds, and validation criteria
"""

import os
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class TestEnvironment:
    """Test environment configuration"""
    name: str
    api_base_url: str
    database_url: str
    redis_url: str
    slack_webhook_url: str
    
    # API limits for testing
    reddit_daily_calls_limit: int
    openai_daily_tokens_limit: int
    
    # Processing configuration
    subreddits: List[str]
    batch_size: int
    
    # Alert thresholds
    queue_alert_threshold: int
    failure_rate_threshold: float
    
    # Retry configuration
    retry_max: int
    backoff_base: int
    backoff_min: int
    backoff_max: int

# Staging environment configuration
STAGING_ENV = TestEnvironment(
    name="staging",
    api_base_url="http://localhost:8001",
    database_url="postgresql://postgres:postgres_staging@localhost:5433/reddit_publisher_staging",
    redis_url="redis://localhost:6380/0",
    slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK/URL"),
    
    # Lower limits for testing
    reddit_daily_calls_limit=100,
    openai_daily_tokens_limit=1000,
    
    # Small batches for testing
    subreddits=["programming", "technology"],
    batch_size=5,
    
    # Lower thresholds for testing
    queue_alert_threshold=10,
    failure_rate_threshold=0.05,
    
    # Standard retry configuration
    retry_max=3,
    backoff_base=2,
    backoff_min=2,
    backoff_max=8
)

# Test validation criteria
class ValidationCriteria:
    """Validation criteria for different test categories"""
    
    # Reddit collection tests (Requirement 1)
    REDDIT_COLLECTION = {
        "min_posts_collected": 5,
        "max_api_calls_per_minute": 60,
        "nsfw_filter_success_rate": 1.0,  # 100% NSFW posts should be filtered
        "duplicate_prevention_rate": 1.0,  # 100% duplicates should be prevented
        "budget_alert_accuracy": 1.0,  # 100% budget alerts should be accurate
    }
    
    # AI processing tests (Requirement 2)
    AI_PROCESSING = {
        "summary_generation_success_rate": 0.95,  # 95% success rate
        "fallback_trigger_rate": 0.1,  # 10% should trigger fallback
        "tag_count_range": (3, 5),  # 3-5 tags per post
        "json_schema_compliance_rate": 1.0,  # 100% schema compliance
        "retry_success_rate": 0.8,  # 80% retry success rate
        "token_budget_accuracy": 1.0,  # 100% budget tracking accuracy
    }
    
    # Ghost publishing tests (Requirement 3)
    GHOST_PUBLISHING = {
        "template_consistency_rate": 1.0,  # 100% template consistency
        "auth_success_rate": 1.0,  # 100% authentication success
        "image_upload_success_rate": 0.95,  # 95% image upload success
        "tag_mapping_accuracy": 1.0,  # 100% tag mapping accuracy
        "source_attribution_rate": 1.0,  # 100% source attribution
        "idempotency_rate": 1.0,  # 100% idempotency
    }
    
    # Architecture tests (Requirement 4)
    ARCHITECTURE = {
        "queue_routing_accuracy": 1.0,  # 100% correct queue routing
        "manual_scaling_alert_rate": 1.0,  # 100% scaling alerts
        "worker_health_check_rate": 1.0,  # 100% worker health checks
    }
    
    # Database tests (Requirement 5)
    DATABASE = {
        "schema_compliance_rate": 1.0,  # 100% schema compliance
        "constraint_enforcement_rate": 1.0,  # 100% constraint enforcement
        "backup_success_rate": 1.0,  # 100% backup success
        "restore_success_rate": 1.0,  # 100% restore success
    }
    
    # Security tests (Requirement 6)
    SECURITY = {
        "secret_masking_rate": 1.0,  # 100% secret masking
        "takedown_sla_compliance_rate": 1.0,  # 100% SLA compliance
        "api_policy_compliance_rate": 1.0,  # 100% API policy compliance
    }
    
    # Monitoring tests (Requirement 7)
    MONITORING = {
        "health_check_availability": 1.0,  # 100% health check availability
        "metrics_accuracy": 1.0,  # 100% metrics accuracy
        "alert_trigger_accuracy": 1.0,  # 100% alert trigger accuracy
        "daily_report_accuracy": 1.0,  # 100% daily report accuracy
    }
    
    # CI/CD tests (Requirement 8)
    CI_CD = {
        "unit_test_coverage": 0.7,  # 70% minimum coverage
        "build_success_rate": 1.0,  # 100% build success
        "smoke_test_pass_rate": 1.0,  # 100% smoke test pass rate
    }
    
    # Performance tests (Requirement 9)
    PERFORMANCE = {
        "api_p95_response_time_ms": 300,  # p95 < 300ms
        "e2e_processing_time_minutes": 5,  # < 5 minutes
        "throughput_posts_per_hour": 100,  # 100 posts/hour
        "failure_recovery_rate": 1.0,  # 100% failure recovery
    }
    
    # UX tests (Requirement 10)
    UX = {
        "template_consistency_rate": 1.0,  # 100% template consistency
        "tag_limit_compliance_rate": 1.0,  # 100% tag limit compliance
        "image_fallback_rate": 1.0,  # 100% image fallback when needed
    }

# Test execution configuration
class TestExecution:
    """Test execution parameters and timeouts"""
    
    # Test timeouts (in seconds)
    TIMEOUTS = {
        "api_request": 30,
        "database_query": 10,
        "redis_operation": 5,
        "external_api_call": 60,
        "e2e_test": 600,  # 10 minutes
        "performance_test": 300,  # 5 minutes
    }
    
    # Test retry configuration
    RETRIES = {
        "max_retries": 3,
        "retry_delay": 2,
        "backoff_multiplier": 2,
    }
    
    # Test data sizes
    DATA_SIZES = {
        "small_batch": 5,
        "medium_batch": 20,
        "large_batch": 100,
        "stress_test_batch": 500,
    }
    
    # Concurrent test limits
    CONCURRENCY = {
        "max_concurrent_requests": 10,
        "max_concurrent_workers": 3,
        "max_concurrent_db_connections": 5,
    }

# Test reporting configuration
class TestReporting:
    """Test reporting and output configuration"""
    
    # Report formats
    FORMATS = ["json", "html", "junit"]
    
    # Output directories
    OUTPUT_DIRS = {
        "reports": "tests/verification/reports",
        "logs": "tests/verification/logs", 
        "screenshots": "tests/verification/screenshots",
        "artifacts": "tests/verification/artifacts",
    }
    
    # Report sections
    SECTIONS = [
        "executive_summary",
        "test_results",
        "performance_metrics",
        "security_findings",
        "recommendations",
        "appendix"
    ]
    
    # Pass/fail criteria
    PASS_CRITERIA = {
        "functional_tests": 1.0,  # 100% functional tests must pass
        "performance_tests": 0.95,  # 95% performance tests must pass
        "security_tests": 1.0,  # 100% security tests must pass
        "integration_tests": 0.98,  # 98% integration tests must pass
    }

# Environment-specific overrides
def get_test_config(environment: str = "staging") -> Dict[str, Any]:
    """Get test configuration for specific environment"""
    
    base_config = {
        "environment": STAGING_ENV if environment == "staging" else None,
        "validation_criteria": ValidationCriteria,
        "execution": TestExecution,
        "reporting": TestReporting,
    }
    
    # Environment-specific overrides
    if environment == "staging":
        base_config.update({
            "debug_mode": True,
            "verbose_logging": True,
            "fail_fast": False,
            "parallel_execution": False,
        })
    elif environment == "production":
        base_config.update({
            "debug_mode": False,
            "verbose_logging": False,
            "fail_fast": True,
            "parallel_execution": True,
        })
    
    return base_config

# Test suite configuration
TEST_SUITES = {
    "smoke": {
        "description": "Basic functionality smoke tests",
        "tests": [
            "test_health_check",
            "test_basic_api_endpoints",
            "test_database_connection",
            "test_redis_connection",
        ],
        "timeout": 300,  # 5 minutes
        "required_pass_rate": 1.0,
    },
    "functional": {
        "description": "Full functional test suite",
        "tests": [
            "test_reddit_collection",
            "test_ai_processing", 
            "test_ghost_publishing",
            "test_queue_routing",
        ],
        "timeout": 1800,  # 30 minutes
        "required_pass_rate": 0.95,
    },
    "performance": {
        "description": "Performance and load tests",
        "tests": [
            "test_api_response_times",
            "test_e2e_processing_time",
            "test_throughput_capacity",
        ],
        "timeout": 900,  # 15 minutes
        "required_pass_rate": 0.90,
    },
    "security": {
        "description": "Security and compliance tests",
        "tests": [
            "test_secret_masking",
            "test_takedown_workflow",
            "test_api_policy_compliance",
        ],
        "timeout": 600,  # 10 minutes
        "required_pass_rate": 1.0,
    },
    "integration": {
        "description": "End-to-end integration tests",
        "tests": [
            "test_full_pipeline",
            "test_error_recovery",
            "test_monitoring_alerts",
        ],
        "timeout": 2400,  # 40 minutes
        "required_pass_rate": 0.95,
    }
}