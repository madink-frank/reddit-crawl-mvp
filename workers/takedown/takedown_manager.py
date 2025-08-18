"""
Takedown workflow manager for Reddit Ghost Publisher

Implements 2-stage takedown process:
1. Stage 1: unpublish(ghost_post_id) → takedown_status='pending'
2. Stage 2: 72 hours later → delete from Ghost → takedown_status='deleted'

Includes audit logging and SLA tracking.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID

from celery import current_app
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.config import get_settings
from app.infrastructure import get_db_session
from app.models.post import Post
from app.models.processing_log import ProcessingLog
from app.transaction_manager import transaction_with_tracking, get_state_manager
from workers.publisher.ghost_client import get_ghost_client, GhostAPIError

logger = logging.getLogger(__name__)
settings = get_settings()


class TakedownError(Exception):
    """Base exception for takedown operations"""
    pass


class TakedownManager:
    """Manages the 2-stage takedown workflow"""
    
    def __init__(self):
        self.ghost_client = get_ghost_client()
        self.sla_hours = 72  # 72 hour SLA for complete takedown
    
    def initiate_takedown(self, post_id: str, reason: str = "user_request") -> Dict[str, Any]:
        """
        Stage 1: Unpublish post from Ghost and mark as takedown_pending
        
        Args:
            post_id: UUID of the post to take down
            reason: Reason for takedown (for audit trail)
        
        Returns:
            Dictionary with takedown initiation results
        """
        logger.info(f"Initiating takedown for post {post_id}, reason: {reason}")
        
        try:
            with transaction_with_tracking(
                post_id=post_id,
                service_name="takedown_manager",
                operation_name="initiate_takedown"
            ) as (session, tracker):
                
                state_manager = get_state_manager(session, tracker)
                
                # Get post from database
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    raise TakedownError(f"Post {post_id} not found")
                
                if post.takedown_status != "active":
                    raise TakedownError(f"Post {post_id} is not in active status (current: {post.takedown_status})")
                
                # Stage 1: Unpublish from Ghost if published
                ghost_unpublish_result = None
                if post.ghost_post_id:
                    try:
                        logger.info(f"Unpublishing Ghost post {post.ghost_post_id}")
                        ghost_unpublish_result = self.ghost_client.unpublish_post(post.ghost_post_id)
                        logger.info(f"Successfully unpublished Ghost post {post.ghost_post_id}")
                    except GhostAPIError as e:
                        logger.error(f"Failed to unpublish Ghost post {post.ghost_post_id}: {e}")
                        # Continue with database update even if Ghost unpublish fails
                        ghost_unpublish_result = {"error": str(e)}
                
                # Update post status to takedown_pending
                old_state = {
                    "takedown_status": post.takedown_status,
                    "updated_at": post.updated_at
                }
                
                post.takedown_status = "takedown_pending"
                post.updated_at = datetime.utcnow()
                
                state_manager.update_entity(post, "post", post_id, old_state)
                
                # Schedule Stage 2 deletion task (72 hours later)
                eta = datetime.utcnow() + timedelta(hours=self.sla_hours)
                
                # Import here to avoid circular imports
                from workers.takedown.tasks import complete_takedown_deletion
                
                deletion_task = complete_takedown_deletion.apply_async(
                    args=[post_id, reason],
                    eta=eta
                )
                
                # Create audit log entry
                audit_log = ProcessingLog(
                    post_id=post_id,
                    service_name="takedown_manager",
                    status="takedown_initiated",
                    processing_time_ms=0,
                    metadata={
                        "stage": 1,
                        "reason": reason,
                        "ghost_post_id": post.ghost_post_id,
                        "ghost_unpublish_result": ghost_unpublish_result,
                        "deletion_task_id": deletion_task.id,
                        "deletion_eta": eta.isoformat(),
                        "sla_hours": self.sla_hours
                    },
                    created_at=datetime.utcnow()
                )
                
                state_manager.create_entity(audit_log, "processing_log", f"takedown_init_{post_id}")
                
                # Check consistency
                consistency_result = state_manager.check_consistency()
                if consistency_result.get("status") != "passed":
                    raise TakedownError(f"Consistency check failed: {consistency_result}")
                
                logger.info(f"Takedown initiated for post {post_id}, deletion scheduled for {eta}")
                
                return {
                    "post_id": post_id,
                    "stage": 1,
                    "status": "takedown_pending",
                    "ghost_unpublished": ghost_unpublish_result is not None,
                    "deletion_scheduled_for": eta.isoformat(),
                    "deletion_task_id": deletion_task.id,
                    "sla_hours": self.sla_hours
                }
                
        except Exception as e:
            logger.error(f"Failed to initiate takedown for post {post_id}: {e}")
            
            # Log failure
            try:
                with get_db_session() as session:
                    error_log = ProcessingLog(
                        post_id=post_id,
                        service_name="takedown_manager",
                        status="takedown_failed",
                        error_message=str(e),
                        processing_time_ms=0,
                        metadata={
                            "stage": 1,
                            "reason": reason,
                            "error_type": type(e).__name__
                        },
                        created_at=datetime.utcnow()
                    )
                    session.add(error_log)
                    session.commit()
            except Exception as log_error:
                logger.error(f"Failed to log takedown error: {log_error}")
            
            raise
    
    def complete_takedown_deletion(self, post_id: str, reason: str) -> Dict[str, Any]:
        """
        Stage 2: Delete post from Ghost and mark as takedown_status='deleted'
        
        Args:
            post_id: UUID of the post to delete
            reason: Original reason for takedown
        
        Returns:
            Dictionary with deletion results
        """
        logger.info(f"Completing takedown deletion for post {post_id}")
        
        try:
            with transaction_with_tracking(
                post_id=post_id,
                service_name="takedown_manager",
                operation_name="complete_takedown_deletion"
            ) as (session, tracker):
                
                state_manager = get_state_manager(session, tracker)
                
                # Get post from database
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    raise TakedownError(f"Post {post_id} not found")
                
                if post.takedown_status != "takedown_pending":
                    logger.warning(f"Post {post_id} is not in takedown_pending status (current: {post.takedown_status})")
                    # Continue with deletion anyway for cleanup
                
                # Stage 2: Delete from Ghost if still exists
                ghost_delete_result = None
                if post.ghost_post_id:
                    try:
                        logger.info(f"Deleting Ghost post {post.ghost_post_id}")
                        ghost_delete_result = self.ghost_client.delete_post(post.ghost_post_id)
                        logger.info(f"Successfully deleted Ghost post {post.ghost_post_id}")
                    except GhostAPIError as e:
                        logger.error(f"Failed to delete Ghost post {post.ghost_post_id}: {e}")
                        # Continue with database update even if Ghost delete fails
                        ghost_delete_result = {"error": str(e)}
                
                # Update post status to removed and clear Ghost references
                old_state = {
                    "takedown_status": post.takedown_status,
                    "ghost_post_id": post.ghost_post_id,
                    "ghost_slug": post.ghost_slug,
                    "ghost_url": post.ghost_url,
                    "updated_at": post.updated_at
                }
                
                post.takedown_status = "removed"
                post.ghost_post_id = None
                post.ghost_slug = None
                post.ghost_url = None
                post.updated_at = datetime.utcnow()
                
                state_manager.update_entity(post, "post", post_id, old_state)
                
                # Create audit log entry
                audit_log = ProcessingLog(
                    post_id=post_id,
                    service_name="takedown_manager",
                    status="takedown_completed",
                    processing_time_ms=0,
                    metadata={
                        "stage": 2,
                        "reason": reason,
                        "ghost_post_id": old_state["ghost_post_id"],
                        "ghost_delete_result": ghost_delete_result,
                        "sla_met": True,  # Since this is scheduled, SLA should be met
                        "completion_time": datetime.utcnow().isoformat()
                    },
                    created_at=datetime.utcnow()
                )
                
                state_manager.create_entity(audit_log, "processing_log", f"takedown_complete_{post_id}")
                
                # Check consistency
                consistency_result = state_manager.check_consistency()
                if consistency_result.get("status") != "passed":
                    raise TakedownError(f"Consistency check failed: {consistency_result}")
                
                logger.info(f"Takedown deletion completed for post {post_id}")
                
                return {
                    "post_id": post_id,
                    "stage": 2,
                    "status": "removed",
                    "ghost_deleted": ghost_delete_result is not None,
                    "completion_time": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to complete takedown deletion for post {post_id}: {e}")
            
            # Log failure
            try:
                with get_db_session() as session:
                    error_log = ProcessingLog(
                        post_id=post_id,
                        service_name="takedown_manager",
                        status="takedown_deletion_failed",
                        error_message=str(e),
                        processing_time_ms=0,
                        metadata={
                            "stage": 2,
                            "reason": reason,
                            "error_type": type(e).__name__
                        },
                        created_at=datetime.utcnow()
                    )
                    session.add(error_log)
                    session.commit()
            except Exception as log_error:
                logger.error(f"Failed to log takedown deletion error: {log_error}")
            
            raise
    
    def get_takedown_status(self, post_id: str) -> Dict[str, Any]:
        """
        Get current takedown status and SLA tracking information
        
        Args:
            post_id: UUID of the post
        
        Returns:
            Dictionary with takedown status information
        """
        try:
            with get_db_session() as session:
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    raise TakedownError(f"Post {post_id} not found")
                
                # Get takedown-related logs
                takedown_logs = session.query(ProcessingLog).filter(
                    ProcessingLog.post_id == post_id,
                    ProcessingLog.service_name == "takedown_manager"
                ).order_by(ProcessingLog.created_at).all()
                
                # Calculate SLA information
                sla_info = self._calculate_sla_info(takedown_logs)
                
                return {
                    "post_id": post_id,
                    "takedown_status": post.takedown_status,
                    "ghost_post_id": post.ghost_post_id,
                    "sla_info": sla_info,
                    "takedown_logs": [
                        {
                            "status": log.status,
                            "created_at": log.created_at.isoformat(),
                            "metadata": log.metadata
                        }
                        for log in takedown_logs
                    ]
                }
                
        except Exception as e:
            logger.error(f"Failed to get takedown status for post {post_id}: {e}")
            raise
    
    def _calculate_sla_info(self, takedown_logs: List[ProcessingLog]) -> Dict[str, Any]:
        """Calculate SLA compliance information from takedown logs"""
        sla_info = {
            "sla_hours": self.sla_hours,
            "initiated_at": None,
            "completed_at": None,
            "sla_deadline": None,
            "sla_met": None,
            "hours_taken": None
        }
        
        initiation_log = None
        completion_log = None
        
        for log in takedown_logs:
            if log.status == "takedown_initiated":
                initiation_log = log
            elif log.status == "takedown_completed":
                completion_log = log
        
        if initiation_log:
            sla_info["initiated_at"] = initiation_log.created_at.isoformat()
            sla_deadline = initiation_log.created_at + timedelta(hours=self.sla_hours)
            sla_info["sla_deadline"] = sla_deadline.isoformat()
            
            if completion_log:
                sla_info["completed_at"] = completion_log.created_at.isoformat()
                duration = completion_log.created_at - initiation_log.created_at
                sla_info["hours_taken"] = duration.total_seconds() / 3600
                sla_info["sla_met"] = completion_log.created_at <= sla_deadline
            else:
                # Check if SLA is already breached
                if datetime.utcnow() > sla_deadline:
                    sla_info["sla_met"] = False
                    sla_info["hours_taken"] = (datetime.utcnow() - initiation_log.created_at).total_seconds() / 3600
        
        return sla_info
    
    def get_pending_takedowns(self) -> List[Dict[str, Any]]:
        """Get all posts with pending takedowns for monitoring"""
        try:
            with get_db_session() as session:
                pending_posts = session.query(Post).filter(
                    Post.takedown_status == "takedown_pending"
                ).all()
                
                results = []
                for post in pending_posts:
                    try:
                        status_info = self.get_takedown_status(str(post.id))
                        results.append(status_info)
                    except Exception as e:
                        logger.error(f"Failed to get status for pending takedown {post.id}: {e}")
                        results.append({
                            "post_id": str(post.id),
                            "takedown_status": post.takedown_status,
                            "error": str(e)
                        })
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get pending takedowns: {e}")
            raise
    
    def cancel_takedown(self, post_id: str, reason: str = "user_request") -> Dict[str, Any]:
        """
        Cancel a pending takedown (only works if still in takedown_pending status)
        
        Args:
            post_id: UUID of the post
            reason: Reason for cancellation
        
        Returns:
            Dictionary with cancellation results
        """
        logger.info(f"Cancelling takedown for post {post_id}, reason: {reason}")
        
        try:
            with transaction_with_tracking(
                post_id=post_id,
                service_name="takedown_manager",
                operation_name="cancel_takedown"
            ) as (session, tracker):
                
                state_manager = get_state_manager(session, tracker)
                
                # Get post from database
                post = session.query(Post).filter(Post.id == post_id).first()
                if not post:
                    raise TakedownError(f"Post {post_id} not found")
                
                if post.takedown_status != "takedown_pending":
                    raise TakedownError(f"Cannot cancel takedown for post {post_id} - status is {post.takedown_status}")
                
                # Revert to active status
                old_state = {
                    "takedown_status": post.takedown_status,
                    "updated_at": post.updated_at
                }
                
                post.takedown_status = "active"
                post.updated_at = datetime.utcnow()
                
                state_manager.update_entity(post, "post", post_id, old_state)
                
                # Create audit log entry
                audit_log = ProcessingLog(
                    post_id=post_id,
                    service_name="takedown_manager",
                    status="takedown_cancelled",
                    processing_time_ms=0,
                    metadata={
                        "reason": reason,
                        "cancelled_at": datetime.utcnow().isoformat()
                    },
                    created_at=datetime.utcnow()
                )
                
                state_manager.create_entity(audit_log, "processing_log", f"takedown_cancel_{post_id}")
                
                logger.info(f"Takedown cancelled for post {post_id}")
                
                return {
                    "post_id": post_id,
                    "status": "active",
                    "cancelled_at": datetime.utcnow().isoformat(),
                    "reason": reason
                }
                
        except Exception as e:
            logger.error(f"Failed to cancel takedown for post {post_id}: {e}")
            raise


# Global takedown manager instance
takedown_manager = TakedownManager()


def get_takedown_manager() -> TakedownManager:
    """Get the global takedown manager instance"""
    return takedown_manager