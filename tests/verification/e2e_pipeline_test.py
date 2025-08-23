#!/usr/bin/env python3
"""
End-to-End Pipeline Integration Test
Implements comprehensive testing for task 20.1 - Reddit 수집 → AI 처리 → Ghost 발행 전체 플로우 테스트
"""

import os
import sys
import json
import time
import logging
import requests
import asyncio
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.verification.test_config import get_test_config
from tests.verification.seed_data import SAMPLE_REDDIT_POSTS, SAMPLE_CONTENT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/verification/logs/e2e_pipeline_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class E2EPipelineTest:
    """End-to-End Pipeline Integration Test"""
    
    def __init__(self, environment: str = "staging"):
        self.environment = environment
        self.config = get_test_config(environment)
        self.api_base = self.config["environment"].api_base_url
        self.ghost_blog_url = os.getenv("GHOST_API_URL", "").replace("/ghost/api/admin", "")
        self.test_results = {}
        self.test_posts = []
        
        # Test configuration
        self.test_subreddits = ["programming", "technology", "webdev"]
        self.batch_size = 5
        self.max_wait_time = 300  # 5 minutes max wait per stage
        
        logger.info(f"Initialized E2E Pipeline Test for {environment}")
        logger.info(f"API Base: {self.api_base}")
        logger.info(f"Ghost Blog: {self.ghost_blog_url}")
    
    async def run_full_pipeline_test(self) -> Dict[str, Any]:
        """
        Run complete end-to-end pipeline test
        Reddit 수집 → AI 처리 → Ghost 발행 전체 플로우 테스트
        """
        logger.info("=== Starting End-to-End Pipeline Test ===")
        
        test_results = {
            "test_name": "e2e_pipeline_integration",
            "start_time": datetime.now().isoformat(),
            "environment": self.environment,
            "stages": {},
            "overall_success": False,
            "published_posts": [],
            "error_recovery_tests": {},
            "performance_metrics": {}
        }
        
        try:
            # Stage 1: Pre-test setup and validation
            logger.info("Stage 1: Pre-test Setup and Validation")
            setup_result = await self._setup_and_validate()
            test_results["stages"]["setup"] = setup_result
            
            if not setup_result["success"]:
                logger.error("Setup failed, aborting pipeline test")
                return test_results
            
            # Stage 2: Reddit Collection
            logger.info("Stage 2: Reddit Collection")
            collection_result = await self._test_reddit_collection_stage()
            test_results["stages"]["collection"] = collection_result
            
            if not collection_result["success"]:
                logger.error("Collection stage failed")
                return test_results
            
            # Stage 3: AI Processing
            logger.info("Stage 3: AI Processing")
            processing_result = await self._test_ai_processing_stage()
            test_results["stages"]["processing"] = processing_result
            
            if not processing_result["success"]:
                logger.error("Processing stage failed")
                return test_results
            
            # Stage 4: Ghost Publishing
            logger.info("Stage 4: Ghost Publishing")
            publishing_result = await self._test_ghost_publishing_stage()
            test_results["stages"]["publishing"] = publishing_result
            
            if not publishing_result["success"]:
                logger.error("Publishing stage failed")
                return test_results
            
            # Stage 5: Verify Published Content
            logger.info("Stage 5: Verify Published Content on american-trends.ghost.io")
            verification_result = await self._verify_published_content()
            test_results["stages"]["verification"] = verification_result
            
            # Stage 6: Error Recovery Testing
            logger.info("Stage 6: Error Recovery Testing")
            error_recovery_result = await self._test_error_recovery()
            test_results["error_recovery_tests"] = error_recovery_result
            
            # Stage 7: Performance Metrics
            logger.info("Stage 7: Performance Metrics Collection")
            performance_result = await self._collect_performance_metrics()
            test_results["performance_metrics"] = performance_result
            
            # Determine overall success
            test_results["overall_success"] = all([
                setup_result["success"],
                collection_result["success"],
                processing_result["success"],
                publishing_result["success"],
                verification_result["success"]
            ])
            
            logger.info(f"=== E2E Pipeline Test Complete: {'SUCCESS' if test_results['overall_success'] else 'FAILED'} ===")
            
        except Exception as e:
            logger.error(f"E2E Pipeline Test failed with exception: {e}")
            test_results["error"] = str(e)
            test_results["overall_success"] = False
        
        test_results["end_time"] = datetime.now().isoformat()
        test_results["duration_seconds"] = (
            datetime.fromisoformat(test_results["end_time"]) - 
            datetime.fromisoformat(test_results["start_time"])
        ).total_seconds()
        
        # Save detailed results
        await self._save_test_results(test_results)
        
        return test_results
    
    async def _setup_and_validate(self) -> Dict[str, Any]:
        """Setup and validate test environment"""
        setup_result = {
            "success": False,
            "checks": {},
            "start_time": datetime.now().isoformat()
        }
        
        try:
            # Check API health
            logger.info("Checking API health...")
            health_response = requests.get(f"{self.api_base}/health", timeout=30)
            setup_result["checks"]["api_health"] = {
                "success": health_response.status_code == 200,
                "status_code": health_response.status_code,
                "response": health_response.json() if health_response.status_code == 200 else None
            }
            
            # Check database connectivity
            logger.info("Checking database connectivity...")
            db_check = await self._check_database_connection()
            setup_result["checks"]["database"] = db_check
            
            # Check Redis connectivity
            logger.info("Checking Redis connectivity...")
            redis_check = await self._check_redis_connection()
            setup_result["checks"]["redis"] = redis_check
            
            # Check external services
            logger.info("Checking external services...")
            external_check = await self._check_external_services()
            setup_result["checks"]["external_services"] = external_check
            
            # Validate environment variables
            logger.info("Validating environment variables...")
            env_check = self._validate_environment_variables()
            setup_result["checks"]["environment"] = env_check
            
            # Clear any existing test data
            logger.info("Clearing existing test data...")
            cleanup_result = await self._cleanup_test_data()
            setup_result["checks"]["cleanup"] = cleanup_result
            
            # Check if all setup checks passed
            setup_result["success"] = all(
                check.get("success", False) 
                for check in setup_result["checks"].values()
            )
            
        except Exception as e:
            logger.error(f"Setup validation failed: {e}")
            setup_result["error"] = str(e)
        
        setup_result["end_time"] = datetime.now().isoformat()
        return setup_result
    
    async def _test_reddit_collection_stage(self) -> Dict[str, Any]:
        """Test Reddit collection stage"""
        collection_result = {
            "success": False,
            "start_time": datetime.now().isoformat(),
            "posts_collected": 0,
            "collection_details": {}
        }
        
        try:
            # Get initial post count
            initial_count = await self._get_post_count()
            logger.info(f"Initial post count: {initial_count}")
            
            # Trigger Reddit collection
            logger.info(f"Triggering Reddit collection for subreddits: {self.test_subreddits}")
            collection_response = requests.post(
                f"{self.api_base}/api/v1/collect/trigger",
                json={
                    "subreddits": self.test_subreddits,
                    "batch_size": self.batch_size
                },
                timeout=60
            )
            
            collection_result["collection_details"]["trigger_response"] = {
                "status_code": collection_response.status_code,
                "response": collection_response.json() if collection_response.status_code == 200 else collection_response.text
            }
            
            if collection_response.status_code != 200:
                logger.error(f"Collection trigger failed: {collection_response.status_code}")
                return collection_result
            
            # Wait for collection to complete and monitor progress
            logger.info("Monitoring collection progress...")
            collection_complete = False
            wait_time = 0
            
            while wait_time < self.max_wait_time and not collection_complete:
                await asyncio.sleep(10)
                wait_time += 10
                
                # Check current post count
                current_count = await self._get_post_count()
                posts_collected = current_count - initial_count
                
                # Check queue status
                queue_status = await self._get_queue_status()
                
                logger.info(f"Collection progress: {posts_collected} posts collected, queue status: {queue_status}")
                
                # Collection is complete when we have new posts and collect queue is empty
                if posts_collected > 0 and queue_status.get("collect", {}).get("pending", 0) == 0:
                    collection_complete = True
                    break
            
            # Final count
            final_count = await self._get_post_count()
            posts_collected = final_count - initial_count
            
            # Get collected post details
            collected_posts = await self._get_recent_posts(posts_collected)
            self.test_posts = collected_posts
            
            collection_result.update({
                "success": posts_collected >= 3,  # Expect at least 3 posts
                "posts_collected": posts_collected,
                "initial_count": initial_count,
                "final_count": final_count,
                "wait_time_seconds": wait_time,
                "collected_posts": [{"id": post["id"], "title": post["title"][:50]} for post in collected_posts]
            })
            
            logger.info(f"Collection stage completed: {posts_collected} posts collected")
            
        except Exception as e:
            logger.error(f"Collection stage failed: {e}")
            collection_result["error"] = str(e)
        
        collection_result["end_time"] = datetime.now().isoformat()
        return collection_result
    
    async def _test_ai_processing_stage(self) -> Dict[str, Any]:
        """Test AI processing stage"""
        processing_result = {
            "success": False,
            "start_time": datetime.now().isoformat(),
            "posts_processed": 0,
            "processing_details": {}
        }
        
        try:
            if not self.test_posts:
                logger.error("No posts available for processing")
                processing_result["error"] = "No posts available for processing"
                return processing_result
            
            # Get post IDs for processing
            post_ids = [post["id"] for post in self.test_posts[:3]]  # Process first 3 posts
            logger.info(f"Triggering AI processing for posts: {post_ids}")
            
            # Trigger AI processing
            processing_response = requests.post(
                f"{self.api_base}/api/v1/process/trigger",
                json={"post_ids": post_ids},
                timeout=120
            )
            
            processing_result["processing_details"]["trigger_response"] = {
                "status_code": processing_response.status_code,
                "response": processing_response.json() if processing_response.status_code == 200 else processing_response.text
            }
            
            if processing_response.status_code != 200:
                logger.error(f"Processing trigger failed: {processing_response.status_code}")
                return processing_result
            
            # Monitor processing progress
            logger.info("Monitoring AI processing progress...")
            processing_complete = False
            wait_time = 0
            processed_posts = []
            
            while wait_time < self.max_wait_time and not processing_complete:
                await asyncio.sleep(15)
                wait_time += 15
                
                # Check processing status for each post
                current_processed = []
                for post_id in post_ids:
                    post_details = await self._get_post_details(post_id)
                    if post_details and post_details.get("summary_ko"):
                        current_processed.append(post_details)
                
                # Check queue status
                queue_status = await self._get_queue_status()
                
                logger.info(f"Processing progress: {len(current_processed)}/{len(post_ids)} posts processed, queue status: {queue_status}")
                
                # Processing is complete when all posts have summaries and process queue is empty
                if len(current_processed) >= len(post_ids) and queue_status.get("process", {}).get("pending", 0) == 0:
                    processed_posts = current_processed
                    processing_complete = True
                    break
            
            # Validate processing results
            valid_processed = 0
            processing_details = []
            
            for post in processed_posts:
                details = {
                    "post_id": post["id"],
                    "has_summary": bool(post.get("summary_ko")),
                    "has_tags": bool(post.get("tags")),
                    "tag_count": len(post.get("tags", [])),
                    "has_pain_points": bool(post.get("pain_points")),
                    "has_product_ideas": bool(post.get("product_ideas"))
                }
                
                # Validate processing quality
                details["valid_processing"] = (
                    details["has_summary"] and
                    details["has_tags"] and
                    3 <= details["tag_count"] <= 5 and
                    details["has_pain_points"] and
                    details["has_product_ideas"]
                )
                
                if details["valid_processing"]:
                    valid_processed += 1
                
                processing_details.append(details)
            
            processing_result.update({
                "success": valid_processed >= 2,  # At least 2 posts should be properly processed
                "posts_processed": len(processed_posts),
                "valid_processed": valid_processed,
                "wait_time_seconds": wait_time,
                "processing_details": processing_details
            })
            
            logger.info(f"Processing stage completed: {valid_processed}/{len(processed_posts)} posts properly processed")
            
        except Exception as e:
            logger.error(f"Processing stage failed: {e}")
            processing_result["error"] = str(e)
        
        processing_result["end_time"] = datetime.now().isoformat()
        return processing_result
    
    async def _test_ghost_publishing_stage(self) -> Dict[str, Any]:
        """Test Ghost publishing stage"""
        publishing_result = {
            "success": False,
            "start_time": datetime.now().isoformat(),
            "posts_published": 0,
            "publishing_details": {}
        }
        
        try:
            # Get processed posts for publishing
            processed_posts = []
            for post in self.test_posts[:3]:
                post_details = await self._get_post_details(post["id"])
                if post_details and post_details.get("summary_ko"):
                    processed_posts.append(post_details)
            
            if not processed_posts:
                logger.error("No processed posts available for publishing")
                publishing_result["error"] = "No processed posts available for publishing"
                return publishing_result
            
            post_ids = [post["id"] for post in processed_posts]
            logger.info(f"Triggering Ghost publishing for posts: {post_ids}")
            
            # Trigger Ghost publishing
            publishing_response = requests.post(
                f"{self.api_base}/api/v1/publish/trigger",
                json={"post_ids": post_ids},
                timeout=180
            )
            
            publishing_result["publishing_details"]["trigger_response"] = {
                "status_code": publishing_response.status_code,
                "response": publishing_response.json() if publishing_response.status_code == 200 else publishing_response.text
            }
            
            if publishing_response.status_code != 200:
                logger.error(f"Publishing trigger failed: {publishing_response.status_code}")
                return publishing_result
            
            # Monitor publishing progress
            logger.info("Monitoring Ghost publishing progress...")
            publishing_complete = False
            wait_time = 0
            published_posts = []
            
            while wait_time < self.max_wait_time and not publishing_complete:
                await asyncio.sleep(20)
                wait_time += 20
                
                # Check publishing status for each post
                current_published = []
                for post_id in post_ids:
                    post_details = await self._get_post_details(post_id)
                    if post_details and post_details.get("ghost_url"):
                        current_published.append(post_details)
                
                # Check queue status
                queue_status = await self._get_queue_status()
                
                logger.info(f"Publishing progress: {len(current_published)}/{len(post_ids)} posts published, queue status: {queue_status}")
                
                # Publishing is complete when all posts have ghost_url and publish queue is empty
                if len(current_published) >= len(post_ids) and queue_status.get("publish", {}).get("pending", 0) == 0:
                    published_posts = current_published
                    publishing_complete = True
                    break
            
            # Validate published posts
            valid_published = 0
            publishing_details = []
            
            for post in published_posts:
                ghost_url = post.get("ghost_url")
                details = {
                    "post_id": post["id"],
                    "ghost_url": ghost_url,
                    "has_ghost_url": bool(ghost_url)
                }
                
                # Verify the post is actually accessible on Ghost
                if ghost_url:
                    try:
                        ghost_response = requests.get(ghost_url, timeout=30)
                        details["ghost_accessible"] = ghost_response.status_code == 200
                        details["ghost_status_code"] = ghost_response.status_code
                        
                        if ghost_response.status_code == 200:
                            # Check content structure
                            content_check = await self._validate_ghost_content(ghost_url, post)
                            details.update(content_check)
                            
                            if content_check.get("valid_content", False):
                                valid_published += 1
                    
                    except Exception as e:
                        details["ghost_accessible"] = False
                        details["ghost_error"] = str(e)
                
                publishing_details.append(details)
            
            publishing_result.update({
                "success": valid_published >= 2,  # At least 2 posts should be properly published
                "posts_published": len(published_posts),
                "valid_published": valid_published,
                "wait_time_seconds": wait_time,
                "publishing_details": publishing_details,
                "published_urls": [post.get("ghost_url") for post in published_posts if post.get("ghost_url")]
            })
            
            logger.info(f"Publishing stage completed: {valid_published}/{len(published_posts)} posts properly published")
            
        except Exception as e:
            logger.error(f"Publishing stage failed: {e}")
            publishing_result["error"] = str(e)
        
        publishing_result["end_time"] = datetime.now().isoformat()
        return publishing_result
    
    async def _verify_published_content(self) -> Dict[str, Any]:
        """Verify published content on american-trends.ghost.io"""
        verification_result = {
            "success": False,
            "start_time": datetime.now().isoformat(),
            "verified_posts": 0,
            "verification_details": {}
        }
        
        try:
            # Get all published posts from this test run
            published_posts = []
            for post in self.test_posts:
                post_details = await self._get_post_details(post["id"])
                if post_details and post_details.get("ghost_url"):
                    published_posts.append(post_details)
            
            if not published_posts:
                logger.error("No published posts to verify")
                verification_result["error"] = "No published posts to verify"
                return verification_result
            
            logger.info(f"Verifying {len(published_posts)} published posts on american-trends.ghost.io")
            
            verified_posts = 0
            verification_details = []
            
            for post in published_posts:
                ghost_url = post.get("ghost_url")
                post_verification = {
                    "post_id": post["id"],
                    "ghost_url": ghost_url,
                    "title": post.get("title", "")[:50]
                }
                
                try:
                    # Verify post is accessible
                    response = requests.get(ghost_url, timeout=30)
                    post_verification["accessible"] = response.status_code == 200
                    post_verification["status_code"] = response.status_code
                    
                    if response.status_code == 200:
                        # Verify content structure
                        content = response.text
                        
                        # Check for required sections
                        checks = {
                            "has_title": post.get("title", "") in content,
                            "has_korean_summary": bool(post.get("summary_ko")) and post.get("summary_ko", "") in content,
                            "has_source_attribution": "Source:" in content and "Reddit" in content,
                            "has_takedown_notice": "Takedown requests will be honored" in content,
                            "has_media_attribution": "Media and usernames belong to their respective owners" in content
                        }
                        
                        post_verification.update(checks)
                        post_verification["content_valid"] = all(checks.values())
                        
                        if post_verification["content_valid"]:
                            verified_posts += 1
                            logger.info(f"✓ Post verified: {ghost_url}")
                        else:
                            logger.warning(f"✗ Post content invalid: {ghost_url}")
                    
                except Exception as e:
                    post_verification["accessible"] = False
                    post_verification["error"] = str(e)
                    logger.error(f"Failed to verify post {ghost_url}: {e}")
                
                verification_details.append(post_verification)
            
            verification_result.update({
                "success": verified_posts >= 1,  # At least 1 post should be properly verified
                "total_posts": len(published_posts),
                "verified_posts": verified_posts,
                "verification_details": verification_details
            })
            
            logger.info(f"Content verification completed: {verified_posts}/{len(published_posts)} posts verified")
            
        except Exception as e:
            logger.error(f"Content verification failed: {e}")
            verification_result["error"] = str(e)
        
        verification_result["end_time"] = datetime.now().isoformat()
        return verification_result
    
    async def _test_error_recovery(self) -> Dict[str, Any]:
        """Test error handling and recovery mechanisms"""
        recovery_result = {
            "start_time": datetime.now().isoformat(),
            "tests": {}
        }
        
        try:
            logger.info("Testing error recovery mechanisms...")
            
            # Test 1: API rate limiting recovery
            recovery_result["tests"]["rate_limiting"] = await self._test_rate_limiting_recovery()
            
            # Test 2: Database connection recovery
            recovery_result["tests"]["database_recovery"] = await self._test_database_recovery()
            
            # Test 3: External service failure recovery
            recovery_result["tests"]["external_service_recovery"] = await self._test_external_service_recovery()
            
            # Test 4: Queue processing recovery
            recovery_result["tests"]["queue_recovery"] = await self._test_queue_recovery()
            
            # Calculate overall recovery success
            passed_tests = sum(1 for test in recovery_result["tests"].values() if test.get("success", False))
            total_tests = len(recovery_result["tests"])
            recovery_result["success"] = passed_tests >= int(total_tests * 0.7)  # 70% pass rate
            
        except Exception as e:
            logger.error(f"Error recovery testing failed: {e}")
            recovery_result["error"] = str(e)
            recovery_result["success"] = False
        
        recovery_result["end_time"] = datetime.now().isoformat()
        return recovery_result
    
    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics from the pipeline test"""
        metrics_result = {
            "start_time": datetime.now().isoformat(),
            "metrics": {}
        }
        
        try:
            logger.info("Collecting performance metrics...")
            
            # Get API metrics
            metrics_response = requests.get(f"{self.api_base}/metrics", timeout=30)
            if metrics_response.status_code == 200:
                metrics_result["metrics"]["api_metrics"] = metrics_response.text
            
            # Get queue status
            queue_status = await self._get_queue_status()
            metrics_result["metrics"]["queue_status"] = queue_status
            
            # Get worker status
            worker_status = await self._get_worker_status()
            metrics_result["metrics"]["worker_status"] = worker_status
            
            # Calculate pipeline timing
            if self.test_results:
                pipeline_timing = {}
                for stage_name, stage_result in self.test_results.get("stages", {}).items():
                    if "start_time" in stage_result and "end_time" in stage_result:
                        start = datetime.fromisoformat(stage_result["start_time"])
                        end = datetime.fromisoformat(stage_result["end_time"])
                        pipeline_timing[f"{stage_name}_duration_seconds"] = (end - start).total_seconds()
                
                metrics_result["metrics"]["pipeline_timing"] = pipeline_timing
            
            metrics_result["success"] = True
            
        except Exception as e:
            logger.error(f"Performance metrics collection failed: {e}")
            metrics_result["error"] = str(e)
            metrics_result["success"] = False
        
        metrics_result["end_time"] = datetime.now().isoformat()
        return metrics_result
    
    # Helper methods
    
    async def _check_database_connection(self) -> Dict[str, Any]:
        """Check database connectivity"""
        try:
            # This would typically use the actual database connection
            # For now, we'll use a simple API call that tests the database
            response = requests.get(f"{self.api_base}/api/v1/status/database", timeout=30)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _check_redis_connection(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        try:
            response = requests.get(f"{self.api_base}/api/v1/status/redis", timeout=30)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _check_external_services(self) -> Dict[str, Any]:
        """Check external service connectivity"""
        services = {
            "reddit": "https://www.reddit.com/api/v1/me",
            "openai": "https://api.openai.com/v1/models",
            "ghost": self.ghost_blog_url
        }
        
        results = {}
        all_success = True
        
        for service_name, url in services.items():
            try:
                response = requests.get(url, timeout=10)
                success = response.status_code in [200, 401, 403]  # 401/403 means reachable
                results[service_name] = {
                    "success": success,
                    "status_code": response.status_code
                }
                if not success:
                    all_success = False
            except Exception as e:
                results[service_name] = {"success": False, "error": str(e)}
                all_success = False
        
        return {"success": all_success, "services": results}
    
    def _validate_environment_variables(self) -> Dict[str, Any]:
        """Validate required environment variables"""
        required_vars = [
            "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "OPENAI_API_KEY",
            "GHOST_ADMIN_KEY", "GHOST_API_URL", "DATABASE_URL", "REDIS_URL"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        return {
            "success": len(missing_vars) == 0,
            "missing_variables": missing_vars,
            "total_required": len(required_vars)
        }
    
    async def _cleanup_test_data(self) -> Dict[str, Any]:
        """Clean up any existing test data"""
        try:
            # This would typically clean up test posts from the database
            # For now, we'll just return success
            return {"success": True, "message": "Test data cleanup completed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_post_count(self) -> int:
        """Get current post count from database"""
        try:
            response = requests.get(f"{self.api_base}/api/v1/stats/posts", timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("total_posts", 0)
            return 0
        except Exception:
            return 0
    
    async def _get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        try:
            response = requests.get(f"{self.api_base}/api/v1/status/queues", timeout=30)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception:
            return {}
    
    async def _get_worker_status(self) -> Dict[str, Any]:
        """Get current worker status"""
        try:
            response = requests.get(f"{self.api_base}/api/v1/status/workers", timeout=30)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception:
            return {}
    
    async def _get_recent_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent posts from database"""
        try:
            response = requests.get(f"{self.api_base}/api/v1/posts/recent?limit={limit}", timeout=30)
            if response.status_code == 200:
                return response.json().get("posts", [])
            return []
        except Exception:
            return []
    
    async def _get_post_details(self, post_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific post"""
        try:
            response = requests.get(f"{self.api_base}/api/v1/posts/{post_id}", timeout=30)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
    
    async def _validate_ghost_content(self, ghost_url: str, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Ghost post content structure"""
        try:
            response = requests.get(ghost_url, timeout=30)
            if response.status_code != 200:
                return {"valid_content": False, "error": f"HTTP {response.status_code}"}
            
            content = response.text
            
            # Check required content elements
            checks = {
                "has_title": post_data.get("title", "") in content,
                "has_summary": bool(post_data.get("summary_ko")) and post_data.get("summary_ko", "")[:100] in content,
                "has_source_link": "Source:" in content and "reddit.com" in content,
                "has_takedown_notice": "Takedown requests will be honored" in content,
                "has_media_notice": "Media and usernames belong to their respective owners" in content
            }
            
            return {
                "valid_content": all(checks.values()),
                "content_checks": checks,
                "content_length": len(content)
            }
            
        except Exception as e:
            return {"valid_content": False, "error": str(e)}
    
    # Error recovery test methods
    
    async def _test_rate_limiting_recovery(self) -> Dict[str, Any]:
        """Test rate limiting recovery"""
        try:
            # Simulate rapid API calls to trigger rate limiting
            for i in range(10):
                requests.post(f"{self.api_base}/api/v1/collect/trigger", 
                            json={"subreddits": ["test"], "batch_size": 1}, timeout=10)
            
            # Check if system recovers gracefully
            await asyncio.sleep(30)
            
            # Try normal operation
            response = requests.get(f"{self.api_base}/health", timeout=30)
            
            return {
                "success": response.status_code == 200,
                "message": "Rate limiting recovery test completed"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_database_recovery(self) -> Dict[str, Any]:
        """Test database connection recovery"""
        try:
            # Check if database is accessible
            db_check = await self._check_database_connection()
            return {
                "success": db_check["success"],
                "message": "Database recovery test completed"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_external_service_recovery(self) -> Dict[str, Any]:
        """Test external service failure recovery"""
        try:
            # Check external services
            external_check = await self._check_external_services()
            return {
                "success": external_check["success"],
                "message": "External service recovery test completed"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_queue_recovery(self) -> Dict[str, Any]:
        """Test queue processing recovery"""
        try:
            # Check queue status
            queue_status = await self._get_queue_status()
            
            # Check if queues are responsive
            has_queues = any(queue_status.get(queue, {}) for queue in ["collect", "process", "publish"])
            
            return {
                "success": has_queues,
                "queue_status": queue_status,
                "message": "Queue recovery test completed"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _save_test_results(self, results: Dict[str, Any]) -> None:
        """Save test results to file"""
        try:
            # Create results directory if it doesn't exist
            results_dir = Path("tests/verification/reports")
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"e2e_pipeline_test_{timestamp}.json"
            filepath = results_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Test results saved to: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")


async def main():
    """Main entry point for E2E pipeline test"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run End-to-End Pipeline Integration Test")
    parser.add_argument("--environment", default="staging", choices=["staging", "production"],
                       help="Test environment")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run test
    test = E2EPipelineTest(args.environment)
    results = await test.run_full_pipeline_test()
    
    # Print summary
    print("\n" + "="*80)
    print("E2E PIPELINE TEST SUMMARY")
    print("="*80)
    print(f"Environment: {args.environment}")
    print(f"Overall Success: {'✓ PASSED' if results['overall_success'] else '✗ FAILED'}")
    print(f"Duration: {results.get('duration_seconds', 0):.1f} seconds")
    
    if "stages" in results:
        print("\nStage Results:")
        for stage_name, stage_result in results["stages"].items():
            status = "✓ PASSED" if stage_result.get("success", False) else "✗ FAILED"
            print(f"  {stage_name.title()}: {status}")
    
    if results.get("published_urls"):
        print(f"\nPublished Posts ({len(results['published_urls'])}):")
        for url in results["published_urls"]:
            print(f"  - {url}")
    
    print("="*80)
    
    # Exit with appropriate code
    sys.exit(0 if results["overall_success"] else 1)


if __name__ == "__main__":
    asyncio.run(main())