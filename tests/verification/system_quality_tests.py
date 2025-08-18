#!/usr/bin/env python3
"""
Task 18.3: System Quality Verification Tests
Requirements 11.23-11.33 implementation
"""

import os
import sys
import json
import time
import requests
import subprocess
from datetime import datetime
from typing import Dict, List, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import redis

class SystemQualityVerifier:
    """System quality verification test suite"""
    
    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        
        # Configuration
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'reddit_publisher'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
        
        self.redis_config = {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': int(os.getenv('REDIS_PORT', '6379')),
            'db': 0
        }
        
        self.api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    def log_test_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        self.total_tests += 1
        
        result = {
            'test_name': test_name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.results.append(result)
        
        if passed:
            self.passed_tests += 1
            print(f"✓ PASS: {test_name}")
        else:
            self.failed_tests += 1
            print(f"✗ FAIL: {test_name}")
        
        if details:
            print(f"  Details: {details}")
    
    def test_database_schema_constraints(self):
        """Test 11.23: Database schema and constraints"""
        print("\n=== Database Schema/Constraints Tests ===")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Test table existence
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('posts', 'media_files', 'processing_logs', 'token_usage')
            """)
            tables = [row['table_name'] for row in cursor.fetchall()]
            
            required_tables = ['posts', 'media_files', 'processing_logs', 'token_usage']
            missing_tables = set(required_tables) - set(tables)
            
            if not missing_tables:
                self.log_test_result("Database Tables Exist", True, f"All required tables found: {tables}")
            else:
                self.log_test_result("Database Tables Exist", False, f"Missing tables: {missing_tables}")
            
            # Test unique constraints
            cursor.execute("""
                SELECT constraint_name FROM information_schema.table_constraints 
                WHERE table_name = 'posts' AND constraint_type = 'UNIQUE'
                AND constraint_name LIKE '%reddit_post_id%'
            """)
            unique_constraints = cursor.fetchall()
            
            if unique_constraints:
                self.log_test_result("Unique Constraints", True, "reddit_post_id unique constraint exists")
            else:
                self.log_test_result("Unique Constraints", False, "reddit_post_id unique constraint missing")
            
            # Test indexes
            cursor.execute("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'posts' AND indexname LIKE 'idx_%'
            """)
            indexes = [row['indexname'] for row in cursor.fetchall()]
            
            if len(indexes) >= 2:
                self.log_test_result("Database Indexes", True, f"Found indexes: {indexes}")
            else:
                self.log_test_result("Database Indexes", False, f"Insufficient indexes found: {indexes}")
            
            # Test required columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'posts'
                ORDER BY ordinal_position
            """)
            columns = {row['column_name']: row for row in cursor.fetchall()}
            
            required_columns = ['id', 'reddit_post_id', 'title', 'subreddit', 'takedown_status']
            missing_columns = set(required_columns) - set(columns.keys())
            
            if not missing_columns:
                self.log_test_result("Required Columns", True, f"All required columns present")
            else:
                self.log_test_result("Required Columns", False, f"Missing columns: {missing_columns}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.log_test_result("Database Connection", False, f"Database connection failed: {str(e)}")
    
    def test_backup_recovery(self):
        """Test 11.24: Backup and recovery"""
        print("\n=== Backup/Recovery Tests ===")
        
        # Check backup script exists
        backup_script = "scripts/backup-database.sh"
        if os.path.exists(backup_script):
            self.log_test_result("Backup Script Exists", True, f"Found {backup_script}")
            
            # Check if backup directory exists
            backup_dir = "backups"
            if os.path.exists(backup_dir):
                self.log_test_result("Backup Directory", True, f"Backup directory exists: {backup_dir}")
                
                # List existing backups
                backup_files = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.sql')]
                if backup_files:
                    latest_backup = max(backup_files, key=lambda x: os.path.getctime(os.path.join(backup_dir, x)))
                    self.log_test_result("Backup Files Exist", True, f"Latest backup: {latest_backup}")
                else:
                    self.log_test_result("Backup Files Exist", False, "No backup files found")
            else:
                self.log_test_result("Backup Directory", False, f"Backup directory missing: {backup_dir}")
        else:
            self.log_test_result("Backup Script Exists", False, f"Backup script not found: {backup_script}")
        
        # Check restore script
        restore_script = "scripts/restore-database.sh"
        if os.path.exists(restore_script):
            self.log_test_result("Restore Script Exists", True, f"Found {restore_script}")
        else:
            self.log_test_result("Restore Script Exists", False, f"Restore script not found: {restore_script}")
    
    def test_secret_management_log_masking(self):
        """Test 11.25: Secret management and log masking"""
        print("\n=== Security/Secret Management Tests ===")
        
        # Check environment variables
        required_env_vars = ['REDDIT_CLIENT_ID', 'OPENAI_API_KEY', 'GHOST_ADMIN_KEY']
        missing_env_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if not missing_env_vars:
            self.log_test_result("Environment Variables", True, "All required environment variables set")
        else:
            self.log_test_result("Environment Variables", False, f"Missing env vars: {missing_env_vars}")
        
        # Check log masking implementation
        logging_config_file = "app/logging_config.py"
        if os.path.exists(logging_config_file):
            with open(logging_config_file, 'r') as f:
                content = f.read()
                if 'mask_sensitive_data' in content or 'PII' in content:
                    self.log_test_result("Log Masking Implementation", True, "PII masking functions found")
                else:
                    self.log_test_result("Log Masking Implementation", False, "PII masking functions not found")
        else:
            self.log_test_result("Log Masking Implementation", False, f"Logging config not found: {logging_config_file}")
        
        # Check for exposed secrets in logs
        log_file = "logs/reddit_publisher.log"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_content = f.read()
                # Look for potential API keys that aren't masked
                import re
                exposed_secrets = re.findall(r'(api[_-]?key|token|secret).*[^*]{10,}', log_content, re.IGNORECASE)
                exposed_secrets = [s for s in exposed_secrets if '****' not in s[1]]
                
                if not exposed_secrets:
                    self.log_test_result("Secret Exposure Check", True, "No exposed secrets in logs")
                else:
                    self.log_test_result("Secret Exposure Check", False, f"Potential exposed secrets: {len(exposed_secrets)}")
        else:
            self.log_test_result("Secret Exposure Check", True, "No log file to check (acceptable)")
    
    def test_takedown_workflow(self):
        """Test 11.26: Takedown workflow"""
        print("\n=== Takedown Workflow Tests ===")
        
        takedown_manager = "workers/takedown/takedown_manager.py"
        if os.path.exists(takedown_manager):
            self.log_test_result("Takedown Manager Exists", True, f"Found {takedown_manager}")
            
            with open(takedown_manager, 'r') as f:
                content = f.read()
                
                # Check for takedown workflow implementation
                if 'takedown_status' in content and ('unpublish' in content or '72' in content):
                    self.log_test_result("Takedown Workflow Logic", True, "Takedown workflow implementation found")
                else:
                    self.log_test_result("Takedown Workflow Logic", False, "Takedown workflow logic not found")
                
                # Check for audit logging
                if 'audit' in content and 'log' in content:
                    self.log_test_result("Takedown Audit Logging", True, "Audit logging implementation found")
                else:
                    self.log_test_result("Takedown Audit Logging", False, "Audit logging not found")
        else:
            self.log_test_result("Takedown Manager Exists", False, f"Takedown manager not found: {takedown_manager}")
        
        # Check takedown API endpoint
        try:
            response = requests.get(f"{self.api_base_url}/docs", timeout=5)
            if response.status_code == 200 and 'takedown' in response.text.lower():
                self.log_test_result("Takedown API Endpoint", True, "Takedown endpoint documented in API")
            else:
                self.log_test_result("Takedown API Endpoint", False, "Takedown endpoint not found in API docs")
        except Exception as e:
            self.log_test_result("Takedown API Endpoint", False, f"Could not check API docs: {str(e)}")
    
    def test_reddit_api_compliance(self):
        """Test 11.27: Reddit API policy compliance"""
        print("\n=== Reddit API Compliance Tests ===")
        
        reddit_client = "workers/collector/reddit_client.py"
        if os.path.exists(reddit_client):
            self.log_test_result("Reddit Client Exists", True, f"Found {reddit_client}")
            
            with open(reddit_client, 'r') as f:
                content = f.read()
                
                # Check for official API usage (PRAW)
                if 'praw' in content.lower() or 'reddit' in content and 'api' in content:
                    self.log_test_result("Official API Usage", True, "PRAW/Official API usage found")
                else:
                    self.log_test_result("Official API Usage", False, "Official API usage not confirmed")
                
                # Check for rate limiting
                if 'rate' in content and ('limit' in content or 'rpm' in content or '60' in content):
                    self.log_test_result("Rate Limiting Implementation", True, "Rate limiting implementation found")
                else:
                    self.log_test_result("Rate Limiting Implementation", False, "Rate limiting not found")
                
                # Check for absence of web scraping
                scraping_indicators = ['requests.get', 'urllib', 'BeautifulSoup', 'selenium', 'scrapy']
                found_scraping = [indicator for indicator in scraping_indicators if indicator in content]
                
                if not found_scraping:
                    self.log_test_result("No Web Scraping", True, "No web scraping detected")
                else:
                    self.log_test_result("No Web Scraping", False, f"Potential scraping found: {found_scraping}")
        else:
            self.log_test_result("Reddit Client Exists", False, f"Reddit client not found: {reddit_client}")
    
    def test_health_metrics_endpoints(self):
        """Test 11.28: /health and /metrics endpoints"""
        print("\n=== Health/Metrics Endpoints Tests ===")
        
        try:
            # Test /health endpoint
            health_response = requests.get(f"{self.api_base_url}/health", timeout=10)
            if health_response.status_code == 200:
                health_data = health_response.json()
                if 'status' in health_data:
                    self.log_test_result("/health Endpoint", True, f"Health status: {health_data.get('status')}")
                else:
                    self.log_test_result("/health Endpoint", False, "Health endpoint missing status field")
            else:
                self.log_test_result("/health Endpoint", False, f"Health endpoint returned {health_response.status_code}")
        except Exception as e:
            self.log_test_result("/health Endpoint", False, f"Health endpoint error: {str(e)}")
        
        try:
            # Test /metrics endpoint
            metrics_response = requests.get(f"{self.api_base_url}/metrics", timeout=10)
            if metrics_response.status_code == 200:
                metrics_text = metrics_response.text
                if 'reddit_posts' in metrics_text and 'counter' in metrics_text:
                    self.log_test_result("/metrics Endpoint", True, "Metrics endpoint returns Prometheus format")
                else:
                    self.log_test_result("/metrics Endpoint", False, "Metrics endpoint not in proper format")
            else:
                self.log_test_result("/metrics Endpoint", False, f"Metrics endpoint returned {metrics_response.status_code}")
        except Exception as e:
            self.log_test_result("/metrics Endpoint", False, f"Metrics endpoint error: {str(e)}")
    
    def test_alerting_system(self):
        """Test 11.29: Failure rate and queue alerting"""
        print("\n=== Alerting System Tests ===")
        
        alert_service = "app/monitoring/alert_service.py"
        if os.path.exists(alert_service):
            self.log_test_result("Alert Service Exists", True, f"Found {alert_service}")
            
            with open(alert_service, 'r') as f:
                content = f.read()
                
                # Check failure rate monitoring
                if 'failure' in content and ('rate' in content or '5%' in content or '0.05' in content):
                    self.log_test_result("Failure Rate Monitoring", True, "Failure rate monitoring found")
                else:
                    self.log_test_result("Failure Rate Monitoring", False, "Failure rate monitoring not found")
                
                # Check queue monitoring
                if 'queue' in content and ('500' in content or 'QUEUE_ALERT_THRESHOLD' in content):
                    self.log_test_result("Queue Monitoring", True, "Queue monitoring found")
                else:
                    self.log_test_result("Queue Monitoring", False, "Queue monitoring not found")
                
                # Check Slack integration
                if 'slack' in content.lower() or 'webhook' in content:
                    self.log_test_result("Slack Integration", True, "Slack integration found")
                else:
                    self.log_test_result("Slack Integration", False, "Slack integration not found")
        else:
            self.log_test_result("Alert Service Exists", False, f"Alert service not found: {alert_service}")
    
    def test_daily_report(self):
        """Test 11.30: Daily report system"""
        print("\n=== Daily Report Tests ===")
        
        daily_report = "app/monitoring/daily_report.py"
        if os.path.exists(daily_report):
            self.log_test_result("Daily Report Service", True, f"Found {daily_report}")
            
            with open(daily_report, 'r') as f:
                content = f.read()
                
                # Check required metrics
                required_metrics = ['collected', 'published', 'token']
                found_metrics = [metric for metric in required_metrics if metric in content.lower()]
                
                if len(found_metrics) >= 2:
                    self.log_test_result("Report Metrics", True, f"Found metrics: {found_metrics}")
                else:
                    self.log_test_result("Report Metrics", False, f"Missing metrics, found: {found_metrics}")
                
                # Check Slack reporting
                if 'slack' in content.lower() or 'webhook' in content or 'send' in content:
                    self.log_test_result("Daily Report Slack", True, "Slack reporting found")
                else:
                    self.log_test_result("Daily Report Slack", False, "Slack reporting not found")
        else:
            self.log_test_result("Daily Report Service", False, f"Daily report not found: {daily_report}")
    
    def test_unit_test_coverage(self):
        """Test 11.31: Unit test coverage 70%"""
        print("\n=== Unit Test Coverage Tests ===")
        
        # Check test configuration
        test_configs = ['pyproject.toml', 'pytest.ini', '.coveragerc']
        found_configs = [config for config in test_configs if os.path.exists(config)]
        
        if found_configs:
            self.log_test_result("Test Configuration", True, f"Found configs: {found_configs}")
        else:
            self.log_test_result("Test Configuration", False, "No test configuration found")
        
        # Check if pytest is available
        try:
            result = subprocess.run(['pytest', '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.log_test_result("Pytest Available", True, f"Pytest version: {result.stdout.strip()}")
                
                # Run coverage test
                try:
                    coverage_result = subprocess.run([
                        'pytest', '--cov=app', '--cov-report=term-missing', 
                        '--cov-fail-under=70', '--tb=short'
                    ], capture_output=True, text=True, timeout=300)
                    
                    # Parse coverage output
                    output = coverage_result.stdout + coverage_result.stderr
                    
                    # Look for coverage percentage
                    import re
                    coverage_match = re.search(r'TOTAL.*?(\d+)%', output)
                    if coverage_match:
                        coverage_percent = int(coverage_match.group(1))
                        if coverage_percent >= 70:
                            self.log_test_result("Unit Test Coverage", True, f"Coverage: {coverage_percent}% (≥70%)")
                        else:
                            self.log_test_result("Unit Test Coverage", False, f"Coverage: {coverage_percent}% (<70%)")
                    else:
                        if coverage_result.returncode == 0:
                            self.log_test_result("Unit Test Coverage", True, "Coverage test passed")
                        else:
                            self.log_test_result("Unit Test Coverage", False, "Coverage test failed")
                    
                    # Check test results
                    if 'failed' not in output or '0 failed' in output:
                        self.log_test_result("Unit Tests Pass", True, "All tests passing")
                    else:
                        self.log_test_result("Unit Tests Pass", False, "Some tests failing")
                        
                except subprocess.TimeoutExpired:
                    self.log_test_result("Unit Test Coverage", False, "Test execution timed out")
                except Exception as e:
                    self.log_test_result("Unit Test Coverage", False, f"Test execution error: {str(e)}")
            else:
                self.log_test_result("Pytest Available", False, "Pytest not working properly")
        except Exception as e:
            self.log_test_result("Pytest Available", False, f"Pytest not available: {str(e)}")
    
    def test_docker_build_deployment(self):
        """Test 11.32: Docker build and deployment configuration"""
        print("\n=== Docker Build/Deployment Tests ===")
        
        # Check Dockerfile
        if os.path.exists("Dockerfile"):
            self.log_test_result("Dockerfile Exists", True, "Dockerfile found")
            
            # Test Docker build (quick syntax check)
            try:
                result = subprocess.run([
                    'docker', 'build', '--dry-run', '-t', 'reddit-publisher-test', '.'
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    self.log_test_result("Docker Build Syntax", True, "Dockerfile syntax valid")
                else:
                    self.log_test_result("Docker Build Syntax", False, f"Docker build error: {result.stderr}")
            except Exception as e:
                self.log_test_result("Docker Build Syntax", False, f"Docker build test failed: {str(e)}")
        else:
            self.log_test_result("Dockerfile Exists", False, "Dockerfile not found")
        
        # Check GitHub Actions workflow
        workflow_files = []
        if os.path.exists(".github/workflows"):
            workflow_files = [f for f in os.listdir(".github/workflows") if f.endswith(('.yml', '.yaml'))]
        
        if workflow_files:
            self.log_test_result("GitHub Actions Workflow", True, f"Found workflows: {workflow_files}")
            
            # Check for manual approval configuration
            manual_approval_found = False
            for workflow_file in workflow_files:
                with open(f".github/workflows/{workflow_file}", 'r') as f:
                    content = f.read()
                    if 'manual' in content.lower() and 'approval' in content.lower():
                        manual_approval_found = True
                        break
                    if 'environment' in content and 'production' in content:
                        manual_approval_found = True
                        break
            
            if manual_approval_found:
                self.log_test_result("Manual Approval Config", True, "Manual approval found in workflow")
            else:
                self.log_test_result("Manual Approval Config", False, "Manual approval not configured")
        else:
            self.log_test_result("GitHub Actions Workflow", False, "No CI workflow found")
    
    def test_postman_smoke_tests(self):
        """Test 11.33: Postman smoke tests"""
        print("\n=== Postman Smoke Tests ===")
        
        postman_collection = "tests/postman/reddit-ghost-publisher-smoke-tests.json"
        if os.path.exists(postman_collection):
            self.log_test_result("Postman Collection", True, f"Found {postman_collection}")
            
            # Check if Newman is available
            try:
                result = subprocess.run(['newman', '--version'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.log_test_result("Newman Available", True, f"Newman version: {result.stdout.strip()}")
                    
                    # Check if API is running
                    try:
                        health_check = requests.get(f"{self.api_base_url}/health", timeout=5)
                        if health_check.status_code == 200:
                            # Run smoke tests
                            try:
                                newman_result = subprocess.run([
                                    'newman', 'run', postman_collection,
                                    '-e', 'tests/postman/test-environment.json',
                                    '--reporters', 'json',
                                    '--reporter-json-export', '/tmp/newman-results.json'
                                ], capture_output=True, text=True, timeout=120)
                                
                                if os.path.exists('/tmp/newman-results.json'):
                                    with open('/tmp/newman-results.json', 'r') as f:
                                        results = json.load(f)
                                        
                                    failed_tests = results.get('run', {}).get('stats', {}).get('assertions', {}).get('failed', 0)
                                    total_tests = results.get('run', {}).get('stats', {}).get('assertions', {}).get('total', 0)
                                    
                                    if failed_tests == 0 and total_tests > 0:
                                        self.log_test_result("Postman Smoke Tests", True, f"All {total_tests} assertions passed (100%)")
                                    else:
                                        self.log_test_result("Postman Smoke Tests", False, f"{failed_tests}/{total_tests} assertions failed")
                                    
                                    # Cleanup
                                    os.remove('/tmp/newman-results.json')
                                else:
                                    self.log_test_result("Postman Smoke Tests", False, "Could not parse Newman results")
                                    
                            except subprocess.TimeoutExpired:
                                self.log_test_result("Postman Smoke Tests", False, "Newman execution timed out")
                            except Exception as e:
                                self.log_test_result("Postman Smoke Tests", False, f"Newman execution error: {str(e)}")
                        else:
                            self.log_test_result("Postman Smoke Tests", False, f"API not responding (status: {health_check.status_code})")
                    except Exception as e:
                        self.log_test_result("Postman Smoke Tests", False, f"API health check failed: {str(e)}")
                else:
                    self.log_test_result("Newman Available", False, "Newman not working properly")
            except Exception as e:
                self.log_test_result("Newman Available", False, f"Newman not available: {str(e)}")
        else:
            self.log_test_result("Postman Collection", False, f"Collection not found: {postman_collection}")
    
    def run_all_tests(self):
        """Run all system quality verification tests"""
        print("=== System Quality Verification Tests ===")
        print(f"Starting tests at {datetime.utcnow().isoformat()}")
        
        # Database tests (Requirements 11.23-11.24)
        self.test_database_schema_constraints()
        self.test_backup_recovery()
        
        # Security/Compliance tests (Requirements 11.25-11.27)
        self.test_secret_management_log_masking()
        self.test_takedown_workflow()
        self.test_reddit_api_compliance()
        
        # Observability/Alerting tests (Requirements 11.28-11.30)
        self.test_health_metrics_endpoints()
        self.test_alerting_system()
        self.test_daily_report()
        
        # CI/Deployment tests (Requirements 11.31-11.33)
        self.test_unit_test_coverage()
        self.test_docker_build_deployment()
        self.test_postman_smoke_tests()
        
        # Print summary
        print(f"\n=== Test Results Summary ===")
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")
        
        if self.failed_tests == 0:
            print("✓ All system quality verification tests passed!")
            return True
        else:
            print("✗ Some system quality verification tests failed.")
            print("Please review the failed tests and fix the issues before proceeding.")
            return False
    
    def save_results(self, filename: str = "system_quality_test_results.json"):
        """Save test results to JSON file"""
        results_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_tests': self.total_tests,
                'passed_tests': self.passed_tests,
                'failed_tests': self.failed_tests,
                'success_rate': (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
            },
            'results': self.results
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"Test results saved to {filename}")

def main():
    """Main execution function"""
    verifier = SystemQualityVerifier()
    
    try:
        success = verifier.run_all_tests()
        verifier.save_results()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Test execution failed with error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()