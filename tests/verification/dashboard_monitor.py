#!/usr/bin/env python3
"""
Real-time Dashboard Monitor for E2E Pipeline Test
Provides real-time monitoring of pipeline progress for Ghost dashboard integration
"""

import os
import sys
import json
import time
import asyncio
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class PipelineDashboardMonitor:
    """Real-time pipeline monitoring for dashboard integration"""
    
    def __init__(self, api_base_url: str, update_interval: int = 10):
        self.api_base_url = api_base_url.rstrip('/')
        self.update_interval = update_interval
        self.monitoring_active = False
        self.pipeline_status = {
            "overall_status": "idle",
            "current_stage": "none",
            "stages": {
                "collection": {"status": "pending", "progress": 0, "details": {}},
                "processing": {"status": "pending", "progress": 0, "details": {}},
                "publishing": {"status": "pending", "progress": 0, "details": {}},
                "verification": {"status": "pending", "progress": 0, "details": {}}
            },
            "metrics": {
                "posts_collected": 0,
                "posts_processed": 0,
                "posts_published": 0,
                "posts_verified": 0,
                "total_duration": 0,
                "stage_durations": {}
            },
            "published_urls": [],
            "errors": [],
            "last_updated": datetime.now().isoformat()
        }
        
        logger.info(f"Dashboard monitor initialized for API: {api_base_url}")
    
    async def start_monitoring(self, duration_minutes: int = 30) -> Dict[str, Any]:
        """Start real-time monitoring of the pipeline"""
        logger.info(f"Starting pipeline monitoring for {duration_minutes} minutes")
        
        self.monitoring_active = True
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        monitoring_results = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "updates": [],
            "final_status": {}
        }
        
        try:
            while self.monitoring_active and datetime.now() < end_time:
                # Update pipeline status
                await self._update_pipeline_status()
                
                # Record status update
                status_update = {
                    "timestamp": datetime.now().isoformat(),
                    "status": self.pipeline_status.copy()
                }
                monitoring_results["updates"].append(status_update)
                
                # Log current status
                self._log_current_status()
                
                # Check if pipeline is complete
                if self._is_pipeline_complete():
                    logger.info("Pipeline completed, stopping monitoring")
                    break
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
            
            # Final status
            monitoring_results["final_status"] = self.pipeline_status.copy()
            
        except Exception as e:
            logger.error(f"Monitoring failed: {e}")
            monitoring_results["error"] = str(e)
        finally:
            self.monitoring_active = False
        
        return monitoring_results
    
    async def _update_pipeline_status(self) -> None:
        """Update pipeline status from API endpoints"""
        try:
            # Update overall metrics
            await self._update_metrics()
            
            # Update queue status
            await self._update_queue_status()
            
            # Update worker status
            await self._update_worker_status()
            
            # Update stage progress
            await self._update_stage_progress()
            
            # Update published posts
            await self._update_published_posts()
            
            # Determine current stage and overall status
            self._determine_current_stage()
            
            # Update timestamp
            self.pipeline_status["last_updated"] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Failed to update pipeline status: {e}")
            self.pipeline_status["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
    
    async def _update_metrics(self) -> None:
        """Update pipeline metrics"""
        try:
            # Get post statistics
            stats_response = await self._api_request("/api/v1/stats/posts")
            if stats_response:
                self.pipeline_status["metrics"].update({
                    "posts_collected": stats_response.get("total_posts", 0),
                    "posts_processed": stats_response.get("processed_posts", 0),
                    "posts_published": stats_response.get("published_posts", 0)
                })
            
            # Get processing metrics
            metrics_response = await self._api_request("/metrics")
            if metrics_response and isinstance(metrics_response, str):
                # Parse Prometheus metrics
                metrics = self._parse_prometheus_metrics(metrics_response)
                self.pipeline_status["metrics"].update(metrics)
            
        except Exception as e:
            logger.error(f"Failed to update metrics: {e}")
    
    async def _update_queue_status(self) -> None:
        """Update queue status"""
        try:
            queue_response = await self._api_request("/api/v1/status/queues")
            if queue_response:
                # Update stage status based on queue activity
                for queue_name, queue_info in queue_response.items():
                    if queue_name in ["collect", "process", "publish"]:
                        stage_name = self._queue_to_stage_name(queue_name)
                        if stage_name in self.pipeline_status["stages"]:
                            self.pipeline_status["stages"][stage_name]["details"]["queue"] = queue_info
                            
                            # Determine stage status based on queue activity
                            pending = queue_info.get("pending", 0)
                            active = queue_info.get("active", 0)
                            
                            if active > 0:
                                self.pipeline_status["stages"][stage_name]["status"] = "running"
                            elif pending > 0:
                                self.pipeline_status["stages"][stage_name]["status"] = "queued"
                            else:
                                # Check if stage has completed work
                                if self._has_stage_completed_work(stage_name):
                                    self.pipeline_status["stages"][stage_name]["status"] = "completed"
        
        except Exception as e:
            logger.error(f"Failed to update queue status: {e}")
    
    async def _update_worker_status(self) -> None:
        """Update worker status"""
        try:
            worker_response = await self._api_request("/api/v1/status/workers")
            if worker_response:
                # Store worker information
                for stage_name in self.pipeline_status["stages"]:
                    self.pipeline_status["stages"][stage_name]["details"]["workers"] = worker_response
        
        except Exception as e:
            logger.error(f"Failed to update worker status: {e}")
    
    async def _update_stage_progress(self) -> None:
        """Update progress for each stage"""
        try:
            # Collection stage progress
            collection_progress = await self._calculate_collection_progress()
            self.pipeline_status["stages"]["collection"]["progress"] = collection_progress
            
            # Processing stage progress
            processing_progress = await self._calculate_processing_progress()
            self.pipeline_status["stages"]["processing"]["progress"] = processing_progress
            
            # Publishing stage progress
            publishing_progress = await self._calculate_publishing_progress()
            self.pipeline_status["stages"]["publishing"]["progress"] = publishing_progress
            
            # Verification stage progress
            verification_progress = await self._calculate_verification_progress()
            self.pipeline_status["stages"]["verification"]["progress"] = verification_progress
        
        except Exception as e:
            logger.error(f"Failed to update stage progress: {e}")
    
    async def _update_published_posts(self) -> None:
        """Update list of published posts"""
        try:
            # Get recent published posts
            posts_response = await self._api_request("/api/v1/posts/published?limit=20")
            if posts_response and "posts" in posts_response:
                published_urls = []
                verified_count = 0
                
                for post in posts_response["posts"]:
                    ghost_url = post.get("ghost_url")
                    if ghost_url:
                        published_urls.append({
                            "url": ghost_url,
                            "title": post.get("title", "")[:50],
                            "published_at": post.get("updated_at"),
                            "verified": await self._verify_post_accessibility(ghost_url)
                        })
                        
                        if published_urls[-1]["verified"]:
                            verified_count += 1
                
                self.pipeline_status["published_urls"] = published_urls
                self.pipeline_status["metrics"]["posts_verified"] = verified_count
        
        except Exception as e:
            logger.error(f"Failed to update published posts: {e}")
    
    def _determine_current_stage(self) -> None:
        """Determine the current active stage"""
        # Check stages in order
        stage_order = ["collection", "processing", "publishing", "verification"]
        
        current_stage = "none"
        overall_status = "idle"
        
        for stage_name in stage_order:
            stage = self.pipeline_status["stages"][stage_name]
            
            if stage["status"] == "running":
                current_stage = stage_name
                overall_status = "running"
                break
            elif stage["status"] == "queued":
                current_stage = stage_name
                overall_status = "queued"
                break
        
        # Check if all stages are completed
        if all(stage["status"] == "completed" for stage in self.pipeline_status["stages"].values()):
            overall_status = "completed"
            current_stage = "completed"
        
        # Check for errors
        if any(stage["status"] == "error" for stage in self.pipeline_status["stages"].values()):
            overall_status = "error"
        
        self.pipeline_status["current_stage"] = current_stage
        self.pipeline_status["overall_status"] = overall_status
    
    def _is_pipeline_complete(self) -> bool:
        """Check if the pipeline is complete"""
        return (
            self.pipeline_status["overall_status"] in ["completed", "error"] or
            all(stage["status"] in ["completed", "error"] for stage in self.pipeline_status["stages"].values())
        )
    
    def _log_current_status(self) -> None:
        """Log current pipeline status"""
        status = self.pipeline_status
        metrics = status["metrics"]
        
        logger.info(
            f"Pipeline Status: {status['overall_status']} | "
            f"Stage: {status['current_stage']} | "
            f"Collected: {metrics['posts_collected']} | "
            f"Processed: {metrics['posts_processed']} | "
            f"Published: {metrics['posts_published']} | "
            f"Verified: {metrics['posts_verified']}"
        )
    
    # Helper methods
    
    async def _api_request(self, endpoint: str) -> Optional[Any]:
        """Make API request with error handling"""
        try:
            url = f"{self.api_base_url}{endpoint}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                if response.headers.get("content-type", "").startswith("application/json"):
                    return response.json()
                else:
                    return response.text
            else:
                logger.warning(f"API request failed: {endpoint} -> {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"API request error for {endpoint}: {e}")
            return None
    
    def _queue_to_stage_name(self, queue_name: str) -> str:
        """Convert queue name to stage name"""
        mapping = {
            "collect": "collection",
            "process": "processing", 
            "publish": "publishing"
        }
        return mapping.get(queue_name, queue_name)
    
    def _has_stage_completed_work(self, stage_name: str) -> bool:
        """Check if a stage has completed some work"""
        metrics = self.pipeline_status["metrics"]
        
        if stage_name == "collection":
            return metrics["posts_collected"] > 0
        elif stage_name == "processing":
            return metrics["posts_processed"] > 0
        elif stage_name == "publishing":
            return metrics["posts_published"] > 0
        elif stage_name == "verification":
            return metrics["posts_verified"] > 0
        
        return False
    
    async def _calculate_collection_progress(self) -> int:
        """Calculate collection stage progress (0-100)"""
        try:
            # Base progress on posts collected vs expected
            collected = self.pipeline_status["metrics"]["posts_collected"]
            expected = 5  # Expected number of posts from test
            
            if collected >= expected:
                return 100
            else:
                return min(int((collected / expected) * 100), 99)
        
        except Exception:
            return 0
    
    async def _calculate_processing_progress(self) -> int:
        """Calculate processing stage progress (0-100)"""
        try:
            collected = self.pipeline_status["metrics"]["posts_collected"]
            processed = self.pipeline_status["metrics"]["posts_processed"]
            
            if collected == 0:
                return 0
            
            progress = int((processed / collected) * 100)
            return min(progress, 100)
        
        except Exception:
            return 0
    
    async def _calculate_publishing_progress(self) -> int:
        """Calculate publishing stage progress (0-100)"""
        try:
            processed = self.pipeline_status["metrics"]["posts_processed"]
            published = self.pipeline_status["metrics"]["posts_published"]
            
            if processed == 0:
                return 0
            
            progress = int((published / processed) * 100)
            return min(progress, 100)
        
        except Exception:
            return 0
    
    async def _calculate_verification_progress(self) -> int:
        """Calculate verification stage progress (0-100)"""
        try:
            published = self.pipeline_status["metrics"]["posts_published"]
            verified = self.pipeline_status["metrics"]["posts_verified"]
            
            if published == 0:
                return 0
            
            progress = int((verified / published) * 100)
            return min(progress, 100)
        
        except Exception:
            return 0
    
    async def _verify_post_accessibility(self, ghost_url: str) -> bool:
        """Verify that a Ghost post is accessible"""
        try:
            response = requests.get(ghost_url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, Any]:
        """Parse Prometheus metrics text"""
        parsed_metrics = {}
        
        try:
            lines = metrics_text.strip().split('\n')
            
            for line in lines:
                if line.startswith('#') or not line.strip():
                    continue
                
                # Simple parsing for counter metrics
                if ' ' in line:
                    metric_name, value = line.rsplit(' ', 1)
                    try:
                        parsed_metrics[metric_name] = float(value)
                    except ValueError:
                        pass
        
        except Exception as e:
            logger.error(f"Failed to parse Prometheus metrics: {e}")
        
        return parsed_metrics
    
    def get_dashboard_status(self) -> Dict[str, Any]:
        """Get current status formatted for dashboard display"""
        return {
            "status": self.pipeline_status["overall_status"],
            "current_stage": self.pipeline_status["current_stage"],
            "progress": {
                stage_name: {
                    "status": stage_info["status"],
                    "progress": stage_info["progress"]
                }
                for stage_name, stage_info in self.pipeline_status["stages"].items()
            },
            "metrics": self.pipeline_status["metrics"],
            "published_posts": len(self.pipeline_status["published_urls"]),
            "published_urls": [post["url"] for post in self.pipeline_status["published_urls"]],
            "last_updated": self.pipeline_status["last_updated"],
            "errors": len(self.pipeline_status["errors"])
        }
    
    def stop_monitoring(self) -> None:
        """Stop the monitoring process"""
        logger.info("Stopping pipeline monitoring")
        self.monitoring_active = False


async def main():
    """Main entry point for dashboard monitor"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline Dashboard Monitor")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--duration", type=int, default=30, help="Monitoring duration in minutes")
    parser.add_argument("--interval", type=int, default=10, help="Update interval in seconds")
    parser.add_argument("--output", help="Output file for monitoring results")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create monitor
    monitor = PipelineDashboardMonitor(args.api_url, args.interval)
    
    try:
        # Start monitoring
        results = await monitor.start_monitoring(args.duration)
        
        # Save results if output file specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Monitoring results saved to: {args.output}")
        
        # Print final status
        final_status = monitor.get_dashboard_status()
        print("\n" + "="*60)
        print("PIPELINE MONITORING SUMMARY")
        print("="*60)
        print(f"Overall Status: {final_status['status']}")
        print(f"Current Stage: {final_status['current_stage']}")
        print(f"Posts Collected: {final_status['metrics']['posts_collected']}")
        print(f"Posts Processed: {final_status['metrics']['posts_processed']}")
        print(f"Posts Published: {final_status['metrics']['posts_published']}")
        print(f"Posts Verified: {final_status['metrics']['posts_verified']}")
        
        if final_status['published_urls']:
            print(f"\nPublished URLs ({len(final_status['published_urls'])}):")
            for url in final_status['published_urls']:
                print(f"  - {url}")
        
        print("="*60)
        
    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user")
        monitor.stop_monitoring()
    except Exception as e:
        print(f"Monitoring failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))