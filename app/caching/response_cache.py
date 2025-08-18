"""
API response caching and compression middleware
"""

import asyncio
import gzip
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge

from app.caching.redis_cache import cache
from app.config import get_settings

logger = logging.getLogger(__name__)

# Prometheus metrics for response caching
response_cache_hits = Counter('response_cache_hits_total', 'Response cache hits', ['endpoint', 'method'])
response_cache_misses = Counter('response_cache_misses_total', 'Response cache misses', ['endpoint', 'method'])
response_compression_ratio = Histogram('response_compression_ratio', 'Response compression ratio', ['endpoint'])
response_size_bytes = Histogram('response_size_bytes', 'Response size in bytes', ['endpoint', 'compressed'])

@dataclass
class CacheRule:
    """Rule for caching API responses"""
    path_pattern: str
    methods: List[str]
    ttl: int
    cache_key_func: Optional[callable] = None
    should_cache_func: Optional[callable] = None
    compress: bool = True
    vary_headers: List[str] = None

class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """Middleware for caching API responses"""
    
    def __init__(self, app, cache_rules: Optional[List[CacheRule]] = None):
        super().__init__(app)
        self.settings = get_settings()
        self.cache_rules = cache_rules or self._get_default_cache_rules()
        self.compression_threshold = 1024  # Compress responses larger than 1KB
        self.max_cache_size = 1024 * 1024  # Don't cache responses larger than 1MB
    
    def _get_default_cache_rules(self) -> List[CacheRule]:
        """Get default caching rules for API endpoints"""
        return [
            CacheRule(
                path_pattern="/health",
                methods=["GET"],
                ttl=60,  # 1 minute
                compress=False
            ),
            CacheRule(
                path_pattern="/api/v1/status/queues",
                methods=["GET"],
                ttl=30,  # 30 seconds
                compress=True
            ),
            CacheRule(
                path_pattern="/api/v1/status/workers",
                methods=["GET"],
                ttl=60,  # 1 minute
                compress=True
            ),
            CacheRule(
                path_pattern="/api/v1/scaling/status",
                methods=["GET"],
                ttl=30,  # 30 seconds
                compress=True
            ),
            CacheRule(
                path_pattern="/api/v1/scaling/metrics/resources",
                methods=["GET"],
                ttl=30,  # 30 seconds
                compress=True
            ),
            CacheRule(
                path_pattern="/metrics",
                methods=["GET"],
                ttl=15,  # 15 seconds
                compress=True,
                should_cache_func=lambda req, resp: resp.status_code == 200
            )
        ]
    
    def _find_matching_rule(self, path: str, method: str) -> Optional[CacheRule]:
        """Find matching cache rule for request"""
        for rule in self.cache_rules:
            if method in rule.methods:
                # Simple pattern matching (could be enhanced with regex)
                if rule.path_pattern == path or path.startswith(rule.path_pattern):
                    return rule
        return None
    
    def _generate_cache_key(self, request: Request, rule: CacheRule) -> str:
        """Generate cache key for request"""
        if rule.cache_key_func:
            return rule.cache_key_func(request)
        
        # Default cache key generation
        key_parts = [
            request.method,
            request.url.path,
            str(sorted(request.query_params.items()))
        ]
        
        # Include vary headers if specified
        if rule.vary_headers:
            header_parts = []
            for header in rule.vary_headers:
                value = request.headers.get(header, '')
                header_parts.append(f"{header}:{value}")
            key_parts.append(":".join(header_parts))
        
        return ":".join(key_parts)
    
    def _should_cache_response(self, request: Request, response: Response, rule: CacheRule) -> bool:
        """Determine if response should be cached"""
        # Check custom should_cache function
        if rule.should_cache_func:
            return rule.should_cache_func(request, response)
        
        # Default caching logic
        if response.status_code != 200:
            return False
        
        # Don't cache responses that are too large
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > self.max_cache_size:
            return False
        
        # Don't cache responses with cache-control: no-cache
        cache_control = response.headers.get('cache-control', '')
        if 'no-cache' in cache_control.lower():
            return False
        
        return True
    
    def _compress_response(self, content: bytes) -> Tuple[bytes, bool]:
        """Compress response content if beneficial"""
        if len(content) < self.compression_threshold:
            return content, False
        
        try:
            compressed = gzip.compress(content)
            
            # Only use compression if it actually reduces size significantly
            compression_ratio = len(compressed) / len(content)
            if compression_ratio < 0.9:  # At least 10% reduction
                return compressed, True
            else:
                return content, False
                
        except Exception as e:
            logger.warning(f"Error compressing response: {e}")
            return content, False
    
    async def dispatch(self, request: Request, call_next):
        """Process request with caching"""
        # Find matching cache rule
        rule = self._find_matching_rule(request.url.path, request.method)
        
        if not rule:
            # No caching rule, proceed normally
            return await call_next(request)
        
        # Generate cache key
        cache_key = self._generate_cache_key(request, rule)
        
        # Try to get cached response
        try:
            cached_data = await cache.get(cache_key, 'api_responses')
            
            if cached_data:
                # Cache hit
                response_cache_hits.labels(
                    endpoint=request.url.path,
                    method=request.method
                ).inc()
                
                # Reconstruct response
                content = cached_data['content']
                headers = cached_data['headers']
                status_code = cached_data['status_code']
                
                # Handle compressed content
                if cached_data.get('compressed', False):
                    content = gzip.decompress(content.encode('latin-1'))
                    headers['content-encoding'] = 'gzip'
                else:
                    content = content.encode('utf-8')
                
                # Add cache headers
                headers['x-cache'] = 'HIT'
                headers['x-cache-key'] = cache_key[:50]  # Truncated for security
                
                response_size_bytes.labels(
                    endpoint=request.url.path,
                    compressed=str(cached_data.get('compressed', False))
                ).observe(len(content))
                
                return Response(
                    content=content,
                    status_code=status_code,
                    headers=headers
                )
                
        except Exception as e:
            logger.warning(f"Error retrieving cached response: {e}")
        
        # Cache miss - execute request
        response_cache_misses.labels(
            endpoint=request.url.path,
            method=request.method
        ).inc()
        
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Check if we should cache this response
        if self._should_cache_response(request, response, rule):
            try:
                # Read response content
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                
                # Compress if enabled and beneficial
                compressed_content, is_compressed = (
                    self._compress_response(response_body) if rule.compress 
                    else (response_body, False)
                )
                
                # Prepare cache data
                cache_data = {
                    'content': compressed_content.decode('latin-1') if is_compressed else response_body.decode('utf-8'),
                    'headers': dict(response.headers),
                    'status_code': response.status_code,
                    'compressed': is_compressed,
                    'cached_at': datetime.utcnow().isoformat(),
                    'duration': duration
                }
                
                # Remove headers that shouldn't be cached
                cache_data['headers'].pop('date', None)
                cache_data['headers'].pop('server', None)
                
                # Cache the response
                await cache.set(cache_key, cache_data, 'api_responses', rule.ttl)
                
                # Record metrics
                if is_compressed:
                    compression_ratio = len(compressed_content) / len(response_body)
                    response_compression_ratio.labels(endpoint=request.url.path).observe(compression_ratio)
                
                response_size_bytes.labels(
                    endpoint=request.url.path,
                    compressed=str(is_compressed)
                ).observe(len(response_body))
                
                # Add cache headers
                response.headers['x-cache'] = 'MISS'
                response.headers['x-cache-ttl'] = str(rule.ttl)
                
                # Create new response with the body we read
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=response.headers,
                    media_type=response.media_type
                )
                
            except Exception as e:
                logger.error(f"Error caching response: {e}")
        
        return response

