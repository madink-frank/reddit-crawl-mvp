"""
Status monitoring endpoints
System status, queue monitoring, and worker information
"""
import time
from typing import Dict, Any, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel

from app.api.middleware.auth import get_current_user
from app.config import get_settings


logger = structlog.get_logger(__name__)

router = APIRouter()


class QueueStatus(BaseModel):
    """Queue status model"""
    name: str
    pending: int
    active: int
    failed: int
    processed: int
    last_updated: float


class WorkerStatus(BaseModel):
    """Worker status model"""
    name: str
    status: str
    active_tasks: int
    processed_tasks: int
    failed_tasks: int
    load_average: List[float]
    last_heartbeat: float


class SystemStatus(BaseModel):
    """System status model"""
    status: str
    timestamp: float
    uptime_seconds: float
    version: str
    environment: str
    queues: List[QueueStatus]
    workers: List[WorkerStatus]
    system_metrics: Dict[str, Any]


async def get_queue_stats() -> List[QueueStatus]:
    """Get queue statistics from Celery"""
    try:
        from app.celery_app import celery_app
        
        # Get queue statistics
        inspect = celery_app.control.inspect()
        
        # Get active tasks
        active_tasks = inspect.active() or {}
        
        # Get reserved tasks
        reserved_tasks = inspect.reserved() or {}
        
        # Get queue lengths from Redis
        from app.infrastructure import get_redis_client
        redis_client = get_redis_client()
        
        queues = []
        queue_names = ["collect", "process", "publish"]
        
        for queue_name in queue_names:
            try:
                # Get queue length
                pending = await redis_client.llen(f"celery:{queue_name}")
                
                # Count active tasks for this queue
                active = 0
                for worker_tasks in active_tasks.values():
                    active += len([task for task in worker_tasks if task.get("delivery_info", {}).get("routing_key") == queue_name])
                
                # Get failed count (simplified)
                failed = await redis_client.llen(f"celery:failed:{queue_name}") or 0
                
                # Get processed count (from stats if available)
                processed = 0  # Would need to implement stats tracking
                
                queues.append(QueueStatus(
                    name=queue_name,
                    pending=pending,
                    active=active,
                    failed=failed,
                    processed=processed,
                    last_updated=time.time()
                ))
                
            except Exception as e:
                logger.warning(f"Failed to get stats for queue {queue_name}", error=str(e))
                queues.append(QueueStatus(
                    name=queue_name,
                    pending=0,
                    active=0,
                    failed=0,
                    processed=0,
                    last_updated=time.time()
                ))
        
        return queues
        
    except Exception as e:
        logger.error("Failed to get queue stats", error=str(e))
        return []


async def get_worker_stats() -> List[WorkerStatus]:
    """Get worker statistics from Celery"""
    try:
        from app.celery_app import celery_app
        
        # Get worker statistics
        inspect = celery_app.control.inspect()
        
        # Get worker stats
        stats = inspect.stats() or {}
        active_tasks = inspect.active() or {}
        
        workers = []
        
        for worker_name, worker_stats in stats.items():
            try:
                # Get active task count
                active_count = len(active_tasks.get(worker_name, []))
                
                # Extract worker metrics
                total_tasks = worker_stats.get("total", {})
                
                workers.append(WorkerStatus(
                    name=worker_name,
                    status="online",
                    active_tasks=active_count,
                    processed_tasks=total_tasks.get("tasks.processed", 0),
                    failed_tasks=total_tasks.get("tasks.failed", 0),
                    load_average=worker_stats.get("rusage", {}).get("load_avg", [0.0, 0.0, 0.0]),
                    last_heartbeat=time.time()
                ))
                
            except Exception as e:
                logger.warning(f"Failed to get stats for worker {worker_name}", error=str(e))
        
        return workers
        
    except Exception as e:
        logger.error("Failed to get worker stats", error=str(e))
        return []


async def get_system_metrics() -> Dict[str, Any]:
    """Get system metrics"""
    try:
        import psutil
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get network stats
        network = psutil.net_io_counters()
        
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count(),
                "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100
            },
            "network": {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
        }
        
    except Exception as e:
        logger.error("Failed to get system metrics", error=str(e))
        return {}


