"""
Resource monitoring and alerting for auto-scaling decisions
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

import psutil
from prometheus_client import Gauge, Counter, Histogram

from app.config import get_settings
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Prometheus metrics for resource monitoring
resource_usage_gauge = Gauge('system_resource_usage_percent', 'System resource usage percentage', ['resource', 'instance'])
resource_alert_counter = Counter('resource_alerts_total', 'Total resource alerts triggered', ['resource', 'severity'])
resource_threshold_gauge = Gauge('resource_threshold_percent', 'Resource usage thresholds', ['resource', 'threshold_type'])

@dataclass
class ResourceThresholds:
    """Resource usage thresholds for alerting and scaling"""
    cpu_warning: float = 70.0
    cpu_critical: float = 85.0
    cpu_scale_up: float = 80.0
    
    memory_warning: float = 75.0
    memory_critical: float = 90.0
    memory_scale_up: float = 85.0
    
    disk_warning: float = 80.0
    disk_critical: float = 95.0
    disk_scale_up: float = 85.0
    
    network_warning_mbps: float = 800.0  # 800 Mbps
    network_critical_mbps: float = 950.0  # 950 Mbps
    
    # Load average thresholds (per CPU core)
    load_warning: float = 0.8
    load_critical: float = 1.2

@dataclass
class ResourceMetrics:
    """Current resource usage metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, float]  # bytes_sent, bytes_recv per second
    load_average: List[float]  # 1, 5, 15 minute averages
    process_count: int
    open_files: int
    timestamp: datetime

@dataclass
class ResourceAlert:
    """Resource usage alert"""
    resource: str
    severity: str  # 'warning', 'critical'
    current_value: float
    threshold: float
    message: str
    timestamp: datetime

