"""
Redis-based caching implementation for performance optimization
"""

import asyncio
import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass

import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge

from app.config import get_settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

# Prometheus metrics for caching
cache_hits = Counter('cache_hits_total', 'Total cache hits', ['cache_type', 'key_pattern'])
cache_misses = Counter('cache_misses_total', 'Total cache misses', ['cache_type', 'key_pattern'])
cache_operations = Histogram('cache_operation_duration_seconds', 'Cache operation duration', ['operation', 'cache_type'])
cache_size = Gauge('cache_size_bytes', 'Current cache size in bytes', ['cache_type'])
cache_keys_count = Gauge('cache_keys_count', 'Number of keys in cache', ['cache_type'])

@dataclass
class CacheConfig:
    """Configuration for cache behavior"""
    default_ttl: int = 3600  # 1 hour
    max_key_length: int = 250
    compression_threshold: int = 1024  # Compress values larger than 1KB
    serialization_method: str = 'json'  # 'json' or 'pickle'
    key_prefix: str = 'reddit_publisher'
    
    # Cache type specific TTLs
    ttl_mapping: Dict[str, int] = None
    
    def __post_init__(self):
        if self.ttl_mapping is None:
            self.ttl_mapping = {
                'reddit_posts': 900,      # 15 minutes
                'api_responses': 300,     # 5 minutes
                'user_sessions': 3600,    # 1 hour
                'processed_content': 7200, # 2 hours
                'ghost_tags': 1800,       # 30 minutes
                'subreddit_info': 3600,   # 1 hour
                'rate_limits': 60,        # 1 minute
                'metrics': 30,            # 30 seconds
                'health_checks': 60       # 1 minute
            }

