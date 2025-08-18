"""
Unified Slack notification system for Reddit Ghost Publisher
Implements standardized alert templates and notification logic
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.monitoring.metrics import MetricsCollector


logger = logging.getLogger(__name__)
settings = get_settings()


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertService(Enum):
    """Service types for alerts"""
    COLLECTOR = "Reddit Collector"
    NLP_PIPELINE = "NLP Pipeline"
    PUBLISHER = "Ghost Publisher"
    SYSTEM = "System"
    API_BUDGET = "API Budget"
    QUEUE = "Queue Management"


class SlackNotifier:
    """Unified Slack notification system with standardized templates"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.slack_webhook_url
        self.settings = get_settings()
    
    def send_alert(
        self,
        severity: AlertSeverity,
        service: AlertService,
        message: str,
        metrics: Optional[Dict[str, Any]] = None,
        time_window: Optional[str] = None
    ) -> bool:
        """
        Send standardized alert to Slack
        
        Args:
            severity: Alert severity level
            service: Service that triggered the alert
            message: Alert message
            metrics: Optional metrics dictionary
            time_window: Optional time window description
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured, skipping notification")
            return False
        
        try:
            payload = self._build_alert_payload(
                severity, service, message, metrics, time_window
            )
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"Slack alert sent successfully: {severity.value} - {service.value}")
                return True
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
            return False
    
    def send_daily_report(
        self,
        collected_posts: int,
        published_posts: int,
        token_usage: int,
        cost_estimate: float,
        failure_count: int = 0,
        additional_metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send daily report to Slack
        
        Args:
            collected_posts: Number of posts collected
            published_posts: Number of posts published
            token_usage: Total token usage
            cost_estimate: Estimated cost in USD
            failure_count: Number of failures
            additional_metrics: Optional additional metrics
            
        Returns:
            True if report sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured, skipping daily report")
            return False
        
        try:
            payload = self._build_daily_report_payload(
                collected_posts, published_posts, token_usage, 
                cost_estimate, failure_count, additional_metrics
            )
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info("Daily report sent to Slack successfully")
                return True
            else:
                logger.error(f"Failed to send daily report: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False
    
    def _build_alert_payload(
        self,
        severity: AlertSeverity,
        service: AlertService,
        message: str,
        metrics: Optional[Dict[str, Any]] = None,
        time_window: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build standardized alert payload for Slack
        
        Args:
            severity: Alert severity level
            service: Service that triggered the alert
            message: Alert message
            metrics: Optional metrics dictionary
            time_window: Optional time window description
            
        Returns:
            Slack payload dictionary
        """
        # Determine color based on severity
        color_map = {
            AlertSeverity.LOW: "good",
            AlertSeverity.MEDIUM: "warning", 
            AlertSeverity.HIGH: "danger",
            AlertSeverity.CRITICAL: "#ff0000"
        }
        
        # Determine emoji based on severity
        emoji_map = {
            AlertSeverity.LOW: "ℹ️",
            AlertSeverity.MEDIUM: "⚠️",
            AlertSeverity.HIGH: "🚨",
            AlertSeverity.CRITICAL: "🔥"
        }
        
        # Build main attachment
        attachment = {
            "color": color_map.get(severity, "warning"),
            "fields": [
                {
                    "title": "Severity",
                    "value": severity.value,
                    "short": True
                },
                {
                    "title": "Service", 
                    "value": service.value,
                    "short": True
                },
                {
                    "title": "Message",
                    "value": message,
                    "short": False
                },
                {
                    "title": "Timestamp",
                    "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "short": True
                }
            ]
        }
        
        # Add time window if provided
        if time_window:
            attachment["fields"].append({
                "title": "Time Window",
                "value": time_window,
                "short": True
            })
        
        # Add metrics if provided
        if metrics:
            for key, value in metrics.items():
                # Format metric name for display
                display_name = key.replace("_", " ").title()
                attachment["fields"].append({
                    "title": display_name,
                    "value": str(value),
                    "short": True
                })
        
        # Build main payload
        payload = {
            "text": f"{emoji_map.get(severity, '🚨')} [{severity.value}] {service.value} Alert",
            "attachments": [attachment]
        }
        
        return payload
    
    def _build_daily_report_payload(
        self,
        collected_posts: int,
        published_posts: int,
        token_usage: int,
        cost_estimate: float,
        failure_count: int = 0,
        additional_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build daily report payload for Slack
        
        Args:
            collected_posts: Number of posts collected
            published_posts: Number of posts published
            token_usage: Total token usage
            cost_estimate: Estimated cost in USD
            failure_count: Number of failures
            additional_metrics: Optional additional metrics
            
        Returns:
            Slack payload dictionary
        """
        # Determine report color based on performance
        if failure_count == 0 and published_posts > 0:
            color = "good"
            status_emoji = "✅"
        elif failure_count > 0 and published_posts > failure_count:
            color = "warning"
            status_emoji = "⚠️"
        else:
            color = "danger"
            status_emoji = "❌"
        
        # Calculate success rate
        total_attempts = collected_posts
        success_rate = (published_posts / total_attempts * 100) if total_attempts > 0 else 0
        
        # Build attachment
        attachment = {
            "color": color,
            "fields": [
                {
                    "title": "Posts Collected",
                    "value": f"{collected_posts:,}",
                    "short": True
                },
                {
                    "title": "Posts Published",
                    "value": f"{published_posts:,}",
                    "short": True
                },
                {
                    "title": "Token Usage",
                    "value": f"{token_usage:,}",
                    "short": True
                },
                {
                    "title": "Estimated Cost",
                    "value": f"${cost_estimate:.2f}",
                    "short": True
                },
                {
                    "title": "Failures",
                    "value": f"{failure_count:,}",
                    "short": True
                },
                {
                    "title": "Success Rate",
                    "value": f"{success_rate:.1f}%",
                    "short": True
                },
                {
                    "title": "Report Date",
                    "value": datetime.utcnow().strftime("%Y-%m-%d"),
                    "short": False
                }
            ]
        }
        
        # Add additional metrics if provided
        if additional_metrics:
            for key, value in additional_metrics.items():
                display_name = key.replace("_", " ").title()
                attachment["fields"].append({
                    "title": display_name,
                    "value": str(value),
                    "short": True
                })
        
        # Build main payload
        payload = {
            "text": f"📊 {status_emoji} Daily Reddit Publisher Report",
            "attachments": [attachment]
        }
        
        return payload


class AlertManager:
    """Manages alert conditions and triggers notifications"""
    
    def __init__(self, db_session: Session, notifier: Optional[SlackNotifier] = None):
        self.db_session = db_session
        self.notifier = notifier or SlackNotifier()
        self.metrics_collector = MetricsCollector(db_session)
        self.settings = get_settings()
    
    def check_failure_rate_alert(self, time_window_minutes: int = 5) -> bool:
        """
        Check if failure rate exceeds threshold and send alert
        
        Args:
            time_window_minutes: Time window for failure rate calculation
            
        Returns:
            True if alert was triggered, False otherwise
        """
        try:
            failure_rate = self.metrics_collector.get_recent_failure_rate(time_window_minutes)
            threshold = self.settings.failure_rate_threshold
            
            if failure_rate > threshold:
                metrics = {
                    "failure_rate": f"{failure_rate:.2%}",
                    "threshold": f"{threshold:.2%}",
                    "time_window": f"{time_window_minutes} minutes"
                }
                
                message = (
                    f"Processing failure rate ({failure_rate:.2%}) exceeds threshold "
                    f"({threshold:.2%}) over the last {time_window_minutes} minutes"
                )
                
                return self.notifier.send_alert(
                    severity=AlertSeverity.HIGH,
                    service=AlertService.SYSTEM,
                    message=message,
                    metrics=metrics,
                    time_window=f"Last {time_window_minutes} minutes"
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking failure rate alert: {e}")
            return False
    
    def check_queue_backlog_alert(self) -> bool:
        """
        Check if queue backlog exceeds threshold and send alert
        
        Returns:
            True if alert was triggered, False otherwise
        """
        try:
            queue_metrics = self.metrics_collector.get_queue_metrics()
            total_pending = queue_metrics.get("queue_total_pending", 0)
            threshold = self.settings.queue_alert_threshold
            
            if total_pending > threshold:
                metrics = {
                    "total_pending": total_pending,
                    "threshold": threshold,
                    "collect_queue": queue_metrics.get("queue_collect_pending", 0),
                    "process_queue": queue_metrics.get("queue_process_pending", 0),
                    "publish_queue": queue_metrics.get("queue_publish_pending", 0)
                }
                
                message = (
                    f"Total queue backlog ({total_pending}) exceeds threshold ({threshold}). "
                    f"Manual worker scaling may be required."
                )
                
                return self.notifier.send_alert(
                    severity=AlertSeverity.MEDIUM,
                    service=AlertService.QUEUE,
                    message=message,
                    metrics=metrics,
                    time_window="Current"
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking queue backlog alert: {e}")
            return False
    
    def check_api_budget_alert(self, service_type: str, usage_percentage: float) -> bool:
        """
        Check API budget usage and send alert if threshold exceeded
        
        Args:
            service_type: Type of service (reddit, openai)
            usage_percentage: Current usage as percentage (0.0 to 1.0)
            
        Returns:
            True if alert was triggered, False otherwise
        """
        try:
            # Alert at 80% usage
            alert_threshold = 0.8
            
            if usage_percentage >= alert_threshold:
                severity = AlertSeverity.HIGH if usage_percentage >= 1.0 else AlertSeverity.MEDIUM
                service_map = {
                    "reddit": AlertService.COLLECTOR,
                    "openai": AlertService.NLP_PIPELINE
                }
                
                service = service_map.get(service_type, AlertService.API_BUDGET)
                
                metrics = {
                    "usage_percentage": f"{usage_percentage:.1%}",
                    "alert_threshold": f"{alert_threshold:.1%}",
                    "service_type": service_type.upper()
                }
                
                if usage_percentage >= 1.0:
                    message = f"{service_type.upper()} API budget exhausted (100%). Service will be throttled."
                else:
                    message = f"{service_type.upper()} API budget at {usage_percentage:.1%} of daily limit."
                
                return self.notifier.send_alert(
                    severity=severity,
                    service=service,
                    message=message,
                    metrics=metrics,
                    time_window="Daily"
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking API budget alert: {e}")
            return False
    
    def send_daily_report(self) -> bool:
        """
        Generate and send daily report
        
        Returns:
            True if report sent successfully, False otherwise
        """
        try:
            # Get metrics for the last 24 hours
            processing_metrics = self.metrics_collector.get_processing_metrics(24)
            token_metrics = self.metrics_collector.get_token_usage_metrics(24)
            error_metrics = self.metrics_collector.get_error_classification_metrics(24)
            
            # Extract key metrics
            collected_posts = processing_metrics.get("reddit_posts_collected_total", 0)
            published_posts = processing_metrics.get("posts_published_total", 0)
            token_usage = int(token_metrics.get("openai_tokens_used_total", 0))
            cost_estimate = token_metrics.get("openai_cost_usd_total", 0.0)
            failure_count = processing_metrics.get("processing_failures_total", 0)
            
            # Additional metrics
            additional_metrics = {
                "processed_posts": processing_metrics.get("posts_processed_total", 0),
                "api_errors_429": error_metrics.get("api_errors_429_total", 0),
                "api_errors_timeout": error_metrics.get("api_errors_timeout_total", 0),
                "api_errors_5xx": error_metrics.get("api_errors_5xx_total", 0)
            }
            
            return self.notifier.send_daily_report(
                collected_posts=collected_posts,
                published_posts=published_posts,
                token_usage=token_usage,
                cost_estimate=cost_estimate,
                failure_count=failure_count,
                additional_metrics=additional_metrics
            )
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False


# Convenience functions for easy integration
def send_failure_rate_alert(db_session: Session) -> bool:
    """Send failure rate alert if threshold exceeded"""
    alert_manager = AlertManager(db_session)
    return alert_manager.check_failure_rate_alert()


def send_queue_backlog_alert(db_session: Session) -> bool:
    """Send queue backlog alert if threshold exceeded"""
    alert_manager = AlertManager(db_session)
    return alert_manager.check_queue_backlog_alert()


def send_api_budget_alert(db_session: Session, service_type: str, usage_percentage: float) -> bool:
    """Send API budget alert if threshold exceeded"""
    alert_manager = AlertManager(db_session)
    return alert_manager.check_api_budget_alert(service_type, usage_percentage)


def send_daily_report(db_session: Session) -> bool:
    """Send daily report"""
    alert_manager = AlertManager(db_session)
    return alert_manager.send_daily_report()


def send_custom_alert(
    severity: AlertSeverity,
    service: AlertService,
    message: str,
    metrics: Optional[Dict[str, Any]] = None
) -> bool:
    """Send custom alert"""
    notifier = SlackNotifier()
    return notifier.send_alert(severity, service, message, metrics)