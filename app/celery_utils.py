"""
Celery utilities and monitoring functions
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from celery import current_app
from celery.result import AsyncResult
from celery.exceptions import WorkerLostError, Retry

from app.celery_app import celery_app
from app.redis_client import redis_client

logger = logging.getLogger(__name__)


class CeleryMonitor:
    """Celery monitoring and management utilities"""
    
    @staticmethod
    async def get_queue_stats() -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        try:
            stats = {}
            
            # Get active tasks
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            reserved_tasks = inspect.reserved()
            scheduled_tasks = inspect.scheduled()
            
            # Count tasks by queue
            queue_counts = {
                "collect": {"active": 0, "reserved": 0, "scheduled": 0},
                "process": {"active": 0, "reserved": 0, "scheduled": 0}, 
                "publish": {"active": 0, "reserved": 0, "scheduled": 0}
            }
            
            # Count active tasks
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        queue_name = task.get("delivery_info", {}).get("routing_key", "").split(".")[0]
                        if queue_name in queue_counts:
                            queue_counts[queue_name]["active"] += 1
            
            # Count reserved tasks
            if reserved_tasks:
                for worker, tasks in reserved_tasks.items():
                    for task in tasks:
                        queue_name = task.get("delivery_info", {}).get("routing_key", "").split(".")[0]
                        if queue_name in queue_counts:
                            queue_counts[queue_name]["reserved"] += 1
            
            # Count scheduled tasks
            if scheduled_tasks:
                for worker, tasks in scheduled_tasks.items():
                    for task in tasks:
                        queue_name = task.get("delivery_info", {}).get("routing_key", "").split(".")[0]
                        if queue_name in queue_counts:
                            queue_counts[queue_name]["scheduled"] += 1
            
            # Get Redis queue lengths
            redis_stats = await redis_client.get_queue_stats()
            
            # Combine stats
            for queue_name in queue_counts:
                queue_counts[queue_name].update({
                    "pending": redis_stats.get(f"{queue_name}_pending", 0),
                    "failed": redis_stats.get(f"{queue_name}_failed", 0)
                })
            
            stats["queues"] = queue_counts
            stats["total_active"] = sum(q["active"] for q in queue_counts.values())
            stats["total_pending"] = sum(q["pending"] for q in queue_counts.values())
            stats["total_failed"] = sum(q["failed"] for q in queue_counts.values())
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def get_worker_stats() -> Dict[str, Any]:
        """Get worker statistics"""
        try:
            inspect = celery_app.control.inspect()
            
            # Get worker info
            stats_info = inspect.stats()
            active_queues = inspect.active_queues()
            registered_tasks = inspect.registered()
            
            workers = {}
            
            if stats_info:
                for worker_name, worker_stats in stats_info.items():
                    workers[worker_name] = {
                        "status": "online",
                        "processed_tasks": worker_stats.get("total", {}),
                        "load": worker_stats.get("rusage", {}),
                        "queues": active_queues.get(worker_name, []) if active_queues else [],
                        "registered_tasks": len(registered_tasks.get(worker_name, [])) if registered_tasks else 0
                    }
            
            return {
                "workers": workers,
                "total_workers": len(workers),
                "online_workers": len([w for w in workers.values() if w["status"] == "online"])
            }
            
        except Exception as e:
            logger.error(f"Failed to get worker stats: {e}")
            return {"error": str(e)}
    
    @staticmethod
    async def get_task_history(
        limit: int = 100,
        task_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent task execution history"""
        try:
            # This would typically come from a task result backend
            # For now, return a placeholder structure
            history = []
            
            # In a real implementation, you'd query the result backend
            # or maintain a separate task history log
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get task history: {e}")
            return []
    
    @staticmethod
    def revoke_task(task_id: str, terminate: bool = False) -> bool:
        """Revoke a running task"""
        try:
            celery_app.control.revoke(task_id, terminate=terminate)
            logger.info(f"Task {task_id} revoked (terminate={terminate})")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke task {task_id}: {e}")
            return False
    
    @staticmethod
    def purge_queue(queue_name: str) -> int:
        """Purge all tasks from a queue"""
        try:
            result = celery_app.control.purge()
            logger.info(f"Queue {queue_name} purged")
            return result
        except Exception as e:
            logger.error(f"Failed to purge queue {queue_name}: {e}")
            return 0


