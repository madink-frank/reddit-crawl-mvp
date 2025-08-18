"""
Health check endpoints
Provides system health and readiness checks
"""
import time
from typing import Dict, Any, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.config import get_settings
from app.monitoring.health import get_health_checker, quick_health_check, full_health_check


logger = structlog.get_logger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    timestamp: str
    version: str
    environment: str
    uptime_seconds: float
    healthy_services: int
    total_services: int
    services: Dict[str, Any]


class ServiceCheck(BaseModel):
    """Individual service check model"""
    status: str
    response_time_ms: float
    message: str
    details: Dict[str, Any]
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check(
    services: Optional[List[str]] = Query(None, description="Specific services to check"),
    detailed: bool = Query(False, description="Include detailed service information")
):
    """
    Comprehensive health check endpoint
    Returns overall system health status with detailed service checks
    
    Query Parameters:
    - services: List of specific services to check (e.g., ?services=database&services=redis)
    - detailed: Include detailed service information and external API checks
    """
    settings = get_settings()
    
    try:
        if detailed:
            # Perform comprehensive health check
            health_data = await full_health_check()
        else:
            # Perform quick health check of critical services
            health_data = await quick_health_check()
            
            # If specific services requested, get detailed info for those
            if services:
                health_checker = get_health_checker()
                detailed_health = await health_checker.check_health(services)
                health_data = detailed_health.to_dict()
        
        # Convert to response format
        response_data = {
            "status": health_data["status"],
            "timestamp": health_data["timestamp"],
            "version": "1.0.0",
            "environment": settings.environment,
            "uptime_seconds": health_data.get("uptime_seconds", 0),
            "healthy_services": health_data.get("healthy_services", 0),
            "total_services": health_data.get("total_services", 0),
            "services": health_data.get("services", {})
        }
        
        logger.info(
            "Health check performed",
            status=health_data["status"],
            services_checked=list(health_data.get("services", {}).keys()),
            detailed=detailed,
            requested_services=services
        )
        
        return HealthResponse(**response_data)
        
    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check for Kubernetes/Docker
    Returns 200 if ready to serve traffic, 503 if not
    
    Checks critical services required for the application to function:
    - Database connectivity
    - Redis connectivity  
    - Celery broker connectivity
    """
    try:
        # Check only critical services for readiness
        critical_services = ['database', 'redis', 'celery_broker']
        health_checker = get_health_checker()
        health_result = await health_checker.check_health(critical_services)
        
        # Check if all critical services are healthy
        critical_healthy = all(
            result.status.value == "healthy" 
            for service, result in health_result.services.items()
            if service in critical_services
        )
        
        if critical_healthy:
            logger.info("Readiness check passed", services=critical_services)
            return {
                "status": "ready", 
                "timestamp": health_result.timestamp.isoformat(),
                "services": {
                    name: result.status.value 
                    for name, result in health_result.services.items()
                }
            }
        else:
            unhealthy_services = [
                name for name, result in health_result.services.items()
                if result.status.value != "healthy"
            ]
            logger.warning(
                "Readiness check failed", 
                unhealthy_services=unhealthy_services
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Service not ready - critical dependencies unhealthy",
                    "unhealthy_services": unhealthy_services,
                    "timestamp": health_result.timestamp.isoformat()
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )


@router.get("/health/live")
async def liveness_check():
    """
    Liveness check for Kubernetes/Docker
    Returns 200 if application is running
    
    This is a simple check that the application process is responsive.
    It doesn't check external dependencies.
    """
    current_time = time.time()
    uptime = current_time - getattr(liveness_check, '_start_time', current_time)
    
    logger.debug("Liveness check performed", uptime_seconds=uptime)
    
    return {
        "status": "alive",
        "timestamp": current_time,
        "uptime_seconds": uptime,
        "version": "1.0.0"
    }


@router.get("/health/dependencies")
async def dependencies_check():
    """
    Check status of external dependencies
    
    Returns detailed information about external service connectivity:
    - Reddit API
    - OpenAI API  
    - Ghost CMS API
    - HashiCorp Vault
    """
    try:
        external_services = ['reddit_api', 'openai_api', 'ghost_api', 'vault']
        health_checker = get_health_checker()
        health_result = await health_checker.check_health(external_services)
        
        logger.info(
            "Dependencies check performed",
            services=external_services,
            status=health_result.status.value
        )
        
        return {
            "status": health_result.status.value,
            "timestamp": health_result.timestamp.isoformat(),
            "uptime_seconds": health_result.uptime_seconds,
            "services": {
                name: {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "message": result.message,
                    "details": result.details
                }
                for name, result in health_result.services.items()
            }
        }
        
    except Exception as e:
        logger.error("Dependencies check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Dependencies check failed: {str(e)}"
        )


@router.get("/health/system")
async def system_health_check():
    """
    Check system resource health
    
    Returns information about system resources:
    - Disk space usage
    - Memory usage
    - CPU metrics (if available)
    """
    try:
        system_services = ['disk_space', 'memory_usage']
        health_checker = get_health_checker()
        health_result = await health_checker.check_health(system_services)
        
        logger.info(
            "System health check performed",
            services=system_services,
            status=health_result.status.value
        )
        
        return {
            "status": health_result.status.value,
            "timestamp": health_result.timestamp.isoformat(),
            "uptime_seconds": health_result.uptime_seconds,
            "resources": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details
                }
                for name, result in health_result.services.items()
            }
        }
        
    except Exception as e:
        logger.error("System health check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"System health check failed: {str(e)}"
        )


# Store start time for uptime calculation
liveness_check._start_time = time.time()