@router.get("/status/queues", response_model=List[QueueStatus])
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """
    Get status of all Celery queues
    
    Returns information about pending, active, and failed tasks in each queue.
    """
    try:
        queues = await get_queue_stats()
        
        # Add health assessment for each queue
        for queue in queues:
            if queue.failed > 50:
                logger.warning(
                    "High failure rate detected",
                    queue=queue.name,
                    failed_count=queue.failed
                )
            if queue.pending > 500:
                logger.warning(
                    "High queue backlog detected",
                    queue=queue.name,
                    pending_count=queue.pending
                )
        
        logger.info(
            "Queue status requested",
            user_id=current_user["sub"],
            queue_count=len(queues),
            total_pending=sum(q.pending for q in queues),
            total_failed=sum(q.failed for q in queues)
        )
        
        return queues
        
    except Exception as e:
        logger.error("Failed to get queue status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )


@router.get("/status/workers", response_model=List[WorkerStatus])
async def get_worker_status(current_user: dict = Depends(get_current_user)):
    """
    Get status of all Celery workers
    
    Returns information about worker health, active tasks, and performance metrics.
    """
    try:
        workers = await get_worker_stats()
        
        # Assess worker health
        healthy_workers = len([w for w in workers if w.status == "online"])
        if healthy_workers == 0:
            logger.error("No healthy workers found")
        elif healthy_workers < len(workers):
            logger.warning(
                "Some workers are unhealthy",
                healthy_count=healthy_workers,
                total_count=len(workers)
            )
        
        logger.info(
            "Worker status requested",
            user_id=current_user["sub"],
            worker_count=len(workers),
            healthy_workers=healthy_workers,
            total_active_tasks=sum(w.active_tasks for w in workers)
        )
        
        return workers
        
    except Exception as e:
        logger.error("Failed to get worker status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get worker status: {str(e)}"
        )


@router.get("/status/system", response_model=SystemStatus)
async def get_system_status(current_user: dict = Depends(get_current_user)):
    """
    Get comprehensive system status
    
    Returns overall system health including queues, workers, and system metrics.
    """
    try:
        settings = get_settings()
        
        # Get all status information
        queues = await get_queue_stats()
        workers = await get_worker_stats()
        system_metrics = await get_system_metrics()
        
        # Determine overall status with more sophisticated logic
        overall_status = "healthy"
        status_reasons = []
        
        # Check queue health
        total_failed = sum(q.failed for q in queues)
        total_pending = sum(q.pending for q in queues)
        
        if total_failed > 100:
            overall_status = "unhealthy"
            status_reasons.append(f"High failure rate: {total_failed} failed tasks")
        elif total_failed > 50:
            overall_status = "degraded"
            status_reasons.append(f"Moderate failure rate: {total_failed} failed tasks")
            
        if total_pending > 2000:
            overall_status = "unhealthy"
            status_reasons.append(f"Critical queue backlog: {total_pending} pending tasks")
        elif total_pending > 1000:
            if overall_status == "healthy":
                overall_status = "degraded"
            status_reasons.append(f"High queue backlog: {total_pending} pending tasks")
        
        # Check worker health
        healthy_workers = len([w for w in workers if w.status == "online"])
        if healthy_workers == 0:
            overall_status = "unhealthy"
            status_reasons.append("No healthy workers available")
        elif healthy_workers < len(workers) * 0.5:  # Less than 50% workers healthy
            if overall_status == "healthy":
                overall_status = "degraded"
            status_reasons.append(f"Only {healthy_workers}/{len(workers)} workers healthy")
        
        # Check system metrics with more granular thresholds
        if system_metrics:
            cpu_percent = system_metrics.get("cpu", {}).get("percent", 0)
            memory_percent = system_metrics.get("memory", {}).get("percent", 0)
            disk_percent = system_metrics.get("disk", {}).get("percent", 0)
            
            if cpu_percent > 95 or memory_percent > 95 or disk_percent > 95:
                overall_status = "unhealthy"
                status_reasons.append(f"Critical resource usage - CPU: {cpu_percent}%, Memory: {memory_percent}%, Disk: {disk_percent}%")
            elif cpu_percent > 85 or memory_percent > 85 or disk_percent > 85:
                if overall_status == "healthy":
                    overall_status = "degraded"
                status_reasons.append(f"High resource usage - CPU: {cpu_percent}%, Memory: {memory_percent}%, Disk: {disk_percent}%")
        
        logger.info(
            "System status requested",
            user_id=current_user["sub"],
            status=overall_status,
            status_reasons=status_reasons,
            queue_count=len(queues),
            worker_count=len(workers),
            healthy_workers=healthy_workers,
            total_pending=total_pending,
            total_failed=total_failed
        )
        
        return SystemStatus(
            status=overall_status,
            timestamp=time.time(),
            uptime_seconds=time.time() - getattr(get_system_status, '_start_time', time.time()),
            version="1.0.0",
            environment=settings.environment,
            queues=queues,
            workers=workers,
            system_metrics=system_metrics
        )
        
    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}"
        )


