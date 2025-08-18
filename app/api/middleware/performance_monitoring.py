"""
Performance monitoring middleware for API response time tracking
"""
import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.monitoring.performance_optimization import record_api_response_time


logger = logging.getLogger(__name__)


class APIPerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor API response times and performance metrics
    """
    
    def __init__(self, app, slow_request_threshold_ms: float = 300.0):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance"""
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Record response time
        record_api_response_time(
            endpoint=request.url.path,
            method=request.method,
            duration_ms=duration_ms
        )
        
        # Log slow requests
        if duration_ms > self.slow_request_threshold_ms:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path} "
                f"(duration: {round(duration_ms, 2)}ms, threshold: {self.slow_request_threshold_ms}ms, "
                f"status: {response.status_code})"
            )
        
        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response


class DatabaseQueryMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor database query performance
    """
    
    def __init__(self, app, enable_query_logging: bool = False):
        super().__init__(app)
        self.enable_query_logging = enable_query_logging
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor database queries during request"""
        if not self.enable_query_logging:
            return await call_next(request)
        
        # This would require SQLAlchemy event listeners to track queries
        # For MVP, we'll just pass through
        return await call_next(request)