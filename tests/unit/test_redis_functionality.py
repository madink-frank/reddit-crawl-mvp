"""
Unit tests for Redis functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.redis_client import RedisClient


class TestRedisClient:
    """Test Redis client functionality"""
    
    @pytest.fixture
    async def redis_client(self):
        """Create Redis client with mocked connection"""
        with patch('app.redis_client.redis.Redis') as mock_redis:
            with patch('app.redis_client.ConnectionPool') as mock_pool:
                mock_connection = AsyncMock()
                mock_redis.return_value = mock_connection
                mock_pool.from_url.return_value = Mock()
                
                client = RedisClient()
                client._client = mock_connection
                client._connected = True
                return client
    
    def test_redis_client_initialization(self):
        """Test Redis client initialization"""
        client = RedisClient()
        
        assert client is not None
        assert client._connected is False
        assert client._client is None
    
    @pytest.mark.asyncio
    async def test_set_and_get_basic(self, redis_client):
        """Test basic set and get operations"""
        # Mock Redis responses
        redis_client._client.set.return_value = True
        redis_client._client.get.return_value = 'test_value'
        
        # Test set
        result = await redis_client.set('test_key', 'test_value')
        assert result is True
        redis_client._client.set.assert_called_with('test_key', 'test_value', ex=None)
        
        # Test get
        result = await redis_client.get('test_key')
        assert result == 'test_value'
        redis_client._client.get.assert_called_with('test_key')
    
    def test_set_with_expiration(self, redis_client):
        """Test set operation with expiration"""
        redis_client.redis.set.return_value = True
        
        result = redis_client.set('test_key', 'test_value', expire_seconds=3600)
        assert result is True
        redis_client.redis.set.assert_called_with('test_key', 'test_value', ex=3600)
    
    def test_get_nonexistent_key(self, redis_client):
        """Test getting non-existent key"""
        redis_client.redis.get.return_value = None
        
        result = redis_client.get('nonexistent_key')
        assert result is None
    
    def test_delete_key(self, redis_client):
        """Test key deletion"""
        redis_client.redis.delete.return_value = 1
        
        result = redis_client.delete('test_key')
        assert result == 1
        redis_client.redis.delete.assert_called_with('test_key')
    
    def test_exists_key(self, redis_client):
        """Test key existence check"""
        redis_client.redis.exists.return_value = 1
        
        result = redis_client.exists('test_key')
        assert result is True
        redis_client.redis.exists.assert_called_with('test_key')
        
        # Test non-existent key
        redis_client.redis.exists.return_value = 0
        result = redis_client.exists('nonexistent_key')
        assert result is False
    
    def test_increment_counter(self, redis_client):
        """Test counter increment"""
        redis_client.redis.incr.return_value = 5
        
        result = redis_client.increment('counter_key')
        assert result == 5
        redis_client.redis.incr.assert_called_with('counter_key', 1)
        
        # Test increment by specific amount
        redis_client.redis.incr.return_value = 10
        result = redis_client.increment('counter_key', amount=5)
        assert result == 10
        redis_client.redis.incr.assert_called_with('counter_key', 5)
    
    def test_list_operations(self, redis_client):
        """Test list operations"""
        # Test list push
        redis_client.redis.lpush.return_value = 3
        result = redis_client.list_push('test_list', 'item1')
        assert result == 3
        redis_client.redis.lpush.assert_called_with('test_list', 'item1')
        
        # Test list pop
        redis_client.redis.rpop.return_value = b'item1'
        result = redis_client.list_pop('test_list')
        assert result == 'item1'
        redis_client.redis.rpop.assert_called_with('test_list')
        
        # Test list length
        redis_client.redis.llen.return_value = 5
        result = redis_client.list_length('test_list')
        assert result == 5
        redis_client.redis.llen.assert_called_with('test_list')
    
    def test_hash_operations(self, redis_client):
        """Test hash operations"""
        # Test hash set
        redis_client.redis.hset.return_value = 1
        result = redis_client.hash_set('test_hash', 'field1', 'value1')
        assert result == 1
        redis_client.redis.hset.assert_called_with('test_hash', 'field1', 'value1')
        
        # Test hash get
        redis_client.redis.hget.return_value = b'value1'
        result = redis_client.hash_get('test_hash', 'field1')
        assert result == 'value1'
        redis_client.redis.hget.assert_called_with('test_hash', 'field1')
        
        # Test hash get all
        redis_client.redis.hgetall.return_value = {b'field1': b'value1', b'field2': b'value2'}
        result = redis_client.hash_get_all('test_hash')
        assert result == {'field1': 'value1', 'field2': 'value2'}
    
    def test_set_operations(self, redis_client):
        """Test set operations"""
        # Test set add
        redis_client.redis.sadd.return_value = 1
        result = redis_client.set_add('test_set', 'member1')
        assert result == 1
        redis_client.redis.sadd.assert_called_with('test_set', 'member1')
        
        # Test set members
        redis_client.redis.smembers.return_value = {b'member1', b'member2'}
        result = redis_client.set_members('test_set')
        assert result == {'member1', 'member2'}
        redis_client.redis.smembers.assert_called_with('test_set')
        
        # Test set is member
        redis_client.redis.sismember.return_value = True
        result = redis_client.set_is_member('test_set', 'member1')
        assert result is True
        redis_client.redis.sismember.assert_called_with('test_set', 'member1')
    
    def test_expire_key(self, redis_client):
        """Test key expiration"""
        redis_client.redis.expire.return_value = True
        
        result = redis_client.expire('test_key', 3600)
        assert result is True
        redis_client.redis.expire.assert_called_with('test_key', 3600)
    
    def test_ttl_key(self, redis_client):
        """Test getting key TTL"""
        redis_client.redis.ttl.return_value = 1800
        
        result = redis_client.ttl('test_key')
        assert result == 1800
        redis_client.redis.ttl.assert_called_with('test_key')
    
    def test_pipeline_operations(self, redis_client):
        """Test pipeline operations"""
        mock_pipeline = Mock()
        redis_client.redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [True, b'value1', 1]
        
        with redis_client.pipeline() as pipe:
            pipe.set('key1', 'value1')
            pipe.get('key2')
            pipe.incr('counter')
            results = pipe.execute()
        
        assert results == [True, 'value1', 1]
        mock_pipeline.set.assert_called_with('key1', 'value1')
        mock_pipeline.get.assert_called_with('key2')
        mock_pipeline.incr.assert_called_with('counter')
    
    def test_connection_error_handling(self, redis_client):
        """Test connection error handling"""
        import redis
        redis_client.redis.get.side_effect = redis.ConnectionError("Connection failed")
        
        with pytest.raises(redis.ConnectionError):
            redis_client.get('test_key')
    
    def test_redis_health_check(self, redis_client):
        """Test Redis health check"""
        redis_client.redis.ping.return_value = True
        
        result = redis_client.health_check()
        assert result is True
        redis_client.redis.ping.assert_called_once()
        
        # Test health check failure
        redis_client.redis.ping.side_effect = Exception("Connection failed")
        result = redis_client.health_check()
        assert result is False


class TestRedisUtilityFunctions:
    """Test Redis utility functions"""
    
    def test_daily_counter_key_generation(self):
        """Test daily counter key generation"""
        from datetime import datetime
        
        def generate_daily_key(prefix, date=None):
            """Generate daily key with date suffix"""
            if date is None:
                date = datetime.utcnow()
            date_str = date.strftime('%Y%m%d')
            return f"{prefix}:{date_str}"
        
        # Test with current date
        key1 = generate_daily_key('api_calls')
        today = datetime.utcnow().strftime('%Y%m%d')
        assert key1 == f"api_calls:{today}"
        
        # Test with specific date
        test_date = datetime(2024, 1, 15)
        key2 = generate_daily_key('token_usage', test_date)
        assert key2 == "token_usage:20240115"
    
    def test_rate_limit_key_generation(self):
        """Test rate limit key generation"""
        def generate_rate_limit_key(service, identifier, window_minutes=60):
            """Generate rate limit key"""
            now = datetime.utcnow()
            window_start = now.replace(minute=(now.minute // window_minutes) * window_minutes, second=0, microsecond=0)
            timestamp = int(window_start.timestamp())
            return f"rate_limit:{service}:{identifier}:{timestamp}"
        
        # Test rate limit key generation
        key = generate_rate_limit_key('reddit_api', 'user123', 60)
        assert key.startswith('rate_limit:reddit_api:user123:')
        assert key.count(':') == 3
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        def generate_cache_key(namespace, *args, **kwargs):
            """Generate cache key from namespace and arguments"""
            key_parts = [namespace]
            key_parts.extend(str(arg) for arg in args)
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
            return ":".join(key_parts)
        
        # Test basic cache key
        key1 = generate_cache_key('subreddit', 'technology', 'hot')
        assert key1 == 'subreddit:technology:hot'
        
        # Test with kwargs
        key2 = generate_cache_key('posts', 'technology', limit=10, sort='hot')
        assert key2 == 'posts:technology:limit=10:sort=hot'
        
        # Test kwargs ordering consistency
        key3 = generate_cache_key('posts', 'technology', sort='hot', limit=10)
        assert key2 == key3  # Should be same regardless of kwargs order


class TestRedisConnectionPool:
    """Test Redis connection pool functionality"""
    
    def test_connection_pool_creation(self):
        """Test connection pool creation"""
        with patch('app.redis_client.redis.ConnectionPool') as mock_pool:
            with patch('app.redis_client.redis.Redis') as mock_redis:
                mock_pool_instance = Mock()
                mock_pool.return_value = mock_pool_instance
                
                # Mock Redis client creation with pool
                mock_redis.return_value = Mock()
                
                client = RedisClient(
                    host='localhost',
                    port=6379,
                    db=0,
                    max_connections=20
                )
                
                # Verify pool was created with correct parameters
                mock_pool.assert_called_once()
                call_kwargs = mock_pool.call_args[1]
                assert call_kwargs['host'] == 'localhost'
                assert call_kwargs['port'] == 6379
                assert call_kwargs['db'] == 0
                assert call_kwargs['max_connections'] == 20
    
    def test_connection_pool_reuse(self):
        """Test connection pool reuse"""
        with patch('app.redis_client.redis.ConnectionPool') as mock_pool:
            with patch('app.redis_client.redis.Redis') as mock_redis:
                mock_pool_instance = Mock()
                mock_pool.return_value = mock_pool_instance
                
                # Create multiple clients with same parameters
                client1 = RedisClient(host='localhost', port=6379)
                client2 = RedisClient(host='localhost', port=6379)
                
                # Pool should be created for each client
                assert mock_pool.call_count == 2


class TestRedisErrorHandling:
    """Test Redis error handling scenarios"""
    
    def test_connection_timeout_handling(self):
        """Test connection timeout handling"""
        with patch('app.redis_client.redis.Redis') as mock_redis:
            import redis
            mock_connection = Mock()
            mock_redis.return_value = mock_connection
            mock_connection.get.side_effect = redis.TimeoutError("Operation timed out")
            
            client = RedisClient()
            
            with pytest.raises(redis.TimeoutError):
                client.get('test_key')
    
    def test_memory_error_handling(self):
        """Test Redis memory error handling"""
        with patch('app.redis_client.redis.Redis') as mock_redis:
            import redis
            mock_connection = Mock()
            mock_redis.return_value = mock_connection
            mock_connection.set.side_effect = redis.ResponseError("OOM command not allowed")
            
            client = RedisClient()
            
            with pytest.raises(redis.ResponseError):
                client.set('test_key', 'test_value')
    
    def test_connection_recovery(self):
        """Test connection recovery after failure"""
        with patch('app.redis_client.redis.Redis') as mock_redis:
            import redis
            mock_connection = Mock()
            mock_redis.return_value = mock_connection
            
            # First call fails, second succeeds
            mock_connection.ping.side_effect = [
                redis.ConnectionError("Connection failed"),
                True
            ]
            
            client = RedisClient()
            
            # First health check should fail
            assert client.health_check() is False
            
            # Second health check should succeed
            assert client.health_check() is True


if __name__ == "__main__":
    pytest.main([__file__])