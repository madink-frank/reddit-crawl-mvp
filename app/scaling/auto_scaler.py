"""
Auto-scaling logic for Reddit Ghost Publisher
Handles queue depth-based worker scaling and API response time-based instance scaling
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta

import psutil
import redis
from celery import Celery
from prometheus_client import Gauge, Counter, Histogram

from app.config import get_settings
from app.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Prometheus metrics for scaling
scaling_decisions = Counter('scaling_decisions_total', 'Total scaling decisions made', ['action', 'service'])
worker_count = Gauge('celery_workers_count', 'Current number of Celery workers', ['queue'])
api_response_time = Histogram('api_response_time_seconds', 'API response time', ['endpoint'])
resource_usage = Gauge('system_resource_usage_percent', 'System resource usage', ['resource'])
scaling_cooldown = Gauge('scaling_cooldown_seconds', 'Time remaining in scaling cooldown')

@dataclass
class ScalingMetrics:
    """Metrics used for scaling decisions"""
    queue_depth: Dict[str, int]
    api_response_times: Dict[str, float]
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_workers: Dict[str, int]
    timestamp: datetime

@dataclass
class ScalingConfig:
    """Configuration for auto-scaling behavior"""
    # Queue depth thresholds
    queue_scale_up_threshold: int = 1000
    queue_scale_down_threshold: int = 100
    
    # API response time thresholds (milliseconds)
    api_scale_up_threshold: float = 400.0
    api_scale_down_threshold: float = 200.0
    
    # Resource usage thresholds (percentage)
    cpu_scale_up_threshold: float = 80.0
    memory_scale_up_threshold: float = 85.0
    disk_alert_threshold: float = 80.0
    
    # Worker scaling limits
    min_workers_per_queue: int = 1
    max_workers_per_queue: int = 8
    
    # Instance scaling limits
    min_api_instances: int = 2
    max_api_instances: int = 6
    
    # Cooldown periods (seconds)
    worker_scale_cooldown: int = 300  # 5 minutes
    instance_scale_cooldown: int = 600  # 10 minutes
    
    # Monitoring intervals
    metrics_collection_interval: int = 30  # 30 seconds
    scaling_decision_interval: int = 60   # 1 minute

class AutoScaler:
    """Main auto-scaling controller"""
    
    def __init__(self, config: Optional[ScalingConfig] = None):
        self.config = config or ScalingConfig()
        self.settings = get_settings()
        self.redis_client = get_redis_client()
        self.celery_app = Celery('reddit_publisher')
        
        # Scaling state tracking
        self.last_worker_scale: Dict[str, datetime] = {}
        self.last_instance_scale: datetime = datetime.min
        self.current_worker_counts: Dict[str, int] = {
            'collect': 2,
            'process': 2, 
            'publish': 1
        }
        self.current_api_instances: int = 2
        
        # Metrics history for trend analysis
        self.metrics_history: List[ScalingMetrics] = []
        self.max_history_size: int = 60  # Keep 60 data points (30 minutes at 30s intervals)
        
    async def collect_metrics(self) -> ScalingMetrics:
        """Collect current system and application metrics"""
        try:
            # Get queue depths from Redis
            queue_depths = {}
            for queue_name in ['collect', 'process', 'publish']:
                queue_key = f"celery:queue:{queue_name}"
                depth = await self.redis_client.llen(queue_key)
                queue_depths[queue_name] = depth
                
            # Get API response times from Prometheus metrics
            api_response_times = await self._get_api_response_times()
            
            # Get system resource usage
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            
            # Get active worker counts
            active_workers = await self._get_active_worker_counts()
            
            metrics = ScalingMetrics(
                queue_depth=queue_depths,
                api_response_times=api_response_times,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                active_workers=active_workers,
                timestamp=datetime.utcnow()
            )
            
            # Update Prometheus metrics
            for queue, depth in queue_depths.items():
                worker_count.labels(queue=queue).set(active_workers.get(queue, 0))
                
            resource_usage.labels(resource='cpu').set(cpu_usage)
            resource_usage.labels(resource='memory').set(memory_usage)
            resource_usage.labels(resource='disk').set(disk_usage)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            raise
    
    async def _get_api_response_times(self) -> Dict[str, float]:
        """Get current API response times from metrics"""
        # This would typically query Prometheus for recent response times
        # For now, we'll simulate with Redis-stored values
        response_times = {}
        try:
            for endpoint in ['/health', '/api/v1/collect/trigger', '/api/v1/status/queues']:
                key = f"metrics:api_response_time:{endpoint.replace('/', '_')}"
                time_ms = await self.redis_client.get(key)
                response_times[endpoint] = float(time_ms) if time_ms else 0.0
        except Exception as e:
            logger.warning(f"Could not get API response times: {e}")
            
        return response_times
    
    async def _get_active_worker_counts(self) -> Dict[str, int]:
        """Get current active worker counts from Celery"""
        try:
            inspect = self.celery_app.control.inspect()
            active_queues = inspect.active_queues()
            
            worker_counts = {}
            if active_queues:
                for worker, queues in active_queues.items():
                    for queue_info in queues:
                        queue_name = queue_info['name']
                        if queue_name in worker_counts:
                            worker_counts[queue_name] += 1
                        else:
                            worker_counts[queue_name] = 1
                            
            return worker_counts
            
        except Exception as e:
            logger.warning(f"Could not get worker counts: {e}")
            return self.current_worker_counts.copy()
    
    def _should_scale_workers(self, queue_name: str, metrics: ScalingMetrics) -> Optional[str]:
        """Determine if workers should be scaled for a queue"""
        current_depth = metrics.queue_depth.get(queue_name, 0)
        current_workers = metrics.active_workers.get(queue_name, 0)
        
        # Check cooldown period
        last_scale = self.last_worker_scale.get(queue_name, datetime.min)
        if datetime.utcnow() - last_scale < timedelta(seconds=self.config.worker_scale_cooldown):
            return None
            
        # Scale up conditions
        if (current_depth > self.config.queue_scale_up_threshold and 
            current_workers < self.config.max_workers_per_queue):
            return 'scale_up'
            
        # Scale down conditions  
        if (current_depth < self.config.queue_scale_down_threshold and
            current_workers > self.config.min_workers_per_queue):
            return 'scale_down'
            
        return None
    
    def _should_scale_api_instances(self, metrics: ScalingMetrics) -> Optional[str]:
        """Determine if API instances should be scaled"""
        # Check cooldown period
        if datetime.utcnow() - self.last_instance_scale < timedelta(seconds=self.config.instance_scale_cooldown):
            return None
            
        # Get average API response time
        if not metrics.api_response_times:
            return None
            
        avg_response_time = sum(metrics.api_response_times.values()) / len(metrics.api_response_times)
        
        # Scale up conditions
        if (avg_response_time > self.config.api_scale_up_threshold and
            self.current_api_instances < self.config.max_api_instances):
            return 'scale_up'
            
        # Scale down conditions
        if (avg_response_time < self.config.api_scale_down_threshold and
            self.current_api_instances > self.config.min_api_instances):
            return 'scale_down'
            
        return None
    
    async def _scale_workers(self, queue_name: str, action: str) -> bool:
        """Execute worker scaling action"""
        try:
            current_count = self.current_worker_counts.get(queue_name, 1)
            
            if action == 'scale_up':
                new_count = min(current_count + 1, self.config.max_workers_per_queue)
            else:  # scale_down
                new_count = max(current_count - 1, self.config.min_workers_per_queue)
                
            if new_count == current_count:
                return False
                
            # Execute scaling command (this would typically use Docker Compose or Kubernetes)
            success = await self._execute_worker_scaling(queue_name, new_count)
            
            if success:
                self.current_worker_counts[queue_name] = new_count
                self.last_worker_scale[queue_name] = datetime.utcnow()
                
                scaling_decisions.labels(action=action, service=f'worker_{queue_name}').inc()
                
                logger.info(f"Scaled {queue_name} workers from {current_count} to {new_count}")
                return True
                
        except Exception as e:
            logger.error(f"Error scaling workers for {queue_name}: {e}")
            
        return False
    
    async def _scale_api_instances(self, action: str) -> bool:
        """Execute API instance scaling action"""
        try:
            current_count = self.current_api_instances
            
            if action == 'scale_up':
                new_count = min(current_count + 1, self.config.max_api_instances)
            else:  # scale_down
                new_count = max(current_count - 1, self.config.min_api_instances)
                
            if new_count == current_count:
                return False
                
            # Execute scaling command
            success = await self._execute_api_scaling(new_count)
            
            if success:
                self.current_api_instances = new_count
                self.last_instance_scale = datetime.utcnow()
                
                scaling_decisions.labels(action=action, service='api').inc()
                
                logger.info(f"Scaled API instances from {current_count} to {new_count}")
                return True
                
        except Exception as e:
            logger.error(f"Error scaling API instances: {e}")
            
        return False
    
    async def _execute_worker_scaling(self, queue_name: str, new_count: int) -> bool:
        """Execute the actual worker scaling command"""
        try:
            # This would typically use Docker Compose scale command
            # docker-compose up -d --scale worker-{queue_name}={new_count}
            
            import subprocess
            
            service_name = f"worker-{queue_name.replace('_', '-')}"
            cmd = [
                "docker-compose", "up", "-d", "--scale", 
                f"{service_name}={new_count}", service_name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"Successfully scaled {service_name} to {new_count} instances")
                return True
            else:
                logger.error(f"Failed to scale {service_name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout scaling {queue_name} workers")
            return False
        except Exception as e:
            logger.error(f"Error executing worker scaling: {e}")
            return False
    
    async def _execute_api_scaling(self, new_count: int) -> bool:
        """Execute the actual API instance scaling command"""
        try:
            import subprocess
            
            cmd = [
                "docker-compose", "up", "-d", "--scale", 
                f"api={new_count}", "api"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                logger.info(f"Successfully scaled API to {new_count} instances")
                return True
            else:
                logger.error(f"Failed to scale API: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Timeout scaling API instances")
            return False
        except Exception as e:
            logger.error(f"Error executing API scaling: {e}")
            return False
    
    def _check_resource_alerts(self, metrics: ScalingMetrics):
        """Check for resource usage alerts"""
        alerts = []
        
        if metrics.cpu_usage > self.config.cpu_scale_up_threshold:
            alerts.append(f"High CPU usage: {metrics.cpu_usage:.1f}%")
            
        if metrics.memory_usage > self.config.memory_scale_up_threshold:
            alerts.append(f"High memory usage: {metrics.memory_usage:.1f}%")
            
        if metrics.disk_usage > self.config.disk_alert_threshold:
            alerts.append(f"High disk usage: {metrics.disk_usage:.1f}%")
            
        for alert in alerts:
            logger.warning(f"Resource alert: {alert}")
            # Here you would typically send alerts to monitoring system
    
    async def run_scaling_loop(self):
        """Main scaling loop that runs continuously"""
        logger.info("Starting auto-scaling loop")
        
        while True:
            try:
                # Collect current metrics
                metrics = await self.collect_metrics()
                
                # Add to history
                self.metrics_history.append(metrics)
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history.pop(0)
                
                # Check for resource alerts
                self._check_resource_alerts(metrics)
                
                # Make scaling decisions for workers
                for queue_name in ['collect', 'process', 'publish']:
                    scaling_action = self._should_scale_workers(queue_name, metrics)
                    if scaling_action:
                        await self._scale_workers(queue_name, scaling_action)
                
                # Make scaling decisions for API instances
                api_scaling_action = self._should_scale_api_instances(metrics)
                if api_scaling_action:
                    await self._scale_api_instances(api_scaling_action)
                
                # Update cooldown metric
                min_cooldown = min([
                    (datetime.utcnow() - self.last_instance_scale).total_seconds(),
                    *[(datetime.utcnow() - ts).total_seconds() 
                      for ts in self.last_worker_scale.values()]
                ])
                scaling_cooldown.set(max(0, self.config.worker_scale_cooldown - min_cooldown))
                
                # Wait for next iteration
                await asyncio.sleep(self.config.scaling_decision_interval)
                
            except Exception as e:
                logger.error(f"Error in scaling loop: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds before retrying

class ScalingManager:
    """Manager for auto-scaling operations"""
    
    def __init__(self):
        self.auto_scaler = AutoScaler()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the auto-scaling service"""
        if self._running:
            logger.warning("Auto-scaler is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self.auto_scaler.run_scaling_loop())
        logger.info("Auto-scaling service started")
    
    async def stop(self):
        """Stop the auto-scaling service"""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
                
        logger.info("Auto-scaling service stopped")
    
    async def get_scaling_status(self) -> Dict:
        """Get current scaling status"""
        metrics = await self.auto_scaler.collect_metrics()
        
        return {
            "auto_scaling_enabled": self._running,
            "current_worker_counts": self.auto_scaler.current_worker_counts,
            "current_api_instances": self.auto_scaler.current_api_instances,
            "queue_depths": metrics.queue_depth,
            "resource_usage": {
                "cpu": metrics.cpu_usage,
                "memory": metrics.memory_usage,
                "disk": metrics.disk_usage
            },
            "api_response_times": metrics.api_response_times,
            "last_scaling_actions": {
                "workers": {k: v.isoformat() for k, v in self.auto_scaler.last_worker_scale.items()},
                "api_instances": self.auto_scaler.last_instance_scale.isoformat()
            }
        }
    
    async def manual_scale_workers(self, queue_name: str, count: int) -> bool:
        """Manually scale workers for a specific queue"""
        if queue_name not in ['collect', 'process', 'publish']:
            raise ValueError(f"Invalid queue name: {queue_name}")
            
        if not (1 <= count <= 8):
            raise ValueError(f"Worker count must be between 1 and 8, got {count}")
            
        return await self.auto_scaler._execute_worker_scaling(queue_name, count)
    
    async def manual_scale_api(self, count: int) -> bool:
        """Manually scale API instances"""
        if not (2 <= count <= 6):
            raise ValueError(f"API instance count must be between 2 and 6, got {count}")
            
        return await self.auto_scaler._execute_api_scaling(count)

# Global scaling manager instance
scaling_manager = ScalingManager()