class RedisCache:
    """High-performance Redis cache with advanced features"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.redis_client = redis_client
        self.settings = get_settings()
        
        # Cache statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    def _make_key(self, key: str, cache_type: str = 'default') -> str:
        """Create a properly formatted cache key"""
        # Sanitize key
        safe_key = key.replace(' ', '_').replace(':', '_')
        
        # Truncate if too long
        if len(safe_key) > self.config.max_key_length:
            safe_key = safe_key[:self.config.max_key_length]
        
        return f"{self.config.key_prefix}:{cache_type}:{safe_key}"
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for storage"""
        try:
            if self.config.serialization_method == 'pickle':
                serialized = pickle.dumps(value)
            else:  # json
                serialized = json.dumps(value, default=str).encode('utf-8')
            
            # Compress if value is large
            if len(serialized) > self.config.compression_threshold:
                import gzip
                serialized = gzip.compress(serialized)
                # Add compression marker
                serialized = b'GZIP:' + serialized
            
            return serialized
            
        except Exception as e:
            logger.error(f"Error serializing cache value: {e}")
            raise
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from storage"""
        try:
            # Check for compression marker
            if data.startswith(b'GZIP:'):
                import gzip
                data = gzip.decompress(data[5:])  # Remove 'GZIP:' prefix
            
            if self.config.serialization_method == 'pickle':
                return pickle.loads(data)
            else:  # json
                return json.loads(data.decode('utf-8'))
                
        except Exception as e:
            logger.error(f"Error deserializing cache value: {e}")
            raise
    
    def _get_ttl(self, cache_type: str) -> int:
        """Get TTL for cache type"""
        return self.config.ttl_mapping.get(cache_type, self.config.default_ttl)
    
    async def get(self, key: str, cache_type: str = 'default') -> Optional[Any]:
        """Get value from cache"""
        cache_key = self._make_key(key, cache_type)
        
        with cache_operations.labels(operation='get', cache_type=cache_type).time():
            try:
                data = await self.redis_client.get(cache_key)
                
                if data is None:
                    cache_misses.labels(cache_type=cache_type, key_pattern=key[:20]).inc()
                    self._stats['misses'] += 1
                    return None
                
                value = self._deserialize_value(data)
                cache_hits.labels(cache_type=cache_type, key_pattern=key[:20]).inc()
                self._stats['hits'] += 1
                
                logger.debug(f"Cache hit for key: {cache_key}")
                return value
                
            except Exception as e:
                logger.error(f"Error getting cache value for key {cache_key}: {e}")
                self._stats['errors'] += 1
                return None
    
    async def set(self, key: str, value: Any, cache_type: str = 'default', 
                  ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        cache_key = self._make_key(key, cache_type)
        ttl = ttl or self._get_ttl(cache_type)
        
        with cache_operations.labels(operation='set', cache_type=cache_type).time():
            try:
                serialized_value = self._serialize_value(value)
                
                await self.redis_client.setex(cache_key, ttl, serialized_value)
                
                self._stats['sets'] += 1
                logger.debug(f"Cache set for key: {cache_key}, TTL: {ttl}")
                return True
                
            except Exception as e:
                logger.error(f"Error setting cache value for key {cache_key}: {e}")
                self._stats['errors'] += 1
                return False
    
    async def delete(self, key: str, cache_type: str = 'default') -> bool:
        """Delete value from cache"""
        cache_key = self._make_key(key, cache_type)
        
        with cache_operations.labels(operation='delete', cache_type=cache_type).time():
            try:
                result = await self.redis_client.delete(cache_key)
                self._stats['deletes'] += 1
                logger.debug(f"Cache delete for key: {cache_key}")
                return result > 0
                
            except Exception as e:
                logger.error(f"Error deleting cache value for key {cache_key}: {e}")
                self._stats['errors'] += 1
                return False
    
    async def exists(self, key: str, cache_type: str = 'default') -> bool:
        """Check if key exists in cache"""
        cache_key = self._make_key(key, cache_type)
        
        try:
            result = await self.redis_client.exists(cache_key)
            return result > 0
        except Exception as e:
            logger.error(f"Error checking cache existence for key {cache_key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int, cache_type: str = 'default') -> bool:
        """Set expiration time for key"""
        cache_key = self._make_key(key, cache_type)
        
        try:
            result = await self.redis_client.expire(cache_key, ttl)
            return result
        except Exception as e:
            logger.error(f"Error setting expiration for key {cache_key}: {e}")
            return False
    
    async def get_many(self, keys: List[str], cache_type: str = 'default') -> Dict[str, Any]:
        """Get multiple values from cache"""
        cache_keys = [self._make_key(key, cache_type) for key in keys]
        
        with cache_operations.labels(operation='mget', cache_type=cache_type).time():
            try:
                values = await self.redis_client.mget(cache_keys)
                
                result = {}
                for i, (original_key, value) in enumerate(zip(keys, values)):
                    if value is not None:
                        try:
                            result[original_key] = self._deserialize_value(value)
                            cache_hits.labels(cache_type=cache_type, key_pattern=original_key[:20]).inc()
                        except Exception as e:
                            logger.error(f"Error deserializing value for key {original_key}: {e}")
                    else:
                        cache_misses.labels(cache_type=cache_type, key_pattern=original_key[:20]).inc()
                
                self._stats['hits'] += len(result)
                self._stats['misses'] += len(keys) - len(result)
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting multiple cache values: {e}")
                self._stats['errors'] += 1
                return {}
    
    async def set_many(self, data: Dict[str, Any], cache_type: str = 'default', 
                       ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache"""
        ttl = ttl or self._get_ttl(cache_type)
        
        with cache_operations.labels(operation='mset', cache_type=cache_type).time():
            try:
                # Use pipeline for better performance
                pipe = self.redis_client.pipeline()
                
                for key, value in data.items():
                    cache_key = self._make_key(key, cache_type)
                    serialized_value = self._serialize_value(value)
                    pipe.setex(cache_key, ttl, serialized_value)
                
                await pipe.execute()
                
                self._stats['sets'] += len(data)
                logger.debug(f"Cache mset for {len(data)} keys, TTL: {ttl}")
                return True
                
            except Exception as e:
                logger.error(f"Error setting multiple cache values: {e}")
                self._stats['errors'] += 1
                return False
    
    async def delete_pattern(self, pattern: str, cache_type: str = 'default') -> int:
        """Delete all keys matching pattern"""
        search_pattern = self._make_key(pattern, cache_type)
        
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=search_pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                self._stats['deletes'] += deleted
                logger.info(f"Deleted {deleted} keys matching pattern: {search_pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Error deleting keys with pattern {search_pattern}: {e}")
            self._stats['errors'] += 1
            return 0
    
    async def clear_cache_type(self, cache_type: str) -> int:
        """Clear all keys for a specific cache type"""
        return await self.delete_pattern('*', cache_type)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            info = await self.redis_client.info('memory')
            keyspace_info = await self.redis_client.info('keyspace')
            
            # Count keys by cache type
            cache_type_counts = {}
            for cache_type in self.config.ttl_mapping.keys():
                pattern = f"{self.config.key_prefix}:{cache_type}:*"
                count = 0
                async for _ in self.redis_client.scan_iter(match=pattern, count=100):
                    count += 1
                cache_type_counts[cache_type] = count
                
                # Update Prometheus metrics
                cache_keys_count.labels(cache_type=cache_type).set(count)
            
            return {
                'local_stats': self._stats.copy(),
                'redis_memory_usage': info.get('used_memory', 0),
                'redis_memory_human': info.get('used_memory_human', '0B'),
                'cache_type_counts': cache_type_counts,
                'total_keys': sum(cache_type_counts.values()),
                'hit_rate': (self._stats['hits'] / (self._stats['hits'] + self._stats['misses'])) 
                           if (self._stats['hits'] + self._stats['misses']) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        try:
            start_time = time.time()
            
            # Test basic operations
            test_key = f"health_check_{int(time.time())}"
            test_value = {"timestamp": datetime.utcnow().isoformat(), "test": True}
            
            # Test set
            set_success = await self.set(test_key, test_value, 'health_checks', 60)
            
            # Test get
            retrieved_value = await self.get(test_key, 'health_checks')
            get_success = retrieved_value is not None and retrieved_value.get('test') is True
            
            # Test delete
            delete_success = await self.delete(test_key, 'health_checks')
            
            end_time = time.time()
            
            return {
                'healthy': set_success and get_success and delete_success,
                'operations': {
                    'set': set_success,
                    'get': get_success,
                    'delete': delete_success
                },
                'response_time_ms': round((end_time - start_time) * 1000, 2),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

# Global cache instance
cache = RedisCache()

def cached(cache_type: str = 'default', ttl: Optional[int] = None, 
           key_func: Optional[Callable] = None):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [func.__name__]
                key_parts.extend([str(arg) for arg in args])
                key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
                cache_key = ":".join(key_parts)
            
            # Try to get from cache
            cached_result = await cache.get(cache_key, cache_type)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, cache_type, ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we need to handle async cache operations
            loop = asyncio.get_event_loop()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                key_parts = [func.__name__]
                key_parts.extend([str(arg) for arg in args])
                key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
                cache_key = ":".join(key_parts)
            
            # Try to get from cache
            try:
                cached_result = loop.run_until_complete(cache.get(cache_key, cache_type))
                if cached_result is not None:
                    return cached_result
            except Exception as e:
                logger.warning(f"Error getting cached result: {e}")
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            
            try:
                loop.run_until_complete(cache.set(cache_key, result, cache_type, ttl))
            except Exception as e:
                logger.warning(f"Error caching result: {e}")
            
            return result
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class CacheManager:
    """Manager for cache operations and maintenance"""
    
    def __init__(self, cache_instance: Optional[RedisCache] = None):
        self.cache = cache_instance or cache
        self._maintenance_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start_maintenance(self, interval_seconds: int = 300):
        """Start cache maintenance task"""
        if self._running:
            logger.warning("Cache maintenance already running")
            return
        
        self._running = True
        self._maintenance_task = asyncio.create_task(
            self._maintenance_loop(interval_seconds)
        )
        logger.info("Cache maintenance started")
    
    async def stop_maintenance(self):
        """Stop cache maintenance task"""
        if not self._running:
            return
        
        self._running = False
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Cache maintenance stopped")
    
    async def _maintenance_loop(self, interval_seconds: int):
        """Cache maintenance loop"""
        while self._running:
            try:
                await self._perform_maintenance()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache maintenance: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _perform_maintenance(self):
        """Perform cache maintenance tasks"""
        try:
            # Get cache statistics
            stats = await self.cache.get_stats()
            
            # Update Prometheus metrics
            if 'redis_memory_usage' in stats:
                cache_size.labels(cache_type='total').set(stats['redis_memory_usage'])
            
            # Log cache statistics
            logger.info(
                "Cache maintenance completed",
                hit_rate=stats.get('hit_rate', 0),
                total_keys=stats.get('total_keys', 0),
                memory_usage=stats.get('redis_memory_human', '0B')
            )
            
            # Clean up expired health check keys (just in case)
            await self.cache.delete_pattern('health_check_*', 'health_checks')
            
        except Exception as e:
            logger.error(f"Error performing cache maintenance: {e}")
    
    async def warm_cache(self, cache_type: str, data: Dict[str, Any], 
                        ttl: Optional[int] = None):
        """Warm up cache with initial data"""
        try:
            success = await self.cache.set_many(data, cache_type, ttl)
            if success:
                logger.info(f"Cache warmed for type '{cache_type}' with {len(data)} items")
            else:
                logger.error(f"Failed to warm cache for type '{cache_type}'")
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
    
    async def invalidate_cache_type(self, cache_type: str):
        """Invalidate all cache entries of a specific type"""
        try:
            deleted_count = await self.cache.clear_cache_type(cache_type)
            logger.info(f"Invalidated {deleted_count} cache entries for type '{cache_type}'")
        except Exception as e:
            logger.error(f"Error invalidating cache type '{cache_type}': {e}")

# Global cache manager
cache_manager = CacheManager()