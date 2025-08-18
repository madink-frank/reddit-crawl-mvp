"""
Celery tasks for takedown workflow management
"""
import logging
from datetime import datetime
from typing import Dict, Any

from celery import current_task
from celery.exceptions import Retry

from app.celery_app import celery_app
from app.config import get_settings
from workers.takedown.takedown_manager import get_takedown_manager, TakedownError

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    bind=True,
    name="workers.takedown.tasks.initiate_takedown",
    max_retries=3,
    default_retry_delay=60  # 1 minute retry delay
)
def initiate_takedown(self, post_id: str, reason: str = "user_request") -> Dict[str, Any]:
    """
    Celery task to initiate takedown workflow (Stage 1)
    
    Args:
        post_id: UUID of the post to take down
        reason: Reason for takedown
    
    Returns:
        Dictionary with takedown initiation results
    """
    task_id = self.request.id
    logger.info(f"Starting takedown initiation task {task_id} for post {post_id}")
    
    try:
        takedown_manager = get_takedown_manager()
        result = takedown_manager.initiate_takedown(post_id, reason)
        
        logger.info(f"Takedown initiation completed for post {post_id}: {result}")
        return result
        
    except TakedownError as e:
        logger.error(f"Takedown error for post {post_id}: {e}")
        # Don't retry takedown errors (business logic errors)
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error in takedown initiation for post {post_id}: {e}")
        
        # Retry on unexpected errors
        if self.request.retries < self.max_retries:
            backoff_time = 60 * (2 ** self.request.retries)  # 1m, 2m, 4m
            logger.info(f"Retrying takedown initiation for post {post_id} in {backoff_time}s")
            raise self.retry(countdown=backoff_time, exc=e)
        
        raise


