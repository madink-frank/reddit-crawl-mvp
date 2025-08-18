"""
Resilience monitoring and management for Reddit Ghost Publisher

This module provides:
1. Circuit breaker and bulkhead monitoring
2. Health checks for resilience patterns
3. Metrics collection for resilience patterns
4. Management interface for manual intervention
5. Alerting for resilience pattern failures
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

import structlog
from prometheus_client import Counter, Gauge, Histogram

from app.error_handling import (
    ServiceType,
    CircuitBreakerState,
    ResilienceManager,
    get_resilience_manager
)
from app.redis_client import redis_client

logger = structlog.get_logger(__name__)


# Prometheus metrics for resilience patterns
circuit_breaker_state_gauge = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half_open, 2=open)',
    ['service']
)

circuit_breaker_failures_total = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['service']
)

circuit_breaker_successes_total = Counter(
    'circuit_breaker_successes_total',
    'Total circuit breaker successes',
    ['service']
)

bulkhead_active_requests_gauge = Gauge(
    'bulkhead_active_requests',
    'Number of active requests in bulkhead',
    ['service']
)

bulkhead_queue_size_gauge = Gauge(
    'bulkhead_queue_size',
    'Size of bulkhead queue',
    ['service']
)

bulkhead_rejections_total = Counter(
    'bulkhead_rejections_total',
    'Total bulkhead rejections',
    ['service']
)

resilience_pattern_execution_time = Histogram(
    'resilience_pattern_execution_seconds',
    'Time spent executing with resilience patterns',
    ['service', 'pattern']
)


class ResilienceAlert(Enum):
    """Types of resilience alerts"""
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_HALF_OPEN = "circuit_breaker_half_open"
    BULKHEAD_QUEUE_FULL = "bulkhead_queue_full"
    HIGH_FAILURE_RATE = "high_failure_rate"
    SERVICE_DEGRADED = "service_degraded"


@dataclass
class ResilienceMetrics:
    """Metrics for resilience patterns"""
    service: ServiceType
    circuit_breaker_state: CircuitBreakerState
    circuit_breaker_failures: int
    circuit_breaker_successes: int
    bulkhead_active_requests: int
    bulkhead_queue_size: int
    bulkhead_max_concurrent: int
    bulkhead_queue_max_size: int
    last_failure_time: Optional[datetime] = None
    failure_rate_1h: float = 0.0
    success_rate_1h: float = 0.0
    avg_response_time_1h: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service.value,
            "circuit_breaker_state": self.circuit_breaker_state.value,
            "circuit_breaker_failures": self.circuit_breaker_failures,
            "circuit_breaker_successes": self.circuit_breaker_successes,
            "bulkhead_active_requests": self.bulkhead_active_requests,
            "bulkhead_queue_size": self.bulkhead_queue_size,
            "bulkhead_max_concurrent": self.bulkhead_max_concurrent,
            "bulkhead_queue_max_size": self.bulkhead_queue_max_size,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "failure_rate_1h": self.failure_rate_1h,
            "success_rate_1h": self.success_rate_1h,
            "avg_response_time_1h": self.avg_response_time_1h,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ResilienceAlertEvent:
    """Alert event for resilience patterns"""
    alert_type: ResilienceAlert
    service: ServiceType
    message: str
    severity: str = "warning"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_type": self.alert_type.value,
            "service": self.service.value,
            "message": self.message,
            "severity": self.severity,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class ResilienceMonitor:
    """Monitor and manage resilience patterns"""
    
    def __init__(self, resilience_manager: ResilienceManager):
        self.resilience_manager = resilience_manager
        self.alert_thresholds = {
            "failure_rate_threshold": 0.5,  # 50% failure rate
            "queue_full_threshold": 0.9,    # 90% queue capacity
            "response_time_threshold": 5.0   # 5 seconds
        }
    
    async def collect_metrics(self) -> Dict[ServiceType, ResilienceMetrics]:
        """Collect metrics from all resilience patterns"""
        metrics = {}
        
        for service in ServiceType:
            if service in self.resilience_manager.circuit_breakers:
                circuit_breaker = self.resilience_manager.circuit_breakers[service]
                bulkhead = self.resilience_manager.bulkheads[service]
                
                # Get historical metrics
                failure_rate, success_rate, avg_response_time = await self._get_historical_metrics(service)
                
                metrics[service] = ResilienceMetrics(
                    service=service,
                    circuit_breaker_state=circuit_breaker.state,
                    circuit_breaker_failures=circuit_breaker.failure_count,
                    circuit_breaker_successes=circuit_breaker.success_count,
                    bulkhead_active_requests=bulkhead.active_requests,
                    bulkhead_queue_size=bulkhead.queue.qsize(),
                    bulkhead_max_concurrent=bulkhead.config.max_concurrent,
                    bulkhead_queue_max_size=bulkhead.config.queue_size,
                    last_failure_time=circuit_breaker.last_failure_time,
                    failure_rate_1h=failure_rate,
                    success_rate_1h=success_rate,
                    avg_response_time_1h=avg_response_time
                )
                
                # Update Prometheus metrics
                self._update_prometheus_metrics(metrics[service])
        
        return metrics
    
    async def _get_historical_metrics(self, service: ServiceType) -> Tuple[float, float, float]:
        """Get historical metrics for a service"""
        try:
            # Get metrics from Redis (last hour)
            now = datetime.utcnow()
            hour_ago = now - timedelta(hours=1)
            
            # Count failures and successes in the last hour
            failures_key = f"failures:{service.value}"
            successes_key = f"successes:{service.value}"
            response_times_key = f"response_times:{service.value}"
            
            # Use Redis sorted sets with timestamps as scores
            failures = await redis_client.zcount(
                failures_key,
                hour_ago.timestamp(),
                now.timestamp()
            )
            
            successes = await redis_client.zcount(
                successes_key,
                hour_ago.timestamp(),
                now.timestamp()
            )
            
            total_requests = failures + successes
            failure_rate = failures / total_requests if total_requests > 0 else 0.0
            success_rate = successes / total_requests if total_requests > 0 else 0.0
            
            # Get average response time
            response_times = await redis_client.zrangebyscore(
                response_times_key,
                hour_ago.timestamp(),
                now.timestamp(),
                withscores=False
            )
            
            avg_response_time = 0.0
            if response_times:
                avg_response_time = sum(float(rt) for rt in response_times) / len(response_times)
            
            return failure_rate, success_rate, avg_response_time
            
        except Exception as e:
            logger.error(
                "Failed to get historical metrics",
                service=service.value,
                error=str(e)
            )
            return 0.0, 0.0, 0.0
    
    def _update_prometheus_metrics(self, metrics: ResilienceMetrics) -> None:
        """Update Prometheus metrics"""
        service_label = metrics.service.value
        
        # Circuit breaker state (0=closed, 1=half_open, 2=open)
        state_value = {
            CircuitBreakerState.CLOSED: 0,
            CircuitBreakerState.HALF_OPEN: 1,
            CircuitBreakerState.OPEN: 2
        }.get(metrics.circuit_breaker_state, 0)
        
        circuit_breaker_state_gauge.labels(service=service_label).set(state_value)
        
        # Bulkhead metrics
        bulkhead_active_requests_gauge.labels(service=service_label).set(
            metrics.bulkhead_active_requests
        )
        bulkhead_queue_size_gauge.labels(service=service_label).set(
            metrics.bulkhead_queue_size
        )
    
    async def check_alerts(self, metrics: Dict[ServiceType, ResilienceMetrics]) -> List[ResilienceAlertEvent]:
        """Check for alert conditions"""
        alerts = []
        
        for service, metric in metrics.items():
            # Check circuit breaker state changes
            if metric.circuit_breaker_state == CircuitBreakerState.OPEN:
                alerts.append(ResilienceAlertEvent(
                    alert_type=ResilienceAlert.CIRCUIT_BREAKER_OPENED,
                    service=service,
                    message=f"Circuit breaker opened for {service.value} due to failures",
                    severity="critical",
                    metadata={
                        "failure_count": metric.circuit_breaker_failures,
                        "last_failure_time": metric.last_failure_time.isoformat() if metric.last_failure_time else None
                    }
                ))
            
            elif metric.circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
                alerts.append(ResilienceAlertEvent(
                    alert_type=ResilienceAlert.CIRCUIT_BREAKER_HALF_OPEN,
                    service=service,
                    message=f"Circuit breaker in half-open state for {service.value}",
                    severity="warning",
                    metadata={"testing_recovery": True}
                ))
            
            # Check bulkhead queue capacity
            queue_utilization = metric.bulkhead_queue_size / metric.bulkhead_queue_max_size
            if queue_utilization >= self.alert_thresholds["queue_full_threshold"]:
                alerts.append(ResilienceAlertEvent(
                    alert_type=ResilienceAlert.BULKHEAD_QUEUE_FULL,
                    service=service,
                    message=f"Bulkhead queue nearly full for {service.value} ({queue_utilization:.1%})",
                    severity="warning",
                    metadata={
                        "queue_size": metric.bulkhead_queue_size,
                        "queue_max_size": metric.bulkhead_queue_max_size,
                        "utilization": queue_utilization
                    }
                ))
            
            # Check failure rate
            if metric.failure_rate_1h >= self.alert_thresholds["failure_rate_threshold"]:
                alerts.append(ResilienceAlertEvent(
                    alert_type=ResilienceAlert.HIGH_FAILURE_RATE,
                    service=service,
                    message=f"High failure rate for {service.value} ({metric.failure_rate_1h:.1%})",
                    severity="critical",
                    metadata={
                        "failure_rate": metric.failure_rate_1h,
                        "success_rate": metric.success_rate_1h
                    }
                ))
            
            # Check response time
            if metric.avg_response_time_1h >= self.alert_thresholds["response_time_threshold"]:
                alerts.append(ResilienceAlertEvent(
                    alert_type=ResilienceAlert.SERVICE_DEGRADED,
                    service=service,
                    message=f"High response time for {service.value} ({metric.avg_response_time_1h:.2f}s)",
                    severity="warning",
                    metadata={"avg_response_time": metric.avg_response_time_1h}
                ))
        
        return alerts
    
    async def send_alerts(self, alerts: List[ResilienceAlertEvent]) -> None:
        """Send alerts to monitoring systems"""
        for alert in alerts:
            # Store alert in Redis
            alert_key = f"alert:{alert.service.value}:{int(alert.timestamp.timestamp())}"
            await redis_client.setex(alert_key, 3600, alert.to_dict())  # 1 hour TTL
            
            # Log alert
            logger.warning(
                "Resilience alert triggered",
                alert_type=alert.alert_type.value,
                service=alert.service.value,
                message=alert.message,
                severity=alert.severity,
                metadata=alert.metadata
            )
            
            # Here you would integrate with your alerting system (Slack, PagerDuty, etc.)
            # await self._send_to_slack(alert)
            # await self._send_to_pagerduty(alert)
    
    async def get_service_health(self, service: ServiceType) -> Dict[str, Any]:
        """Get comprehensive health status for a service"""
        try:
            status = self.resilience_manager.get_service_status(service)
            metrics = await self.collect_metrics()
            service_metrics = metrics.get(service)
            
            health = {
                "service": service.value,
                "overall_status": "healthy",
                "circuit_breaker": status.get("circuit_breaker"),
                "bulkhead": status.get("bulkhead"),
                "metrics": service_metrics.to_dict() if service_metrics else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Determine overall status
            if service_metrics:
                if service_metrics.circuit_breaker_state == CircuitBreakerState.OPEN:
                    health["overall_status"] = "unhealthy"
                elif (service_metrics.circuit_breaker_state == CircuitBreakerState.HALF_OPEN or
                      service_metrics.failure_rate_1h > 0.3):
                    health["overall_status"] = "degraded"
            
            return health
            
        except Exception as e:
            logger.error(
                "Failed to get service health",
                service=service.value,
                error=str(e)
            )
            return {
                "service": service.value,
                "overall_status": "unknown",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def reset_circuit_breaker(self, service: ServiceType) -> bool:
        """Manually reset a circuit breaker"""
        try:
            circuit_breaker = self.resilience_manager.circuit_breakers.get(service)
            if circuit_breaker:
                circuit_breaker.state = CircuitBreakerState.CLOSED
                circuit_breaker.failure_count = 0
                circuit_breaker.success_count = 0
                circuit_breaker.last_failure_time = None
                
                await circuit_breaker._save_state_to_redis()
                
                logger.info(
                    "Circuit breaker manually reset",
                    service=service.value
                )
                return True
            
        except Exception as e:
            logger.error(
                "Failed to reset circuit breaker",
                service=service.value,
                error=str(e)
            )
        
        return False
    
    async def adjust_bulkhead_limits(
        self,
        service: ServiceType,
        max_concurrent: Optional[int] = None,
        queue_size: Optional[int] = None
    ) -> bool:
        """Adjust bulkhead limits for a service"""
        try:
            bulkhead = self.resilience_manager.bulkheads.get(service)
            if bulkhead:
                if max_concurrent is not None:
                    bulkhead.config.max_concurrent = max_concurrent
                    # Create new semaphore with updated limit
                    bulkhead.semaphore = asyncio.Semaphore(max_concurrent)
                
                if queue_size is not None:
                    bulkhead.config.queue_size = queue_size
                    # Note: Can't resize existing queue, would need to create new one
                
                logger.info(
                    "Bulkhead limits adjusted",
                    service=service.value,
                    max_concurrent=max_concurrent,
                    queue_size=queue_size
                )
                return True
            
        except Exception as e:
            logger.error(
                "Failed to adjust bulkhead limits",
                service=service.value,
                error=str(e)
            )
        
        return False
    
    async def run_monitoring_loop(self, interval: int = 60) -> None:
        """Run continuous monitoring loop"""
        logger.info("Starting resilience monitoring loop", interval=interval)
        
        while True:
            try:
                # Collect metrics
                metrics = await self.collect_metrics()
                
                # Check for alerts
                alerts = await self.check_alerts(metrics)
                
                # Send alerts if any
                if alerts:
                    await self.send_alerts(alerts)
                
                # Store metrics for historical analysis
                await self._store_metrics_history(metrics)
                
                logger.debug(
                    "Monitoring cycle completed",
                    services_monitored=len(metrics),
                    alerts_generated=len(alerts)
                )
                
            except Exception as e:
                logger.error("Error in monitoring loop", error=str(e))
            
            await asyncio.sleep(interval)
    
    async def _store_metrics_history(self, metrics: Dict[ServiceType, ResilienceMetrics]) -> None:
        """Store metrics history in Redis"""
        try:
            timestamp = datetime.utcnow().timestamp()
            
            for service, metric in metrics.items():
                # Store metrics with timestamp as score
                metrics_key = f"metrics_history:{service.value}"
                await redis_client.zadd(metrics_key, {json.dumps(metric.to_dict()): timestamp})
                
                # Keep only last 24 hours of data
                cutoff_time = timestamp - 86400  # 24 hours ago
                await redis_client.zremrangebyscore(metrics_key, 0, cutoff_time)
                
        except Exception as e:
            logger.error("Failed to store metrics history", error=str(e))


# Global resilience monitor instance
resilience_monitor = ResilienceMonitor(get_resilience_manager())


def get_resilience_monitor() -> ResilienceMonitor:
    """Get the global resilience monitor instance"""
    return resilience_monitor


async def start_resilience_monitoring(interval: int = 60) -> None:
    """Start the resilience monitoring background task"""
    monitor = get_resilience_monitor()
    await monitor.run_monitoring_loop(interval)