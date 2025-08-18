"""
Manual trigger endpoints
Trigger collection, processing, and publishing tasks manually
"""
import time
from typing import Dict, Any, Optional, List

import structlog
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status
from pydantic import BaseModel, Field

from app.api.middleware.auth import get_current_user, get_admin_user
from app.config import get_settings


logger = structlog.get_logger(__name__)

router = APIRouter()


class TriggerRequest(BaseModel):
    """Base trigger request model"""
    priority: int = Field(default=5, ge=1, le=10, description="Task priority (1-10)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CollectTriggerRequest(TriggerRequest):
    """Collection trigger request"""
    subreddits: List[str] = Field(default=["python", "programming"], description="Subreddits to collect from")
    sort_type: str = Field(default="hot", pattern="^(hot|new|rising|top)$", description="Sort type")
    limit: int = Field(default=25, ge=1, le=100, description="Number of posts to collect")


class ProcessTriggerRequest(TriggerRequest):
    """Processing trigger request"""
    post_ids: Optional[List[str]] = Field(default=None, description="Specific post IDs to process")
    batch_size: int = Field(default=10, ge=1, le=50, description="Batch size for processing")


class PublishTriggerRequest(TriggerRequest):
    """Publishing trigger request"""
    post_ids: Optional[List[str]] = Field(default=None, description="Specific post IDs to publish")
    template_type: str = Field(default="article", pattern="^(article|list|qa)$", description="Template type")


class TriggerResponse(BaseModel):
    """Trigger response model"""
    task_id: str
    status: str
    message: str
    timestamp: float
    estimated_completion: Optional[float] = None


async def queue_celery_task(task_name: str, args: list = None, kwargs: dict = None, priority: int = 5) -> str:
    """Queue a Celery task and return task ID"""
    try:
        # Import Celery app
        from app.celery_app import celery_app
        
        # Queue the task
        result = celery_app.send_task(
            task_name,
            args=args or [],
            kwargs=kwargs or {},
            priority=priority
        )
        
        logger.info(
            "Task queued successfully",
            task_name=task_name,
            task_id=result.id,
            priority=priority
        )
        
        return result.id
        
    except Exception as e:
        logger.error(
            "Failed to queue task",
            task_name=task_name,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue task: {str(e)}"
        )


@router.post("/collect/trigger", response_model=TriggerResponse)
async def trigger_collection(
    request: CollectTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger Reddit content collection
    
    Requires: operator or admin role
    """
    # Check permissions
    user_role = current_user.get("role", "viewer")
    if user_role not in ["operator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin role required"
        )
    
    try:
        # Queue collection task
        task_id = await queue_celery_task(
            "collect_reddit_posts",
            kwargs={
                "subreddits": request.subreddits,
                "sort_type": request.sort_type,
                "limit": request.limit,
                "metadata": request.metadata
            },
            priority=request.priority
        )
        
        logger.info(
            "Collection triggered",
            task_id=task_id,
            subreddits=request.subreddits,
            sort_type=request.sort_type,
            limit=request.limit,
            user_id=current_user["sub"]
        )
        
        return TriggerResponse(
            task_id=task_id,
            status="queued",
            message=f"Collection task queued for {len(request.subreddits)} subreddits",
            timestamp=time.time(),
            estimated_completion=time.time() + 300  # 5 minutes estimate
        )
        
    except Exception as e:
        logger.error(
            "Collection trigger failed",
            error=str(e),
            user_id=current_user["sub"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger collection: {str(e)}"
        )


@router.post("/process/trigger", response_model=TriggerResponse)
async def trigger_processing(
    request: ProcessTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger AI content processing
    
    Requires: operator or admin role
    """
    # Check permissions
    user_role = current_user.get("role", "viewer")
    if user_role not in ["operator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin role required"
        )
    
    try:
        # Queue processing task
        task_id = await queue_celery_task(
            "process_content_with_ai",
            kwargs={
                "post_ids": request.post_ids,
                "batch_size": request.batch_size,
                "metadata": request.metadata
            },
            priority=request.priority
        )
        
        logger.info(
            "Processing triggered",
            task_id=task_id,
            post_ids_count=len(request.post_ids) if request.post_ids else "all",
            batch_size=request.batch_size,
            user_id=current_user["sub"]
        )
        
        return TriggerResponse(
            task_id=task_id,
            status="queued",
            message=f"Processing task queued with batch size {request.batch_size}",
            timestamp=time.time(),
            estimated_completion=time.time() + 600  # 10 minutes estimate
        )
        
    except Exception as e:
        logger.error(
            "Processing trigger failed",
            error=str(e),
            user_id=current_user["sub"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger processing: {str(e)}"
        )


@router.post("/publish/trigger", response_model=TriggerResponse)
async def trigger_publishing(
    request: PublishTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger Ghost CMS publishing
    
    Requires: operator or admin role
    """
    # Check permissions
    user_role = current_user.get("role", "viewer")
    if user_role not in ["operator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin role required"
        )
    
    try:
        # Queue publishing task
        task_id = await queue_celery_task(
            "publish_to_ghost",
            kwargs={
                "post_ids": request.post_ids,
                "template_type": request.template_type,
                "metadata": request.metadata
            },
            priority=request.priority
        )
        
        logger.info(
            "Publishing triggered",
            task_id=task_id,
            post_ids_count=len(request.post_ids) if request.post_ids else "all",
            template_type=request.template_type,
            user_id=current_user["sub"]
        )
        
        return TriggerResponse(
            task_id=task_id,
            status="queued",
            message=f"Publishing task queued with {request.template_type} template",
            timestamp=time.time(),
            estimated_completion=time.time() + 180  # 3 minutes estimate
        )
        
    except Exception as e:
        logger.error(
            "Publishing trigger failed",
            error=str(e),
            user_id=current_user["sub"]
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger publishing: {str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get status of a triggered task
    """
    try:
        from app.celery_app import celery_app
        
        # Get task result
        result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": result.status,
            "timestamp": time.time()
        }
        
        if result.ready():
            if result.successful():
                response["result"] = result.result
                response["message"] = "Task completed successfully"
            else:
                response["error"] = str(result.result)
                response["message"] = "Task failed"
        else:
            response["message"] = "Task is still running"
            
            # Add progress info if available
            if hasattr(result, 'info') and result.info:
                response["progress"] = result.info
        
        return response
        
    except Exception as e:
        logger.error(
            "Failed to get task status",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: dict = Depends(get_admin_user)
):
    """
    Cancel a running task
    
    Requires: admin role
    """
    try:
        from app.celery_app import celery_app
        
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        
        logger.info(
            "Task cancelled",
            task_id=task_id,
            user_id=current_user["sub"]
        )
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "Task cancelled successfully",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(
            "Failed to cancel task",
            task_id=task_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )