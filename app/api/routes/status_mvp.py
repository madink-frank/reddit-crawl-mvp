"""
Status monitoring endpoints - MVP version
Provides queue and worker status monitoring
"""
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.api.middleware.security_mvp import QueueStatusResponse, WorkerStatusResponse


router = APIRouter()


class QueueStatus(BaseModel):
    """Queue status model"""
    queue_name: str
    active: int
    pending: int
    scheduled: int
    reserved: int


class WorkerStatus(BaseModel):
    """Worker status model"""
    worker_name: str
    status: str
    active_tasks: int
    processed_tasks: int
    last_heartbeat: str
    queues: List[str]


class SystemStatus(BaseModel):
    """Overall system status model"""
    status: str
    timestamp: str
    queues: Dict[str, QueueStatus]
    workers: Dict[str, WorkerStatus]
    total_active_tasks: int
    total_pending_tasks: int


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


async def get_redis_queue_length(queue_name: str) -> int:
    """Get queue length from Redis"""
    try:
        from app.infrastructure import get_redis_client
        
        redis_client = get_redis_client()
        # Celery uses different key format: celery (default) or custom queue name
        queue_key = f"celery" if queue_name == "celery" else queue_name
        length = await redis_client.llen(queue_key)
        return length
    except Exception:
        return 0


@router.get("/status/queues")
async def get_queue_status():
    """
    Get status of all task queues
    
    Returns active, reserved, scheduled, and queued task counts
    Uses limited caching for performance optimization
    """
    try:
        # Try to get from cache first (limited caching scope)
        from app.monitoring.performance_optimization import get_cached_status_data, cache_status_data
        
        cached_data = get_cached_status_data('queue_status')
        if cached_data:
            return cached_data
        
        celery_app = get_celery_app()
        settings = get_settings()
        
        # Get Celery inspector
        inspect = celery_app.control.inspect()
        
        # Get active and scheduled tasks
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        
        # Queue names from settings
        queue_names = [
            settings.queue_collect_name,
            settings.queue_process_name,
            settings.queue_publish_name
        ]
        
        queue_stats = {}
        
        for queue_name in queue_names:
            # Count active tasks for this queue
            active_count = sum(
                len([task for task in worker_tasks if task.get('delivery_info', {}).get('routing_key') == queue_name])
                for worker_tasks in active_tasks.values()
            )
            
            # Count scheduled tasks for this queue
            scheduled_count = sum(
                len([task for task in worker_tasks if task.get('delivery_info', {}).get('routing_key') == queue_name])
                for worker_tasks in scheduled_tasks.values()
            )
            
            # Count reserved tasks for this queue
            reserved_count = sum(
                len([task for task in worker_tasks if task.get('delivery_info', {}).get('routing_key') == queue_name])
                for worker_tasks in reserved_tasks.values()
            )
            
            # Get pending tasks from Redis
            pending_count = await get_redis_queue_length(queue_name)
            
            queue_stats[queue_name] = QueueStatus(
                queue_name=queue_name,
                active=active_count,
                pending=pending_count,
                scheduled=scheduled_count,
                reserved=reserved_count
            )
        
        response_data = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "queues": {name: status.dict() for name, status in queue_stats.items()}
        }
        
        # Cache the response (limited caching scope - status pages only)
        cache_status_data('queue_status', response_data)
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get queue status: {str(e)}"
        )


@router.get("/status/workers")
async def get_worker_status():
    """
    Get status of all Celery workers
    
    Returns worker name, heartbeat, active tasks, and consumed queues
    Uses limited caching for performance optimization
    """
    try:
        # Try to get from cache first (limited caching scope)
        from app.monitoring.performance_optimization import get_cached_status_data, cache_status_data
        
        cached_data = get_cached_status_data('worker_status')
        if cached_data:
            return cached_data
        
        celery_app = get_celery_app()
        
        # Get Celery inspector
        inspect = celery_app.control.inspect()
        
        # Get worker stats and active tasks
        stats = inspect.stats() or {}
        active_tasks = inspect.active() or {}
        
        worker_stats = {}
        
        for worker_name, worker_info in stats.items():
            # Get active task count for this worker
            active_count = len(active_tasks.get(worker_name, []))
            
            # Get processed task count
            processed_count = worker_info.get('total', {}).get('tasks.collector.collect_reddit_posts', 0)
            processed_count += worker_info.get('total', {}).get('tasks.nlp_pipeline.process_content_with_ai', 0)
            processed_count += worker_info.get('total', {}).get('tasks.publisher.publish_to_ghost', 0)
            
            # Get last heartbeat (current time as approximation)
            last_heartbeat = datetime.utcnow().isoformat()
            
            # Get consumed queues (from worker configuration)
            queues = worker_info.get('pool', {}).get('processes', [])
            if not queues:
                # Fallback: determine from worker name
                if 'collect' in worker_name:
                    queues = ['collect']
                elif 'process' in worker_name:
                    queues = ['process']
                elif 'publish' in worker_name:
                    queues = ['publish']
                else:
                    queues = ['celery']  # default queue
            
            worker_stats[worker_name] = WorkerStatus(
                worker_name=worker_name,
                status="online",
                active_tasks=active_count,
                processed_tasks=processed_count,
                last_heartbeat=last_heartbeat,
                queues=queues if isinstance(queues, list) else [str(queues)]
            )
        
        response_data = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "workers": {name: status.dict() for name, status in worker_stats.items()}
        }
        
        # Cache the response (limited caching scope - status pages only)
        cache_status_data('worker_status', response_data)
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get worker status: {str(e)}"
        )


@router.get("/status/system")
async def get_system_status():
    """
    Get overall system status
    
    Combines queue and worker status with summary metrics
    """
    try:
        # Get queue and worker status
        queue_response = await get_queue_status()
        worker_response = await get_worker_status()
        
        queues = queue_response["queues"]
        workers = worker_response["workers"]
        
        # Calculate totals
        total_active = sum(queue["active"] for queue in queues.values())
        total_pending = sum(queue["pending"] for queue in queues.values())
        
        # Determine overall status
        online_workers = sum(1 for worker in workers.values() if worker["status"] == "online")
        overall_status = "healthy" if online_workers > 0 else "unhealthy"
        
        return SystemStatus(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            queues=queues,
            workers=workers,
            total_active_tasks=total_active,
            total_pending_tasks=total_pending
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system status: {str(e)}"
        )