class TaskRetryHandler:
    """Handle task retry logic with exponential backoff"""
    
    @staticmethod
    def calculate_retry_delay(retry_count: int, base_delay: int = 60) -> int:
        """Calculate exponential backoff delay"""
        return min(base_delay * (2 ** retry_count), 3600)  # Max 1 hour
    
    @staticmethod
    async def log_task_failure(
        task_id: str,
        task_name: str,
        error: Exception,
        retry_count: int
    ) -> None:
        """Log task failure details"""
        try:
            failure_data = {
                "task_id": task_id,
                "task_name": task_name,
                "error": str(error),
                "error_type": type(error).__name__,
                "retry_count": retry_count,
                "timestamp": datetime.utcnow().isoformat(),
                "max_retries_reached": retry_count >= 3
            }
            
            # Store in Redis for monitoring
            await redis_client.lpush(
                f"task_failures:{datetime.utcnow().strftime('%Y-%m-%d')}", 
                failure_data
            )
            
            # Set expiration for daily failure logs
            await redis_client.expire(
                f"task_failures:{datetime.utcnow().strftime('%Y-%m-%d')}", 
                86400 * 7  # Keep for 7 days
            )
            
            logger.error(
                f"Task failure logged: {task_name} ({task_id}) - "
                f"{error} (retry {retry_count}/3)"
            )
            
        except Exception as e:
            logger.error(f"Failed to log task failure: {e}")
    
    @staticmethod
    def should_retry(
        error: Exception, 
        retry_count: int, 
        max_retries: int = 3
    ) -> bool:
        """Determine if task should be retried based on error type"""
        
        # Don't retry certain error types
        non_retryable_errors = (
            ValueError,  # Bad input data
            TypeError,   # Programming errors
            KeyError,    # Missing required data
        )
        
        if isinstance(error, non_retryable_errors):
            return False
        
        # Don't retry if max retries reached
        if retry_count >= max_retries:
            return False
        
        return True


