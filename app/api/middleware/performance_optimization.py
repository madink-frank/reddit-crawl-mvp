"""
Production Performance Optimization Middleware
Implements caching, compression, and response optimization for production environment
"""

import time
import gzip
import json
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings
from app.monitoring.logging import get_logger

logger = get_logger(__name__)


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """Response caching middleware for production optimization"""
    
    def __init__(self, app: ASGIApp, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
        
        # Start cache cleanup task
        asyncio.create_task(self._cleanup_cache_periodically())
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only cache GET requests for specific endpoints
        if request.method != "GET" or not self._should_cache_endpoint(request.url.path):
            return await call_next(request)
        
        # Generate cache key
        cache_key = self._generate_cache_key(request)
        
        # Check cache
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            self.cache_stats["hits"] += 1
            logger.debug(f"Cache hit for {request.url.path}")
            
            return JSONResponse(
                content=cached_response["content"],
                status_code=cached_response["status_code"],
                headers={
                    **cached_response["headers"],
                    "X-Cache": "HIT",
                    "X-Cache-Age": str(int(time.time() - cached_response["timestamp"]))
                }
            )
        
        # Cache miss - call next middleware
        self.cache_stats["misses"] += 1
        response = await call_next(request)
        
        # Cache successful responses
        if response.status_code == 200 and hasattr(response, 'body'):
            await self._cache_response(cache_key, response)
        
        # Add cache headers
        response.headers["X-Cache"] = "MISS"
        
        return response
    
    def _should_cache_endpoint(self, path: str) -> bool:
        """Determine if endpoint should be cached"""
        cacheable_endpoints = [
            "/health",
            "/metrics",
            "/api/v1/status/queues",
            "/api/v1/status/workers",
            "/api/v1/stats/",
            "/dashboard/api/pipeline/status"
        ]
        
        return any(path.startswith(endpoint) for endpoint in cacheable_endpoints)
    
    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key for request"""
        return f"{request.method}:{request.url.path}:{str(sorted(request.query_params.items()))}"
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if valid"""
        if cache_key not in self.cache:
            return None
        
        cached_item = self.cache[cache_key]
        
        # Check if expired
        if time.time() - cached_item["timestamp"] > self.cache_ttl:
            del self.cache[cache_key]
            self.cache_stats["evictions"] += 1
            return None
        
        return cached_item
    
    async def _cache_response(self, cache_key: str, response: Response) -> None:
        """Cache response"""
        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Parse JSON content
            content = json.loads(body.decode())
            
            # Store in cache
            self.cache[cache_key] = {
                "content": content,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "timestamp": time.time()
            }
            
            # Recreate response body iterator
            response.body_iterator = self._create_body_iterator(body)
            
        except Exception as e:
            logger.warning(f"Failed to cache response for {cache_key}: {e}")
    
    def _create_body_iterator(self, body: bytes):
        """Create body iterator from bytes"""
        async def generate():
            yield body
        return generate()
    
    async def _cleanup_cache_periodically(self) -> None:
        """Periodic cache cleanup"""
        while True:
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes
                
                current_time = time.time()
                expired_keys = [
                    key for key, item in self.cache.items()
                    if current_time - item["timestamp"] > self.cache_ttl
                ]
                
                for key in expired_keys:
                    del self.cache[key]
                    self.cache_stats["evictions"] += 1
                
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                
            except Exception as e:
                logger.error(f"Cache cleanup failed: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            "hit_rate_percent": round(hit_rate, 2),
            "cache_size": len(self.cache),
            "total_requests": total_requests
        }


class CompressionMiddleware(BaseHTTPMiddleware):
    """Response compression middleware for production"""
    
    def __init__(self, app: ASGIApp, minimum_size: int = 1024):
        super().__init__(app)
        self.minimum_size = minimum_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return response
        
        # Check if response should be compressed
        if not self._should_compress_response(response):
            return response
        
        # Compress response
        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Compress if large enough
            if len(body) >= self.minimum_size:
                compressed_body = gzip.compress(body)
                
                # Update headers
                response.headers["content-encoding"] = "gzip"
                response.headers["content-length"] = str(len(compressed_body))
                
                # Create new body iterator
                response.body_iterator = self._create_body_iterator(compressed_body)
                
                logger.debug(f"Compressed response: {len(body)} -> {len(compressed_body)} bytes")
            else:
                # Recreate original body iterator
                response.body_iterator = self._create_body_iterator(body)
        
        except Exception as e:
            logger.warning(f"Response compression failed: {e}")
        
        return response
    
    def _should_compress_response(self, response: Response) -> bool:
        """Check if response should be compressed"""
        # Only compress successful responses
        if response.status_code != 200:
            return False
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        compressible_types = [
            "application/json",
            "text/html",
            "text/css",
            "text/javascript",
            "application/javascript"
        ]
        
        return any(ct in content_type for ct in compressible_types)
    
    def _create_body_iterator(self, body: bytes):
        """Create body iterator from bytes"""
        async def generate():
            yield body
        return generate()


class APIOptimizationMiddleware(BaseHTTPMiddleware):
    """API response optimization middleware"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.response_times = []
        self.slow_endpoints = {}
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Track response times
            self._track_response_time(request.url.path, response_time)
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{response_time:.2f}ms"
            response.headers["X-Timestamp"] = str(int(time.time()))
            
            # Log slow responses
            if response_time > 1000:  # Log responses slower than 1 second
                logger.warning(
                    f"Slow API response: {request.method} {request.url.path} took {response_time:.2f}ms",
                    method=request.method,
                    path=request.url.path,
                    response_time_ms=response_time,
                    status_code=response.status_code
                )
            
            return response
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            logger.error(
                f"API request failed: {request.method} {request.url.path}",
                method=request.method,
                path=request.url.path,
                response_time_ms=response_time,
                error=str(e)
            )
            
            # Return optimized error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "timestamp": datetime.now().isoformat(),
                    "request_id": f"{int(time.time())}-{hash(str(request.url))}"
                },
                headers={
                    "X-Response-Time": f"{response_time:.2f}ms",
                    "X-Error": "true"
                }
            )
    
    def _track_response_time(self, path: str, response_time: float) -> None:
        """Track response times for performance monitoring"""
        # Keep last 100 response times
        self.response_times.append({
            "path": path,
            "response_time": response_time,
            "timestamp": time.time()
        })
        
        if len(self.response_times) > 100:
            self.response_times.pop(0)
        
        # Track slow endpoints
        if response_time > 500:  # Endpoints slower than 500ms
            if path not in self.slow_endpoints:
                self.slow_endpoints[path] = []
            
            self.slow_endpoints[path].append(response_time)
            
            # Keep only last 10 slow responses per endpoint
            if len(self.slow_endpoints[path]) > 10:
                self.slow_endpoints[path].pop(0)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.response_times:
            return {"message": "No performance data available"}
        
        recent_times = [rt["response_time"] for rt in self.response_times[-50:]]  # Last 50 requests
        
        stats = {
            "total_requests": len(self.response_times),
            "average_response_time_ms": sum(recent_times) / len(recent_times),
            "min_response_time_ms": min(recent_times),
            "max_response_time_ms": max(recent_times),
            "slow_endpoints": {
                path: {
                    "count": len(times),
                    "average_ms": sum(times) / len(times),
                    "max_ms": max(times)
                }
                for path, times in self.slow_endpoints.items()
            }
        }
        
        # Calculate percentiles
        sorted_times = sorted(recent_times)
        length = len(sorted_times)
        
        if length > 0:
            stats["p50_response_time_ms"] = sorted_times[int(length * 0.5)]
            stats["p95_response_time_ms"] = sorted_times[int(length * 0.95)]
            stats["p99_response_time_ms"] = sorted_times[int(length * 0.99)]
        
        return stats


class DatabaseConnectionPoolOptimizer:
    """Database connection pool optimization for production"""
    
    def __init__(self):
        self.connection_stats = {
            "active_connections": 0,
            "total_queries": 0,
            "slow_queries": 0,
            "failed_queries": 0,
            "average_query_time_ms": 0.0
        }
        self.query_times = []
    
    async def optimize_query(self, query_func: Callable, *args, **kwargs) -> Any:
        """Optimize database query execution"""
        start_time = time.time()
        
        try:
            self.connection_stats["active_connections"] += 1
            
            # Execute query
            result = await query_func(*args, **kwargs)
            
            # Track timing
            query_time = (time.time() - start_time) * 1000
            self._track_query_time(query_time)
            
            self.connection_stats["total_queries"] += 1
            
            if query_time > 1000:  # Slow query threshold: 1 second
                self.connection_stats["slow_queries"] += 1
                logger.warning(f"Slow database query: {query_time:.2f}ms")
            
            return result
            
        except Exception as e:
            self.connection_stats["failed_queries"] += 1
            logger.error(f"Database query failed: {e}")
            raise
        
        finally:
            self.connection_stats["active_connections"] -= 1
    
    def _track_query_time(self, query_time: float) -> None:
        """Track query execution times"""
        self.query_times.append(query_time)
        
        # Keep only last 100 query times
        if len(self.query_times) > 100:
            self.query_times.pop(0)
        
        # Update average
        if self.query_times:
            self.connection_stats["average_query_time_ms"] = sum(self.query_times) / len(self.query_times)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get database connection statistics"""
        return self.connection_stats.copy()


# Global instances for production optimization
response_cache_middleware = None
compression_middleware = None
api_optimization_middleware = None
db_optimizer = DatabaseConnectionPoolOptimizer()


def setup_production_optimizations(app) -> None:
    """Setup production optimizations"""
    global response_cache_middleware, compression_middleware, api_optimization_middleware
    
    settings = get_settings()
    
    if settings.environment == "production":
        logger.info("Setting up production optimizations...")
        
        # Add optimization middleware
        response_cache_middleware = ResponseCacheMiddleware(app, cache_ttl=300)
        compression_middleware = CompressionMiddleware(app, minimum_size=1024)
        api_optimization_middleware = APIOptimizationMiddleware(app)
        
        # Add middleware to app
        app.add_middleware(ResponseCacheMiddleware, cache_ttl=300)
        app.add_middleware(CompressionMiddleware, minimum_size=1024)
        app.add_middleware(APIOptimizationMiddleware)
        
        logger.info("Production optimizations enabled")


def get_optimization_stats() -> Dict[str, Any]:
    """Get optimization statistics"""
    stats = {
        "environment": get_settings().environment,
        "optimizations_enabled": get_settings().environment == "production"
    }
    
    if response_cache_middleware:
        stats["cache"] = response_cache_middleware.get_cache_stats()
    
    if api_optimization_middleware:
        stats["performance"] = api_optimization_middleware.get_performance_stats()
    
    stats["database"] = db_optimizer.get_connection_stats()
    
    return stats