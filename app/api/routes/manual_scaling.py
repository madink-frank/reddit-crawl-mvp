"""
Manual scaling monitoring and recommendation endpoints
Provides queue backlog alerts and scaling guidance for MVP
"""
from typing import Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.infrastructure import get_async_session
from app.monitoring.manual_scaling import (
    ManualScalingAlertManager,
    ScalingRecommendation,
    check_queue_scaling_alert,
    check_resource_usage_alert,
    get_scaling_recommendations,
    get_manual_scaling_guide
)


router = APIRouter()
settings = get_settings()


class ScalingRecommendationResponse(BaseModel):
    """Scaling recommendation response model"""
    queue_name: str
    current_pending: int
    recommended_workers: int
    current_workers: int
    reason: str
    priority: str


class ManualScalingGuideResponse(BaseModel):
    """Manual scaling guide response model"""
    current_status: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    scaling_commands: Dict[str, str]
    scaling_steps: List[str]
    monitoring_endpoints: Dict[str, str]
    alert_thresholds: Dict[str, Any]
    timestamp: str


class AlertCheckResponse(BaseModel):
    """Alert check response model"""
    alert_triggered: bool
    alert_type: str
    message: str
    timestamp: str


@router.get("/scaling/recommendations")
async def get_current_scaling_recommendations(
    db: Session = Depends(get_async_session)
) -> List[ScalingRecommendationResponse]:
    """
    Get current scaling recommendations based on queue metrics
    
    Returns:
        List of scaling recommendations with priority and commands
    """
    try:
        recommendations = get_scaling_recommendations(db)
        
        return [
            ScalingRecommendationResponse(
                queue_name=rec.queue_name,
                current_pending=rec.current_pending,
                recommended_workers=rec.recommended_workers,
                current_workers=rec.current_workers,
                reason=rec.reason,
                priority=rec.priority
            )
            for rec in recommendations
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scaling recommendations: {str(e)}"
        )


@router.get("/scaling/guide")
async def get_scaling_guide(
    db: Session = Depends(get_async_session)
) -> ManualScalingGuideResponse:
    """
    Get comprehensive manual scaling guide with current status and recommendations
    
    Returns:
        Complete scaling guide with commands and monitoring information
    """
    try:
        guide = get_manual_scaling_guide(db)
        
        if "error" in guide:
            raise HTTPException(
                status_code=500,
                detail=guide["error"]
            )
        
        return ManualScalingGuideResponse(**guide)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scaling guide: {str(e)}"
        )


@router.post("/scaling/check-alerts")
async def check_scaling_alerts(
    db: Session = Depends(get_async_session)
) -> List[AlertCheckResponse]:
    """
    Manually trigger scaling alert checks
    
    Returns:
        List of alert check results
    """
    try:
        results = []
        
        # Check queue scaling alert
        queue_alert_triggered = check_queue_scaling_alert(db)
        results.append(AlertCheckResponse(
            alert_triggered=queue_alert_triggered,
            alert_type="queue_scaling",
            message="Queue backlog alert check completed" if queue_alert_triggered else "No queue scaling alert needed",
            timestamp=datetime.utcnow().isoformat()
        ))
        
        # Check resource usage alert
        resource_alert_triggered = check_resource_usage_alert(db)
        results.append(AlertCheckResponse(
            alert_triggered=resource_alert_triggered,
            alert_type="resource_usage",
            message="Resource usage alert check completed" if resource_alert_triggered else "No resource usage alert needed",
            timestamp=datetime.utcnow().isoformat()
        ))
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check scaling alerts: {str(e)}"
        )


