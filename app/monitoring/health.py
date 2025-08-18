"""
Enhanced health check system with dependency monitoring and alerting
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.monitoring.logging import get_logger
from app.monitoring.metrics import MetricsCollector


logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServiceHealth:
    """Individual service health information"""
    
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        response_time_ms: float,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.status = status
        self.response_time_ms = response_time_ms
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "name": self.name,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() + "Z"
        }


class HealthChecker:
    """Enhanced health checker with external API monitoring"""
    
    def __init__(self):
        self.settings = get_settings()
        self.start_time = time.time()
    
    async def check_database(self) -> ServiceHealth:
        """Check PostgreSQL database connectivity with detailed diagnostics"""
        start_time = time.time()
        
        try:
            from app.infrastructure import get_database_session
            
            db_session = get_database_session()
            try:
                # Test basic connectivity
                db_session.execute(text("SELECT 1"))
                
                # Test table access
                db_session.execute(text("SELECT COUNT(*) FROM processing_logs LIMIT 1"))
                
                # Check connection pool status
                from app.infrastructure import get_database
                engine = get_database()
                pool = engine.pool
                
                response_time = (time.time() - start_time) * 1000
                
                return ServiceHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=round(response_time, 2),
                    message="Database connection successful",
                    details={
                        "pool_size": pool.size(),
                        "checked_in": pool.checkedin(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow()
                    }
                )
                
            finally:
                db_session.close()
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Database health check failed", error=str(e))
            
            return ServiceHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                message=f"Database connection failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    async def check_redis(self) -> ServiceHealth:
        """Check Redis connectivity with detailed diagnostics"""
        start_time = time.time()
        
        try:
            from app.infrastructure import get_redis_client
            
            redis_client = get_redis_client()
            
            # Test basic connectivity
            await redis_client.ping()
            
            # Test queue operations
            test_key = "health_check_test"
            await redis_client.set(test_key, "test_value", ex=10)
            test_value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            if test_value != "test_value":
                raise Exception("Redis read/write test failed")
            
            # Get Redis info
            info = await redis_client.info()
            
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                response_time_ms=round(response_time, 2),
                message="Redis connection successful",
                details={
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "redis_version": info.get("redis_version", "unknown"),
                    "uptime_in_seconds": info.get("uptime_in_seconds", 0)
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Redis health check failed", error=str(e))
            
            return ServiceHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                message=f"Redis connection failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    async def check_external_apis(self) -> List[ServiceHealth]:
        """Check external API connectivity"""
        external_checks = []
        
        # Check Reddit API (if configured)
        if self.settings.reddit_client_id and self.settings.reddit_client_secret:
            reddit_health = await self._check_reddit_api()
            external_checks.append(reddit_health)
        
        # Check OpenAI API (if configured)
        if self.settings.openai_api_key:
            openai_health = await self._check_openai_api()
            external_checks.append(openai_health)
        
        # Check Ghost API (if configured)
        if self.settings.ghost_admin_key and self.settings.ghost_api_url:
            ghost_health = await self._check_ghost_api()
            external_checks.append(ghost_health)
        
        return external_checks
    
    async def _check_reddit_api(self) -> ServiceHealth:
        """Check Reddit API connectivity"""
        start_time = time.time()
        
        try:
            # Simple API check - get user agent info
            headers = {
                'User-Agent': self.settings.reddit_user_agent
            }
            
            response = requests.get(
                'https://www.reddit.com/api/v1/me',
                headers=headers,
                timeout=10
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 401:
                # Expected for unauthenticated request
                return ServiceHealth(
                    name="reddit_api",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=round(response_time, 2),
                    message="Reddit API accessible",
                    details={
                        "status_code": response.status_code,
                        "rate_limit_remaining": response.headers.get("x-ratelimit-remaining"),
                        "rate_limit_reset": response.headers.get("x-ratelimit-reset")
                    }
                )
            elif response.status_code == 429:
                return ServiceHealth(
                    name="reddit_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=round(response_time, 2),
                    message="Reddit API rate limited",
                    details={
                        "status_code": response.status_code,
                        "retry_after": response.headers.get("retry-after")
                    }
                )
            else:
                return ServiceHealth(
                    name="reddit_api",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=round(response_time, 2),
                    message="Reddit API accessible",
                    details={"status_code": response.status_code}
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="reddit_api",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                message=f"Reddit API check failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    async def _check_openai_api(self) -> ServiceHealth:
        """Check OpenAI API connectivity"""
        start_time = time.time()
        
        try:
            headers = {
                'Authorization': f'Bearer {self.settings.openai_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Simple API check - list models
            response = requests.get(
                'https://api.openai.com/v1/models',
                headers=headers,
                timeout=10
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ServiceHealth(
                    name="openai_api",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=round(response_time, 2),
                    message="OpenAI API accessible",
                    details={"status_code": response.status_code}
                )
            elif response.status_code == 429:
                return ServiceHealth(
                    name="openai_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=round(response_time, 2),
                    message="OpenAI API rate limited",
                    details={
                        "status_code": response.status_code,
                        "retry_after": response.headers.get("retry-after")
                    }
                )
            else:
                return ServiceHealth(
                    name="openai_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=round(response_time, 2),
                    message=f"OpenAI API returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="openai_api",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                message=f"OpenAI API check failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    async def _check_ghost_api(self) -> ServiceHealth:
        """Check Ghost API connectivity"""
        start_time = time.time()
        
        try:
            # Simple API check - get site info
            response = requests.get(
                f"{self.settings.ghost_api_url}/ghost/api/v3/content/settings/",
                timeout=10
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ServiceHealth(
                    name="ghost_api",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=round(response_time, 2),
                    message="Ghost API accessible",
                    details={"status_code": response.status_code}
                )
            elif response.status_code == 429:
                return ServiceHealth(
                    name="ghost_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=round(response_time, 2),
                    message="Ghost API rate limited",
                    details={
                        "status_code": response.status_code,
                        "retry_after": response.headers.get("retry-after")
                    }
                )
            else:
                return ServiceHealth(
                    name="ghost_api",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=round(response_time, 2),
                    message=f"Ghost API returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return ServiceHealth(
                name="ghost_api",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                message=f"Ghost API check failed: {str(e)}",
                details={"error_type": type(e).__name__}
            )
    
    async def get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        # Check core services
        db_health = await self.check_database()
        redis_health = await self.check_redis()
        
        # Check external APIs
        external_health = await self.check_external_apis()
        
        # Combine all health checks
        all_services = [db_health, redis_health] + external_health
        
        # Determine overall status
        unhealthy_count = sum(1 for s in all_services if s.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for s in all_services if s.status == HealthStatus.DEGRADED)
        
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Build response
        services_dict = {service.name: service.to_dict() for service in all_services}
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0",
            "environment": self.settings.environment,
            "uptime_seconds": round(uptime, 2),
            "services": services_dict,
            "summary": {
                "total_services": len(all_services),
                "healthy": sum(1 for s in all_services if s.status == HealthStatus.HEALTHY),
                "degraded": degraded_count,
                "unhealthy": unhealthy_count
            }
        }


class AlertManager:
    """Manages health-based alerting with Slack notifications"""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)
    
    async def check_and_alert(self, db_session: Session) -> Dict[str, Any]:
        """
        Check system health and send alerts if thresholds are exceeded
        
        Returns:
            Dictionary with alert status and actions taken
        """
        alerts_sent = []
        
        try:
            # Check failure rate (5-minute sliding window)
            failure_rate = await self._get_recent_failure_rate(db_session)
            if failure_rate > self.settings.failure_rate_threshold:
                alert_sent = await self._send_failure_rate_alert(failure_rate)
                if alert_sent:
                    alerts_sent.append("failure_rate")
            
            # Check queue backlog
            queue_backlog = await self._get_queue_backlog()
            if queue_backlog > self.settings.queue_alert_threshold:
                alert_sent = await self._send_queue_backlog_alert(queue_backlog)
                if alert_sent:
                    alerts_sent.append("queue_backlog")
            
            # Check service health
            health_checker = HealthChecker()
            health_status = await health_checker.get_comprehensive_health()
            
            unhealthy_services = [
                name for name, service in health_status["services"].items()
                if service["status"] == "unhealthy"
            ]
            
            if unhealthy_services:
                alert_sent = await self._send_service_health_alert(unhealthy_services, health_status)
                if alert_sent:
                    alerts_sent.append("service_health")
            
            return {
                "status": "completed",
                "alerts_sent": alerts_sent,
                "failure_rate": failure_rate,
                "queue_backlog": queue_backlog,
                "unhealthy_services": unhealthy_services,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            self.logger.error("Alert check failed", error=str(e))
            return {
                "status": "failed",
                "error": str(e),
                "alerts_sent": alerts_sent,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    async def _get_recent_failure_rate(self, db_session: Session) -> float:
        """Get failure rate for the last 5 minutes"""
        try:
            collector = MetricsCollector(db_session)
            return collector.get_recent_failure_rate(time_window_minutes=5)
        except Exception as e:
            self.logger.error("Failed to get failure rate", error=str(e))
            return 0.0
    
    async def _get_queue_backlog(self) -> int:
        """Get total queue backlog"""
        try:
            from app.infrastructure import get_redis_client
            
            redis_client = get_redis_client()
            
            total_backlog = 0
            queues = [
                self.settings.queue_collect_name,
                self.settings.queue_process_name,
                self.settings.queue_publish_name
            ]
            
            for queue_name in queues:
                queue_length = await redis_client.llen(queue_name)
                total_backlog += queue_length
            
            return total_backlog
            
        except Exception as e:
            self.logger.error("Failed to get queue backlog", error=str(e))
            return 0
    
    async def _send_failure_rate_alert(self, failure_rate: float) -> bool:
        """Send failure rate alert to Slack"""
        if not self.settings.slack_webhook_url:
            return False
        
        try:
            payload = {
                "text": "🚨 High Failure Rate Alert",
                "attachments": [
                    {
                        "color": "danger",
                        "fields": [
                            {
                                "title": "Severity",
                                "value": "HIGH",
                                "short": True
                            },
                            {
                                "title": "Service",
                                "value": "Reddit Ghost Publisher",
                                "short": True
                            },
                            {
                                "title": "Metric",
                                "value": f"Failure Rate: {failure_rate:.2%}",
                                "short": True
                            },
                            {
                                "title": "Threshold",
                                "value": f"{self.settings.failure_rate_threshold:.2%}",
                                "short": True
                            },
                            {
                                "title": "Time Window",
                                "value": "Last 5 minutes",
                                "short": True
                            },
                            {
                                "title": "Timestamp",
                                "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                self.settings.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info("Failure rate alert sent to Slack", failure_rate=failure_rate)
                return True
            else:
                self.logger.error("Failed to send Slack alert", status_code=response.status_code)
                return False
                
        except Exception as e:
            self.logger.error("Failed to send failure rate alert", error=str(e))
            return False
    
    async def _send_queue_backlog_alert(self, queue_backlog: int) -> bool:
        """Send queue backlog alert to Slack"""
        if not self.settings.slack_webhook_url:
            return False
        
        try:
            payload = {
                "text": "⚠️ Queue Backlog Alert",
                "attachments": [
                    {
                        "color": "warning",
                        "fields": [
                            {
                                "title": "Severity",
                                "value": "MEDIUM",
                                "short": True
                            },
                            {
                                "title": "Service",
                                "value": "Reddit Ghost Publisher",
                                "short": True
                            },
                            {
                                "title": "Metric",
                                "value": f"Queue Backlog: {queue_backlog} tasks",
                                "short": True
                            },
                            {
                                "title": "Threshold",
                                "value": f"{self.settings.queue_alert_threshold} tasks",
                                "short": True
                            },
                            {
                                "title": "Time Window",
                                "value": "Current",
                                "short": True
                            },
                            {
                                "title": "Timestamp",
                                "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                self.settings.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info("Queue backlog alert sent to Slack", queue_backlog=queue_backlog)
                return True
            else:
                self.logger.error("Failed to send Slack alert", status_code=response.status_code)
                return False
                
        except Exception as e:
            self.logger.error("Failed to send queue backlog alert", error=str(e))
            return False
    
    async def _send_service_health_alert(self, unhealthy_services: List[str], health_status: Dict[str, Any]) -> bool:
        """Send service health alert to Slack"""
        if not self.settings.slack_webhook_url:
            return False
        
        try:
            services_text = ", ".join(unhealthy_services)
            
            payload = {
                "text": "🔴 Service Health Alert",
                "attachments": [
                    {
                        "color": "danger",
                        "fields": [
                            {
                                "title": "Severity",
                                "value": "HIGH",
                                "short": True
                            },
                            {
                                "title": "Service",
                                "value": "Reddit Ghost Publisher",
                                "short": True
                            },
                            {
                                "title": "Unhealthy Services",
                                "value": services_text,
                                "short": False
                            },
                            {
                                "title": "Overall Status",
                                "value": health_status["status"].upper(),
                                "short": True
                            },
                            {
                                "title": "Time Window",
                                "value": "Current",
                                "short": True
                            },
                            {
                                "title": "Timestamp",
                                "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                self.settings.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info("Service health alert sent to Slack", unhealthy_services=unhealthy_services)
                return True
            else:
                self.logger.error("Failed to send Slack alert", status_code=response.status_code)
                return False
                
        except Exception as e:
            self.logger.error("Failed to send service health alert", error=str(e))
            return False