@celery_app.task(
    bind=True,
    name="workers.takedown.tasks.complete_takedown_deletion",
    max_retries=5,  # More retries for deletion as it's critical
    default_retry_delay=300  # 5 minute retry delay
)
def complete_takedown_deletion(self, post_id: str, reason: str) -> Dict[str, Any]:
    """
    Celery task to complete takedown deletion (Stage 2)
    Scheduled to run 72 hours after initiation
    
    Args:
        post_id: UUID of the post to delete
        reason: Original reason for takedown
    
    Returns:
        Dictionary with deletion results
    """
    task_id = self.request.id
    logger.info(f"Starting takedown deletion task {task_id} for post {post_id}")
    
    try:
        takedown_manager = get_takedown_manager()
        result = takedown_manager.complete_takedown_deletion(post_id, reason)
        
        logger.info(f"Takedown deletion completed for post {post_id}: {result}")
        return result
        
    except TakedownError as e:
        logger.error(f"Takedown deletion error for post {post_id}: {e}")
        
        # Retry takedown errors for deletion (might be temporary Ghost API issues)
        if self.request.retries < self.max_retries:
            backoff_time = 300 * (2 ** self.request.retries)  # 5m, 10m, 20m, 40m, 80m
            logger.info(f"Retrying takedown deletion for post {post_id} in {backoff_time}s")
            raise self.retry(countdown=backoff_time, exc=e)
        
        # If all retries exhausted, log critical error but don't fail completely
        logger.critical(f"Failed to complete takedown deletion for post {post_id} after {self.max_retries} retries: {e}")
        
        # Return partial success to indicate the attempt was made
        return {
            "post_id": post_id,
            "stage": 2,
            "status": "deletion_failed",
            "error": str(e),
            "retries_exhausted": True,
            "requires_manual_intervention": True
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in takedown deletion for post {post_id}: {e}")
        
        # Retry on unexpected errors
        if self.request.retries < self.max_retries:
            backoff_time = 300 * (2 ** self.request.retries)
            logger.info(f"Retrying takedown deletion for post {post_id} in {backoff_time}s")
            raise self.retry(countdown=backoff_time, exc=e)
        
        # Critical error - requires manual intervention
        logger.critical(f"Failed to complete takedown deletion for post {post_id} after {self.max_retries} retries: {e}")
        
        return {
            "post_id": post_id,
            "stage": 2,
            "status": "deletion_failed",
            "error": str(e),
            "retries_exhausted": True,
            "requires_manual_intervention": True
        }


@celery_app.task(
    bind=True,
    name="workers.takedown.tasks.cancel_takedown",
    max_retries=3,
    default_retry_delay=30
)
def cancel_takedown(self, post_id: str, reason: str = "user_request") -> Dict[str, Any]:
    """
    Celery task to cancel a pending takedown
    
    Args:
        post_id: UUID of the post
        reason: Reason for cancellation
    
    Returns:
        Dictionary with cancellation results
    """
    task_id = self.request.id
    logger.info(f"Starting takedown cancellation task {task_id} for post {post_id}")
    
    try:
        takedown_manager = get_takedown_manager()
        result = takedown_manager.cancel_takedown(post_id, reason)
        
        logger.info(f"Takedown cancellation completed for post {post_id}: {result}")
        return result
        
    except TakedownError as e:
        logger.error(f"Takedown cancellation error for post {post_id}: {e}")
        # Don't retry business logic errors
        raise
        
    except Exception as e:
        logger.error(f"Unexpected error in takedown cancellation for post {post_id}: {e}")
        
        # Retry on unexpected errors
        if self.request.retries < self.max_retries:
            backoff_time = 30 * (2 ** self.request.retries)  # 30s, 1m, 2m
            logger.info(f"Retrying takedown cancellation for post {post_id} in {backoff_time}s")
            raise self.retry(countdown=backoff_time, exc=e)
        
        raise


@celery_app.task(
    name="workers.takedown.tasks.get_takedown_status"
)
def get_takedown_status(post_id: str) -> Dict[str, Any]:
    """
    Get takedown status for a post
    
    Args:
        post_id: UUID of the post
    
    Returns:
        Dictionary with takedown status information
    """
    try:
        takedown_manager = get_takedown_manager()
        return takedown_manager.get_takedown_status(post_id)
        
    except Exception as e:
        logger.error(f"Failed to get takedown status for post {post_id}: {e}")
        return {
            "post_id": post_id,
            "error": str(e),
            "status": "error"
        }


@celery_app.task(
    name="workers.takedown.tasks.get_pending_takedowns"
)
def get_pending_takedowns() -> Dict[str, Any]:
    """
    Get all posts with pending takedowns for monitoring
    
    Returns:
        Dictionary with pending takedowns information
    """
    try:
        takedown_manager = get_takedown_manager()
        pending_takedowns = takedown_manager.get_pending_takedowns()
        
        return {
            "pending_count": len(pending_takedowns),
            "pending_takedowns": pending_takedowns,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get pending takedowns: {e}")
        return {
            "error": str(e),
            "status": "error",
            "retrieved_at": datetime.utcnow().isoformat()
        }


@celery_app.task(
    name="workers.takedown.tasks.monitor_sla_compliance",
    bind=True
)
def monitor_sla_compliance(self) -> Dict[str, Any]:
    """
    Monitor SLA compliance for takedown requests
    This task should be run periodically (e.g., every hour)
    
    Returns:
        Dictionary with SLA compliance monitoring results
    """
    task_id = self.request.id
    logger.info(f"Starting SLA compliance monitoring task {task_id}")
    
    try:
        takedown_manager = get_takedown_manager()
        pending_takedowns = takedown_manager.get_pending_takedowns()
        
        sla_violations = []
        sla_warnings = []  # Within 6 hours of deadline
        
        for takedown in pending_takedowns:
            sla_info = takedown.get("sla_info", {})
            
            if sla_info.get("sla_met") is False:
                sla_violations.append({
                    "post_id": takedown["post_id"],
                    "hours_overdue": sla_info.get("hours_taken", 0) - sla_info.get("sla_hours", 72),
                    "initiated_at": sla_info.get("initiated_at"),
                    "sla_deadline": sla_info.get("sla_deadline")
                })
            elif sla_info.get("sla_deadline"):
                # Check if within 6 hours of deadline
                from datetime import datetime
                deadline = datetime.fromisoformat(sla_info["sla_deadline"].replace('Z', '+00:00'))
                hours_until_deadline = (deadline - datetime.utcnow()).total_seconds() / 3600
                
                if 0 < hours_until_deadline <= 6:
                    sla_warnings.append({
                        "post_id": takedown["post_id"],
                        "hours_until_deadline": hours_until_deadline,
                        "initiated_at": sla_info.get("initiated_at"),
                        "sla_deadline": sla_info.get("sla_deadline")
                    })
        
        # Send alerts if there are violations or warnings
        if sla_violations:
            logger.critical(f"SLA violations detected: {len(sla_violations)} takedowns overdue")
            # Here you could send Slack/email alerts
        
        if sla_warnings:
            logger.warning(f"SLA warnings: {len(sla_warnings)} takedowns approaching deadline")
        
        result = {
            "monitoring_completed_at": datetime.utcnow().isoformat(),
            "total_pending": len(pending_takedowns),
            "sla_violations": sla_violations,
            "sla_warnings": sla_warnings,
            "violations_count": len(sla_violations),
            "warnings_count": len(sla_warnings)
        }
        
        logger.info(f"SLA compliance monitoring completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to monitor SLA compliance: {e}")
        return {
            "error": str(e),
            "status": "error",
            "monitoring_completed_at": datetime.utcnow().isoformat()
        }


# Utility functions for manual task triggering
def trigger_takedown(post_id: str, reason: str = "user_request") -> str:
    """Trigger takedown initiation for a specific post"""
    task = initiate_takedown.delay(post_id, reason)
    return task.id


def trigger_takedown_cancellation(post_id: str, reason: str = "user_request") -> str:
    """Trigger takedown cancellation for a specific post"""
    task = cancel_takedown.delay(post_id, reason)
    return task.id


def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a takedown task"""
    try:
        result = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "unknown",
            "error": str(e)
        }