"""
Manual scaling alert system for Reddit Ghost Publisher
Implements queue backlog monitoring and manual scaling guidance
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.monitoring.notifications import SlackNotifier, AlertSeverity, AlertService
from app.monitoring.metrics import MetricsCollector


logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ScalingRecommendation:
    """Manual scaling recommendation"""
    queue_name: str
    current_pending: int
    recommended_workers: int
    current_workers: int
    reason: str
    priority: str  # "high", "medium", "low"


@dataclass
class ResourceUsage:
    """Resource usage metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: datetime


class ManualScalingAlertManager:
    """Manages manual scaling alerts and recommendations"""
    
    def __init__(self, db_session: Session, notifier: Optional[SlackNotifier] = None):
        self.db_session = db_session
        self.notifier = notifier or SlackNotifier()
        self.metrics_collector = MetricsCollector(db_session)
        self.settings = get_settings()
        
        # Alert state tracking
        self._last_alert_time = {}
        self._alert_cooldown_minutes = 15  # Prevent spam alerts
    
    def check_queue_scaling_alert(self) -> bool:
        """
        Check if queue backlog exceeds threshold and send manual scaling alert
        
        Returns:
            True if alert was triggered, False otherwise
        """
        try:
            queue_metrics = self.metrics_collector.get_queue_metrics()
            total_pending = queue_metrics.get("queue_total_pending", 0)
            threshold = self.settings.queue_alert_threshold
            
            # Check if alert is needed
            if total_pending <= threshold:
                return False
            
            # Check cooldown to prevent spam
            alert_key = "queue_scaling"
            if self._is_in_cooldown(alert_key):
                logger.debug(f"Queue scaling alert in cooldown, skipping")
                return False
            
            # Generate scaling recommendations
            recommendations = self._generate_scaling_recommendations(queue_metrics)
            
            # Build alert message with manual scaling guide
            message = self._build_scaling_alert_message(total_pending, threshold, recommendations)
            
            # Prepare metrics for alert
            alert_metrics = {
                "total_pending": total_pending,
                "threshold": threshold,
                "collect_queue": queue_metrics.get("queue_collect_pending", 0),
                "process_queue": queue_metrics.get("queue_process_pending", 0),
                "publish_queue": queue_metrics.get("queue_publish_pending", 0)
            }
            
            # Add recommendations to metrics
            for i, rec in enumerate(recommendations[:3]):  # Show top 3 recommendations
                alert_metrics[f"rec_{i+1}_queue"] = rec.queue_name
                alert_metrics[f"rec_{i+1}_workers"] = f"{rec.current_workers} → {rec.recommended_workers}"
            
            # Send alert
            success = self.notifier.send_alert(
                severity=AlertSeverity.MEDIUM,
                service=AlertService.QUEUE,
                message=message,
                metrics=alert_metrics,
                time_window="Current"
            )
            
            if success:
                self._update_alert_time(alert_key)
                logger.info(f"Manual scaling alert sent: {total_pending} pending tasks > {threshold} threshold")
            
            return success
            
        except Exception as e:
            logger.error(f"Error checking queue scaling alert: {e}")
            return False
    
    def check_resource_usage_alert(self) -> bool:
        """
        Check resource usage and send scaling recommendations
        
        Returns:
            True if alert was triggered, False otherwise
        """
        try:
            resource_usage = self._get_resource_usage()
            
            if not resource_usage:
                return False
            
            # Check if any resource is above threshold
            cpu_threshold = 80.0
            memory_threshold = 80.0
            disk_threshold = 85.0
            
            alerts_needed = []
            
            if resource_usage.cpu_percent > cpu_threshold:
                alerts_needed.append(("CPU", resource_usage.cpu_percent, cpu_threshold))
            
            if resource_usage.memory_percent > memory_threshold:
                alerts_needed.append(("Memory", resource_usage.memory_percent, memory_threshold))
            
            if resource_usage.disk_percent > disk_threshold:
                alerts_needed.append(("Disk", resource_usage.disk_percent, disk_threshold))
            
            if not alerts_needed:
                return False
            
            # Check cooldown
            alert_key = "resource_usage"
            if self._is_in_cooldown(alert_key):
                return False
            
            # Build resource alert message
            message = self._build_resource_alert_message(alerts_needed, resource_usage)
            
            # Prepare metrics
            alert_metrics = {
                "cpu_percent": f"{resource_usage.cpu_percent:.1f}%",
                "memory_percent": f"{resource_usage.memory_percent:.1f}%",
                "disk_percent": f"{resource_usage.disk_percent:.1f}%",
                "cpu_threshold": f"{cpu_threshold:.1f}%",
                "memory_threshold": f"{memory_threshold:.1f}%",
                "disk_threshold": f"{disk_threshold:.1f}%"
            }
            
            # Determine severity
            max_usage = max(alert[1] for alert in alerts_needed)
            severity = AlertSeverity.HIGH if max_usage > 90.0 else AlertSeverity.MEDIUM
            
            # Send alert
            success = self.notifier.send_alert(
                severity=severity,
                service=AlertService.SYSTEM,
                message=message,
                metrics=alert_metrics,
                time_window="Current"
            )
            
            if success:
                self._update_alert_time(alert_key)
                logger.info(f"Resource usage alert sent: {alerts_needed}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error checking resource usage alert: {e}")
            return False
    
    def get_scaling_recommendations(self) -> List[ScalingRecommendation]:
        """
        Get current scaling recommendations based on queue metrics
        
        Returns:
            List of scaling recommendations
        """
        try:
            queue_metrics = self.metrics_collector.get_queue_metrics()
            return self._generate_scaling_recommendations(queue_metrics)
        except Exception as e:
            logger.error(f"Error getting scaling recommendations: {e}")
            return []
    
    def get_manual_scaling_guide(self) -> Dict[str, Any]:
        """
        Get comprehensive manual scaling guide
        
        Returns:
            Dictionary with scaling guide information
        """
        try:
            queue_metrics = self.metrics_collector.get_queue_metrics()
            recommendations = self._generate_scaling_recommendations(queue_metrics)
            resource_usage = self._get_resource_usage()
            
            # Docker Compose scaling commands
            scaling_commands = {
                "collect": "docker-compose up -d --scale worker-collector=N",
                "process": "docker-compose up -d --scale worker-nlp=N", 
                "publish": "docker-compose up -d --scale worker-publisher=N"
            }
            
            # Current worker counts (estimated from queue metrics)
            current_workers = self._estimate_current_workers()
            
            guide = {
                "current_status": {
                    "queue_metrics": queue_metrics,
                    "resource_usage": resource_usage.__dict__ if resource_usage else None,
                    "estimated_workers": current_workers
                },
                "recommendations": [rec.__dict__ for rec in recommendations],
                "scaling_commands": scaling_commands,
                "scaling_steps": [
                    "1. Identify the bottleneck queue from metrics",
                    "2. Scale the corresponding worker type using Docker Compose",
                    "3. Monitor queue metrics for 5-10 minutes",
                    "4. Adjust further if needed",
                    "5. Scale down during low traffic periods"
                ],
                "monitoring_endpoints": {
                    "queue_status": "/api/v1/status/queues",
                    "worker_status": "/api/v1/status/workers",
                    "system_metrics": "/metrics"
                },
                "alert_thresholds": {
                    "queue_alert_threshold": self.settings.queue_alert_threshold,
                    "cpu_threshold": 80.0,
                    "memory_threshold": 80.0,
                    "disk_threshold": 85.0
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return guide
            
        except Exception as e:
            logger.error(f"Error getting manual scaling guide: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
    
    def _generate_scaling_recommendations(self, queue_metrics: Dict[str, int]) -> List[ScalingRecommendation]:
        """
        Generate scaling recommendations based on queue metrics
        
        Args:
            queue_metrics: Queue metrics dictionary
            
        Returns:
            List of scaling recommendations
        """
        recommendations = []
        
        # Queue thresholds for scaling recommendations
        queue_configs = [
            {
                "name": "collect",
                "pending_key": "queue_collect_pending",
                "light_threshold": 50,
                "medium_threshold": 150,
                "heavy_threshold": 300
            },
            {
                "name": "process", 
                "pending_key": "queue_process_pending",
                "light_threshold": 30,
                "medium_threshold": 100,
                "heavy_threshold": 200
            },
            {
                "name": "publish",
                "pending_key": "queue_publish_pending", 
                "light_threshold": 20,
                "medium_threshold": 80,
                "heavy_threshold": 150
            }
        ]
        
        for config in queue_configs:
            pending = queue_metrics.get(config["pending_key"], 0)
            current_workers = self._estimate_workers_for_queue(config["name"])
            
            if pending <= config["light_threshold"]:
                continue  # No scaling needed
            
            # Determine recommended worker count
            if pending > config["heavy_threshold"]:
                recommended_workers = min(current_workers + 3, 8)  # Cap at 8 workers
                priority = "high"
                reason = f"Heavy load: {pending} pending tasks (>{config['heavy_threshold']} threshold)"
            elif pending > config["medium_threshold"]:
                recommended_workers = min(current_workers + 2, 6)  # Cap at 6 workers
                priority = "medium"
                reason = f"Medium load: {pending} pending tasks (>{config['medium_threshold']} threshold)"
            else:
                recommended_workers = min(current_workers + 1, 4)  # Cap at 4 workers
                priority = "low"
                reason = f"Light load: {pending} pending tasks (>{config['light_threshold']} threshold)"
            
            if recommended_workers > current_workers:
                recommendations.append(ScalingRecommendation(
                    queue_name=config["name"],
                    current_pending=pending,
                    recommended_workers=recommended_workers,
                    current_workers=current_workers,
                    reason=reason,
                    priority=priority
                ))
        
        # Sort by priority (high -> medium -> low) and pending count
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: (priority_order[x.priority], -x.current_pending))
        
        return recommendations
    
    def _build_scaling_alert_message(
        self, 
        total_pending: int, 
        threshold: int, 
        recommendations: List[ScalingRecommendation]
    ) -> str:
        """
        Build scaling alert message with manual scaling guide
        
        Args:
            total_pending: Total pending tasks
            threshold: Alert threshold
            recommendations: Scaling recommendations
            
        Returns:
            Formatted alert message
        """
        message_parts = [
            f"Queue backlog ({total_pending}) exceeds threshold ({threshold}).",
            "Manual worker scaling is required.",
            "",
            "🔧 SCALING RECOMMENDATIONS:"
        ]
        
        if recommendations:
            for i, rec in enumerate(recommendations[:3], 1):  # Show top 3
                message_parts.append(
                    f"{i}. {rec.queue_name.upper()} queue: Scale from {rec.current_workers} to {rec.recommended_workers} workers"
                )
                message_parts.append(f"   Reason: {rec.reason}")
                message_parts.append(f"   Command: docker-compose up -d --scale worker-{rec.queue_name}={rec.recommended_workers}")
                message_parts.append("")
        else:
            message_parts.append("No specific recommendations available. Consider scaling all worker types.")
            message_parts.append("")
        
        message_parts.extend([
            "📊 MONITORING:",
            "• Check queue status: GET /api/v1/status/queues",
            "• Check worker status: GET /api/v1/status/workers",
            "• Monitor metrics: GET /metrics",
            "",
            "⚠️ Remember to scale down during low traffic periods to save resources."
        ])
        
        return "\n".join(message_parts)
    
    def _build_resource_alert_message(
        self, 
        alerts_needed: List[tuple], 
        resource_usage: ResourceUsage
    ) -> str:
        """
        Build resource usage alert message
        
        Args:
            alerts_needed: List of (resource_name, current_value, threshold) tuples
            resource_usage: Current resource usage
            
        Returns:
            Formatted alert message
        """
        message_parts = [
            "High resource usage detected. Consider scaling or optimization.",
            "",
            "📈 CURRENT USAGE:"
        ]
        
        for resource_name, current_value, threshold in alerts_needed:
            message_parts.append(f"• {resource_name}: {current_value:.1f}% (threshold: {threshold:.1f}%)")
        
        message_parts.extend([
            "",
            "🔧 RECOMMENDED ACTIONS:",
            "1. Scale worker containers if CPU/Memory high:",
            "   docker-compose up -d --scale worker-collector=2",
            "   docker-compose up -d --scale worker-nlp=2", 
            "   docker-compose up -d --scale worker-publisher=2",
            "",
            "2. Check for stuck tasks or infinite loops",
            "3. Review recent error logs for issues",
            "4. Consider optimizing processing logic",
            "",
            "📊 MONITORING:",
            "• System metrics: GET /metrics",
            "• Queue status: GET /api/v1/status/queues",
            "• Processing logs: Check app logs for errors"
        ])
        
        return "\n".join(message_parts)
    
    def _get_resource_usage(self) -> Optional[ResourceUsage]:
        """
        Get current resource usage metrics
        
        Returns:
            ResourceUsage object or None if unavailable
        """
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return ResourceUsage(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                timestamp=datetime.utcnow()
            )
            
        except ImportError:
            logger.warning("psutil not available, cannot get resource usage")
            return None
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return None
    
    def _estimate_current_workers(self) -> Dict[str, int]:
        """
        Estimate current worker counts (simplified for MVP)
        
        Returns:
            Dictionary with estimated worker counts
        """
        # For MVP, assume 1 worker per queue type as baseline
        # In production, this would query Docker or Celery for actual counts
        return {
            "collect": 1,
            "process": 1,
            "publish": 1
        }
    
    def _estimate_workers_for_queue(self, queue_name: str) -> int:
        """
        Estimate current workers for a specific queue
        
        Args:
            queue_name: Queue name
            
        Returns:
            Estimated worker count
        """
        workers = self._estimate_current_workers()
        return workers.get(queue_name, 1)
    
    def _is_in_cooldown(self, alert_key: str) -> bool:
        """
        Check if alert is in cooldown period
        
        Args:
            alert_key: Alert identifier
            
        Returns:
            True if in cooldown, False otherwise
        """
        last_alert = self._last_alert_time.get(alert_key)
        if not last_alert:
            return False
        
        cooldown_end = last_alert + timedelta(minutes=self._alert_cooldown_minutes)
        return datetime.utcnow() < cooldown_end
    
    def _update_alert_time(self, alert_key: str):
        """
        Update last alert time for cooldown tracking
        
        Args:
            alert_key: Alert identifier
        """
        self._last_alert_time[alert_key] = datetime.utcnow()


# Convenience functions for easy integration
def check_queue_scaling_alert(db_session: Session) -> bool:
    """Check and send queue scaling alert if needed"""
    alert_manager = ManualScalingAlertManager(db_session)
    return alert_manager.check_queue_scaling_alert()


def check_resource_usage_alert(db_session: Session) -> bool:
    """Check and send resource usage alert if needed"""
    alert_manager = ManualScalingAlertManager(db_session)
    return alert_manager.check_resource_usage_alert()


def get_scaling_recommendations(db_session: Session) -> List[ScalingRecommendation]:
    """Get current scaling recommendations"""
    alert_manager = ManualScalingAlertManager(db_session)
    return alert_manager.get_scaling_recommendations()


def get_manual_scaling_guide(db_session: Session) -> Dict[str, Any]:
    """Get comprehensive manual scaling guide"""
    alert_manager = ManualScalingAlertManager(db_session)
    return alert_manager.get_manual_scaling_guide()