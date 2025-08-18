"""
Redis connection management for Reddit Ghost Publisher
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RedisClient:
    """Async Redis client with connection pooling and error handling"""
    
    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Initialize Redis connection pool"""
        try:
            redis_url = settings.redis_url or "redis://localhost:6379/0"
            
            self._pool = ConnectionPool.from_url(
                redis_url,
                max_connections=settings.redis_max_connections,
                retry_on_timeout=True,
                retry_on_error=[ConnectionError, TimeoutError],
                health_check_interval=30,
                socket_keepalive=True,
                socket_keepalive_options={},
                decode_responses=True
            )
            
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            self._connected = True
            
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection"""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._connected = False
        logger.info("Redis connection closed")
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._connected
    
    async def ping(self) -> bool:
        """Test Redis connection"""
        try:
            if not self._client:
                return False
            await self._client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    # String operations
    async def set(
        self, 
        key: str, 
        value: Union[str, int, float, dict, list], 
        ex: Optional[int] = None,
        nx: bool = False
    ) -> bool:
        """Set a key-value pair with optional expiration"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            result = await self._client.set(key, value, ex=ex, nx=nx)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        try:
            value = await self._client.get(key)
            if value is None:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            return None
    
    async def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        try:
            return await self._client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE failed for keys {keys}: {e}")
            return 0
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment key by amount"""
        try:
            return await self._client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis INCR failed for key {key}: {e}")
            return amount
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return bool(await self._client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS failed for key {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for a key"""
        try:
            return bool(await self._client.expire(key, seconds))
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key {key}: {e}")
            return False
    
    # Hash operations
    async def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields"""
        try:
            # Convert dict/list values to JSON
            json_mapping = {}
            for k, v in mapping.items():
                if isinstance(v, (dict, list)):
                    json_mapping[k] = json.dumps(v)
                else:
                    json_mapping[k] = v
            
            return await self._client.hset(name, mapping=json_mapping)
        except Exception as e:
            logger.error(f"Redis HSET failed for hash {name}: {e}")
            return 0
    
    async def hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field value"""
        try:
            value = await self._client.hget(name, key)
            if value is None:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis HGET failed for hash {name}, key {key}: {e}")
            return None
    
    async def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all hash fields"""
        try:
            result = await self._client.hgetall(name)
            
            # Parse JSON values
            parsed_result = {}
            for k, v in result.items():
                try:
                    parsed_result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    parsed_result[k] = v
            
            return parsed_result
        except Exception as e:
            logger.error(f"Redis HGETALL failed for hash {name}: {e}")
            return {}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields"""
        try:
            return await self._client.hdel(name, *keys)
        except Exception as e:
            logger.error(f"Redis HDEL failed for hash {name}, keys {keys}: {e}")
            return 0
    
    # List operations
    async def lpush(self, name: str, *values: Any) -> int:
        """Push values to the left of a list"""
        try:
            json_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    json_values.append(json.dumps(value))
                else:
                    json_values.append(value)
            
            return await self._client.lpush(name, *json_values)
        except Exception as e:
            logger.error(f"Redis LPUSH failed for list {name}: {e}")
            return 0
    
    async def rpop(self, name: str) -> Optional[Any]:
        """Pop value from the right of a list"""
        try:
            value = await self._client.rpop(name)
            if value is None:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis RPOP failed for list {name}: {e}")
            return None
    
    async def llen(self, name: str) -> int:
        """Get list length"""
        try:
            return await self._client.llen(name)
        except Exception as e:
            logger.error(f"Redis LLEN failed for list {name}: {e}")
            return 0
    
    # Sorted set operations
    async def zadd(self, name: str, mapping: Dict[str, float]) -> int:
        """Add members to sorted set"""
        try:
            return await self._client.zadd(name, mapping)
        except Exception as e:
            logger.error(f"Redis ZADD failed for sorted set {name}: {e}")
            return 0
    
    async def zrange(
        self, 
        name: str, 
        start: int, 
        end: int, 
        withscores: bool = False
    ) -> List[Any]:
        """Get range from sorted set"""
        try:
            return await self._client.zrange(name, start, end, withscores=withscores)
        except Exception as e:
            logger.error(f"Redis ZRANGE failed for sorted set {name}: {e}")
            return []
    
    async def zrem(self, name: str, *values: str) -> int:
        """Remove members from sorted set"""
        try:
            return await self._client.zrem(name, *values)
        except Exception as e:
            logger.error(f"Redis ZREM failed for sorted set {name}: {e}")
            return 0
    
    # Queue monitoring operations
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        try:
            stats = {}
            
            # Get queue lengths
            for queue_name in ["collect", "process", "publish"]:
                pending_key = f"{queue_name}:pending"
                failed_key = f"failed:{queue_name}"
                
                stats[f"{queue_name}_pending"] = await self.llen(pending_key)
                stats[f"{queue_name}_failed"] = await self.llen(failed_key)
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}
    
    # Rate limiting operations
    async def check_rate_limit(
        self, 
        key: str, 
        limit: int, 
        window: int
    ) -> bool:
        """Check if rate limit is exceeded"""
        try:
            current_time = int(asyncio.get_event_loop().time())
            window_start = current_time - window
            
            # Remove old entries
            await self._client.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            current_count = await self._client.zcard(key)
            
            if current_count >= limit:
                return False
            
            # Add current request
            await self._client.zadd(key, {str(current_time): current_time})
            await self._client.expire(key, window)
            
            return True
        except Exception as e:
            logger.error(f"Rate limit check failed for key {key}: {e}")
            return False
    
    # Cache operations
    async def cache_set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 3600
    ) -> bool:
        """Set cache with TTL"""
        cache_key = f"cache:{key}"
        return await self.set(cache_key, value, ex=ttl)
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get from cache"""
        cache_key = f"cache:{key}"
        return await self.get(cache_key)
    
    async def cache_delete(self, key: str) -> int:
        """Delete from cache"""
        cache_key = f"cache:{key}"
        return await self.delete(cache_key)


# Global Redis client instance
redis_client = RedisClient()


@asynccontextmanager
async def get_redis():
    """Context manager for Redis operations"""
    if not redis_client.is_connected:
        await redis_client.connect()
    
    try:
        yield redis_client
    except Exception as e:
        logger.error(f"Redis operation failed: {e}")
        raise
    finally:
        # Connection stays open for reuse
        pass


async def init_redis() -> None:
    """Initialize Redis connection"""
    await redis_client.connect()


async def close_redis() -> None:
    """Close Redis connection"""
    await redis_client.disconnect()


# Health check function
async def redis_health_check() -> Dict[str, Any]:
    """Check Redis health status"""
    try:
        if not redis_client.is_connected:
            return {
                "status": "unhealthy",
                "error": "Not connected",
                "connected": False
            }
        
        # Test basic operations
        test_key = "health_check_test"
        await redis_client.set(test_key, "test_value", ex=10)
        value = await redis_client.get(test_key)
        await redis_client.delete(test_key)
        
        if value != "test_value":
            return {
                "status": "unhealthy", 
                "error": "Read/write test failed",
                "connected": True
            }
        
        # Get queue stats
        queue_stats = await redis_client.get_queue_stats()
        
        return {
            "status": "healthy",
            "connected": True,
            "queue_stats": queue_stats
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "connected": False
        }