"""
Monitoring and alerting API endpoints
Provides alert management, budget tracking, and notification controls
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.monitoring.alert_service import (
    run_monitoring_checks, get_system_status, send_daily_system_report
)
from app.monitoring.budget_tracker import get_budget_summary
from app.monitoring.notifications import (
    SlackNotifier, AlertSeverity, AlertService, send_custom_alert
)
from app.monitoring.tasks import (
    trigger_health_checks, trigger_daily_report, trigger_budget_checks,
    trigger_failure_rate_check, trigger_queue_backlog_check
)


logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class AlertRequest(BaseModel):
    """Request model for sending custom alerts"""
    severity: str
    service: str
    message: str
    metrics: Optional[Dict[str, Any]] = None


class BudgetSummaryResponse(BaseModel):
    """Response model for budget summary"""
    date: str
    reddit: Dict[str, Any]
    openai: Dict[str, Any]
    total_cost_usd: float
    any_budget_exhausted: bool


class SystemStatusResponse(BaseModel):
    """Response model for system status"""
    timestamp: str
    overall_status: str
    status_color: str
    health_issues: list
    metrics: Dict[str, Any]


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


@router.get("/monitoring/status", response_model=SystemStatusResponse)
async def get_monitoring_status(db_session: Session = Depends(get_database_session)):
    """
    Get comprehensive system status with health indicators
    
    Returns:
        - Overall system health status
        - Current metrics and performance indicators
        - Active health issues and alerts
        - Budget usage and queue status
    """
    try:
        status = get_system_status(db_session)
        return SystemStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Failed to get monitoring status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system status: {str(e)}"
        )


@router.get("/monitoring/budget", response_model=BudgetSummaryResponse)
async def get_budget_status(
    date: Optional[str] = None,
    db_session: Session = Depends(get_database_session)
):
    """
    Get API budget usage summary
    
    Args:
        date: Optional date in YYYY-MM-DD format (defaults to today)
        
    Returns:
        - Reddit API call usage and limits
        - OpenAI token usage, costs, and limits
        - Budget exhaustion status
    """
    try:
        # Parse date if provided
        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        
        from app.monitoring.budget_tracker import get_budget_summary
        summary = get_budget_summary(db_session, target_date)
        
        return BudgetSummaryResponse(**summary)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get budget status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get budget status: {str(e)}"
        )


@router.post("/monitoring/alerts/check")
async def run_alert_checks(
    background_tasks: BackgroundTasks,
    db_session: Session = Depends(get_database_session)
):
    """
    Manually trigger all monitoring checks and send alerts if needed
    
    Runs in background to avoid blocking the API response
    
    Returns:
        - Immediate acknowledgment
        - Task ID for tracking (if available)
    """
    try:
        # Trigger health checks in background
        task = trigger_health_checks()
        
        return {
            "status": "triggered",
            "message": "Health checks started in background",
            "task_id": task.id if hasattr(task, 'id') else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger alert checks: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger alert checks: {str(e)}"
        )


@router.post("/monitoring/alerts/failure-rate")
async def check_failure_rate_alert(db_session: Session = Depends(get_database_session)):
    """
    Manually check failure rate and send alert if threshold exceeded
    
    Returns:
        - Alert status (sent/not sent)
        - Current failure rate
        - Threshold configuration
    """
    try:
        task = trigger_failure_rate_check()
        
        # Also get current failure rate for immediate response
        from app.monitoring.metrics import MetricsCollector
        collector = MetricsCollector(db_session)
        current_rate = collector.get_recent_failure_rate(5)
        
        return {
            "status": "triggered",
            "task_id": task.id if hasattr(task, 'id') else None,
            "current_failure_rate": f"{current_rate:.2%}",
            "threshold": f"{settings.failure_rate_threshold:.2%}",
            "alert_needed": current_rate > settings.failure_rate_threshold,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to check failure rate: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check failure rate: {str(e)}"
        )


@router.post("/monitoring/alerts/queue-backlog")
async def check_queue_backlog_alert(db_session: Session = Depends(get_database_session)):
    """
    Manually check queue backlog and send alert if threshold exceeded
    
    Returns:
        - Alert status (sent/not sent)
        - Current queue lengths
        - Threshold configuration
    """
    try:
        task = trigger_queue_backlog_check()
        
        # Also get current queue status for immediate response
        from app.monitoring.metrics import MetricsCollector
        collector = MetricsCollector(db_session)
        queue_metrics = collector.get_queue_metrics()
        
        total_pending = queue_metrics.get("queue_total_pending", 0)
        
        return {
            "status": "triggered",
            "task_id": task.id if hasattr(task, 'id') else None,
            "current_queue_backlog": total_pending,
            "threshold": settings.queue_alert_threshold,
            "alert_needed": total_pending > settings.queue_alert_threshold,
            "queue_details": queue_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to check queue backlog: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check queue backlog: {str(e)}"
        )


@router.post("/monitoring/alerts/budget")
async def check_budget_alerts(db_session: Session = Depends(get_database_session)):
    """
    Manually check API budget usage and send alerts if thresholds exceeded
    
    Returns:
        - Alert status for each service
        - Current usage percentages
        - Budget limits and remaining quotas
    """
    try:
        task = trigger_budget_checks()
        
        # Also get current budget status for immediate response
        from app.monitoring.budget_tracker import get_budget_summary
        budget_summary = get_budget_summary(db_session)
        
        return {
            "status": "triggered",
            "task_id": task.id if hasattr(task, 'id') else None,
            "budget_summary": budget_summary,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to check budget alerts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check budget alerts: {str(e)}"
        )


@router.get("/monitoring/reports/daily")
async def get_daily_report(
    date: Optional[str] = None,
    db_session: Session = Depends(get_database_session)
):
    """
    Get daily report data (without sending to Slack)
    
    Args:
        date: Optional date in YYYY-MM-DD format (defaults to yesterday)
        
    Returns:
        - Comprehensive daily report with all metrics
        - Cost analysis and performance data
        - Error summaries and success rates
    """
    try:
        # Parse date if provided
        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        
        from app.monitoring.daily_report import generate_daily_report
        report = generate_daily_report(db_session, target_date)
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get daily report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get daily report: {str(e)}"
        )


@router.post("/monitoring/reports/daily")
async def send_daily_report_manual(db_session: Session = Depends(get_database_session)):
    """
    Manually trigger daily report generation and sending to Slack
    
    Returns:
        - Report generation status
        - Task ID for tracking
        - Summary of metrics included
    """
    try:
        task = trigger_daily_report()
        
        return {
            "status": "triggered",
            "message": "Comprehensive daily report generation started",
            "task_id": task.id if hasattr(task, 'id') else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger daily report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger daily report: {str(e)}"
        )


@router.post("/monitoring/alerts/custom")
async def send_custom_alert_endpoint(alert_request: AlertRequest):
    """
    Send custom alert to Slack
    
    Args:
        alert_request: Custom alert details including severity, service, message
        
    Returns:
        - Alert sending status
        - Alert details sent
    """
    try:
        # Validate severity
        try:
            severity = AlertSeverity(alert_request.severity.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity. Must be one of: {[s.value for s in AlertSeverity]}"
            )
        
        # Validate service
        try:
            service = AlertService(alert_request.service)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid service. Must be one of: {[s.value for s in AlertService]}"
            )
        
        # Send alert
        success = send_custom_alert(
            severity=severity,
            service=service,
            message=alert_request.message,
            metrics=alert_request.metrics
        )
        
        return {
            "status": "sent" if success else "failed",
            "alert_details": {
                "severity": severity.value,
                "service": service.value,
                "message": alert_request.message,
                "metrics": alert_request.metrics
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send custom alert: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send custom alert: {str(e)}"
        )


@router.get("/monitoring/config")
async def get_monitoring_config():
    """
    Get current monitoring configuration and thresholds
    
    Returns:
        - Alert thresholds
        - Notification settings
        - Budget limits
        - Monitoring intervals
    """
    try:
        return {
            "alert_thresholds": {
                "failure_rate_threshold": settings.failure_rate_threshold,
                "queue_alert_threshold": settings.queue_alert_threshold,
                "api_budget_alert_threshold": 0.8  # 80%
            },
            "budget_limits": {
                "reddit_daily_calls_limit": settings.reddit_daily_calls_limit,
                "openai_daily_tokens_limit": settings.openai_daily_tokens_limit
            },
            "notification_settings": {
                "slack_webhook_configured": bool(settings.slack_webhook_url),
                "slack_webhook_url_masked": "***" + settings.slack_webhook_url[-10:] if settings.slack_webhook_url else None
            },
            "monitoring_intervals": {
                "health_check_interval": "5 minutes",
                "daily_report_time": "06:00 UTC"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get monitoring config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get monitoring config: {str(e)}"
        )


@router.get("/monitoring/health")
async def get_monitoring_health():
    """
    Health check for monitoring system itself
    
    Returns:
        - Monitoring service status
        - Slack connectivity
        - Database connectivity for metrics
    """
    try:
        health_status = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check Slack connectivity
        try:
            if settings.slack_webhook_url:
                notifier = SlackNotifier()
                # We don't actually send a test message, just validate configuration
                health_status["components"]["slack"] = "configured"
            else:
                health_status["components"]["slack"] = "not_configured"
        except Exception as e:
            health_status["components"]["slack"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check database connectivity
        try:
            from app.infrastructure import get_database_session
            db_session = get_database_session()
            db_session.execute("SELECT 1")
            db_session.close()
            health_status["components"]["database"] = "available"
        except Exception as e:
            health_status["components"]["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check Redis connectivity
        try:
            from app.infrastructure import get_redis_client
            redis_client = get_redis_client()
            redis_client.ping()
            health_status["components"]["redis"] = "available"
        except Exception as e:
            health_status["components"]["redis"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Monitoring health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }