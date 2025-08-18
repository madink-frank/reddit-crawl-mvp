"""
Centralized error handling and resilience patterns for Reddit Ghost Publisher

This module provides:
1. External service error handling with backoff logic
2. Circuit breaker pattern implementation
3. Bulkhead pattern for resource isolation
4. Retry mechanisms with exponential backoff
5. Error classification and recovery strategies
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from functools import wraps
import random

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    retry_if_result,
    before_sleep_log,
    after_log
)

from app.redis_client import redis_client

logger = structlog.get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceType(Enum):
    """External service types"""
    REDDIT = "reddit"
    OPENAI = "openai"
    GHOST = "ghost"
    DATABASE = "database"
    REDIS = "redis"
    VAULT = "vault"


@dataclass
class ErrorContext:
    """Context information for error handling"""
    service: ServiceType
    operation: str
    attempt: int
    error: Exception
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service.value,
            "operation": self.operation,
            "attempt": self.attempt,
            "error_type": type(self.error).__name__,
            "error_message": str(self.error),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class ServiceError(Exception):
    """Base exception for service errors"""
    def __init__(self, message: str, service: ServiceType, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        super().__init__(message)
        self.service = service
        self.severity = severity
        self.timestamp = datetime.utcnow()


class RetryableError(ServiceError):
    """Error that can be retried"""
    pass


class NonRetryableError(ServiceError):
    """Error that should not be retried"""
    pass


class RateLimitError(RetryableError):
    """Rate limit exceeded error"""
    def __init__(self, service: ServiceType, retry_after: Optional[int] = None):
        super().__init__(f"Rate limit exceeded for {service.value}", service, ErrorSeverity.MEDIUM)
        self.retry_after = retry_after


class AuthenticationError(NonRetryableError):
    """Authentication failed error"""
    def __init__(self, service: ServiceType):
        super().__init__(f"Authentication failed for {service.value}", service, ErrorSeverity.HIGH)


class QuotaExceededError(NonRetryableError):
    """Quota/budget exceeded error"""
    def __init__(self, service: ServiceType, quota_type: str):
        super().__init__(f"{quota_type} quota exceeded for {service.value}", service, ErrorSeverity.HIGH)
        self.quota_type = quota_type


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5  # Number of failures to open circuit
    recovery_timeout: int = 60  # Seconds to wait before trying half-open
    success_threshold: int = 3  # Successes needed to close circuit from half-open
    timeout: int = 30  # Request timeout in seconds


class CircuitBreaker:
    """Circuit breaker implementation for external services"""
    
    def __init__(self, service: ServiceType, config: CircuitBreakerConfig):
        self.service = service
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.redis_key = f"circuit_breaker:{service.value}"
        
    async def _get_state_from_redis(self) -> Dict[str, Any]:
        """Get circuit breaker state from Redis"""
        try:
            state_data = await redis_client.hgetall(self.redis_key)
            if state_data:
                return {
                    "state": CircuitBreakerState(state_data.get("state", "closed")),
                    "failure_count": int(state_data.get("failure_count", 0)),
                    "success_count": int(state_data.get("success_count", 0)),
                    "last_failure_time": datetime.fromisoformat(state_data["last_failure_time"]) 
                                       if state_data.get("last_failure_time") else None
                }
        except Exception as e:
            logger.warning("Failed to get circuit breaker state from Redis", error=str(e))
        
        return {
            "state": CircuitBreakerState.CLOSED,
            "failure_count": 0,
            "success_count": 0,
            "last_failure_time": None
        }
    
    async def _save_state_to_redis(self) -> None:
        """Save circuit breaker state to Redis"""
        try:
            state_data = {
                "state": self.state.value,
                "failure_count": str(self.failure_count),
                "success_count": str(self.success_count),
                "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else ""
            }
            await redis_client.hset(self.redis_key, state_data)
            await redis_client.expire(self.redis_key, 3600)  # Expire after 1 hour
        except Exception as e:
            logger.warning("Failed to save circuit breaker state to Redis", error=str(e))
    
    async def _load_state(self) -> None:
        """Load circuit breaker state"""
        state_data = await self._get_state_from_redis()
        self.state = state_data["state"]
        self.failure_count = state_data["failure_count"]
        self.success_count = state_data["success_count"]
        self.last_failure_time = state_data["last_failure_time"]
    
    async def can_execute(self) -> bool:
        """Check if request can be executed"""
        await self._load_state()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (self.last_failure_time and 
                datetime.utcnow() - self.last_failure_time >= timedelta(seconds=self.config.recovery_timeout)):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                await self._save_state_to_redis()
                logger.info("Circuit breaker transitioning to half-open", service=self.service.value)
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    async def record_success(self) -> None:
        """Record successful operation"""
        await self._load_state()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_failure_time = None
                logger.info("Circuit breaker closed after recovery", service=self.service.value)
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            if self.failure_count > 0:
                self.failure_count = 0
        
        await self._save_state_to_redis()
    
    async def record_failure(self, error: Exception) -> None:
        """Record failed operation"""
        await self._load_state()
        
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(
                    "Circuit breaker opened due to failures",
                    service=self.service.value,
                    failure_count=self.failure_count,
                    error=str(error)
                )
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            logger.warning(
                "Circuit breaker reopened after half-open failure",
                service=self.service.value,
                error=str(error)
            )
        
        await self._save_state_to_redis()
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if not await self.can_execute():
            raise ServiceError(
                f"Circuit breaker is open for {self.service.value}",
                self.service,
                ErrorSeverity.HIGH
            )
        
        try:
            # Add timeout to the operation
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            await self.record_success()
            return result
        except asyncio.TimeoutError as e:
            timeout_error = ServiceError(
                f"Operation timeout for {self.service.value}",
                self.service,
                ErrorSeverity.MEDIUM
            )
            await self.record_failure(timeout_error)
            raise timeout_error
        except Exception as e:
            await self.record_failure(e)
            raise


class BulkheadConfig:
    """Bulkhead pattern configuration"""
    def __init__(self, max_concurrent: int = 10, queue_size: int = 100):
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size


class Bulkhead:
    """Bulkhead pattern implementation for resource isolation"""
    
    def __init__(self, service: ServiceType, config: BulkheadConfig):
        self.service = service
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        self.queue = asyncio.Queue(maxsize=config.queue_size)
        self.active_requests = 0
        
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with bulkhead protection"""
        try:
            # Try to acquire semaphore (non-blocking)
            if self.semaphore.locked():
                if self.queue.full():
                    raise ServiceError(
                        f"Bulkhead queue full for {self.service.value}",
                        self.service,
                        ErrorSeverity.HIGH
                    )
                
                # Queue the request
                await self.queue.put((func, args, kwargs))
                logger.info(
                    "Request queued due to bulkhead limit",
                    service=self.service.value,
                    queue_size=self.queue.qsize()
                )
            
            async with self.semaphore:
                self.active_requests += 1
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    self.active_requests -= 1
                    
        except Exception as e:
            logger.error(
                "Bulkhead execution failed",
                service=self.service.value,
                error=str(e)
            )
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead statistics"""
        return {
            "service": self.service.value,
            "max_concurrent": self.config.max_concurrent,
            "active_requests": self.active_requests,
            "queue_size": self.queue.qsize(),
            "queue_max_size": self.config.queue_size,
            "available_slots": self.config.max_concurrent - self.active_requests
        }


class ResilienceManager:
    """Central manager for resilience patterns"""
    
    def __init__(self):
        self.circuit_breakers: Dict[ServiceType, CircuitBreaker] = {}
        self.bulkheads: Dict[ServiceType, Bulkhead] = {}
        self._initialize_patterns()
    
    def _initialize_patterns(self) -> None:
        """Initialize circuit breakers and bulkheads for each service"""
        service_configs = {
            ServiceType.REDDIT: {
                "circuit_breaker": CircuitBreakerConfig(
                    failure_threshold=3,
                    recovery_timeout=120,
                    success_threshold=2,
                    timeout=30
                ),
                "bulkhead": BulkheadConfig(max_concurrent=5, queue_size=50)
            },
            ServiceType.OPENAI: {
                "circuit_breaker": CircuitBreakerConfig(
                    failure_threshold=5,
                    recovery_timeout=300,
                    success_threshold=3,
                    timeout=60
                ),
                "bulkhead": BulkheadConfig(max_concurrent=3, queue_size=20)
            },
            ServiceType.GHOST: {
                "circuit_breaker": CircuitBreakerConfig(
                    failure_threshold=4,
                    recovery_timeout=180,
                    success_threshold=2,
                    timeout=45
                ),
                "bulkhead": BulkheadConfig(max_concurrent=4, queue_size=30)
            }
        }
        
        for service, config in service_configs.items():
            self.circuit_breakers[service] = CircuitBreaker(service, config["circuit_breaker"])
            self.bulkheads[service] = Bulkhead(service, config["bulkhead"])
    
    async def execute_with_resilience(
        self,
        service: ServiceType,
        operation: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with full resilience patterns"""
        circuit_breaker = self.circuit_breakers.get(service)
        bulkhead = self.bulkheads.get(service)
        
        if not circuit_breaker or not bulkhead:
            # Fallback to direct execution if patterns not configured
            return await func(*args, **kwargs)
        
        logger.debug(
            "Executing with resilience patterns",
            service=service.value,
            operation=operation
        )
        
        # Execute with both circuit breaker and bulkhead
        async def protected_execution():
            return await bulkhead.execute(func, *args, **kwargs)
        
        return await circuit_breaker.execute(protected_execution)
    
    def get_service_status(self, service: ServiceType) -> Dict[str, Any]:
        """Get status of resilience patterns for a service"""
        circuit_breaker = self.circuit_breakers.get(service)
        bulkhead = self.bulkheads.get(service)
        
        status = {
            "service": service.value,
            "circuit_breaker": None,
            "bulkhead": None
        }
        
        if circuit_breaker:
            status["circuit_breaker"] = {
                "state": circuit_breaker.state.value,
                "failure_count": circuit_breaker.failure_count,
                "success_count": circuit_breaker.success_count,
                "last_failure_time": circuit_breaker.last_failure_time.isoformat() 
                                   if circuit_breaker.last_failure_time else None
            }
        
        if bulkhead:
            status["bulkhead"] = bulkhead.get_stats()
        
        return status
    
    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all services"""
        return {
            service.value: self.get_service_status(service)
            for service in ServiceType
            if service in self.circuit_breakers
        }


# Global resilience manager instance
resilience_manager = ResilienceManager()


def with_resilience(service: ServiceType, operation: str):
    """Decorator for adding resilience patterns to functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await resilience_manager.execute_with_resilience(
                service, operation, func, *args, **kwargs
            )
        return wrapper
    return decorator


