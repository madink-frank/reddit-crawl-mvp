"""
Takedown request endpoints - MVP version
Handles content takedown requests with 2-stage workflow
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.api.middleware.security_mvp import TakedownRequest


router = APIRouter()


class TakedownResponse(BaseModel):
    """Response model for takedown requests"""
    status: str
    message: str
    reddit_post_id: str
    action_taken: str
    deletion_scheduled: Optional[str] = None
    timestamp: str


def get_database():
    """Get database connection"""
    try:
        from app.infrastructure import get_database
        return get_database()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Database not available"
        )


def get_celery_app():
    """Get Celery app instance"""
    try:
        from app.celery_app import celery_app
        return celery_app
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Task queue not available"
        )


async def unpublish_from_ghost(ghost_post_id: str) -> bool:
    """Unpublish post from Ghost CMS"""
    try:
        # Import Ghost client
        from workers.publisher.ghost_client import GhostClient
        
        settings = get_settings()
        ghost_client = GhostClient(
            api_url=settings.ghost_api_url,
            admin_key=settings.ghost_admin_key
        )
        
        # Unpublish the post
        success = await ghost_client.unpublish_post(ghost_post_id)
        return success
        
    except Exception as e:
        # Log error but don't fail the takedown request
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to unpublish Ghost post {ghost_post_id}: {str(e)}")
        return False


@router.post("/takedown/{reddit_post_id}", response_model=TakedownResponse)
async def handle_takedown_request(
    reddit_post_id: str = Path(..., description="Reddit post ID to take down"),
    request: TakedownRequest = TakedownRequest(reason="Takedown requested")
):
    """
    Handle content takedown request (2-stage process)
    
    Stage 1: Immediately unpublish from Ghost and mark as takedown_pending
    Stage 2: Schedule deletion after 72 hours
    """
    try:
        database = get_database()
        celery_app = get_celery_app()
        
        with database.connect() as conn:
            # Check if post exists
            query = text("""
                SELECT id, ghost_post_id, ghost_slug, takedown_status
                FROM posts 
                WHERE reddit_post_id = :reddit_post_id
            """)
            
            result = conn.execute(query, {"reddit_post_id": reddit_post_id})
            post = result.fetchone()
            
            if not post:
                raise HTTPException(
                    status_code=404,
                    detail=f"Post with reddit_post_id '{reddit_post_id}' not found"
                )
            
            post_id, ghost_post_id, ghost_slug, current_status = post
            
            # Check if already taken down
            if current_status in ["takedown_pending", "removed"]:
                return TakedownResponse(
                    status="already_processed",
                    message=f"Post already in takedown process (status: {current_status})",
                    reddit_post_id=reddit_post_id,
                    action_taken="none",
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Stage 1: Immediate unpublish
            unpublish_success = False
            if ghost_post_id:
                unpublish_success = await unpublish_from_ghost(ghost_post_id)
            
            # Update post status to takedown_pending
            update_query = text("""
                UPDATE posts 
                SET takedown_status = 'takedown_pending',
                    updated_at = NOW()
                WHERE reddit_post_id = :reddit_post_id
            """)
            
            conn.execute(update_query, {"reddit_post_id": reddit_post_id})
            conn.commit()
            
            # Log the takedown request
            log_query = text("""
                INSERT INTO processing_logs (post_id, service_name, status, error_message, created_at)
                VALUES (:post_id, 'takedown', 'success', :message, NOW())
            """)
            
            log_message = f"Takedown requested: {request.reason}"
            if request.contact_email:
                log_message += f" (Contact: {request.contact_email})"
            
            conn.execute(log_query, {
                "post_id": post_id,
                "message": log_message
            })
            conn.commit()
            
            # Stage 2: Schedule deletion after 72 hours
            deletion_time = datetime.utcnow() + timedelta(hours=72)
            
            # Import and schedule deletion task
            from workers.publisher.tasks import schedule_post_deletion
            
            deletion_task = schedule_post_deletion.apply_async(
                args=[reddit_post_id, request.reason],
                eta=deletion_time
            )
            
            action_message = "Post unpublished from Ghost" if unpublish_success else "Post marked for takedown"
            if not ghost_post_id:
                action_message = "Post marked for takedown (not published to Ghost)"
            
            return TakedownResponse(
                status="success",
                message=f"Takedown request processed. {action_message}. Deletion scheduled in 72 hours.",
                reddit_post_id=reddit_post_id,
                action_taken="unpublished" if unpublish_success else "marked_for_takedown",
                deletion_scheduled=deletion_time.isoformat(),
                timestamp=datetime.utcnow().isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process takedown request: {str(e)}"
        )


@router.get("/takedown/{reddit_post_id}/status")
async def get_takedown_status(
    reddit_post_id: str = Path(..., description="Reddit post ID to check")
):
    """
    Get status of a takedown request
    """
    try:
        database = get_database()
        
        with database.connect() as conn:
            # Get post status and takedown logs
            query = text("""
                SELECT 
                    p.takedown_status,
                    p.updated_at,
                    pl.created_at as takedown_requested_at,
                    pl.error_message as takedown_reason
                FROM posts p
                LEFT JOIN processing_logs pl ON p.id = pl.post_id 
                    AND pl.service_name = 'takedown' 
                    AND pl.status = 'success'
                WHERE p.reddit_post_id = :reddit_post_id
                ORDER BY pl.created_at DESC
                LIMIT 1
            """)
            
            result = conn.execute(query, {"reddit_post_id": reddit_post_id})
            row = result.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Post with reddit_post_id '{reddit_post_id}' not found"
                )
            
            status, updated_at, takedown_requested_at, takedown_reason = row
            
            # Calculate deletion ETA if pending
            deletion_eta = None
            if status == "takedown_pending" and takedown_requested_at:
                deletion_eta = (takedown_requested_at + timedelta(hours=72)).isoformat()
            
            return {
                "reddit_post_id": reddit_post_id,
                "status": status,
                "takedown_requested_at": takedown_requested_at.isoformat() if takedown_requested_at else None,
                "takedown_reason": takedown_reason,
                "deletion_scheduled": deletion_eta,
                "last_updated": updated_at.isoformat() if updated_at else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get takedown status: {str(e)}"
        )