class ResponseCacheManager:
    """Manager for response cache operations"""
    
    def __init__(self):
        self.cache_rules: List[CacheRule] = []
    
    def add_cache_rule(self, rule: CacheRule):
        """Add a new cache rule"""
        self.cache_rules.append(rule)
        logger.info(f"Added cache rule for {rule.path_pattern} with TTL {rule.ttl}s")
    
    def remove_cache_rule(self, path_pattern: str):
        """Remove cache rule by path pattern"""
        self.cache_rules = [r for r in self.cache_rules if r.path_pattern != path_pattern]
        logger.info(f"Removed cache rule for {path_pattern}")
    
    async def invalidate_endpoint_cache(self, path_pattern: str):
        """Invalidate all cached responses for an endpoint"""
        try:
            # Delete all keys matching the pattern
            pattern = f"*{path_pattern}*"
            deleted_count = await cache.delete_pattern(pattern, 'api_responses')
            logger.info(f"Invalidated {deleted_count} cached responses for {path_pattern}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error invalidating cache for {path_pattern}: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get response cache statistics"""
        try:
            # Get cache statistics
            cache_stats = await cache.get_stats()
            
            # Get response-specific stats
            response_cache_size = 0
            response_cache_keys = 0
            
            # This would require scanning Redis keys, which can be expensive
            # In production, you might want to maintain these stats separately
            
            return {
                'total_cache_stats': cache_stats,
                'response_cache': {
                    'estimated_size_bytes': response_cache_size,
                    'estimated_keys': response_cache_keys,
                    'rules_count': len(self.cache_rules)
                },
                'cache_rules': [
                    {
                        'path_pattern': rule.path_pattern,
                        'methods': rule.methods,
                        'ttl': rule.ttl,
                        'compress': rule.compress
                    }
                    for rule in self.cache_rules
                ],
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    async def warm_endpoint_cache(self, endpoints: List[str], base_url: str = "http://localhost:8000"):
        """Warm up cache for specific endpoints"""
        import aiohttp
        
        warmed_count = 0
        failed_count = 0
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            warmed_count += 1
                            logger.debug(f"Warmed cache for {endpoint}")
                        else:
                            failed_count += 1
                            logger.warning(f"Failed to warm cache for {endpoint}: {response.status}")
                            
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error warming cache for {endpoint}: {e}")
        
        logger.info(f"Cache warming completed: {warmed_count} success, {failed_count} failed")
        return {'warmed': warmed_count, 'failed': failed_count}

# Global response cache manager
response_cache_manager = ResponseCacheManager()

def cache_response(ttl: int, compress: bool = True, vary_headers: Optional[List[str]] = None):
    """Decorator to add caching to specific endpoints"""
    def decorator(func):
        # This would be used with FastAPI route decorators
        # The actual caching is handled by the middleware
        func._cache_config = {
            'ttl': ttl,
            'compress': compress,
            'vary_headers': vary_headers or []
        }
        return func
    return decorator

# Utility functions for cache management

async def invalidate_cache_by_tag(tag: str):
    """Invalidate cache entries by tag"""
    pattern = f"*{tag}*"
    return await cache.delete_pattern(pattern, 'api_responses')

async def get_cached_response_info(cache_key: str) -> Optional[Dict]:
    """Get information about a cached response"""
    try:
        cached_data = await cache.get(cache_key, 'api_responses')
        if cached_data:
            return {
                'cached_at': cached_data.get('cached_at'),
                'status_code': cached_data.get('status_code'),
                'compressed': cached_data.get('compressed', False),
                'content_size': len(cached_data.get('content', '')),
                'headers_count': len(cached_data.get('headers', {}))
            }
        return None
    except Exception as e:
        logger.error(f"Error getting cached response info: {e}")
        return None