@router.get("/status/metrics/summary")
async def get_metrics_summary(current_user: dict = Depends(get_current_user)):
    """
    Get summary metrics for dashboard
    
    Returns aggregated metrics suitable for monitoring dashboards
    """
    try:
        # Get basic metrics
        queues = await get_queue_stats()
        workers = await get_worker_stats()
        system_metrics = await get_system_metrics()
        
        # Calculate summary metrics
        total_pending = sum(q.pending for q in queues)
        total_active = sum(q.active for q in queues)
        total_failed = sum(q.failed for q in queues)
        total_processed = sum(q.processed for q in queues)
        
        active_workers = len([w for w in workers if w.status == "online"])
        
        # Calculate rates and trends (simplified)
        current_time = time.time()
        
        # Queue health indicators
        queue_health = "healthy"
        if total_failed > 100:
            queue_health = "unhealthy"
        elif total_failed > 50 or total_pending > 1000:
            queue_health = "degraded"
        
        # Worker health indicators
        worker_health = "healthy"
        if active_workers == 0:
            worker_health = "unhealthy"
        elif active_workers < len(workers) * 0.7:
            worker_health = "degraded"
        
        # System health indicators
        system_health = "healthy"
        if system_metrics:
            cpu_percent = system_metrics.get("cpu", {}).get("percent", 0)
            memory_percent = system_metrics.get("memory", {}).get("percent", 0)
            disk_percent = system_metrics.get("disk", {}).get("percent", 0)
            
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
                system_health = "unhealthy"
            elif cpu_percent > 80 or memory_percent > 80 or disk_percent > 80:
                system_health = "degraded"
        
        summary = {
            "timestamp": current_time,
            "overall_health": min([queue_health, worker_health, system_health], 
                                key=lambda x: ["healthy", "degraded", "unhealthy"].index(x)),
            "tasks": {
                "pending": total_pending,
                "active": total_active,
                "failed": total_failed,
                "processed": total_processed,
                "total": total_pending + total_active + total_failed + total_processed,
                "health": queue_health
            },
            "workers": {
                "active": active_workers,
                "total": len(workers),
                "health": worker_health,
                "utilization": (sum(w.active_tasks for w in workers) / max(active_workers, 1)) if active_workers > 0 else 0
            },
            "system": {
                "cpu_percent": system_metrics.get("cpu", {}).get("percent", 0),
                "memory_percent": system_metrics.get("memory", {}).get("percent", 0),
                "disk_percent": system_metrics.get("disk", {}).get("percent", 0),
                "health": system_health
            },
            "queues": {
                queue.name: {
                    "pending": queue.pending,
                    "active": queue.active,
                    "failed": queue.failed,
                    "health": "unhealthy" if queue.failed > 20 else "degraded" if queue.failed > 10 or queue.pending > 500 else "healthy"
                }
                for queue in queues
            }
        }
        
        logger.info(
            "Metrics summary requested",
            user_id=current_user["sub"],
            overall_health=summary["overall_health"],
            total_pending=total_pending,
            active_workers=active_workers
        )
        
        return summary
        
    except Exception as e:
        logger.error("Failed to get metrics summary", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics summary: {str(e)}"
        )


@router.get("/status/dependencies")
async def get_dependencies_status(current_user: dict = Depends(get_current_user)):
    """
    Get status of external dependencies
    
    Returns detailed information about external service connectivity and health
    """
    try:
        from app.monitoring.health import get_health_checker
        
        # Check external dependencies
        external_services = ['reddit_api', 'openai_api', 'ghost_api', 'vault']
        health_checker = get_health_checker()
        health_result = await health_checker.check_health(external_services)
        
        # Format response
        dependencies = {}
        for service_name, result in health_result.services.items():
            dependencies[service_name] = {
                "status": result.status.value,
                "response_time_ms": result.response_time_ms,
                "message": result.message,
                "details": result.details,
                "last_checked": result.timestamp.isoformat()
            }
        
        # Determine overall dependency health
        overall_status = health_result.status.value
        
        logger.info(
            "Dependencies status requested",
            user_id=current_user["sub"],
            overall_status=overall_status,
            services_checked=list(dependencies.keys())
        )
        
        return {
            "status": overall_status,
            "timestamp": health_result.timestamp.isoformat(),
            "dependencies": dependencies,
            "summary": {
                "total": len(dependencies),
                "healthy": len([d for d in dependencies.values() if d["status"] == "healthy"]),
                "degraded": len([d for d in dependencies.values() if d["status"] == "degraded"]),
                "unhealthy": len([d for d in dependencies.values() if d["status"] == "unhealthy"])
            }
        }
        
    except Exception as e:
        logger.error("Failed to get dependencies status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dependencies status: {str(e)}"
        )