@router.get("/scaling/thresholds")
async def get_scaling_thresholds() -> Dict[str, Any]:
    """
    Get current scaling alert thresholds and configuration
    
    Returns:
        Dictionary with threshold values and configuration
    """
    try:
        return {
            "queue_thresholds": {
                "alert_threshold": settings.queue_alert_threshold,
                "collect_light": 50,
                "collect_medium": 150,
                "collect_heavy": 300,
                "process_light": 30,
                "process_medium": 100,
                "process_heavy": 200,
                "publish_light": 20,
                "publish_medium": 80,
                "publish_heavy": 150
            },
            "resource_thresholds": {
                "cpu_threshold": 80.0,
                "memory_threshold": 80.0,
                "disk_threshold": 85.0
            },
            "alert_configuration": {
                "cooldown_minutes": 15,
                "failure_rate_threshold": settings.failure_rate_threshold,
                "max_workers_per_queue": 8
            },
            "worker_configuration": {
                "collector_concurrency": settings.worker_collector_concurrency,
                "nlp_concurrency": settings.worker_nlp_concurrency,
                "publisher_concurrency": settings.worker_publisher_concurrency
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scaling thresholds: {str(e)}"
        )


@router.get("/scaling/status")
async def get_scaling_status(
    db: Session = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    Get current scaling status with queue metrics and recommendations
    
    Returns:
        Combined status with metrics, recommendations, and resource usage
    """
    try:
        alert_manager = ManualScalingAlertManager(db)
        
        # Get queue metrics
        queue_metrics = alert_manager.metrics_collector.get_queue_metrics()
        
        # Get scaling recommendations
        recommendations = alert_manager.get_scaling_recommendations()
        
        # Get resource usage
        resource_usage = alert_manager._get_resource_usage()
        
        # Determine if scaling is needed
        scaling_needed = len(recommendations) > 0
        total_pending = queue_metrics.get("queue_total_pending", 0)
        threshold_exceeded = total_pending > settings.queue_alert_threshold
        
        # Determine status
        if threshold_exceeded:
            status = "scaling_required"
        elif scaling_needed:
            status = "scaling_recommended"
        else:
            status = "normal"
        
        return {
            "status": status,
            "scaling_needed": scaling_needed,
            "threshold_exceeded": threshold_exceeded,
            "queue_metrics": queue_metrics,
            "recommendations": [rec.__dict__ for rec in recommendations],
            "resource_usage": resource_usage.__dict__ if resource_usage else None,
            "alert_thresholds": {
                "queue_alert_threshold": settings.queue_alert_threshold,
                "failure_rate_threshold": settings.failure_rate_threshold
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scaling status: {str(e)}"
        )


@router.get("/scaling/commands")
async def get_scaling_commands() -> Dict[str, Any]:
    """
    Get Docker Compose scaling commands for manual scaling
    
    Returns:
        Dictionary with scaling commands and examples
    """
    try:
        return {
            "docker_compose_commands": {
                "scale_collector": "docker-compose up -d --scale worker-collector=N",
                "scale_nlp": "docker-compose up -d --scale worker-nlp=N",
                "scale_publisher": "docker-compose up -d --scale worker-publisher=N",
                "scale_all": "docker-compose up -d --scale worker-collector=N --scale worker-nlp=N --scale worker-publisher=N"
            },
            "examples": {
                "light_load": {
                    "collector": "docker-compose up -d --scale worker-collector=2",
                    "nlp": "docker-compose up -d --scale worker-nlp=2",
                    "publisher": "docker-compose up -d --scale worker-publisher=2"
                },
                "medium_load": {
                    "collector": "docker-compose up -d --scale worker-collector=3",
                    "nlp": "docker-compose up -d --scale worker-nlp=3",
                    "publisher": "docker-compose up -d --scale worker-publisher=3"
                },
                "heavy_load": {
                    "collector": "docker-compose up -d --scale worker-collector=4",
                    "nlp": "docker-compose up -d --scale worker-nlp=4",
                    "publisher": "docker-compose up -d --scale worker-publisher=4"
                }
            },
            "monitoring_commands": {
                "check_containers": "docker-compose ps",
                "view_logs": "docker-compose logs -f worker-collector",
                "check_resources": "docker stats"
            },
            "scaling_guidelines": [
                "1. Identify bottleneck queue from /api/v1/status/queues",
                "2. Scale the corresponding worker type first",
                "3. Monitor for 5-10 minutes before additional scaling",
                "4. Scale down during low traffic periods",
                "5. Maximum recommended: 4-8 workers per queue type"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scaling commands: {str(e)}"
        )