class ResourceMonitor:
    """Monitor system resources and trigger alerts"""
    
    def __init__(self, thresholds: Optional[ResourceThresholds] = None):
        self.thresholds = thresholds or ResourceThresholds()
        self.settings = get_settings()
        self.redis_client = get_redis_client()
        
        # Alert callbacks
        self.alert_callbacks: List[Callable[[ResourceAlert], None]] = []
        
        # Metrics history
        self.metrics_history: List[ResourceMetrics] = []
        self.max_history_size: int = 720  # 6 hours at 30s intervals
        
        # Alert state tracking to prevent spam
        self.active_alerts: Dict[str, ResourceAlert] = {}
        self.alert_cooldown: timedelta = timedelta(minutes=5)
        
        # Network baseline for calculating rates
        self.last_network_stats = None
        self.last_network_time = None
        
        # Initialize threshold metrics
        self._update_threshold_metrics()
    
    def _update_threshold_metrics(self):
        """Update Prometheus threshold metrics"""
        resource_threshold_gauge.labels(resource='cpu', threshold_type='warning').set(self.thresholds.cpu_warning)
        resource_threshold_gauge.labels(resource='cpu', threshold_type='critical').set(self.thresholds.cpu_critical)
        resource_threshold_gauge.labels(resource='cpu', threshold_type='scale_up').set(self.thresholds.cpu_scale_up)
        
        resource_threshold_gauge.labels(resource='memory', threshold_type='warning').set(self.thresholds.memory_warning)
        resource_threshold_gauge.labels(resource='memory', threshold_type='critical').set(self.thresholds.memory_critical)
        resource_threshold_gauge.labels(resource='memory', threshold_type='scale_up').set(self.thresholds.memory_scale_up)
        
        resource_threshold_gauge.labels(resource='disk', threshold_type='warning').set(self.thresholds.disk_warning)
        resource_threshold_gauge.labels(resource='disk', threshold_type='critical').set(self.thresholds.disk_critical)
        resource_threshold_gauge.labels(resource='disk', threshold_type='scale_up').set(self.thresholds.disk_scale_up)
    
    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """Add a callback function to be called when alerts are triggered"""
        self.alert_callbacks.append(callback)
    
    def collect_metrics(self) -> ResourceMetrics:
        """Collect current resource usage metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage (root filesystem)
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network I/O rates
            network_io = self._calculate_network_rates()
            
            # Load average
            load_average = list(psutil.getloadavg())
            
            # Process and file descriptor counts
            process_count = len(psutil.pids())
            try:
                open_files = len(psutil.Process().open_files())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                open_files = 0
            
            metrics = ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_io=network_io,
                load_average=load_average,
                process_count=process_count,
                open_files=open_files,
                timestamp=datetime.utcnow()
            )
            
            # Update Prometheus metrics
            instance_id = self.settings.INSTANCE_ID or 'default'
            resource_usage_gauge.labels(resource='cpu', instance=instance_id).set(cpu_percent)
            resource_usage_gauge.labels(resource='memory', instance=instance_id).set(memory_percent)
            resource_usage_gauge.labels(resource='disk', instance=instance_id).set(disk_percent)
            resource_usage_gauge.labels(resource='network_sent', instance=instance_id).set(network_io.get('bytes_sent_per_sec', 0))
            resource_usage_gauge.labels(resource='network_recv', instance=instance_id).set(network_io.get('bytes_recv_per_sec', 0))
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")
            raise
    
    def _calculate_network_rates(self) -> Dict[str, float]:
        """Calculate network I/O rates in bytes per second"""
        try:
            current_stats = psutil.net_io_counters()
            current_time = time.time()
            
            if self.last_network_stats is None or self.last_network_time is None:
                self.last_network_stats = current_stats
                self.last_network_time = current_time
                return {'bytes_sent_per_sec': 0.0, 'bytes_recv_per_sec': 0.0}
            
            time_delta = current_time - self.last_network_time
            if time_delta <= 0:
                return {'bytes_sent_per_sec': 0.0, 'bytes_recv_per_sec': 0.0}
            
            bytes_sent_rate = (current_stats.bytes_sent - self.last_network_stats.bytes_sent) / time_delta
            bytes_recv_rate = (current_stats.bytes_recv - self.last_network_stats.bytes_recv) / time_delta
            
            self.last_network_stats = current_stats
            self.last_network_time = current_time
            
            return {
                'bytes_sent_per_sec': max(0, bytes_sent_rate),
                'bytes_recv_per_sec': max(0, bytes_recv_rate)
            }
            
        except Exception as e:
            logger.warning(f"Error calculating network rates: {e}")
            return {'bytes_sent_per_sec': 0.0, 'bytes_recv_per_sec': 0.0}
    
    def check_thresholds(self, metrics: ResourceMetrics) -> List[ResourceAlert]:
        """Check metrics against thresholds and generate alerts"""
        alerts = []
        
        # CPU alerts
        if metrics.cpu_percent >= self.thresholds.cpu_critical:
            alerts.append(ResourceAlert(
                resource='cpu',
                severity='critical',
                current_value=metrics.cpu_percent,
                threshold=self.thresholds.cpu_critical,
                message=f"Critical CPU usage: {metrics.cpu_percent:.1f}%",
                timestamp=metrics.timestamp
            ))
        elif metrics.cpu_percent >= self.thresholds.cpu_warning:
            alerts.append(ResourceAlert(
                resource='cpu',
                severity='warning',
                current_value=metrics.cpu_percent,
                threshold=self.thresholds.cpu_warning,
                message=f"High CPU usage: {metrics.cpu_percent:.1f}%",
                timestamp=metrics.timestamp
            ))
        
        # Memory alerts
        if metrics.memory_percent >= self.thresholds.memory_critical:
            alerts.append(ResourceAlert(
                resource='memory',
                severity='critical',
                current_value=metrics.memory_percent,
                threshold=self.thresholds.memory_critical,
                message=f"Critical memory usage: {metrics.memory_percent:.1f}%",
                timestamp=metrics.timestamp
            ))
        elif metrics.memory_percent >= self.thresholds.memory_warning:
            alerts.append(ResourceAlert(
                resource='memory',
                severity='warning',
                current_value=metrics.memory_percent,
                threshold=self.thresholds.memory_warning,
                message=f"High memory usage: {metrics.memory_percent:.1f}%",
                timestamp=metrics.timestamp
            ))
        
        # Disk alerts
        if metrics.disk_percent >= self.thresholds.disk_critical:
            alerts.append(ResourceAlert(
                resource='disk',
                severity='critical',
                current_value=metrics.disk_percent,
                threshold=self.thresholds.disk_critical,
                message=f"Critical disk usage: {metrics.disk_percent:.1f}%",
                timestamp=metrics.timestamp
            ))
        elif metrics.disk_percent >= self.thresholds.disk_warning:
            alerts.append(ResourceAlert(
                resource='disk',
                severity='warning',
                current_value=metrics.disk_percent,
                threshold=self.thresholds.disk_warning,
                message=f"High disk usage: {metrics.disk_percent:.1f}%",
                timestamp=metrics.timestamp
            ))
        
        # Load average alerts (normalized by CPU count)
        cpu_count = psutil.cpu_count()
        if cpu_count and len(metrics.load_average) > 0:
            load_1min = metrics.load_average[0] / cpu_count
            
            if load_1min >= self.thresholds.load_critical:
                alerts.append(ResourceAlert(
                    resource='load',
                    severity='critical',
                    current_value=load_1min,
                    threshold=self.thresholds.load_critical,
                    message=f"Critical system load: {load_1min:.2f} (normalized)",
                    timestamp=metrics.timestamp
                ))
            elif load_1min >= self.thresholds.load_warning:
                alerts.append(ResourceAlert(
                    resource='load',
                    severity='warning',
                    current_value=load_1min,
                    threshold=self.thresholds.load_warning,
                    message=f"High system load: {load_1min:.2f} (normalized)",
                    timestamp=metrics.timestamp
                ))
        
        # Network alerts (convert to Mbps)
        network_sent_mbps = (metrics.network_io.get('bytes_sent_per_sec', 0) * 8) / (1024 * 1024)
        network_recv_mbps = (metrics.network_io.get('bytes_recv_per_sec', 0) * 8) / (1024 * 1024)
        
        if network_sent_mbps >= self.thresholds.network_critical_mbps:
            alerts.append(ResourceAlert(
                resource='network_sent',
                severity='critical',
                current_value=network_sent_mbps,
                threshold=self.thresholds.network_critical_mbps,
                message=f"Critical network send rate: {network_sent_mbps:.1f} Mbps",
                timestamp=metrics.timestamp
            ))
        elif network_sent_mbps >= self.thresholds.network_warning_mbps:
            alerts.append(ResourceAlert(
                resource='network_sent',
                severity='warning',
                current_value=network_sent_mbps,
                threshold=self.thresholds.network_warning_mbps,
                message=f"High network send rate: {network_sent_mbps:.1f} Mbps",
                timestamp=metrics.timestamp
            ))
        
        return alerts
    
    def process_alerts(self, alerts: List[ResourceAlert]):
        """Process alerts, applying cooldown and triggering callbacks"""
        for alert in alerts:
            alert_key = f"{alert.resource}_{alert.severity}"
            
            # Check if we're in cooldown for this alert
            if alert_key in self.active_alerts:
                last_alert = self.active_alerts[alert_key]
                if alert.timestamp - last_alert.timestamp < self.alert_cooldown:
                    continue  # Skip this alert due to cooldown
            
            # Update active alerts
            self.active_alerts[alert_key] = alert
            
            # Update Prometheus counter
            resource_alert_counter.labels(resource=alert.resource, severity=alert.severity).inc()
            
            # Log the alert
            log_func = logger.critical if alert.severity == 'critical' else logger.warning
            log_func(f"Resource alert: {alert.message}")
            
            # Trigger callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
    
    def get_scaling_recommendations(self, metrics: ResourceMetrics) -> Dict[str, str]:
        """Get scaling recommendations based on current metrics"""
        recommendations = {}
        
        # CPU-based recommendations
        if metrics.cpu_percent >= self.thresholds.cpu_scale_up:
            recommendations['cpu'] = 'scale_up'
        elif metrics.cpu_percent < 30:  # Scale down threshold
            recommendations['cpu'] = 'scale_down'
        
        # Memory-based recommendations
        if metrics.memory_percent >= self.thresholds.memory_scale_up:
            recommendations['memory'] = 'scale_up'
        elif metrics.memory_percent < 40:  # Scale down threshold
            recommendations['memory'] = 'scale_down'
        
        # Load-based recommendations
        cpu_count = psutil.cpu_count()
        if cpu_count and len(metrics.load_average) > 0:
            load_1min = metrics.load_average[0] / cpu_count
            if load_1min >= 0.9:
                recommendations['load'] = 'scale_up'
            elif load_1min < 0.3:
                recommendations['load'] = 'scale_down'
        
        return recommendations
    
    async def store_metrics_history(self, metrics: ResourceMetrics):
        """Store metrics in Redis for historical analysis"""
        try:
            # Add to in-memory history
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history.pop(0)
            
            # Store in Redis with TTL
            key = f"resource_metrics:{int(metrics.timestamp.timestamp())}"
            data = {
                'cpu_percent': metrics.cpu_percent,
                'memory_percent': metrics.memory_percent,
                'disk_percent': metrics.disk_percent,
                'network_sent': metrics.network_io.get('bytes_sent_per_sec', 0),
                'network_recv': metrics.network_io.get('bytes_recv_per_sec', 0),
                'load_1min': metrics.load_average[0] if metrics.load_average else 0,
                'process_count': metrics.process_count,
                'timestamp': metrics.timestamp.isoformat()
            }
            
            await self.redis_client.hset(key, mapping=data)
            await self.redis_client.expire(key, 86400)  # 24 hour TTL
            
        except Exception as e:
            logger.error(f"Error storing metrics history: {e}")
    
    def get_metrics_summary(self, duration_minutes: int = 60) -> Dict:
        """Get summary statistics for metrics over the specified duration"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=duration_minutes)
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {}
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        disk_values = [m.disk_percent for m in recent_metrics]
        
        return {
            'duration_minutes': duration_minutes,
            'sample_count': len(recent_metrics),
            'cpu': {
                'current': recent_metrics[-1].cpu_percent,
                'average': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values)
            },
            'memory': {
                'current': recent_metrics[-1].memory_percent,
                'average': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values)
            },
            'disk': {
                'current': recent_metrics[-1].disk_percent,
                'average': sum(disk_values) / len(disk_values),
                'max': max(disk_values),
                'min': min(disk_values)
            },
            'load_average': recent_metrics[-1].load_average,
            'network_io': recent_metrics[-1].network_io
        }

