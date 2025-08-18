#!/usr/bin/env python3
"""
Task 18.3 Test Configuration
System Quality Verification Test Configuration
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class DatabaseTestConfig:
    """Database test configuration"""
    host: str = "localhost"
    port: str = "5432"
    database: str = "reddit_publisher"
    user: str = "postgres"
    password: str = "postgres"
    
    required_tables: List[str] = None
    required_indexes: List[str] = None
    required_constraints: List[str] = None
    
    def __post_init__(self):
        if self.required_tables is None:
            self.required_tables = ['posts', 'media_files', 'processing_logs', 'token_usage']
        
        if self.required_indexes is None:
            self.required_indexes = ['idx_posts_reddit_post_id', 'idx_posts_created_ts', 'idx_posts_subreddit']
        
        if self.required_constraints is None:
            self.required_constraints = ['posts_reddit_post_id_key', 'posts_pkey']

@dataclass
class SecurityTestConfig:
    """Security test configuration"""
    required_env_vars: List[str] = None
    sensitive_patterns: List[str] = None
    log_files_to_check: List[str] = None
    
    def __post_init__(self):
        if self.required_env_vars is None:
            self.required_env_vars = [
                'REDDIT_CLIENT_ID',
                'REDDIT_CLIENT_SECRET', 
                'OPENAI_API_KEY',
                'GHOST_ADMIN_KEY',
                'SLACK_WEBHOOK_URL'
            ]
        
        if self.sensitive_patterns is None:
            self.sensitive_patterns = [
                r'(api[_-]?key["\s]*[:=]["\s]*)([a-zA-Z0-9-_]{10,})',
                r'(token["\s]*[:=]["\s]*)([a-zA-Z0-9-_]{10,})',
                r'(secret["\s]*[:=]["\s]*)([a-zA-Z0-9-_]{10,})',
                r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
        
        if self.log_files_to_check is None:
            self.log_files_to_check = [
                'logs/reddit_publisher.log',
                'logs/reddit_publisher_errors.log',
                'logs/security_audit.log'
            ]

@dataclass
class ObservabilityTestConfig:
    """Observability test configuration"""
    api_base_url: str = "http://localhost:8000"
    health_endpoint: str = "/health"
    metrics_endpoint: str = "/metrics"
    
    required_health_fields: List[str] = None
    required_metrics: List[str] = None
    alert_thresholds: Dict[str, float] = None
    
    def __post_init__(self):
        if self.required_health_fields is None:
            self.required_health_fields = ['status', 'timestamp', 'services']
        
        if self.required_metrics is None:
            self.required_metrics = [
                'reddit_posts_collected_total',
                'posts_processed_total', 
                'posts_published_total',
                'processing_failures_total'
            ]
        
        if self.alert_thresholds is None:
            self.alert_thresholds = {
                'failure_rate': 0.05,  # 5%
                'queue_threshold': 500,
                'api_budget_warning': 0.8,  # 80%
                'token_budget_warning': 0.8  # 80%
            }

@dataclass
class CITestConfig:
    """CI/CD test configuration"""
    coverage_threshold: float = 70.0
    docker_build_timeout: int = 300  # 5 minutes
    test_timeout: int = 600  # 10 minutes
    
    required_workflow_files: List[str] = None
    required_test_files: List[str] = None
    postman_collection_path: str = "tests/postman/reddit-ghost-publisher-smoke-tests.json"
    postman_environment_path: str = "tests/postman/test-environment.json"
    
    def __post_init__(self):
        if self.required_workflow_files is None:
            self.required_workflow_files = [
                '.github/workflows/ci.yml',
                '.github/workflows/main.yml'
            ]
        
        if self.required_test_files is None:
            self.required_test_files = [
                'pyproject.toml',
                'pytest.ini',
                '.coveragerc'
            ]

@dataclass
class SystemQualityTestConfig:
    """Main system quality test configuration"""
    database: DatabaseTestConfig = None
    security: SecurityTestConfig = None
    observability: ObservabilityTestConfig = None
    ci: CITestConfig = None
    
    # Test execution settings
    parallel_execution: bool = False
    stop_on_first_failure: bool = False
    verbose_output: bool = True
    save_results: bool = True
    results_file: str = "system_quality_test_results.json"
    
    def __post_init__(self):
        if self.database is None:
            self.database = DatabaseTestConfig()
        if self.security is None:
            self.security = SecurityTestConfig()
        if self.observability is None:
            self.observability = ObservabilityTestConfig()
        if self.ci is None:
            self.ci = CITestConfig()
    
    @classmethod
    def from_environment(cls) -> 'SystemQualityTestConfig':
        """Create configuration from environment variables"""
        config = cls()
        
        # Override database config from environment
        config.database.host = os.getenv('DB_HOST', config.database.host)
        config.database.port = os.getenv('DB_PORT', config.database.port)
        config.database.database = os.getenv('DB_NAME', config.database.database)
        config.database.user = os.getenv('DB_USER', config.database.user)
        config.database.password = os.getenv('DB_PASSWORD', config.database.password)
        
        # Override observability config from environment
        config.observability.api_base_url = os.getenv('API_BASE_URL', config.observability.api_base_url)
        
        # Override CI config from environment
        coverage_threshold = os.getenv('COVERAGE_THRESHOLD')
        if coverage_threshold:
            config.ci.coverage_threshold = float(coverage_threshold)
        
        return config

# Test requirement mappings for Requirements 11.23-11.33
REQUIREMENT_TEST_MAPPING = {
    '11.23': {
        'name': 'Database Schema/Constraints Test',
        'description': 'Test database schema, constraints, and indexes',
        'test_methods': ['test_database_schema_constraints']
    },
    '11.24': {
        'name': 'Backup/Recovery Test', 
        'description': 'Test backup creation and recovery procedures',
        'test_methods': ['test_backup_recovery']
    },
    '11.25': {
        'name': 'Secret Management/Log Masking Test',
        'description': 'Test environment variable security and PII masking',
        'test_methods': ['test_secret_management_log_masking']
    },
    '11.26': {
        'name': 'Takedown Workflow Test',
        'description': 'Test takedown request handling and audit logging',
        'test_methods': ['test_takedown_workflow']
    },
    '11.27': {
        'name': 'Reddit API Compliance Test',
        'description': 'Test Reddit API policy compliance and rate limiting',
        'test_methods': ['test_reddit_api_compliance']
    },
    '11.28': {
        'name': 'Health/Metrics Endpoints Test',
        'description': 'Test /health and /metrics endpoint functionality',
        'test_methods': ['test_health_metrics_endpoints']
    },
    '11.29': {
        'name': 'Failure Rate/Queue Alerting Test',
        'description': 'Test alerting system for failures and queue backlogs',
        'test_methods': ['test_alerting_system']
    },
    '11.30': {
        'name': 'Daily Report Test',
        'description': 'Test daily report generation and Slack integration',
        'test_methods': ['test_daily_report']
    },
    '11.31': {
        'name': 'Unit Test Coverage Test',
        'description': 'Test unit test coverage meets 70% threshold',
        'test_methods': ['test_unit_test_coverage']
    },
    '11.32': {
        'name': 'Docker Build/Deployment Test',
        'description': 'Test Docker build and CI/CD deployment configuration',
        'test_methods': ['test_docker_build_deployment']
    },
    '11.33': {
        'name': 'Postman Smoke Tests',
        'description': 'Test API endpoints with Postman smoke test suite',
        'test_methods': ['test_postman_smoke_tests']
    }
}

# Expected test outcomes for each requirement
EXPECTED_OUTCOMES = {
    '11.23': {
        'database_tables_exist': True,
        'unique_constraints_present': True,
        'required_indexes_exist': True,
        'required_columns_present': True
    },
    '11.24': {
        'backup_script_exists': True,
        'backup_directory_exists': True,
        'restore_script_exists': True,
        'backup_files_created': True
    },
    '11.25': {
        'environment_variables_set': True,
        'log_masking_implemented': True,
        'no_exposed_secrets': True
    },
    '11.26': {
        'takedown_manager_exists': True,
        'takedown_workflow_implemented': True,
        'audit_logging_present': True,
        'takedown_api_endpoint': True
    },
    '11.27': {
        'reddit_client_exists': True,
        'official_api_usage': True,
        'rate_limiting_implemented': True,
        'no_web_scraping': True
    },
    '11.28': {
        'health_endpoint_working': True,
        'metrics_endpoint_working': True,
        'prometheus_format': True
    },
    '11.29': {
        'alert_service_exists': True,
        'failure_rate_monitoring': True,
        'queue_monitoring': True,
        'slack_integration': True
    },
    '11.30': {
        'daily_report_service': True,
        'required_metrics_included': True,
        'slack_reporting': True
    },
    '11.31': {
        'test_configuration_exists': True,
        'pytest_available': True,
        'coverage_threshold_met': True,
        'all_tests_pass': True
    },
    '11.32': {
        'dockerfile_exists': True,
        'docker_build_works': True,
        'github_actions_workflow': True,
        'manual_approval_configured': True
    },
    '11.33': {
        'postman_collection_exists': True,
        'newman_available': True,
        'api_responding': True,
        'smoke_tests_pass': True
    }
}

def get_test_config() -> SystemQualityTestConfig:
    """Get the test configuration"""
    return SystemQualityTestConfig.from_environment()

def get_requirement_info(requirement_id: str) -> Optional[Dict]:
    """Get information about a specific requirement"""
    return REQUIREMENT_TEST_MAPPING.get(requirement_id)

def get_expected_outcomes(requirement_id: str) -> Optional[Dict]:
    """Get expected outcomes for a specific requirement"""
    return EXPECTED_OUTCOMES.get(requirement_id)

def list_all_requirements() -> List[str]:
    """List all requirement IDs"""
    return list(REQUIREMENT_TEST_MAPPING.keys())

if __name__ == "__main__":
    # Print configuration for debugging
    config = get_test_config()
    print("System Quality Test Configuration:")
    print(f"Database: {config.database}")
    print(f"Security: {config.security}")
    print(f"Observability: {config.observability}")
    print(f"CI: {config.ci}")
    
    print("\nRequirement Test Mapping:")
    for req_id, req_info in REQUIREMENT_TEST_MAPPING.items():
        print(f"{req_id}: {req_info['name']}")