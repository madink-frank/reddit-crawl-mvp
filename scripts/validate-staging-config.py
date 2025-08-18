#!/usr/bin/env python3
"""
Validate Staging Configuration for MVP Verification Tests
Checks environment variables, service connectivity, and test readiness
"""

import os
import sys
import json
import requests
import subprocess
from typing import Dict, List, Any
from datetime import datetime

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def log(message: str, color: str = Colors.NC):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')}]{Colors.NC} {message}")

def success(message: str):
    log(f"✅ {message}", Colors.GREEN)

def warning(message: str):
    log(f"⚠️  {message}", Colors.YELLOW)

def error(message: str):
    log(f"❌ {message}", Colors.RED)

def info(message: str):
    log(f"ℹ️  {message}", Colors.BLUE)

class StagingValidator:
    """Validates staging environment configuration"""
    
    def __init__(self):
        self.validation_results = {}
        self.overall_status = True
    
    def validate_all(self) -> Dict[str, Any]:
        """Run all validation checks"""
        info("Starting staging environment validation...")
        
        # 1. Environment variables
        env_result = self.validate_environment_variables()
        self.validation_results["environment_variables"] = env_result
        
        # 2. Docker environment
        docker_result = self.validate_docker_environment()
        self.validation_results["docker_environment"] = docker_result
        
        # 3. Service connectivity
        service_result = self.validate_service_connectivity()
        self.validation_results["service_connectivity"] = service_result
        
        # 4. External APIs
        api_result = self.validate_external_apis()
        self.validation_results["external_apis"] = api_result
        
        # 5. Database schema
        db_result = self.validate_database_schema()
        self.validation_results["database_schema"] = db_result
        
        # 6. Test data
        test_data_result = self.validate_test_data()
        self.validation_results["test_data"] = test_data_result
        
        # Generate summary
        summary = self.generate_summary()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": self.overall_status,
            "validation_results": self.validation_results,
            "summary": summary
        }
    
    def validate_environment_variables(self) -> Dict[str, Any]:
        """Validate required environment variables"""
        info("Validating environment variables...")
        
        # Load .env.staging if it exists
        env_file = ".env.staging"
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        
        required_vars = {
            "REDDIT_CLIENT_ID": "Reddit API client ID",
            "REDDIT_CLIENT_SECRET": "Reddit API client secret",
            "OPENAI_API_KEY": "OpenAI API key",
            "GHOST_ADMIN_KEY": "Ghost CMS admin key",
            "GHOST_API_URL": "Ghost CMS API URL",
            "SLACK_WEBHOOK_URL": "Slack webhook URL for notifications"
        }
        
        optional_vars = {
            "REDDIT_DAILY_CALLS_LIMIT": "100",
            "OPENAI_DAILY_TOKENS_LIMIT": "1000",
            "BATCH_SIZE": "5",
            "QUEUE_ALERT_THRESHOLD": "10",
            "RETRY_MAX": "3"
        }
        
        missing_required = []
        placeholder_values = []
        configured_vars = {}
        
        # Check required variables
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value:
                missing_required.append(f"{var} ({description})")
            elif value.startswith("your_") or "example" in value.lower():
                placeholder_values.append(f"{var} (has placeholder value)")
            else:
                configured_vars[var] = "✓ Configured"
        
        # Check optional variables
        for var, default in optional_vars.items():
            value = os.getenv(var, default)
            configured_vars[var] = f"✓ {value}"
        
        # Report results
        if missing_required:
            error(f"Missing required environment variables: {', '.join(missing_required)}")
            self.overall_status = False
        
        if placeholder_values:
            warning(f"Placeholder values detected: {', '.join(placeholder_values)}")
            self.overall_status = False
        
        if not missing_required and not placeholder_values:
            success("All required environment variables are configured")
        
        return {
            "passed": len(missing_required) == 0 and len(placeholder_values) == 0,
            "missing_required": missing_required,
            "placeholder_values": placeholder_values,
            "configured_variables": configured_vars
        }
    
    def validate_docker_environment(self) -> Dict[str, Any]:
        """Validate Docker Compose staging environment"""
        info("Validating Docker Compose staging environment...")
        
        try:
            # Check if docker-compose.staging.yml exists
            if not os.path.exists("docker-compose.staging.yml"):
                error("docker-compose.staging.yml not found")
                return {"passed": False, "error": "docker-compose.staging.yml not found"}
            
            # Check if services are running
            result = subprocess.run(
                ["docker-compose", "-f", "docker-compose.staging.yml", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                warning("Docker Compose staging environment not running")
                return {
                    "passed": False,
                    "running": False,
                    "message": "Run './scripts/setup-staging-environment.sh' to start"
                }
            
            # Parse service status
            services = []
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    try:
                        service_info = json.loads(line)
                        services.append({
                            "name": service_info.get("Name", "unknown"),
                            "status": service_info.get("State", "unknown"),
                            "health": service_info.get("Health", "unknown")
                        })
                    except json.JSONDecodeError:
                        continue
            
            running_services = [s for s in services if "running" in s["status"].lower()]
            healthy_services = [s for s in services if s["health"] == "healthy" or s["health"] == "unknown"]
            
            if len(running_services) >= 5:  # Expect at least 5 services
                success(f"Docker Compose staging environment running ({len(running_services)} services)")
                return {
                    "passed": True,
                    "running": True,
                    "services": services,
                    "running_count": len(running_services),
                    "healthy_count": len(healthy_services)
                }
            else:
                warning(f"Only {len(running_services)} services running (expected ≥5)")
                return {
                    "passed": False,
                    "running": True,
                    "services": services,
                    "running_count": len(running_services),
                    "message": "Some services may not be running properly"
                }
                
        except subprocess.TimeoutExpired:
            error("Docker command timed out")
            return {"passed": False, "error": "Docker command timeout"}
        except Exception as e:
            error(f"Docker validation failed: {e}")
            return {"passed": False, "error": str(e)}
    
    def validate_service_connectivity(self) -> Dict[str, Any]:
        """Validate internal service connectivity"""
        info("Validating service connectivity...")
        
        services = {
            "API": "http://localhost:8001/health",
            "Database": "postgresql://postgres:postgres_staging@localhost:5433/reddit_publisher_staging",
            "Redis": "redis://localhost:6380/0"
        }
        
        results = {}
        
        # Test API
        try:
            response = requests.get(services["API"], timeout=10)
            if response.status_code == 200:
                success("API service is accessible")
                results["API"] = {
                    "passed": True,
                    "status_code": response.status_code,
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            else:
                warning(f"API service returned status {response.status_code}")
                results["API"] = {
                    "passed": False,
                    "status_code": response.status_code
                }
        except Exception as e:
            error(f"API service not accessible: {e}")
            results["API"] = {"passed": False, "error": str(e)}
        
        # Test Database
        try:
            import psycopg2
            conn = psycopg2.connect(services["Database"])
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result[0] == 1:
                success("Database service is accessible")
                results["Database"] = {"passed": True}
            else:
                error("Database query failed")
                results["Database"] = {"passed": False, "error": "Query failed"}
                
        except Exception as e:
            error(f"Database service not accessible: {e}")
            results["Database"] = {"passed": False, "error": str(e)}
        
        # Test Redis
        try:
            import redis
            r = redis.from_url(services["Redis"])
            r.ping()
            success("Redis service is accessible")
            results["Redis"] = {"passed": True}
        except Exception as e:
            error(f"Redis service not accessible: {e}")
            results["Redis"] = {"passed": False, "error": str(e)}
        
        all_passed = all(result.get("passed", False) for result in results.values())
        if not all_passed:
            self.overall_status = False
        
        return {
            "passed": all_passed,
            "services": results
        }
    
    def validate_external_apis(self) -> Dict[str, Any]:
        """Validate external API connectivity"""
        info("Validating external API connectivity...")
        
        results = {}
        
        # Test Reddit API
        try:
            response = requests.get(
                "https://www.reddit.com/api/v1/me",
                headers={"User-Agent": "RedditGhostPublisher/1.0-staging"},
                timeout=10
            )
            # 401 is expected without proper auth, but means API is reachable
            if response.status_code in [200, 401, 403]:
                success("Reddit API is reachable")
                results["reddit"] = {"passed": True, "status_code": response.status_code}
            else:
                warning(f"Reddit API returned unexpected status: {response.status_code}")
                results["reddit"] = {"passed": False, "status_code": response.status_code}
        except Exception as e:
            error(f"Reddit API not reachable: {e}")
            results["reddit"] = {"passed": False, "error": str(e)}
        
        # Test OpenAI API
        try:
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', 'test')}"},
                timeout=10
            )
            if response.status_code in [200, 401]:
                success("OpenAI API is reachable")
                results["openai"] = {"passed": True, "status_code": response.status_code}
            else:
                warning(f"OpenAI API returned unexpected status: {response.status_code}")
                results["openai"] = {"passed": False, "status_code": response.status_code}
        except Exception as e:
            error(f"OpenAI API not reachable: {e}")
            results["openai"] = {"passed": False, "error": str(e)}
        
        # Test Ghost API
        ghost_url = os.getenv("GHOST_API_URL", "").rstrip('/')
        if ghost_url and not ghost_url.startswith("your-"):
            try:
                response = requests.get(f"{ghost_url}/ghost/api/admin/site/", timeout=10)
                if response.status_code in [200, 401, 403]:
                    success("Ghost API is reachable")
                    results["ghost"] = {"passed": True, "status_code": response.status_code}
                else:
                    warning(f"Ghost API returned unexpected status: {response.status_code}")
                    results["ghost"] = {"passed": False, "status_code": response.status_code}
            except Exception as e:
                error(f"Ghost API not reachable: {e}")
                results["ghost"] = {"passed": False, "error": str(e)}
        else:
            warning("Ghost API URL not configured or using placeholder")
            results["ghost"] = {"passed": False, "error": "Not configured"}
        
        # Test Slack webhook
        slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
        if slack_url and not slack_url.endswith("TEST/WEBHOOK/URL"):
            try:
                response = requests.post(
                    slack_url,
                    json={"text": "🧪 Staging validation test - please ignore"},
                    timeout=10
                )
                if response.status_code == 200:
                    success("Slack webhook is working")
                    results["slack"] = {"passed": True, "status_code": response.status_code}
                else:
                    warning(f"Slack webhook returned status: {response.status_code}")
                    results["slack"] = {"passed": False, "status_code": response.status_code}
            except Exception as e:
                error(f"Slack webhook not working: {e}")
                results["slack"] = {"passed": False, "error": str(e)}
        else:
            warning("Slack webhook URL not configured or using placeholder")
            results["slack"] = {"passed": False, "error": "Not configured"}
        
        return {
            "passed": True,  # External APIs are not critical for basic testing
            "services": results,
            "note": "External API failures won't block testing but may affect some test scenarios"
        }
    
    def validate_database_schema(self) -> Dict[str, Any]:
        """Validate database schema"""
        info("Validating database schema...")
        
        try:
            import psycopg2
            conn = psycopg2.connect("postgresql://postgres:postgres_staging@localhost:5433/reddit_publisher_staging")
            cursor = conn.cursor()
            
            # Check required tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ["posts", "media_files", "processing_logs", "token_usage"]
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                error(f"Missing database tables: {', '.join(missing_tables)}")
                cursor.close()
                conn.close()
                return {
                    "passed": False,
                    "missing_tables": missing_tables,
                    "existing_tables": tables
                }
            
            success("All required database tables exist")
            
            # Check if posts table has correct structure
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'posts' AND table_schema = 'public'
            """)
            columns = {row[0]: row[1] for row in cursor.fetchall()}
            
            required_columns = {
                "id": "uuid",
                "reddit_post_id": "text",
                "title": "text",
                "subreddit": "text",
                "takedown_status": "text"
            }
            
            missing_columns = []
            for col, expected_type in required_columns.items():
                if col not in columns:
                    missing_columns.append(col)
            
            cursor.close()
            conn.close()
            
            if missing_columns:
                error(f"Missing columns in posts table: {', '.join(missing_columns)}")
                return {
                    "passed": False,
                    "missing_columns": missing_columns,
                    "existing_columns": list(columns.keys())
                }
            
            success("Database schema validation passed")
            return {
                "passed": True,
                "tables": tables,
                "posts_columns": list(columns.keys())
            }
            
        except Exception as e:
            error(f"Database schema validation failed: {e}")
            return {"passed": False, "error": str(e)}
    
    def validate_test_data(self) -> Dict[str, Any]:
        """Validate test data availability"""
        info("Validating test data...")
        
        try:
            # Check if test data files exist
            test_files = [
                "tests/verification/seed_data.py",
                "tests/verification/test_config.py",
                "tests/verification/run_verification_tests.py"
            ]
            
            missing_files = [f for f in test_files if not os.path.exists(f)]
            
            if missing_files:
                error(f"Missing test files: {', '.join(missing_files)}")
                return {"passed": False, "missing_files": missing_files}
            
            # Try to import test data
            sys.path.insert(0, "tests/verification")
            from seed_data import SAMPLE_REDDIT_POSTS, TEST_CONFIGS
            from test_config import get_test_config
            
            # Validate test data structure
            if not SAMPLE_REDDIT_POSTS or not TEST_CONFIGS:
                error("Test data is empty or invalid")
                return {"passed": False, "error": "Invalid test data"}
            
            config = get_test_config("staging")
            if not config:
                error("Test configuration is invalid")
                return {"passed": False, "error": "Invalid test configuration"}
            
            success("Test data validation passed")
            return {
                "passed": True,
                "sample_posts_count": sum(len(posts) for posts in SAMPLE_REDDIT_POSTS.values()),
                "test_configs_count": len(TEST_CONFIGS)
            }
            
        except Exception as e:
            error(f"Test data validation failed: {e}")
            return {"passed": False, "error": str(e)}
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate validation summary"""
        passed_checks = sum(1 for result in self.validation_results.values() if result.get("passed", False))
        total_checks = len(self.validation_results)
        
        return {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": total_checks - passed_checks,
            "pass_rate": passed_checks / total_checks if total_checks > 0 else 0,
            "overall_status": self.overall_status,
            "ready_for_testing": self.overall_status and passed_checks >= 4  # Allow some external API failures
        }

def main():
    """Main entry point"""
    print(f"{Colors.BLUE}=== Staging Environment Validation ==={Colors.NC}")
    print()
    
    validator = StagingValidator()
    results = validator.validate_all()
    
    # Display summary
    print()
    print(f"{Colors.BLUE}=== Validation Summary ==={Colors.NC}")
    summary = results["summary"]
    
    if summary["overall_status"]:
        success(f"Validation passed: {summary['passed_checks']}/{summary['total_checks']} checks")
    else:
        error(f"Validation failed: {summary['failed_checks']}/{summary['total_checks']} checks failed")
    
    print(f"Pass rate: {summary['pass_rate']:.1%}")
    print(f"Ready for testing: {'Yes' if summary['ready_for_testing'] else 'No'}")
    
    # Save results
    results_file = "tests/verification/staging_validation.json"
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    info(f"Validation results saved to: {results_file}")
    
    # Recommendations
    print()
    print(f"{Colors.BLUE}=== Recommendations ==={Colors.NC}")
    
    if not summary["ready_for_testing"]:
        print("❌ Environment is not ready for testing. Please address the following:")
        
        for check_name, check_result in results["validation_results"].items():
            if not check_result.get("passed", False):
                print(f"   • Fix {check_name.replace('_', ' ')}")
        
        print()
        print("Next steps:")
        print("1. Update .env.staging with actual API keys")
        print("2. Run './scripts/setup-staging-environment.sh'")
        print("3. Re-run this validation script")
    else:
        print("✅ Environment is ready for testing!")
        print()
        print("Next steps:")
        print("1. Run verification tests:")
        print("   ./scripts/run-verification-tests.sh")
        print("2. Or run specific test suites:")
        print("   ./scripts/run-verification-tests.sh -s smoke")
    
    # Exit with appropriate code
    sys.exit(0 if summary["ready_for_testing"] else 1)

if __name__ == "__main__":
    main()