#!/usr/bin/env python3
"""
Integrated E2E Pipeline Test with Dashboard Monitoring
Runs the complete E2E pipeline test while providing real-time dashboard monitoring
"""

import os
import sys
import json
import time
import asyncio
import logging
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.verification.e2e_pipeline_test import E2EPipelineTest
from tests.verification.dashboard_monitor import PipelineDashboardMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/verification/logs/e2e_with_dashboard.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class IntegratedE2ETestRunner:
    """Integrated E2E test runner with dashboard monitoring"""
    
    def __init__(self, environment: str = "staging", api_base_url: str = "http://localhost:8000"):
        self.environment = environment
        self.api_base_url = api_base_url
        self.test_results = {}
        self.monitoring_results = {}
        
        # Initialize components
        self.e2e_test = E2EPipelineTest(environment)
        self.dashboard_monitor = PipelineDashboardMonitor(api_base_url)
        
        logger.info(f"Initialized integrated E2E test runner for {environment}")
    
    async def run_integrated_test(self) -> Dict[str, Any]:
        """
        Run integrated E2E pipeline test with dashboard monitoring
        """
        logger.info("=== Starting Integrated E2E Pipeline Test with Dashboard Monitoring ===")
        
        integrated_results = {
            "test_name": "integrated_e2e_with_dashboard",
            "start_time": datetime.now().isoformat(),
            "environment": self.environment,
            "api_base_url": self.api_base_url,
            "e2e_test_results": {},
            "monitoring_results": {},
            "dashboard_url": f"{self.api_base_url}/dashboard/pipeline-monitor",
            "overall_success": False,
            "integration_metrics": {}
        }
        
        try:
            # Step 1: Pre-test validation
            logger.info("Step 1: Pre-test Environment Validation")
            validation_result = await self._validate_test_environment()
            integrated_results["environment_validation"] = validation_result
            
            if not validation_result["success"]:
                logger.error("Environment validation failed")
                return integrated_results
            
            # Step 2: Start dashboard monitoring
            logger.info("Step 2: Starting Dashboard Monitoring")
            monitoring_task = asyncio.create_task(
                self.dashboard_monitor.start_monitoring(duration_minutes=45)
            )
            
            # Give monitoring a moment to initialize
            await asyncio.sleep(5)
            
            # Step 3: Run E2E pipeline test
            logger.info("Step 3: Running E2E Pipeline Test")
            e2e_task = asyncio.create_task(
                self.e2e_test.run_full_pipeline_test()
            )
            
            # Step 4: Monitor both tasks
            logger.info("Step 4: Monitoring Test Progress")
            progress_task = asyncio.create_task(
                self._monitor_test_progress()
            )
            
            # Wait for E2E test to complete
            logger.info("Waiting for E2E pipeline test to complete...")
            e2e_results = await e2e_task
            integrated_results["e2e_test_results"] = e2e_results
            
            # Stop monitoring after E2E test completes
            logger.info("E2E test completed, stopping monitoring...")
            self.dashboard_monitor.stop_monitoring()
            
            # Wait a bit more for monitoring to finish
            await asyncio.sleep(10)
            
            # Get monitoring results
            try:
                monitoring_results = await asyncio.wait_for(monitoring_task, timeout=30)
                integrated_results["monitoring_results"] = monitoring_results
            except asyncio.TimeoutError:
                logger.warning("Monitoring task timed out")
                integrated_results["monitoring_results"] = {"error": "Monitoring timed out"}
            
            # Stop progress monitoring
            progress_task.cancel()
            
            # Step 5: Analyze integration results
            logger.info("Step 5: Analyzing Integration Results")
            integration_analysis = await self._analyze_integration_results(
                e2e_results, integrated_results.get("monitoring_results", {})
            )
            integrated_results["integration_metrics"] = integration_analysis
            
            # Determine overall success
            integrated_results["overall_success"] = (
                e2e_results.get("overall_success", False) and
                validation_result["success"] and
                integration_analysis.get("dashboard_integration_success", False)
            )
            
            logger.info(f"=== Integrated E2E Test Complete: {'SUCCESS' if integrated_results['overall_success'] else 'FAILED'} ===")
            
        except Exception as e:
            logger.error(f"Integrated E2E test failed with exception: {e}")
            integrated_results["error"] = str(e)
            integrated_results["overall_success"] = False
        
        integrated_results["end_time"] = datetime.now().isoformat()
        integrated_results["duration_seconds"] = (
            datetime.fromisoformat(integrated_results["end_time"]) - 
            datetime.fromisoformat(integrated_results["start_time"])
        ).total_seconds()
        
        # Save comprehensive results
        await self._save_integrated_results(integrated_results)
        
        return integrated_results
    
    async def _validate_test_environment(self) -> Dict[str, Any]:
        """Validate test environment before starting"""
        validation_result = {
            "success": False,
            "checks": {},
            "start_time": datetime.now().isoformat()
        }
        
        try:
            # Check API availability
            logger.info("Checking API availability...")
            import requests
            
            try:
                response = requests.get(f"{self.api_base_url}/health", timeout=30)
                validation_result["checks"]["api_health"] = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            except Exception as e:
                validation_result["checks"]["api_health"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Check dashboard endpoint
            logger.info("Checking dashboard endpoint...")
            try:
                response = requests.get(f"{self.api_base_url}/dashboard/pipeline-monitor", timeout=30)
                validation_result["checks"]["dashboard_endpoint"] = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code
                }
            except Exception as e:
                validation_result["checks"]["dashboard_endpoint"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Check pipeline monitoring API
            logger.info("Checking pipeline monitoring API...")
            try:
                response = requests.get(f"{self.api_base_url}/dashboard/api/pipeline/status", timeout=30)
                validation_result["checks"]["monitoring_api"] = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code
                }
            except Exception as e:
                validation_result["checks"]["monitoring_api"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Check environment variables
            logger.info("Checking environment variables...")
            required_vars = [
                "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "OPENAI_API_KEY",
                "GHOST_ADMIN_KEY", "GHOST_API_URL", "DATABASE_URL", "REDIS_URL"
            ]
            
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            validation_result["checks"]["environment_variables"] = {
                "success": len(missing_vars) == 0,
                "missing_variables": missing_vars,
                "total_required": len(required_vars)
            }
            
            # Check Docker services (if applicable)
            logger.info("Checking Docker services...")
            try:
                result = subprocess.run(
                    ["docker-compose", "ps", "--services", "--filter", "status=running"],
                    capture_output=True, text=True, timeout=30
                )
                
                running_services = result.stdout.strip().split('\n') if result.stdout.strip() else []
                validation_result["checks"]["docker_services"] = {
                    "success": len(running_services) >= 3,  # Expect at least 3 services
                    "running_services": running_services,
                    "service_count": len(running_services)
                }
            except Exception as e:
                validation_result["checks"]["docker_services"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Overall validation success
            validation_result["success"] = all(
                check.get("success", False) 
                for check in validation_result["checks"].values()
            )
            
        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            validation_result["error"] = str(e)
        
        validation_result["end_time"] = datetime.now().isoformat()
        return validation_result
    
    async def _monitor_test_progress(self) -> None:
        """Monitor and log test progress"""
        try:
            while True:
                # Get current dashboard status
                dashboard_status = self.dashboard_monitor.get_dashboard_status()
                
                # Log progress
                logger.info(
                    f"Test Progress - Status: {dashboard_status['status']} | "
                    f"Stage: {dashboard_status['current_stage']} | "
                    f"Collected: {dashboard_status['metrics']['posts_collected']} | "
                    f"Processed: {dashboard_status['metrics']['posts_processed']} | "
                    f"Published: {dashboard_status['metrics']['posts_published']} | "
                    f"Verified: {dashboard_status['metrics']['posts_verified']}"
                )
                
                # Check if test is complete
                if dashboard_status['status'] in ['completed', 'error']:
                    logger.info("Test appears to be complete based on dashboard status")
                    break
                
                await asyncio.sleep(30)  # Log progress every 30 seconds
                
        except asyncio.CancelledError:
            logger.info("Progress monitoring cancelled")
        except Exception as e:
            logger.error(f"Progress monitoring failed: {e}")
    
    async def _analyze_integration_results(self, e2e_results: Dict[str, Any], monitoring_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze integration between E2E test and dashboard monitoring"""
        analysis = {
            "dashboard_integration_success": False,
            "monitoring_coverage": 0.0,
            "real_time_accuracy": 0.0,
            "performance_metrics": {},
            "issues_found": []
        }
        
        try:
            # Check if dashboard monitoring was active during test
            if monitoring_results and "updates" in monitoring_results:
                updates = monitoring_results["updates"]
                
                if len(updates) > 0:
                    analysis["monitoring_coverage"] = 100.0
                    
                    # Analyze real-time accuracy
                    # Compare E2E results with monitoring data
                    final_monitoring_status = monitoring_results.get("final_status", {})
                    e2e_metrics = e2e_results.get("stages", {})
                    
                    accuracy_checks = []
                    
                    # Check collection accuracy
                    if "collection" in e2e_metrics and e2e_metrics["collection"].get("success"):
                        collected_posts = e2e_metrics["collection"].get("posts_collected", 0)
                        monitored_collected = final_monitoring_status.get("metrics", {}).get("posts_collected", 0)
                        
                        if collected_posts > 0:
                            accuracy = min(monitored_collected / collected_posts, 1.0)
                            accuracy_checks.append(accuracy)
                    
                    # Check publishing accuracy
                    if "publishing" in e2e_metrics and e2e_metrics["publishing"].get("success"):
                        published_posts = e2e_metrics["publishing"].get("posts_published", 0)
                        monitored_published = final_monitoring_status.get("metrics", {}).get("posts_published", 0)
                        
                        if published_posts > 0:
                            accuracy = min(monitored_published / published_posts, 1.0)
                            accuracy_checks.append(accuracy)
                    
                    # Calculate overall accuracy
                    if accuracy_checks:
                        analysis["real_time_accuracy"] = sum(accuracy_checks) / len(accuracy_checks) * 100
                    
                    # Performance metrics
                    analysis["performance_metrics"] = {
                        "total_monitoring_updates": len(updates),
                        "monitoring_duration_seconds": (
                            datetime.fromisoformat(monitoring_results["end_time"]) -
                            datetime.fromisoformat(monitoring_results["start_time"])
                        ).total_seconds() if "end_time" in monitoring_results else 0,
                        "average_update_interval": len(updates) / max(1, analysis["performance_metrics"].get("monitoring_duration_seconds", 1) / 60)
                    }
                    
                    # Dashboard integration success criteria
                    analysis["dashboard_integration_success"] = (
                        analysis["monitoring_coverage"] >= 90.0 and
                        analysis["real_time_accuracy"] >= 70.0 and
                        len(updates) >= 5  # At least 5 monitoring updates
                    )
                
                else:
                    analysis["issues_found"].append("No monitoring updates recorded")
            
            else:
                analysis["issues_found"].append("No monitoring results available")
            
            # Check for published posts accessibility
            if e2e_results.get("stages", {}).get("verification", {}).get("verified_posts", 0) > 0:
                analysis["ghost_integration_success"] = True
            else:
                analysis["issues_found"].append("No posts verified on american-trends.ghost.io")
            
        except Exception as e:
            logger.error(f"Integration analysis failed: {e}")
            analysis["issues_found"].append(f"Analysis error: {str(e)}")
        
        return analysis
    
    async def _save_integrated_results(self, results: Dict[str, Any]) -> None:
        """Save integrated test results"""
        try:
            # Create results directory
            results_dir = Path("tests/verification/reports")
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Save comprehensive results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"integrated_e2e_test_{timestamp}.json"
            filepath = results_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Integrated test results saved to: {filepath}")
            
            # Also save a summary report
            summary_filename = f"integrated_e2e_summary_{timestamp}.json"
            summary_filepath = results_dir / summary_filename
            
            summary = {
                "test_name": results["test_name"],
                "start_time": results["start_time"],
                "end_time": results["end_time"],
                "duration_seconds": results["duration_seconds"],
                "environment": results["environment"],
                "overall_success": results["overall_success"],
                "dashboard_url": results["dashboard_url"],
                "e2e_success": results["e2e_test_results"].get("overall_success", False),
                "monitoring_success": results["integration_metrics"].get("dashboard_integration_success", False),
                "posts_published": results["e2e_test_results"].get("stages", {}).get("publishing", {}).get("posts_published", 0),
                "posts_verified": results["e2e_test_results"].get("stages", {}).get("verification", {}).get("verified_posts", 0),
                "published_urls": results["e2e_test_results"].get("stages", {}).get("publishing", {}).get("published_urls", []),
                "issues_found": results["integration_metrics"].get("issues_found", [])
            }
            
            with open(summary_filepath, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            logger.info(f"Test summary saved to: {summary_filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save integrated results: {e}")


async def main():
    """Main entry point for integrated E2E test"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Integrated E2E Pipeline Test with Dashboard Monitoring")
    parser.add_argument("--environment", default="staging", choices=["staging", "production"],
                       help="Test environment")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run integrated test
    runner = IntegratedE2ETestRunner(args.environment, args.api_url)
    results = await runner.run_integrated_test()
    
    # Print comprehensive summary
    print("\n" + "="*100)
    print("INTEGRATED E2E PIPELINE TEST WITH DASHBOARD MONITORING - SUMMARY")
    print("="*100)
    print(f"Environment: {args.environment}")
    print(f"API URL: {args.api_url}")
    print(f"Dashboard URL: {results.get('dashboard_url', 'N/A')}")
    print(f"Overall Success: {'✓ PASSED' if results['overall_success'] else '✗ FAILED'}")
    print(f"Duration: {results.get('duration_seconds', 0):.1f} seconds")
    
    # E2E Test Results
    e2e_results = results.get("e2e_test_results", {})
    print(f"\nE2E Pipeline Test: {'✓ PASSED' if e2e_results.get('overall_success', False) else '✗ FAILED'}")
    
    if "stages" in e2e_results:
        print("\nPipeline Stages:")
        for stage_name, stage_result in e2e_results["stages"].items():
            status = "✓ PASSED" if stage_result.get("success", False) else "✗ FAILED"
            print(f"  {stage_name.title()}: {status}")
    
    # Dashboard Integration Results
    integration_metrics = results.get("integration_metrics", {})
    print(f"\nDashboard Integration: {'✓ PASSED' if integration_metrics.get('dashboard_integration_success', False) else '✗ FAILED'}")
    print(f"Monitoring Coverage: {integration_metrics.get('monitoring_coverage', 0):.1f}%")
    print(f"Real-time Accuracy: {integration_metrics.get('real_time_accuracy', 0):.1f}%")
    
    # Published Posts
    published_urls = e2e_results.get("stages", {}).get("publishing", {}).get("published_urls", [])
    if published_urls:
        print(f"\nPublished Posts ({len(published_urls)}):")
        for url in published_urls:
            print(f"  - {url}")
    
    # Issues Found
    issues = integration_metrics.get("issues_found", [])
    if issues:
        print(f"\nIssues Found ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
    
    print("="*100)
    print(f"Dashboard URL for real-time monitoring: {results.get('dashboard_url', 'N/A')}")
    print("="*100)
    
    # Exit with appropriate code
    sys.exit(0 if results["overall_success"] else 1)


if __name__ == "__main__":
    asyncio.run(main())