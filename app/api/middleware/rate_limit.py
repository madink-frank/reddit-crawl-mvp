"""
Rate limiting middleware
Implements token bucket and sliding window rate limiting
"""
import time
import asyncio
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from app.config import get_settings
from app.infrastructure import get_redis_client


logger = structlog.get_logger(__name__)


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window"""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict[str, int]]:
        """Check if request is allowed and return rate limit info"""
        async with self.lock:
            now = time.time()
            window_start = now - window_seconds
            
            # Clean old requests
            request_times = self.requests[key]
            while request_times and request_times[0] < window_start:
                request_times.popleft()
            
            # Check if limit exceeded
            current_count = len(request_times)
            allowed = current_count < limit
            
            if allowed:
                request_times.append(now)
            
            # Calculate reset time
            reset_time = int(window_start + window_seconds) if request_times else int(now + window_seconds)
            
            return allowed, {
                "limit": limit,
                "remaining": max(0, limit - current_count - (1 if allowed else 0)),
                "reset": reset_time,
                "retry_after": max(1, reset_time - int(now)) if not allowed else 0
            }


class RedisRateLimiter:
    """Redis-based rate limiter using sliding window log"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict[str, int]]:
        """Check if request is allowed using Redis sliding window"""
        now = time.time()
        window_start = now - window_seconds
        
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request with score as timestamp
        pipe.zadd(key, {str(now): now})
        
        # Set expiration
        pipe.expire(key, window_seconds + 1)
        
        results = await pipe.execute()
        current_count = results[1]
        
        # Check if limit exceeded
        allowed = current_count < limit
        
        if not allowed:
            # Remove the request we just added since it's not allowed
            await self.redis.zrem(key, str(now))
        
        # Calculate reset time
        oldest_request = await self.redis.zrange(key, 0, 0, withscores=True)
        if oldest_request:
            reset_time = int(oldest_request[0][1] + window_seconds)
        else:
            reset_time = int(now + window_seconds)
        
        return allowed, {
            "limit": limit,
            "remaining": max(0, limit - current_count - (1 if allowed else 0)),
            "reset": reset_time,
            "retry_after": max(1, reset_time - int(now)) if not allowed else 0
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with multiple strategies"""
    
    def __init__(
        self,
        app,
        default_limit: int = 100,
        default_window: int = 60,
        path_limits: Dict[str, Tuple[int, int]] = None,
        use_redis: bool = True
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        self.path_limits = path_limits or {}
        self.use_redis = use_redis
        
        # Initialize rate limiter
        if use_redis:
            try:
                redis_client = get_redis_client()
                self.limiter = RedisRateLimiter(redis_client)
                logger.info("Using Redis rate limiter")
            except Exception as e:
                logger.warning("Failed to initialize Redis rate limiter, falling back to in-memory", error=str(e))
                self.limiter = InMemoryRateLimiter()
        else:
            self.limiter = InMemoryRateLimiter()
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/health/ready", "/health/live"]:
            return await call_next(request)
        
        # Get rate limit settings for this path
        limit, window = self._get_rate_limit(request.url.path)
        
        # Generate rate limit key
        key = self._generate_key(request)
        
        try:
            # Check rate limit
            allowed, info = await self.limiter.is_allowed(key, limit, window)
            
            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    key=key,
                    path=request.url.path,
                    limit=limit,
                    window=window,
                    client_ip=request.client.host if request.client else "unknown"
                )
                
                return Response(
                    content="Rate limit exceeded",
                    status_code=429,
                    headers={
                        "Content-Type": "text/plain",
                        "X-RateLimit-Limit": str(info["limit"]),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(info["reset"]),
                        "Retry-After": str(info["retry_after"])
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to response
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(info["reset"])
            
            return response
            
        except Exception as e:
            logger.error("Rate limiting error", error=str(e), key=key)
            # Continue without rate limiting on error
            return await call_next(request)
    
    def _get_rate_limit(self, path: str) -> Tuple[int, int]:
        """Get rate limit settings for path"""
        # Check for specific path limits
        for path_pattern, (limit, window) in self.path_limits.items():
            if path.startswith(path_pattern):
                return limit, window
        
        # Return default limits
        return self.default_limit, self.default_window
    
    def _generate_key(self, request: Request) -> str:
        """Generate rate limit key for request"""
        # Use IP address as primary identifier
        client_ip = self._get_client_ip(request)
        
        # Add user ID if authenticated
        user_id = getattr(request.state, "user", {}).get("sub")
        if user_id:
            return f"rate_limit:user:{user_id}"
        
        # Fall back to IP
        return f"rate_limit:ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check X-Forwarded-For header
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"


class AdaptiveRateLimitMiddleware(BaseHTTPMiddleware):
    """Adaptive rate limiting based on system load"""
    
    def __init__(
        self,
        app,
        base_limit: int = 100,
        base_window: int = 60,
        load_threshold: float = 0.8
    ):
        super().__init__(app)
        self.base_limit = base_limit
        self.base_window = base_window
        self.load_threshold = load_threshold
        self.rate_limiter = RateLimitMiddleware(
            app, 
            default_limit=base_limit, 
            default_window=base_window
        )
    
    async def dispatch(self, request: Request, call_next):
        # Get current system load
        load_factor = await self._get_load_factor()
        
        # Adjust rate limits based on load
        if load_factor > self.load_threshold:
            # Reduce limits when system is under load
            adjustment_factor = max(0.1, 1.0 - (load_factor - self.load_threshold))
            adjusted_limit = int(self.base_limit * adjustment_factor)
            
            logger.info(
                "Adaptive rate limiting active",
                load_factor=load_factor,
                original_limit=self.base_limit,
                adjusted_limit=adjusted_limit
            )
            
            # Temporarily adjust the rate limiter
            original_limit = self.rate_limiter.default_limit
            self.rate_limiter.default_limit = adjusted_limit
            
            try:
                response = await self.rate_limiter.dispatch(request, call_next)
            finally:
                # Restore original limit
                self.rate_limiter.default_limit = original_limit
            
            return response
        
        # Normal rate limiting
        return await self.rate_limiter.dispatch(request, call_next)
    
    async def _get_load_factor(self) -> float:
        """Get current system load factor (0.0 to 1.0)"""
        try:
            import psutil
            
            # Combine CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            # Weight CPU more heavily
            load_factor = (cpu_percent * 0.7 + memory_percent * 0.3) / 100.0
            
            return min(1.0, load_factor)
            
        except Exception as e:
            logger.warning("Failed to get system load", error=str(e))
            return 0.0


def create_rate_limit_middleware(app, settings: Optional[Dict] = None):
    """Factory function to create rate limit middleware"""
    if not settings:
        app_settings = get_settings()
        settings = {
            "default_limit": app_settings.rate_limit_requests,
            "default_window": app_settings.rate_limit_window,
            "path_limits": {
                "/api/v1/collect/trigger": (10, 60),  # 10 requests per minute for triggers
                "/api/v1/process/trigger": (10, 60),
                "/api/v1/publish/trigger": (10, 60),
                "/api/v1/status/": (60, 60),  # 60 requests per minute for status
                "/metrics": (30, 60),  # 30 requests per minute for metrics
            }
        }
    
    return RateLimitMiddleware(
        app,
        default_limit=settings["default_limit"],
        default_window=settings["default_window"],
        path_limits=settings.get("path_limits", {}),
        use_redis=True
    )