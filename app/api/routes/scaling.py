"""
API endpoints for auto-scaling management and monitoring
"""

from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.scaling.auto_scaler import scaling_manager
from app.scaling.resource_monitor import resource_monitor_service
from app.api.middleware.auth import verify_admin_token

router = APIRouter(prefix="/api/v1/scaling", tags=["scaling"])

class ScaleWorkersRequest(BaseModel):
    """Request model for manual worker scaling"""
    queue_name: str = Field(..., description="Queue name (collect, process, publish)")
    count: int = Field(..., ge=1, le=8, description="Number of workers (1-8)")

class ScaleAPIRequest(BaseModel):
    """Request model for manual API scaling"""
    count: int = Field(..., ge=2, le=6, description="Number of API instances (2-6)")

class ScalingConfigUpdate(BaseModel):
    """Request model for updating scaling configuration"""
    queue_scale_up_threshold: Optional[int] = Field(None, ge=100, le=5000)
    queue_scale_down_threshold: Optional[int] = Field(None, ge=10, le=1000)
    api_scale_up_threshold: Optional[float] = Field(None, ge=100.0, le=2000.0)
    api_scale_down_threshold: Optional[float] = Field(None, ge=50.0, le=500.0)
    cpu_scale_up_threshold: Optional[float] = Field(None, ge=50.0, le=95.0)
    memory_scale_up_threshold: Optional[float] = Field(None, ge=50.0, le=95.0)