class ResourceMonitorService:
    """Service for running resource monitoring in the background"""
    
    def __init__(self, monitor: Optional[ResourceMonitor] = None):
        self.monitor = monitor or ResourceMonitor()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.monitoring_interval = 30  # seconds
    
    async def start(self):
        """Start the resource monitoring service"""
        if self._running:
            logger.warning("Resource monitor is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Resource monitoring service started")
    
    async def stop(self):
        """Stop the resource monitoring service"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Resource monitoring service stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                # Collect metrics
                metrics = self.monitor.collect_metrics()
                
                # Store metrics history
                await self.monitor.store_metrics_history(metrics)
                
                # Check thresholds and process alerts
                alerts = self.monitor.check_thresholds(metrics)
                if alerts:
                    self.monitor.process_alerts(alerts)
                
                # Wait for next iteration
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                await asyncio.sleep(10)  # Wait 10 seconds before retrying
    
    def get_current_status(self) -> Dict:
        """Get current monitoring status"""
        if not self.monitor.metrics_history:
            return {"status": "no_data"}
        
        latest_metrics = self.monitor.metrics_history[-1]
        summary = self.monitor.get_metrics_summary(60)
        recommendations = self.monitor.get_scaling_recommendations(latest_metrics)
        
        return {
            "status": "running" if self._running else "stopped",
            "latest_metrics": {
                "cpu_percent": latest_metrics.cpu_percent,
                "memory_percent": latest_metrics.memory_percent,
                "disk_percent": latest_metrics.disk_percent,
                "load_average": latest_metrics.load_average,
                "network_io": latest_metrics.network_io,
                "timestamp": latest_metrics.timestamp.isoformat()
            },
            "summary_1h": summary,
            "scaling_recommendations": recommendations,
            "active_alerts": len(self.monitor.active_alerts),
            "monitoring_interval": self.monitoring_interval
        }

# Global resource monitor service
resource_monitor_service = ResourceMonitorService()