@router.get("/status/alerts")
async def get_system_alerts(current_user: dict = Depends(get_current_user)):
    """
    Get current system alerts and warnings
    
    Returns active alerts based on system health thresholds
    """
    try:
        alerts = []
        
        # Check queue alerts
        queues = await get_queue_stats()
        for queue in queues:
            if queue.failed > 50:
                alerts.append({
                    "type": "error",
                    "service": "queue",
                    "queue": queue.name,
                    "message": f"High failure rate in {queue.name} queue: {queue.failed} failed tasks",
                    "severity": "high" if queue.failed > 100 else "medium",
                    "timestamp": time.time()
                })
            
            if queue.pending > 1000:
                alerts.append({
                    "type": "warning",
                    "service": "queue",
                    "queue": queue.name,
                    "message": f"High backlog in {queue.name} queue: {queue.pending} pending tasks",
                    "severity": "high" if queue.pending > 2000 else "medium",
                    "timestamp": time.time()
                })
        
        # Check worker alerts
        workers = await get_worker_stats()
        healthy_workers = len([w for w in workers if w.status == "online"])
        
        if healthy_workers == 0:
            alerts.append({
                "type": "error",
                "service": "workers",
                "message": "No healthy workers available",
                "severity": "critical",
                "timestamp": time.time()
            })
        elif healthy_workers < len(workers) * 0.5:
            alerts.append({
                "type": "warning",
                "service": "workers",
                "message": f"Only {healthy_workers}/{len(workers)} workers are healthy",
                "severity": "medium",
                "timestamp": time.time()
            })
        
        # Check system resource alerts
        system_metrics = await get_system_metrics()
        if system_metrics:
            cpu_percent = system_metrics.get("cpu", {}).get("percent", 0)
            memory_percent = system_metrics.get("memory", {}).get("percent", 0)
            disk_percent = system_metrics.get("disk", {}).get("percent", 0)
            
            if cpu_percent > 90:
                alerts.append({
                    "type": "error",
                    "service": "system",
                    "resource": "cpu",
                    "message": f"High CPU usage: {cpu_percent:.1f}%",
                    "severity": "high",
                    "timestamp": time.time()
                })
            
            if memory_percent > 90:
                alerts.append({
                    "type": "error",
                    "service": "system",
                    "resource": "memory",
                    "message": f"High memory usage: {memory_percent:.1f}%",
                    "severity": "high",
                    "timestamp": time.time()
                })
            
            if disk_percent > 90:
                alerts.append({
                    "type": "error",
                    "service": "system",
                    "resource": "disk",
                    "message": f"High disk usage: {disk_percent:.1f}%",
                    "severity": "high",
                    "timestamp": time.time()
                })
        
        # Sort alerts by severity and timestamp
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: (severity_order.get(x["severity"], 3), -x["timestamp"]))
        
        logger.info(
            "System alerts requested",
            user_id=current_user["sub"],
            alert_count=len(alerts),
            critical_alerts=len([a for a in alerts if a["severity"] == "critical"]),
            high_alerts=len([a for a in alerts if a["severity"] == "high"])
        )
        
        return {
            "timestamp": time.time(),
            "alert_count": len(alerts),
            "alerts": alerts,
            "summary": {
                "critical": len([a for a in alerts if a["severity"] == "critical"]),
                "high": len([a for a in alerts if a["severity"] == "high"]),
                "medium": len([a for a in alerts if a["severity"] == "medium"]),
                "low": len([a for a in alerts if a["severity"] == "low"])
            }
        }
        
    except Exception as e:
        logger.error("Failed to get system alerts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system alerts: {str(e)}"
        )


# Store start time for uptime calculation
get_system_status._start_time = time.time()