@router.get("/status")
async def get_scaling_status():
    """Get current auto-scaling status and metrics"""
    try:
        scaling_status = await scaling_manager.get_scaling_status()
        resource_status = resource_monitor_service.get_current_status()
        
        return {
            "scaling": scaling_status,
            "resources": resource_status,
            "timestamp": scaling_status.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting scaling status: {str(e)}")

@router.post("/workers/scale")
async def scale_workers(
    request: ScaleWorkersRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Manually scale workers for a specific queue"""
    try:
        success = await scaling_manager.manual_scale_workers(
            request.queue_name, 
            request.count
        )
        
        if success:
            return {
                "success": True,
                "message": f"Successfully scaled {request.queue_name} workers to {request.count}",
                "queue_name": request.queue_name,
                "new_count": request.count
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to scale {request.queue_name} workers"
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scaling workers: {str(e)}")

@router.post("/api/scale")
async def scale_api_instances(
    request: ScaleAPIRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Manually scale API instances"""
    try:
        success = await scaling_manager.manual_scale_api(request.count)
        
        if success:
            return {
                "success": True,
                "message": f"Successfully scaled API instances to {request.count}",
                "new_count": request.count
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to scale API instances"
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scaling API: {str(e)}")

@router.post("/enable")
async def enable_auto_scaling(admin_token: str = Depends(verify_admin_token)):
    """Enable auto-scaling service"""
    try:
        await scaling_manager.start()
        await resource_monitor_service.start()
        
        return {
            "success": True,
            "message": "Auto-scaling service enabled"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enabling auto-scaling: {str(e)}")

@router.post("/disable")
async def disable_auto_scaling(admin_token: str = Depends(verify_admin_token)):
    """Disable auto-scaling service"""
    try:
        await scaling_manager.stop()
        await resource_monitor_service.stop()
        
        return {
            "success": True,
            "message": "Auto-scaling service disabled"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error disabling auto-scaling: {str(e)}")

@router.get("/metrics/resources")
async def get_resource_metrics():
    """Get current resource usage metrics"""
    try:
        status = resource_monitor_service.get_current_status()
        
        if status.get("status") == "no_data":
            raise HTTPException(status_code=404, detail="No resource metrics available")
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting resource metrics: {str(e)}")

@router.get("/metrics/history")
async def get_metrics_history(duration_minutes: int = 60):
    """Get resource metrics history summary"""
    try:
        if not (1 <= duration_minutes <= 1440):  # 1 minute to 24 hours
            raise HTTPException(
                status_code=400, 
                detail="Duration must be between 1 and 1440 minutes"
            )
        
        summary = resource_monitor_service.monitor.get_metrics_summary(duration_minutes)
        
        if not summary:
            raise HTTPException(
                status_code=404, 
                detail="No metrics data available for the specified duration"
            )
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting metrics history: {str(e)}")

@router.get("/recommendations")
async def get_scaling_recommendations():
    """Get current scaling recommendations based on metrics"""
    try:
        status = resource_monitor_service.get_current_status()
        
        if status.get("status") == "no_data":
            raise HTTPException(status_code=404, detail="No metrics available for recommendations")
        
        return {
            "recommendations": status.get("scaling_recommendations", {}),
            "based_on_metrics": status.get("latest_metrics", {}),
            "timestamp": status.get("latest_metrics", {}).get("timestamp")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")

@router.put("/config")
async def update_scaling_config(
    config: ScalingConfigUpdate,
    admin_token: str = Depends(verify_admin_token)
):
    """Update auto-scaling configuration"""
    try:
        # Get current config
        current_config = scaling_manager.auto_scaler.config
        
        # Update only provided fields
        update_data = config.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(current_config, key):
                setattr(current_config, key, value)
        
        return {
            "success": True,
            "message": "Scaling configuration updated",
            "updated_fields": list(update_data.keys()),
            "current_config": {
                "queue_scale_up_threshold": current_config.queue_scale_up_threshold,
                "queue_scale_down_threshold": current_config.queue_scale_down_threshold,
                "api_scale_up_threshold": current_config.api_scale_up_threshold,
                "api_scale_down_threshold": current_config.api_scale_down_threshold,
                "cpu_scale_up_threshold": current_config.cpu_scale_up_threshold,
                "memory_scale_up_threshold": current_config.memory_scale_up_threshold
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")

@router.get("/alerts")
async def get_active_alerts():
    """Get currently active resource alerts"""
    try:
        monitor = resource_monitor_service.monitor
        active_alerts = []
        
        for alert_key, alert in monitor.active_alerts.items():
            active_alerts.append({
                "resource": alert.resource,
                "severity": alert.severity,
                "current_value": alert.current_value,
                "threshold": alert.threshold,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "duration_minutes": (alert.timestamp - alert.timestamp).total_seconds() / 60
            })
        
        return {
            "active_alerts": active_alerts,
            "alert_count": len(active_alerts),
            "timestamp": active_alerts[-1]["timestamp"] if active_alerts else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting alerts: {str(e)}")

@router.delete("/alerts")
async def clear_alerts(admin_token: str = Depends(verify_admin_token)):
    """Clear all active alerts"""
    try:
        monitor = resource_monitor_service.monitor
        cleared_count = len(monitor.active_alerts)
        monitor.active_alerts.clear()
        
        return {
            "success": True,
            "message": f"Cleared {cleared_count} active alerts",
            "cleared_count": cleared_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing alerts: {str(e)}")

@router.post("/test-scaling")
async def test_scaling_decision(admin_token: str = Depends(verify_admin_token)):
    """Test scaling decision logic with current metrics (dry run)"""
    try:
        # Collect current metrics
        metrics = await scaling_manager.auto_scaler.collect_metrics()
        
        # Test scaling decisions without executing them
        scaling_decisions = {}
        
        # Test worker scaling decisions
        for queue_name in ['collect', 'process', 'publish']:
            decision = scaling_manager.auto_scaler._should_scale_workers(queue_name, metrics)
            if decision:
                scaling_decisions[f"worker_{queue_name}"] = decision
        
        # Test API scaling decision
        api_decision = scaling_manager.auto_scaler._should_scale_api_instances(metrics)
        if api_decision:
            scaling_decisions["api_instances"] = api_decision
        
        # Get resource recommendations
        resource_recommendations = resource_monitor_service.monitor.get_scaling_recommendations(metrics)
        
        return {
            "current_metrics": {
                "queue_depths": metrics.queue_depth,
                "api_response_times": metrics.api_response_times,
                "cpu_usage": metrics.cpu_usage,
                "memory_usage": metrics.memory_usage,
                "active_workers": metrics.active_workers
            },
            "scaling_decisions": scaling_decisions,
            "resource_recommendations": resource_recommendations,
            "would_scale": len(scaling_decisions) > 0,
            "timestamp": metrics.timestamp.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing scaling: {str(e)}")