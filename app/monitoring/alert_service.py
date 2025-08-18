"""
Alert service for monitoring system health and triggering notifications
Integrates failure rate, queue backlog, and budget monitoring
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.monitoring.notifications import (
    AlertManager, send_failure_rate_alert, send_queue_backlog_alert, send_daily_report
)
from app.monitoring.budget_tracker import BudgetTracker
from app.monitoring.metrics import MetricsCollector


logger = logging.getLogger(__name__)
settings = get_settings()


class AlertService:
    """Centralized alert service for system monitoring"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.settings = get_settings()
        self.alert_manager = AlertManager(db_session)
        self.budget_tracker = BudgetTracker(db_session)
        self.metrics_collector = MetricsCollector(db_session)
    
    def run_all_checks(self) -> Dict[str, Any]:
        """
        Run all monitoring checks and send alerts as needed
        
        Returns:
            Dictionary with results of all checks
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "checks_performed": [],
            "alerts_sent": [],
            "errors": []
        }
        
        try:
            # Check failure rate (5% threshold over 5 minutes)
            logger.info("Checking failure rate alert...")
            results["checks_performed"].append("failure_rate")
            
            try:
                if self.alert_manager.check_failure_rate_alert(time_window_minutes=5):
                    results["alerts_sent"].append("failure_rate_alert")
                    logger.info("Failure rate alert sent")
            except Exception as e:
                error_msg = f"Error checking failure rate: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            # Check queue backlog (500 threshold)
            logger.info("Checking queue backlog alert...")
            results["checks_performed"].append("queue_backlog")
            
            try:
                if self.alert_manager.check_queue_backlog_alert():
                    results["alerts_sent"].append("queue_backlog_alert")
                    logger.info("Queue backlog alert sent")
            except Exception as e:
                error_msg = f"Error checking queue backlog: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            # Check API budget alerts (80% threshold)
            logger.info("Checking API budget alerts...")
            results["checks_performed"].append("api_budgets")
            
            try:
                budget_alerts = self.budget_tracker.check_all_budget_alerts()
                if budget_alerts["reddit_alert_sent"]:
                    results["alerts_sent"].append("reddit_budget_alert")
                    logger.info("Reddit budget alert sent")
                if budget_alerts["openai_alert_sent"]:
                    results["alerts_sent"].append("openai_budget_alert")
                    logger.info("OpenAI budget alert sent")
            except Exception as e:
                error_msg = f"Error checking API budgets: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
            
            # Log summary
            total_alerts = len(results["alerts_sent"])
            total_errors = len(results["errors"])
            
            if total_alerts > 0:
                logger.warning(f"Alert check completed: {total_alerts} alerts sent")
            else:
                logger.info("Alert check completed: no alerts triggered")
            
            if total_errors > 0:
                logger.error(f"Alert check completed with {total_errors} errors")
            
            return results
            
        except Exception as e:
            error_msg = f"Critical error in alert service: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            return results
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status for monitoring
        
        Returns:
            Dictionary with system status information
        """
        try:
            # Get current metrics
            processing_metrics = self.metrics_collector.get_processing_metrics(time_window_hours=1)
            queue_metrics = self.metrics_collector.get_queue_metrics()
            failure_rate = self.metrics_collector.get_recent_failure_rate(time_window_minutes=5)
            budget_summary = self.budget_tracker.get_budget_summary()
            
            # Determine overall system health
            health_issues = []
            
            # Check failure rate
            if failure_rate > self.settings.failure_rate_threshold:
                health_issues.append(f"High failure rate: {failure_rate:.2%}")
            
            # Check queue backlog
            total_pending = queue_metrics.get("queue_total_pending", 0)
            if total_pending > self.settings.queue_alert_threshold:
                health_issues.append(f"Queue backlog: {total_pending} tasks")
            
            # Check budget exhaustion
            if budget_summary.get("any_budget_exhausted", False):
                health_issues.append("API budget exhausted")
            
            # Determine overall status
            if not health_issues:
                overall_status = "healthy"
                status_color = "green"
            elif len(health_issues) == 1 and "budget" not in health_issues[0].lower():
                overall_status = "warning"
                status_color = "yellow"
            else:
                overall_status = "critical"
                status_color = "red"
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": overall_status,
                "status_color": status_color,
                "health_issues": health_issues,
                "metrics": {
                    "processing": {
                        "collected_last_hour": processing_metrics.get("reddit_posts_collected_total", 0),
                        "processed_last_hour": processing_metrics.get("posts_processed_total", 0),
                        "published_last_hour": processing_metrics.get("posts_published_total", 0),
                        "failures_last_hour": processing_metrics.get("processing_failures_total", 0)
                    },
                    "queues": queue_metrics,
                    "failure_rate_5m": failure_rate,
                    "budgets": budget_summary
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": "unknown",
                "status_color": "gray",
                "health_issues": [f"Error getting status: {e}"],
                "metrics": {}
            }
    
    def send_daily_report(self) -> bool:
        """
        Send comprehensive daily report with system metrics
        
        Returns:
            True if report sent successfully, False otherwise
        """
        try:
            logger.info("Sending comprehensive daily report...")
            
            # Use the comprehensive daily report system
            from app.monitoring.daily_report import send_daily_report as send_comprehensive_report
            success = send_comprehensive_report(self.db_session)
            
            if success:
                logger.info("Comprehensive daily report sent successfully")
            else:
                logger.error("Failed to send comprehensive daily report")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False


# Convenience functions for Celery tasks and API endpoints
def run_monitoring_checks(db_session: Session) -> Dict[str, Any]:
    """Run all monitoring checks"""
    alert_service = AlertService(db_session)
    return alert_service.run_all_checks()


def get_system_status(db_session: Session) -> Dict[str, Any]:
    """Get system status"""
    alert_service = AlertService(db_session)
    return alert_service.get_system_status()


def send_daily_system_report(db_session: Session) -> bool:
    """Send comprehensive daily system report"""
    from app.monitoring.daily_report import send_daily_report
    return send_daily_report(db_session)


# Individual check functions for targeted monitoring
def check_failure_rate_only(db_session: Session) -> bool:
    """Check only failure rate alert"""
    return send_failure_rate_alert(db_session)


def check_queue_backlog_only(db_session: Session) -> bool:
    """Check only queue backlog alert"""
    return send_queue_backlog_alert(db_session)


def check_budget_alerts_only(db_session: Session) -> Dict[str, bool]:
    """Check only budget alerts"""
    tracker = BudgetTracker(db_session)
    return tracker.check_all_budget_alerts()