class TaskMetrics:
    """Collect and store task execution metrics"""
    
    @staticmethod
    async def record_task_start(task_id: str, task_name: str) -> None:
        """Record task start time"""
        try:
            start_data = {
                "task_id": task_id,
                "task_name": task_name,
                "start_time": datetime.utcnow().isoformat(),
                "status": "started"
            }
            
            await redis_client.hset(f"task_metrics:{task_id}", start_data)
            await redis_client.expire(f"task_metrics:{task_id}", 3600)  # 1 hour
            
        except Exception as e:
            logger.error(f"Failed to record task start: {e}")
    
    @staticmethod
    async def record_task_completion(
        task_id: str, 
        success: bool, 
        execution_time: float,
        error: Optional[str] = None
    ) -> None:
        """Record task completion metrics"""
        try:
            completion_data = {
                "end_time": datetime.utcnow().isoformat(),
                "success": success,
                "execution_time_seconds": execution_time,
                "status": "completed" if success else "failed"
            }
            
            if error:
                completion_data["error"] = error
            
            await redis_client.hset(f"task_metrics:{task_id}", completion_data)
            
            # Update daily metrics
            date_key = datetime.utcnow().strftime('%Y-%m-%d')
            daily_metrics_key = f"daily_metrics:{date_key}"
            
            # Get current task name from stored metrics
            task_data = await redis_client.hgetall(f"task_metrics:{task_id}")
            task_name = task_data.get("task_name", "unknown")
            
            # Increment counters
            if success:
                await redis_client.hincrby(daily_metrics_key, f"{task_name}_success", 1)
            else:
                await redis_client.hincrby(daily_metrics_key, f"{task_name}_failed", 1)
            
            # Update execution time stats
            await redis_client.hincrbyfloat(
                daily_metrics_key, 
                f"{task_name}_total_time", 
                execution_time
            )
            
            # Set expiration for daily metrics
            await redis_client.expire(daily_metrics_key, 86400 * 30)  # Keep for 30 days
            
        except Exception as e:
            logger.error(f"Failed to record task completion: {e}")
    
    @staticmethod
    async def get_daily_metrics(date: Optional[str] = None) -> Dict[str, Any]:
        """Get daily task execution metrics"""
        try:
            if not date:
                date = datetime.utcnow().strftime('%Y-%m-%d')
            
            daily_metrics_key = f"daily_metrics:{date}"
            metrics = await redis_client.hgetall(daily_metrics_key)
            
            # Parse metrics into structured format
            parsed_metrics = {}
            for key, value in metrics.items():
                if "_success" in key:
                    task_name = key.replace("_success", "")
                    if task_name not in parsed_metrics:
                        parsed_metrics[task_name] = {}
                    parsed_metrics[task_name]["success_count"] = int(value)
                elif "_failed" in key:
                    task_name = key.replace("_failed", "")
                    if task_name not in parsed_metrics:
                        parsed_metrics[task_name] = {}
                    parsed_metrics[task_name]["failed_count"] = int(value)
                elif "_total_time" in key:
                    task_name = key.replace("_total_time", "")
                    if task_name not in parsed_metrics:
                        parsed_metrics[task_name] = {}
                    parsed_metrics[task_name]["total_execution_time"] = float(value)
            
            # Calculate derived metrics
            for task_name, task_metrics in parsed_metrics.items():
                success = task_metrics.get("success_count", 0)
                failed = task_metrics.get("failed_count", 0)
                total_time = task_metrics.get("total_execution_time", 0.0)
                
                task_metrics["total_count"] = success + failed
                task_metrics["success_rate"] = (success / (success + failed)) if (success + failed) > 0 else 0
                task_metrics["average_execution_time"] = (total_time / success) if success > 0 else 0
            
            return {
                "date": date,
                "tasks": parsed_metrics
            }
            
        except Exception as e:
            logger.error(f"Failed to get daily metrics: {e}")
            return {"error": str(e)}


# Utility functions for task management
async def trigger_task(
    task_name: str, 
    args: List[Any] = None, 
    kwargs: Dict[str, Any] = None,
    queue: str = "collect",
    priority: int = 5
) -> str:
    """Trigger a Celery task and return task ID"""
    try:
        task = celery_app.send_task(
            task_name,
            args=args or [],
            kwargs=kwargs or {},
            queue=queue,
            priority=priority
        )
        
        logger.info(f"Task {task_name} triggered with ID: {task.id}")
        return task.id
        
    except Exception as e:
        logger.error(f"Failed to trigger task {task_name}: {e}")
        raise


def get_task_result(task_id: str) -> Dict[str, Any]:
    """Get task result by ID"""
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
            "date_done": result.date_done.isoformat() if result.date_done else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get task result for {task_id}: {e}")
        return {"error": str(e)}


# Health check for Celery
def celery_health_check() -> Dict[str, Any]:
    """Check Celery health status"""
    try:
        # Check if workers are responding
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            return {
                "status": "unhealthy",
                "error": "No workers responding",
                "workers": 0
            }
        
        # Check worker health
        healthy_workers = 0
        total_workers = len(stats)
        
        for worker_name, worker_stats in stats.items():
            if worker_stats.get("total"):
                healthy_workers += 1
        
        status = "healthy" if healthy_workers == total_workers else "degraded"
        
        return {
            "status": status,
            "total_workers": total_workers,
            "healthy_workers": healthy_workers,
            "workers": list(stats.keys())
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "workers": 0
        }