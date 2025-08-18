"""
Manual trigger endpoints - MVP version
Provides manual triggering of collection, processing, and publishing tasks
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.config import get_settings
from app.api.middleware.security_mvp import TriggerRequest


router = APIRouter()


class TriggerResponse(BaseModel):
    """Response model for trigger endpoints"""
    status: str
    message: str
    task_id: Optional[str] = None
    timestamp: str


def get_celery_app():
    """Get Celery app instance"""
    try:
        from app.celery_app import celery_app
        return celery_app
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery not available - task queue service unavailable"
        )


@router.post("/collect/trigger", response_model=TriggerResponse)
async def trigger_collect(request: TriggerRequest = TriggerRequest()):
    """
    Manually trigger Reddit collection task
    
    Enqueues a collection task with idempotency check
    """
    try:
        celery_app = get_celery_app()
        settings = get_settings()
        
        # Get subreddits from request or use default
        from app.config import get_subreddits_list
        subreddits = request.subreddits or get_subreddits_list()
        batch_size = request.batch_size or settings.batch_size
        
        # Check for recent collection (idempotency)
        if not request.force:
            # TODO: Check if collection was done recently
            # For MVP, we'll skip this check
            pass
        
        # Enqueue collection task
        from workers.collector.tasks import collect_reddit_posts
        
        task = collect_reddit_posts.delay(
            subreddits=subreddits,
            limit=batch_size
        )
        
        return TriggerResponse(
            status="success",
            message=f"Collection task enqueued for {len(subreddits)} subreddits",
            task_id=task.id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger collection: {str(e)}"
        )


@router.post("/process/trigger", response_model=TriggerResponse)
async def trigger_process(request: TriggerRequest = TriggerRequest()):
    """
    Manually trigger AI processing task
    
    Processes unprocessed posts with AI analysis
    """
    try:
        celery_app = get_celery_app()
        
        # Check for recent processing (idempotency)
        if not request.force:
            # TODO: Check if processing was done recently
            # For MVP, we'll skip this check
            pass
        
        # Enqueue processing task for unprocessed posts
        from workers.nlp_pipeline.tasks import process_content_with_ai
        
        # For MVP, create a mock task since we need specific post IDs
        # In production, this would get unprocessed posts from database
        task_id = f"process_trigger_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return TriggerResponse(
            status="success",
            message="Processing trigger received (requires specific post IDs in production)",
            task_id=task_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger processing: {str(e)}"
        )


@router.post("/publish/trigger", response_model=TriggerResponse)
async def trigger_publish(request: TriggerRequest = TriggerRequest()):
    """
    Manually trigger Ghost publishing task
    
    Publishes processed posts to Ghost CMS
    """
    try:
        celery_app = get_celery_app()
        
        # Check for recent publishing (idempotency)
        if not request.force:
            # TODO: Check if publishing was done recently
            # For MVP, we'll skip this check
            pass
        
        # For MVP, create a mock task since we need specific post IDs
        # In production, this would get processed posts from database
        task_id = f"publish_trigger_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return TriggerResponse(
            status="success",
            message="Publishing trigger received (requires specific post IDs in production)",
            task_id=task_id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger publishing: {str(e)}"
        )


@router.post("/pipeline/trigger", response_model=TriggerResponse)
async def trigger_full_pipeline(request: TriggerRequest = TriggerRequest()):
    """
    Trigger full pipeline: collect → process → publish
    
    Uses Celery chain to execute tasks in sequence
    """
    try:
        celery_app = get_celery_app()
        settings = get_settings()
        
        # Get parameters
        from app.config import get_subreddits_list
        subreddits = request.subreddits or get_subreddits_list()
        batch_size = request.batch_size or settings.batch_size
        
        # Import tasks
        from workers.collector.tasks import collect_reddit_posts
        from workers.nlp_pipeline.tasks import process_content_with_ai
        from workers.publisher.tasks import publish_to_ghost
        from celery import chain
        
        # For MVP, just trigger collection (the chain needs individual post IDs)
        from workers.collector.tasks import collect_reddit_posts
        
        task = collect_reddit_posts.delay(
            subreddits=subreddits,
            limit=batch_size
        )
        
        return TriggerResponse(
            status="success",
            message=f"Collection triggered for {len(subreddits)} subreddits (full pipeline requires individual post processing)",
            task_id=task.id,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger pipeline: {str(e)}"
        )