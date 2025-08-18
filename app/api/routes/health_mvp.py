"""
Enhanced health check endpoints with dependency monitoring and alerting
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.monitoring.health import HealthChecker, AlertManager
from app.monitoring.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Enhanced health check response model"""
    status: str
    timestamp: str
    version: str
    environment: str
    uptime_seconds: float
    services: Dict[str, Any]
    summary: Dict[str, int]


class ServiceStatus(BaseModel):
    """Individual service status model"""
    status: str
    response_time_ms: float
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None


def get_database_session():
    """Get database session dependency"""
    try:
        from app.infrastructure import get_database_session
        db_session = get_database_session()
        try:
            yield db_session
        finally:
            db_session.close()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Database not available"
        )


# Store start time for uptime calculation
_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Enhanced health check endpoint with comprehensive dependency monitoring
    
    Checks:
    - Database (PostgreSQL) with connection pool status
    - Redis with diagnostics
    - External APIs (Reddit, OpenAI, Ghost)
    - System metrics and uptime
    """
    try:
        health_checker = HealthChecker()
        health_status = await health_checker.get_comprehensive_health()
        
        response = HealthResponse(
            status=health_status["status"],
            timestamp=health_status["timestamp"],
            version=health_status["version"],
            environment=health_status["environment"],
            uptime_seconds=health_status["uptime_seconds"],
            services=health_status["services"],
            summary=health_status["summary"]
        )
        
        # Log health check result
        logger.info(
            "Health check completed",
            status=health_status["status"],
            healthy_services=health_status["summary"]["healthy"],
            degraded_services=health_status["summary"]["degraded"],
            unhealthy_services=health_status["summary"]["unhealthy"]
        )
        
        return response
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check for container orchestration
    Returns 200 if ready to serve traffic, 503 if not
    """
    try:
        health_checker = HealthChecker()
        
        # Check only critical services for readiness
        db_health = await health_checker.check_database()
        redis_health = await health_checker.check_redis()
        
        critical_services = [db_health, redis_health]
        unhealthy_services = [
            service.name for service in critical_services 
            if service.status.value != "healthy"
        ]
        
        if not unhealthy_services:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "services": {
                    service.name: service.status.value 
                    for service in critical_services
                }
            }
        else:
            logger.warning("Service not ready", unhealthy_services=unhealthy_services)
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Service not ready - critical dependencies unhealthy",
                    "unhealthy_services": unhealthy_services,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )


@router.get("/health/live")
async def liveness_check():
    """
    Liveness check for container orchestration
    Returns 200 if application process is responsive
    """
    current_time = time.time()
    uptime = current_time - _start_time
    
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": round(uptime, 2),
        "version": "1.0.0"
    }


@router.post("/health/alerts/check")
async def check_alerts(db_session: Session = Depends(get_database_session)):
    """
    Manual alert check endpoint
    
    Checks system health and sends alerts if thresholds are exceeded:
    - Failure rate > 5% (last 5 minutes)
    - Queue backlog > 500 tasks
    - Unhealthy services
    """
    try:
        alert_manager = AlertManager()
        result = await alert_manager.check_and_alert(db_session)
        
        logger.info(
            "Alert check completed",
            status=result["status"],
            alerts_sent=result.get("alerts_sent", []),
            failure_rate=result.get("failure_rate", 0),
            queue_backlog=result.get("queue_backlog", 0)
        )
        
        return result
        
    except Exception as e:
        logger.error("Alert check failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Alert check failed: {str(e)}"
        )