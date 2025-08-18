"""
API routes for resilience pattern monitoring and management
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.error_handling import ServiceType, get_resilience_manager
from app.resilience_monitor import get_resilience_monitor

router = APIRouter(prefix="/resilience", tags=["resilience"])


class ServiceHealthResponse(BaseModel):
    """Response model for service health"""
    service: str
    overall_status: str
    circuit_breaker: Optional[Dict]
    bulkhead: Optional[Dict]
    metrics: Optional[Dict]
    timestamp: str


class ResilienceStatusResponse(BaseModel):
    """Response model for overall resilience status"""
    services: Dict[str, ServiceHealthResponse]
    timestamp: str


class CircuitBreakerResetRequest(BaseModel):
    """Request model for circuit breaker reset"""
    service: str


class BulkheadAdjustRequest(BaseModel):
    """Request model for bulkhead adjustment"""
    service: str
    max_concurrent: Optional[int] = None
    queue_size: Optional[int] = None


@router.get("/status", response_model=ResilienceStatusResponse)
async def get_resilience_status():
    """Get overall resilience status for all services"""
    monitor = get_resilience_monitor()
    services = {}
    
    for service in ServiceType:
        try:
            health = await monitor.get_service_health(service)
            services[service.value] = ServiceHealthResponse(**health)
        except Exception as e:
            services[service.value] = ServiceHealthResponse(
                service=service.value,
                overall_status="error",
                circuit_breaker=None,
                bulkhead=None,
                metrics=None,
                timestamp=datetime.utcnow().isoformat()
            )
    
    return ResilienceStatusResponse(
        services=services,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/status/{service}", response_model=ServiceHealthResponse)
async def get_service_status(service: str):
    """Get resilience status for a specific service"""
    try:
        service_type = ServiceType(service)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid service: {service}")
    
    monitor = get_resilience_monitor()
    health = await monitor.get_service_health(service_type)
    
    return ServiceHealthResponse(**health)


@router.get("/metrics")
async def get_resilience_metrics():
    """Get current resilience metrics for all services"""
    monitor = get_resilience_monitor()
    metrics = await monitor.collect_metrics()
    
    return {
        service.value: metric.to_dict()
        for service, metric in metrics.items()
    }


@router.get("/metrics/{service}")
async def get_service_metrics(service: str):
    """Get resilience metrics for a specific service"""
    try:
        service_type = ServiceType(service)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid service: {service}")
    
    monitor = get_resilience_monitor()
    metrics = await monitor.collect_metrics()
    
    if service_type not in metrics:
        raise HTTPException(status_code=404, detail=f"Metrics not found for service: {service}")
    
    return metrics[service_type].to_dict()


@router.get("/alerts")
async def get_recent_alerts(
    hours: int = Query(default=24, ge=1, le=168),  # 1 hour to 1 week
    service: Optional[str] = Query(default=None)
):
    """Get recent resilience alerts"""
    monitor = get_resilience_monitor()
    
    # This would fetch alerts from Redis
    # Implementation depends on how alerts are stored
    return {
        "message": "Alert retrieval not yet implemented",
        "hours": hours,
        "service": service
    }


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(request: CircuitBreakerResetRequest):
    """Manually reset a circuit breaker"""
    try:
        service_type = ServiceType(request.service)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid service: {request.service}")
    
    monitor = get_resilience_monitor()
    success = await monitor.reset_circuit_breaker(service_type)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset circuit breaker")
    
    return {
        "message": f"Circuit breaker reset successfully for {request.service}",
        "service": request.service,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/bulkhead/adjust")
async def adjust_bulkhead_limits(request: BulkheadAdjustRequest):
    """Adjust bulkhead limits for a service"""
    try:
        service_type = ServiceType(request.service)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid service: {request.service}")
    
    if request.max_concurrent is None and request.queue_size is None:
        raise HTTPException(status_code=400, detail="At least one limit must be specified")
    
    monitor = get_resilience_monitor()
    success = await monitor.adjust_bulkhead_limits(
        service_type,
        request.max_concurrent,
        request.queue_size
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to adjust bulkhead limits")
    
    return {
        "message": f"Bulkhead limits adjusted successfully for {request.service}",
        "service": request.service,
        "max_concurrent": request.max_concurrent,
        "queue_size": request.queue_size,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health")
async def resilience_health_check():
    """Health check endpoint for resilience patterns"""
    manager = get_resilience_manager()
    monitor = get_resilience_monitor()
    
    try:
        # Get status of all services
        all_status = manager.get_all_status()
        
        # Count healthy vs unhealthy services
        healthy_count = 0
        total_count = len(all_status)
        
        for service_status in all_status.values():
            circuit_breaker = service_status.get("circuit_breaker", {})
            if circuit_breaker.get("state") == "closed":
                healthy_count += 1
        
        overall_health = "healthy" if healthy_count == total_count else "degraded"
        if healthy_count == 0:
            overall_health = "unhealthy"
        
        return {
            "status": overall_health,
            "services_total": total_count,
            "services_healthy": healthy_count,
            "services_unhealthy": total_count - healthy_count,
            "details": all_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }