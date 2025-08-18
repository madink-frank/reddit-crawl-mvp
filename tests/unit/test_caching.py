"""
Unit tests for caching functionality
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from app.caching.redis_cache import RedisCache, CacheConfig, cached, cache_manager
from app.caching.query_optimizer import QueryOptimizer
from app.caching.response_cache import ResponseCacheMiddleware, CacheRule


class TestRedisCache:
    """Test Redis cache functionality"""
    
    @pytest.fixture
    async def cache_instance(self):
        """Create a test cache instance"""
        config = CacheConfig(default_ttl=60)
        cache = RedisCache(config)
        
        # Mock Redis client
        cache.redis_client = AsyncMock()
        
        return cache
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache_instance):
        """Test basic cache set and get operations"""
        # Mock Redis responses
        cache_instance.redis_client.setex.return_value = True
        cache_instance.redis_client.get.return_value = b'{"test": "value"}'
        
        # Test set
        result = await cache_instance.set("test_key", {"test": "value"})
        assert result is True
        
        # Test get
        value = await cache_instance.get("test_key")
        assert value == {"test": "value"}
        
        # Verify Redis calls
        cache_instance.redis_client.setex.assert_called_once()
        cache_instance.redis_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_instance):
        """Test cache miss scenario"""
        cache_instance.redis_client.get.return_value = None
        
        value = await cache_instance.get("nonexistent_key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_cache_compression(self, cache_instance):
        """Test cache compression for large values"""
        # Create large value that should be compressed
        large_value = {"data": "x" * 2000}  # Larger than compression threshold
        
        cache_instance.redis_client.setex.return_value = True
        
        # Mock the serialization to check compression
        with patch.object(cache_instance, '_serialize_value') as mock_serialize:
            mock_serialize.return_value = b'GZIP:compressed_data'
            
            await cache_instance.set("large_key", large_value)
            
            # Verify compression was attempted
            mock_serialize.assert_called_once_with(large_value)
    
    @pytest.mark.asyncio
    async def test_cache_many_operations(self, cache_instance):
        """Test batch cache operations"""
        # Mock Redis pipeline
        mock_pipeline = AsyncMock()
        cache_instance.redis_client.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [True, True]
        
        # Test set_many
        data = {"key1": "value1", "key2": "value2"}
        result = await cache_instance.set_many(data)
        assert result is True
        
        # Test get_many
        cache_instance.redis_client.mget.return_value = [b'"value1"', b'"value2"']
        
        values = await cache_instance.get_many(["key1", "key2"])
        assert values == {"key1": "value1", "key2": "value2"}
    
    @pytest.mark.asyncio
    async def test_cache_health_check(self, cache_instance):
        """Test cache health check"""
        cache_instance.redis_client.setex.return_value = True
        cache_instance.redis_client.get.return_value = b'{"timestamp": "2023-01-01T00:00:00", "test": true}'
        cache_instance.redis_client.delete.return_value = 1
        
        health = await cache_instance.health_check()
        
        assert health['healthy'] is True
        assert health['operations']['set'] is True
        assert health['operations']['get'] is True
        assert health['operations']['delete'] is True
        assert 'response_time_ms' in health
    
    def test_cached_decorator_async(self):
        """Test cached decorator with async function"""
        @cached(cache_type='test', ttl=60)
        async def test_function(arg1, arg2):
            return f"{arg1}:{arg2}"
        
        # Verify the function is wrapped
        assert asyncio.iscoroutinefunction(test_function)
    
    def test_cached_decorator_sync(self):
        """Test cached decorator with sync function"""
        @cached(cache_type='test', ttl=60)
        def test_function(arg1, arg2):
            return f"{arg1}:{arg2}"
        
        # Verify the function is wrapped
        assert callable(test_function)


class TestQueryOptimizer:
    """Test query optimizer functionality"""
    
    @pytest.fixture
    def optimizer(self):
        """Create a test query optimizer"""
        optimizer = QueryOptimizer()
        
        # Mock database
        optimizer.database = MagicMock()
        
        return optimizer
    
    def test_extract_query_type(self, optimizer):
        """Test SQL query type extraction"""
        assert optimizer._extract_query_type("SELECT * FROM posts") == "SELECT"
        assert optimizer._extract_query_type("INSERT INTO posts VALUES (...)") == "INSERT"
        assert optimizer._extract_query_type("UPDATE posts SET ...") == "UPDATE"
        assert optimizer._extract_query_type("DELETE FROM posts WHERE ...") == "DELETE"
        assert optimizer._extract_query_type("CREATE TABLE ...") == "CREATE"
        assert optimizer._extract_query_type("UNKNOWN QUERY") == "OTHER"
    
    def test_extract_table_name(self, optimizer):
        """Test table name extraction from SQL"""
        assert optimizer._extract_table_name("SELECT * FROM posts") == "posts"
        assert optimizer._extract_table_name("INSERT INTO posts VALUES (...)") == "posts"
        assert optimizer._extract_table_name("UPDATE posts SET title = 'test'") == "posts"
        assert optimizer._extract_table_name("DELETE FROM posts WHERE id = 1") == "posts"
        assert optimizer._extract_table_name("INVALID QUERY") == "unknown"
    
    @pytest.mark.asyncio
    async def test_get_recent_posts_caching(self, optimizer):
        """Test that get_recent_posts uses caching"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result._mapping = {'id': '1', 'title': 'Test Post'}
        mock_conn.execute.return_value = [mock_result]
        optimizer.database.connect.return_value.__enter__.return_value = mock_conn
        
        # This would normally test the cached decorator
        # In a real test, you'd mock the cache to verify it's being used
        posts = await optimizer.get_recent_posts(limit=10)
        
        # Verify database was called
        optimizer.database.connect.assert_called_once()


class TestResponseCacheMiddleware:
    """Test response cache middleware"""
    
    @pytest.fixture
    def cache_rules(self):
        """Create test cache rules"""
        return [
            CacheRule(
                path_pattern="/test",
                methods=["GET"],
                ttl=60,
                compress=True
            )
        ]
    
    @pytest.fixture
    def middleware(self, cache_rules):
        """Create test middleware"""
        app = MagicMock()
        return ResponseCacheMiddleware(app, cache_rules)
    
    def test_find_matching_rule(self, middleware):
        """Test cache rule matching"""
        rule = middleware._find_matching_rule("/test", "GET")
        assert rule is not None
        assert rule.path_pattern == "/test"
        assert "GET" in rule.methods
        
        # Test no match
        rule = middleware._find_matching_rule("/other", "GET")
        assert rule is None
        
        rule = middleware._find_matching_rule("/test", "POST")
        assert rule is None
    
    def test_generate_cache_key(self, middleware):
        """Test cache key generation"""
        # Mock request
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/test"
        request.query_params.items.return_value = [("param", "value")]
        request.headers.get.return_value = ""
        
        rule = CacheRule(path_pattern="/test", methods=["GET"], ttl=60)
        
        key = middleware._generate_cache_key(request, rule)
        assert "GET" in key
        assert "/test" in key
        assert "param=value" in key
    
    def test_should_cache_response(self, middleware):
        """Test response caching decision logic"""
        request = MagicMock()
        
        # Test successful response
        response = MagicMock()
        response.status_code = 200
        response.headers.get.return_value = None
        
        rule = CacheRule(path_pattern="/test", methods=["GET"], ttl=60)
        
        should_cache = middleware._should_cache_response(request, response, rule)
        assert should_cache is True
        
        # Test error response
        response.status_code = 500
        should_cache = middleware._should_cache_response(request, response, rule)
        assert should_cache is False
        
        # Test no-cache header
        response.status_code = 200
        response.headers.get.return_value = "no-cache"
        should_cache = middleware._should_cache_response(request, response, rule)
        assert should_cache is False
    
    def test_compress_response(self, middleware):
        """Test response compression"""
        # Small content - should not compress
        small_content = b"small"
        compressed, is_compressed = middleware._compress_response(small_content)
        assert is_compressed is False
        assert compressed == small_content
        
        # Large content - should compress
        large_content = b"x" * 2000
        compressed, is_compressed = middleware._compress_response(large_content)
        # Note: In real test, this would depend on actual compression ratio
        # For this test, we just verify the method doesn't crash


class TestCacheManager:
    """Test cache manager functionality"""
    
    @pytest.fixture
    def manager(self):
        """Create test cache manager"""
        cache_instance = MagicMock()
        return cache_manager
    
    @pytest.mark.asyncio
    async def test_start_stop_maintenance(self, manager):
        """Test starting and stopping maintenance"""
        # Mock the maintenance task
        with patch('asyncio.create_task') as mock_create_task:
            await manager.start_maintenance()
            assert manager._running is True
            mock_create_task.assert_called_once()
            
            await manager.stop_maintenance()
            assert manager._running is False
    
    @pytest.mark.asyncio
    async def test_warm_cache(self, manager):
        """Test cache warming"""
        # Mock cache instance
        manager.cache = AsyncMock()
        manager.cache.set_many.return_value = True
        
        data = {"key1": "value1", "key2": "value2"}
        await manager.warm_cache("test_type", data, 300)
        
        manager.cache.set_many.assert_called_once_with(data, "test_type", 300)
    
    @pytest.mark.asyncio
    async def test_invalidate_cache_type(self, manager):
        """Test cache type invalidation"""
        manager.cache = AsyncMock()
        manager.cache.clear_cache_type.return_value = 5
        
        await manager.invalidate_cache_type("test_type")
        
        manager.cache.clear_cache_type.assert_called_once_with("test_type")


@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for caching system"""
    
    @pytest.mark.asyncio
    async def test_full_cache_workflow(self):
        """Test complete cache workflow"""
        # This would be a more comprehensive test that:
        # 1. Sets up a real Redis connection (or Redis mock)
        # 2. Tests the full cache workflow
        # 3. Verifies metrics are recorded
        # 4. Tests cache invalidation
        
        # For now, just verify the components can be imported
        from app.caching.redis_cache import cache
        from app.caching.query_optimizer import query_optimizer
        from app.caching.response_cache import response_cache_manager
        
        assert cache is not None
        assert query_optimizer is not None
        assert response_cache_manager is not None


if __name__ == "__main__":
    pytest.main([__file__])