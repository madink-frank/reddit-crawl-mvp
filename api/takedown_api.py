"""
API endpoints for takedown workflow management
"""
import logging
from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from workers.takedown import (
    get_takedown_manager,
    trigger_takedown,
    trigger_takedown_cancellation,
    get_task_status
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/takedown", tags=["takedown"])


class TakedownRequest(BaseModel):
    """Request model for takedown initiation"""
    post_id: str
    reason: str = "user_request"


class TakedownCancelRequest(BaseModel):
    """Request model for takedown cancellation"""
    post_id: str
    reason: str = "user_request"


@router.post("/initiate")
async def initiate_takedown_endpoint(request: TakedownRequest) -> Dict[str, Any]:
    """
    Initiate takedown workflow for a post
    
    This will:
    1. Unpublish the post from Ghost CMS
    2. Mark the post as takedown_pending
    3. Schedule deletion for 72 hours later
    """
    try:
        # Validate UUID format
        try:
            UUID(request.post_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid post_id format")
        
        # Trigger takedown task
        task_id = trigger_takedown(request.post_id, request.reason)
        
        logger.info(f"Takedown initiated for post {request.post_id}, task_id: {task_id}")
        
        return {
            "message": "Takedown initiated successfully",
            "post_id": request.post_id,
            "task_id": task_id,
            "reason": request.reason
        }
        
    except Exception as e:
        logger.error(f"Failed to initiate takedown for post {request.post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate takedown: {str(e)}")


@router.post("/cancel")
async def cancel_takedown_endpoint(request: TakedownCancelRequest) -> Dict[str, Any]:
    """
    Cancel a pending takedown
    
    This only works if the post is still in takedown_pending status
    """
    try:
        # Validate UUID format
        try:
            UUID(request.post_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid post_id format")
        
        # Trigger cancellation task
        task_id = trigger_takedown_cancellation(request.post_id, request.reason)
        
        logger.info(f"Takedown cancellation initiated for post {request.post_id}, task_id: {task_id}")
        
        return {
            "message": "Takedown cancellation initiated successfully",
            "post_id": request.post_id,
            "task_id": task_id,
            "reason": request.reason
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel takedown for post {request.post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel takedown: {str(e)}")


@router.get("/status/{post_id}")
async def get_takedown_status_endpoint(post_id: str) -> Dict[str, Any]:
    """
    Get takedown status and SLA information for a post
    """
    try:
        # Validate UUID format
        try:
            UUID(post_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid post_id format")
        
        takedown_manager = get_takedown_manager()
        status_info = takedown_manager.get_takedown_status(post_id)
        
        return status_info
        
    except Exception as e:
        logger.error(f"Failed to get takedown status for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get takedown status: {str(e)}")


@router.get("/pending")
async def get_pending_takedowns_endpoint() -> Dict[str, Any]:
    """
    Get all posts with pending takedowns for monitoring
    """
    try:
        takedown_manager = get_takedown_manager()
        pending_takedowns = takedown_manager.get_pending_takedowns()
        
        return {
            "pending_count": len(pending_takedowns),
            "pending_takedowns": pending_takedowns
        }
        
    except Exception as e:
        logger.error(f"Failed to get pending takedowns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pending takedowns: {str(e)}")


@router.get("/task/{task_id}")
async def get_task_status_endpoint(task_id: str) -> Dict[str, Any]:
    """
    Get status of a takedown task
    """
    try:
        task_status = get_task_status(task_id)
        return task_status
        
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.get("/health")
async def takedown_health_check() -> Dict[str, Any]:
    """
    Health check for takedown service
    """
    try:
        takedown_manager = get_takedown_manager()
        
        # Basic health check - try to get pending takedowns
        pending_takedowns = takedown_manager.get_pending_takedowns()
        
        return {
            "status": "healthy",
            "service": "takedown_manager",
            "pending_takedowns_count": len(pending_takedowns),
            "ghost_client_available": takedown_manager.ghost_client is not None
        }
        
    except Exception as e:
        logger.error(f"Takedown health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "takedown_manager",
            "error": str(e)
        }