"""
Unit tests for Redis client
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from redis.exceptions import ConnectionError, TimeoutError

from app.redis_client import RedisClient, get_redis, init_redis, close_redis, redis_health_check


class TestRedisClient:
    """Test Redis client functionality"""
    
    @pytest.fixture
    def redis_client(self):
        """Create Redis client instance"""
        return RedisClient()
    
    @pytest.mark.asyncio
    async def test_connect_success(self, redis_client):
        """Test successful Redis connection"""
        with patch('redis.asyncio.ConnectionPool.from_url') as mock_pool:
            with patch('redis.asyncio.Redis') as mock_redis:
                mock_client = AsyncMock()
                mock_client.ping.return_value = True
                mock_redis.return_value = mock_client
                
                await redis_client.connect()
                
                assert redis_client.is_connected is True
                mock_pool.assert_called_once()
                mock_redis.assert_called_once()
                mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, redis_client):
        """Test Redis connection failure"""
        with patch('redis.asyncio.ConnectionPool.from_url') as mock_pool:
            with patch('redis.asyncio.Redis') as mock_redis:
                mock_client = AsyncMock()
                mock_client.ping.side_effect = ConnectionError("Connection failed")
                mock_redis.return_value = mock_client
                
                with pytest.raises(ConnectionError):
                    await redis_client.connect()
                
                assert redis_client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self, redis_client):
        """Test Redis disconnection"""
        mock_client = AsyncMock()
        mock_pool = AsyncMock()
        
        redis_client._client = mock_client
        redis_client._pool = mock_pool
        redis_client._connected = True
        
        await redis_client.disconnect()
        
        mock_client.close.assert_called_once()
        mock_pool.disconnect.assert_called_once()
        assert redis_client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_ping_success(self, redis_client):
        """Test successful ping"""
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        redis_client._client = mock_client
        
        result = await redis_client.ping()
        
        assert result is True
        mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ping_failure(self, redis_client):
        """Test ping failure"""
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("Ping failed")
        redis_client._client = mock_client
        
        result = await redis_client.ping()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_set_string_value(self, redis_client):
        """Test setting string value"""
        mock_client = AsyncMock()
        mock_client.set.return_value = True
        redis_client._client = mock_client
        
        result = await redis_client.set("test_key", "test_value", ex=3600)
        
        assert result is True
        mock_client.set.assert_called_once_with("test_key", "test_value", ex=3600, nx=False)
    
    @pytest.mark.asyncio
    async def test_set_dict_value(self, redis_client):
        """Test setting dictionary value"""
        mock_client = AsyncMock()
        mock_client.set.return_value = True
        redis_client._client = mock_client
        
        test_dict = {"key": "value", "number": 42}
        result = await redis_client.set("test_key", test_dict)
        
        assert result is True
        expected_json = json.dumps(test_dict)
        mock_client.set.assert_called_once_with("test_key", expected_json, ex=None, nx=False)
    
    @pytest.mark.asyncio
    async def test_get_string_value(self, redis_client):
        """Test getting string value"""
        mock_client = AsyncMock()
        mock_client.get.return_value = "test_value"
        redis_client._client = mock_client
        
        result = await redis_client.get("test_key")
        
        assert result == "test_value"
        mock_client.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_get_json_value(self, redis_client):
        """Test getting JSON value"""
        mock_client = AsyncMock()
        test_dict = {"key": "value", "number": 42}
        mock_client.get.return_value = json.dumps(test_dict)
        redis_client._client = mock_client
        
        result = await redis_client.get("test_key")
        
        assert result == test_dict
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, redis_client):
        """Test getting nonexistent key"""
        mock_client = AsyncMock()
        mock_client.get.return_value = None
        redis_client._client = mock_client
        
        result = await redis_client.get("nonexistent_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_keys(self, redis_client):
        """Test deleting keys"""
        mock_client = AsyncMock()
        mock_client.delete.return_value = 2
        redis_client._client = mock_client
        
        result = await redis_client.delete("key1", "key2")
        
        assert result == 2
        mock_client.delete.assert_called_once_with("key1", "key2")
    
    @pytest.mark.asyncio
    async def test_exists_key(self, redis_client):
        """Test checking key existence"""
        mock_client = AsyncMock()
        mock_client.exists.return_value = 1
        redis_client._client = mock_client
        
        result = await redis_client.exists("test_key")
        
        assert result is True
        mock_client.exists.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_expire_key(self, redis_client):
        """Test setting key expiration"""
        mock_client = AsyncMock()
        mock_client.expire.return_value = True
        redis_client._client = mock_client
        
        result = await redis_client.expire("test_key", 3600)
        
        assert result is True
        mock_client.expire.assert_called_once_with("test_key", 3600)
    
    @pytest.mark.asyncio
    async def test_hset_hash(self, redis_client):
        """Test setting hash fields"""
        mock_client = AsyncMock()
        mock_client.hset.return_value = 2
        redis_client._client = mock_client
        
        mapping = {"field1": "value1", "field2": {"nested": "value"}}
        result = await redis_client.hset("test_hash", mapping)
        
        assert result == 2
        expected_mapping = {
            "field1": "value1",
            "field2": json.dumps({"nested": "value"})
        }
        mock_client.hset.assert_called_once_with("test_hash", mapping=expected_mapping)
    
    @pytest.mark.asyncio
    async def test_hget_hash_field(self, redis_client):
        """Test getting hash field"""
        mock_client = AsyncMock()
        mock_client.hget.return_value = "field_value"
        redis_client._client = mock_client
        
        result = await redis_client.hget("test_hash", "field1")
        
        assert result == "field_value"
        mock_client.hget.assert_called_once_with("test_hash", "field1")
    
    @pytest.mark.asyncio
    async def test_hgetall_hash(self, redis_client):
        """Test getting all hash fields"""
        mock_client = AsyncMock()
        mock_client.hgetall.return_value = {
            "field1": "value1",
            "field2": json.dumps({"nested": "value"})
        }
        redis_client._client = mock_client
        
        result = await redis_client.hgetall("test_hash")
        
        expected_result = {
            "field1": "value1",
            "field2": {"nested": "value"}
        }
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_lpush_list(self, redis_client):
        """Test pushing to list"""
        mock_client = AsyncMock()
        mock_client.lpush.return_value = 3
        redis_client._client = mock_client
        
        result = await redis_client.lpush("test_list", "value1", {"key": "value"})
        
        assert result == 3
        mock_client.lpush.assert_called_once_with("test_list", "value1", json.dumps({"key": "value"}))
    
    @pytest.mark.asyncio
    async def test_rpop_list(self, redis_client):
        """Test popping from list"""
        mock_client = AsyncMock()
        mock_client.rpop.return_value = json.dumps({"key": "value"})
        redis_client._client = mock_client
        
        result = await redis_client.rpop("test_list")
        
        assert result == {"key": "value"}
        mock_client.rpop.assert_called_once_with("test_list")
    
    @pytest.mark.asyncio
    async def test_llen_list(self, redis_client):
        """Test getting list length"""
        mock_client = AsyncMock()
        mock_client.llen.return_value = 5
        redis_client._client = mock_client
        
        result = await redis_client.llen("test_list")
        
        assert result == 5
        mock_client.llen.assert_called_once_with("test_list")
    
    @pytest.mark.asyncio
    async def test_zadd_sorted_set(self, redis_client):
        """Test adding to sorted set"""
        mock_client = AsyncMock()
        mock_client.zadd.return_value = 2
        redis_client._client = mock_client
        
        mapping = {"member1": 1.0, "member2": 2.0}
        result = await redis_client.zadd("test_zset", mapping)
        
        assert result == 2
        mock_client.zadd.assert_called_once_with("test_zset", mapping)
    
    @pytest.mark.asyncio
    async def test_zrange_sorted_set(self, redis_client):
        """Test getting range from sorted set"""
        mock_client = AsyncMock()
        mock_client.zrange.return_value = ["member1", "member2"]
        redis_client._client = mock_client
        
        result = await redis_client.zrange("test_zset", 0, -1)
        
        assert result == ["member1", "member2"]
        mock_client.zrange.assert_called_once_with("test_zset", 0, -1, withscores=False)
    
    @pytest.mark.asyncio
    async def test_get_queue_stats(self, redis_client):
        """Test getting queue statistics"""
        mock_client = AsyncMock()
        redis_client._client = mock_client
        
        # Mock llen calls for different queues
        def mock_llen(key):
            if key == "collect:pending":
                return 5
            elif key == "process:pending":
                return 3
            elif key == "publish:pending":
                return 1
            elif key == "failed:collect":
                return 0
            elif key == "failed:process":
                return 2
            elif key == "failed:publish":
                return 0
            return 0
        
        mock_client.llen.side_effect = mock_llen
        
        result = await redis_client.get_queue_stats()
        
        expected_stats = {
            "collect_pending": 5,
            "process_pending": 3,
            "publish_pending": 1,
            "collect_failed": 0,
            "process_failed": 2,
            "publish_failed": 0
        }
        assert result == expected_stats
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, redis_client):
        """Test rate limit check when allowed"""
        mock_client = AsyncMock()
        mock_client.zremrangebyscore.return_value = 0
        mock_client.zcard.return_value = 5  # Below limit of 10
        mock_client.zadd.return_value = 1
        mock_client.expire.return_value = True
        redis_client._client = mock_client
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.time.return_value = 1000000000
            
            result = await redis_client.check_rate_limit("test_key", 10, 60)
            
            assert result is True
            mock_client.zremrangebyscore.assert_called_once()
            mock_client.zcard.assert_called_once()
            mock_client.zadd.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, redis_client):
        """Test rate limit check when exceeded"""
        mock_client = AsyncMock()
        mock_client.zremrangebyscore.return_value = 0
        mock_client.zcard.return_value = 10  # At limit of 10
        redis_client._client = mock_client
        
        result = await redis_client.check_rate_limit("test_key", 10, 60)
        
        assert result is False
        mock_client.zremrangebyscore.assert_called_once()
        mock_client.zcard.assert_called_once()
        # zadd should not be called when limit is exceeded
        mock_client.zadd.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cache_operations(self, redis_client):
        """Test cache set/get/delete operations"""
        mock_client = AsyncMock()
        mock_client.set.return_value = True
        mock_client.get.return_value = json.dumps({"cached": "data"})
        mock_client.delete.return_value = 1
        redis_client._client = mock_client
        
        # Test cache set
        result = await redis_client.cache_set("test_key", {"cached": "data"}, ttl=1800)
        assert result is True
        mock_client.set.assert_called_with("cache:test_key", json.dumps({"cached": "data"}), ex=1800, nx=False)
        
        # Test cache get
        result = await redis_client.cache_get("test_key")
        assert result == {"cached": "data"}
        mock_client.get.assert_called_with("cache:test_key")
        
        # Test cache delete
        result = await redis_client.cache_delete("test_key")
        assert result == 1
        mock_client.delete.assert_called_with("cache:test_key")


class TestRedisUtilityFunctions:
    """Test Redis utility functions"""
    
    @pytest.mark.asyncio
    async def test_get_redis_context_manager(self):
        """Test get_redis context manager"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.is_connected = True
            
            async with get_redis() as redis:
                assert redis is mock_client
    
    @pytest.mark.asyncio
    async def test_get_redis_not_connected(self):
        """Test get_redis when not connected"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.is_connected = False
            mock_client.connect = AsyncMock()
            
            async with get_redis() as redis:
                assert redis is mock_client
                mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_init_redis(self):
        """Test Redis initialization"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.connect = AsyncMock()
            
            await init_redis()
            
            mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_redis(self):
        """Test Redis closure"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.disconnect = AsyncMock()
            
            await close_redis()
            
            mock_client.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_health_check_healthy(self):
        """Test healthy Redis health check"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.is_connected = True
            mock_client.set = AsyncMock(return_value=True)
            mock_client.get = AsyncMock(return_value="test_value")
            mock_client.delete = AsyncMock(return_value=1)
            mock_client.get_queue_stats = AsyncMock(return_value={
                "collect_pending": 5,
                "process_pending": 3
            })
            
            result = await redis_health_check()
            
            assert result["status"] == "healthy"
            assert result["connected"] is True
            assert "queue_stats" in result
    
    @pytest.mark.asyncio
    async def test_redis_health_check_not_connected(self):
        """Test Redis health check when not connected"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.is_connected = False
            
            result = await redis_health_check()
            
            assert result["status"] == "unhealthy"
            assert result["connected"] is False
            assert result["error"] == "Not connected"
    
    @pytest.mark.asyncio
    async def test_redis_health_check_read_write_failure(self):
        """Test Redis health check with read/write failure"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.is_connected = True
            mock_client.set = AsyncMock(return_value=True)
            mock_client.get = AsyncMock(return_value="wrong_value")  # Wrong value
            mock_client.delete = AsyncMock(return_value=1)
            
            result = await redis_health_check()
            
            assert result["status"] == "unhealthy"
            assert result["connected"] is True
            assert "Read/write test failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_redis_health_check_exception(self):
        """Test Redis health check with exception"""
        with patch('app.redis_client.redis_client') as mock_client:
            mock_client.is_connected = True
            mock_client.set = AsyncMock(side_effect=ConnectionError("Connection lost"))
            
            result = await redis_health_check()
            
            assert result["status"] == "unhealthy"
            assert result["connected"] is False
            assert "Connection lost" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])