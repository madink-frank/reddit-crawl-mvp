"""
Celery tasks for monitoring and alerting
Implements periodic checks and daily reporting
"""
import logging
from datetime import datetime

from celery import current_app as celery_app

from app.infrastructure import get_database_session
from app.monitoring.alert_service import (
    run_monitoring_checks, send_daily_system_report, get_system_status
)
from app.monitoring.budget_tracker import check_budget_alerts
from app.monitoring.notifications import send_failure_rate_alert, send_queue_backlog_alert
from app.monitoring.manual_scaling import check_queue_scaling_alert, check_resource_usage_alert


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="monitoring.run_health_checks")
def run_health_checks(self):
    """
    Run comprehensive health checks and send alerts if needed
    Scheduled to run every 5 minutes
    """
    try:
        logger.info("Starting health checks...")
        
        with get_database_session() as db_session:
            results = run_monitoring_checks(db_session)
            
            # Log results
            alerts_sent = len(results.get("alerts_sent", []))
            errors_count = len(results.get("errors", []))
            
            if alerts_sent > 0:
                logger.warning(f"Health checks completed: {alerts_sent} alerts sent")
            else:
                logger.info("Health checks completed: system healthy")
            
            if errors_count > 0:
                logger.error(f"Health checks completed with {errors_count} errors")
            
            return {
                "task": "run_health_checks",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "alerts_sent": alerts_sent,
                "errors_count": errors_count,
                "results": results
            }
    
    except Exception as e:
        logger.error(f"Error in health checks task: {e}")
        return {
            "task": "run_health_checks",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@celery_app.task(bind=True, name="monitoring.check_failure_rate")
def check_failure_rate(self):
    """
    Check failure rate and send alert if threshold exceeded
    Can be called independently or as part of health checks
    """
    try:
        logger.info("Checking failure rate...")
        
        with get_database_session() as db_session:
            alert_sent = send_failure_rate_alert(db_session)
            
            return {
                "task": "check_failure_rate",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "alert_sent": alert_sent
            }
    
    except Exception as e:
        logger.error(f"Error in failure rate check task: {e}")
        return {
            "task": "check_failure_rate",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@celery_app.task(bind=True, name="monitoring.check_queue_backlog")
def check_queue_backlog(self):
    """
    Check queue backlog and send alert if threshold exceeded
    Can be called independently or as part of health checks
    """
    try:
        logger.info("Checking queue backlog...")
        
        with get_database_session() as db_session:
            alert_sent = send_queue_backlog_alert(db_session)
            
            return {
                "task": "check_queue_backlog",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "alert_sent": alert_sent
            }
    
    except Exception as e:
        logger.error(f"Error in queue backlog check task: {e}")
        return {
            "task": "check_queue_backlog",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@celery_app.task(bind=True, name="monitoring.check_api_budgets")
def check_api_budgets(self):
    """
    Check API budget usage and send alerts if thresholds exceeded
    Can be called independently or as part of health checks
    """
    try:
        logger.info("Checking API budgets...")
        
        with get_database_session() as db_session:
            results = check_budget_alerts(db_session)
            
            alerts_sent = sum(1 for sent in results.values() if sent)
            
            return {
                "task": "check_api_budgets",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "alerts_sent": alerts_sent,
                "results": results
            }
    
    except Exception as e:
        logger.error(f"Error in API budget check task: {e}")
        return {
            "task": "check_api_budgets",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@celery_app.task(bind=True, name="monitoring.send_daily_report")
def send_daily_report(self):
    """
    Send comprehensive daily system report to Slack
    Scheduled to run once daily (typically early morning)
    """
    try:
        logger.info("Generating and sending daily report...")
        
        with get_database_session() as db_session:
            # Use the comprehensive daily report system
            from app.monitoring.daily_report import send_daily_report as send_comprehensive_report
            success = send_comprehensive_report(db_session)
            
            if success:
                logger.info("Comprehensive daily report sent successfully")
            else:
                logger.error("Failed to send comprehensive daily report")
            
            return {
                "task": "send_daily_report",
                "status": "completed" if success else "failed",
                "timestamp": datetime.utcnow().isoformat(),
                "report_sent": success,
                "report_type": "comprehensive"
            }
    
    except Exception as e:
        logger.error(f"Error in daily report task: {e}")
        return {
            "task": "send_daily_report",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@celery_app.task(bind=True, name="monitoring.check_manual_scaling")
def check_manual_scaling(self):
    """
    Check manual scaling requirements and send alerts if needed
    Includes queue backlog and resource usage monitoring
    """
    try:
        logger.info("Checking manual scaling requirements...")
        
        with get_database_session() as db_session:
            # Check queue scaling alert
            queue_alert_sent = check_queue_scaling_alert(db_session)
            
            # Check resource usage alert
            resource_alert_sent = check_resource_usage_alert(db_session)
            
            total_alerts = sum([queue_alert_sent, resource_alert_sent])
            
            if total_alerts > 0:
                logger.warning(f"Manual scaling checks completed: {total_alerts} alerts sent")
            else:
                logger.info("Manual scaling checks completed: no scaling needed")
            
            return {
                "task": "check_manual_scaling",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "queue_alert_sent": queue_alert_sent,
                "resource_alert_sent": resource_alert_sent,
                "total_alerts": total_alerts
            }
    
    except Exception as e:
        logger.error(f"Error in manual scaling check task: {e}")
        return {
            "task": "check_manual_scaling",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@celery_app.task(bind=True, name="monitoring.get_system_status")
def get_system_status_task(self):
    """
    Get current system status for monitoring dashboards
    Can be called on-demand for status checks
    """
    try:
        logger.info("Getting system status...")
        
        with get_database_session() as db_session:
            status = get_system_status(db_session)
            
            return {
                "task": "get_system_status",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "system_status": status
            }
    
    except Exception as e:
        logger.error(f"Error in system status task: {e}")
        return {
            "task": "get_system_status",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Task scheduling configuration for Celery Beat
MONITORING_SCHEDULE = {
    # Health checks every 5 minutes
    'run-health-checks': {
        'task': 'monitoring.run_health_checks',
        'schedule': 300.0,  # 5 minutes in seconds
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring.health'
        }
    },
    
    # Manual scaling checks every 10 minutes
    'check-manual-scaling': {
        'task': 'monitoring.check_manual_scaling',
        'schedule': 600.0,  # 10 minutes in seconds
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring.scaling'
        }
    },
    
    # Daily report at 6 AM UTC
    'send-daily-report': {
        'task': 'monitoring.send_daily_report',
        'schedule': {
            'hour': 6,
            'minute': 0
        },
        'options': {
            'queue': 'monitoring',
            'routing_key': 'monitoring.report'
        }
    }
}


# Individual task triggers for manual execution
def trigger_health_checks():
    """Trigger health checks manually"""
    return run_health_checks.delay()


def trigger_failure_rate_check():
    """Trigger failure rate check manually"""
    return check_failure_rate.delay()


def trigger_queue_backlog_check():
    """Trigger queue backlog check manually"""
    return check_queue_backlog.delay()


def trigger_budget_checks():
    """Trigger API budget checks manually"""
    return check_api_budgets.delay()


def trigger_daily_report():
    """Trigger daily report manually"""
    return send_daily_report.delay()


def trigger_manual_scaling_check():
    """Trigger manual scaling check manually"""
    return check_manual_scaling.delay()


def trigger_system_status():
    """Trigger system status check manually"""
    return get_system_status_task.delay()