# Retry decorators for different error types
def retry_on_rate_limit(service: ServiceType):
    """Retry decorator specifically for rate limit errors"""
    def should_retry_rate_limit(exception):
        return isinstance(exception, RateLimitError) and exception.service == service
    
    def wait_for_rate_limit(retry_state):
        exception = retry_state.outcome.exception()
        if isinstance(exception, RateLimitError) and exception.retry_after:
            return exception.retry_after
        return wait_exponential(multiplier=2, min=60, max=300)(retry_state)
    
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_for_rate_limit,
        retry=retry_if_exception_type(RateLimitError),
        before_sleep=before_sleep_log(logger, "warning"),
        after=after_log(logger, "info")
    )


def retry_on_transient_errors(service: ServiceType, max_attempts: int = 3):
    """Retry decorator for transient errors"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(multiplier=1, max=60),
        retry=retry_if_exception_type(RetryableError),
        before_sleep=before_sleep_log(logger, "warning"),
        after=after_log(logger, "info")
    )


async def log_error_context(context: ErrorContext) -> None:
    """Log error context for monitoring and debugging"""
    logger.error(
        "Service error occurred",
        **context.to_dict()
    )
    
    # Store error in Redis for monitoring
    try:
        error_key = f"errors:{context.service.value}:{int(time.time())}"
        await redis_client.setex(error_key, 3600, context.to_dict())  # Store for 1 hour
    except Exception as e:
        logger.warning("Failed to store error context in Redis", error=str(e))


def get_resilience_manager() -> ResilienceManager:
    """Get the global resilience manager instance"""
    return resilience_manager