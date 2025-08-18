"""
API endpoints for cache management and optimization
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.caching.redis_cache import cache_manager, cache
from app.caching.query_optimizer import query_optimizer
from app.caching.response_cache import response_cache_manager
from app.api.middleware.auth import verify_admin_token

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])

class CacheInvalidateRequest(BaseModel):
    """Request model for cache invalidation"""
    cache_type: str = Field(..., description="Type of cache to invalidate")
    pattern: Optional[str] = Field(None, description="Pattern to match keys (optional)")

class CacheWarmupRequest(BaseModel):
    """Request model for cache warmup"""
    cache_type: str = Field(..., description="Type of cache to warm up")
    data: Dict = Field(..., description="Data to warm up cache with")
    ttl: Optional[int] = Field(None, description="TTL for cached items")

class QueryOptimizationRequest(BaseModel):
    """Request model for query optimization"""
    analyze_tables: bool = Field(default=True, description="Whether to analyze table statistics")
    suggest_indexes: bool = Field(default=True, description="Whether to suggest index optimizations")

@router.get("/status")
async def get_cache_status():
    """Get overall cache status and statistics"""
    try:
        # Get Redis cache stats
        cache_stats = await cache.get_stats()
        
        # Get response cache stats
        response_stats = await response_cache_manager.get_cache_stats()
        
        # Get cache manager status
        manager_status = {
            'maintenance_running': cache_manager._running,
            'cache_types': list(cache.config.ttl_mapping.keys())
        }
        
        return {
            'redis_cache': cache_stats,
            'response_cache': response_stats,
            'cache_manager': manager_status,
            'health': await cache.health_check()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache status: {str(e)}")

@router.get("/stats/{cache_type}")
async def get_cache_type_stats(cache_type: str):
    """Get statistics for a specific cache type"""
    try:
        if cache_type not in cache.config.ttl_mapping:
            raise HTTPException(status_code=404, detail=f"Cache type '{cache_type}' not found")
        
        # Count keys for this cache type
        pattern = f"{cache.config.key_prefix}:{cache_type}:*"
        key_count = 0
        sample_keys = []
        
        async for key in cache.redis_client.scan_iter(match=pattern, count=100):
            key_count += 1
            if len(sample_keys) < 10:  # Get sample of keys
                sample_keys.append(key.decode('utf-8'))
        
        return {
            'cache_type': cache_type,
            'key_count': key_count,
            'ttl': cache.config.ttl_mapping[cache_type],
            'sample_keys': sample_keys,
            'timestamp': cache_stats.get('timestamp') if 'cache_stats' in locals() else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache stats: {str(e)}")

@router.post("/invalidate")
async def invalidate_cache(
    request: CacheInvalidateRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Invalidate cache entries"""
    try:
        if request.cache_type not in cache.config.ttl_mapping and request.cache_type != 'all':
            raise HTTPException(status_code=400, detail=f"Invalid cache type: {request.cache_type}")
        
        if request.cache_type == 'all':
            # Invalidate all cache types
            total_deleted = 0
            for cache_type in cache.config.ttl_mapping.keys():
                deleted = await cache.clear_cache_type(cache_type)
                total_deleted += deleted
            
            return {
                'success': True,
                'message': f"Invalidated all cache types",
                'deleted_keys': total_deleted
            }
        else:
            # Invalidate specific cache type
            if request.pattern:
                deleted = await cache.delete_pattern(request.pattern, request.cache_type)
            else:
                deleted = await cache.clear_cache_type(request.cache_type)
            
            return {
                'success': True,
                'message': f"Invalidated cache type '{request.cache_type}'",
                'deleted_keys': deleted,
                'pattern': request.pattern
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error invalidating cache: {str(e)}")

@router.post("/warmup")
async def warmup_cache(
    request: CacheWarmupRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Warm up cache with initial data"""
    try:
        if request.cache_type not in cache.config.ttl_mapping:
            raise HTTPException(status_code=400, detail=f"Invalid cache type: {request.cache_type}")
        
        await cache_manager.warm_cache(
            request.cache_type,
            request.data,
            request.ttl
        )
        
        return {
            'success': True,
            'message': f"Warmed up cache type '{request.cache_type}'",
            'items_cached': len(request.data),
            'ttl': request.ttl or cache.config.ttl_mapping[request.cache_type]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error warming up cache: {str(e)}")

@router.get("/query-performance")
async def get_query_performance(
    hours: int = Query(default=24, ge=1, le=168, description="Hours of data to analyze")
):
    """Get database query performance statistics"""
    try:
        stats = await query_optimizer.get_query_performance_stats(hours)
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting query performance: {str(e)}")

@router.post("/optimize-queries")
async def optimize_queries(
    request: QueryOptimizationRequest,
    admin_token: str = Depends(verify_admin_token)
):
    """Analyze and optimize database queries"""
    try:
        results = {}
        
        if request.analyze_tables:
            # Update table statistics
            analyze_results = await query_optimizer.update_table_statistics()
            results['table_analysis'] = analyze_results
        
        if request.suggest_indexes:
            # Get index optimization suggestions
            optimization_results = await query_optimizer.optimize_table_indexes()
            results['index_suggestions'] = optimization_results
        
        return {
            'success': True,
            'message': "Query optimization analysis completed",
            'results': results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizing queries: {str(e)}")

@router.get("/response-cache/stats")
async def get_response_cache_stats():
    """Get response cache statistics"""
    try:
        stats = await response_cache_manager.get_cache_stats()
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting response cache stats: {str(e)}")

@router.post("/response-cache/invalidate")
async def invalidate_response_cache(
    endpoint_pattern: str = Query(..., description="Endpoint pattern to invalidate"),
    admin_token: str = Depends(verify_admin_token)
):
    """Invalidate response cache for specific endpoints"""
    try:
        deleted_count = await response_cache_manager.invalidate_endpoint_cache(endpoint_pattern)
        
        return {
            'success': True,
            'message': f"Invalidated response cache for pattern '{endpoint_pattern}'",
            'deleted_keys': deleted_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error invalidating response cache: {str(e)}")

@router.post("/response-cache/warmup")
async def warmup_response_cache(
    endpoints: List[str] = Query(..., description="List of endpoints to warm up"),
    admin_token: str = Depends(verify_admin_token)
):
    """Warm up response cache for specific endpoints"""
    try:
        results = await response_cache_manager.warm_endpoint_cache(endpoints)
        
        return {
            'success': True,
            'message': "Response cache warmup completed",
            'warmed_endpoints': results['warmed'],
            'failed_endpoints': results['failed'],
            'total_endpoints': len(endpoints)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error warming up response cache: {str(e)}")

@router.get("/health")
async def cache_health_check():
    """Perform comprehensive cache health check"""
    try:
        # Redis cache health
        redis_health = await cache.health_check()
        
        # Query optimizer health (check if we can access database)
        query_health = {'healthy': True}
        try:
            await query_optimizer.get_query_performance_stats(1)
        except Exception as e:
            query_health = {'healthy': False, 'error': str(e)}
        
        # Response cache health
        response_health = {'healthy': True}
        try:
            await response_cache_manager.get_cache_stats()
        except Exception as e:
            response_health = {'healthy': False, 'error': str(e)}
        
        overall_healthy = (
            redis_health.get('healthy', False) and
            query_health.get('healthy', False) and
            response_health.get('healthy', False)
        )
        
        return {
            'healthy': overall_healthy,
            'components': {
                'redis_cache': redis_health,
                'query_optimizer': query_health,
                'response_cache': response_health
            },
            'timestamp': redis_health.get('timestamp')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing cache health check: {str(e)}")

@router.post("/maintenance/start")
async def start_cache_maintenance(admin_token: str = Depends(verify_admin_token)):
    """Start cache maintenance tasks"""
    try:
        await cache_manager.start_maintenance()
        
        return {
            'success': True,
            'message': "Cache maintenance started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting cache maintenance: {str(e)}")

@router.post("/maintenance/stop")
async def stop_cache_maintenance(admin_token: str = Depends(verify_admin_token)):
    """Stop cache maintenance tasks"""
    try:
        await cache_manager.stop_maintenance()
        
        return {
            'success': True,
            'message': "Cache maintenance stopped"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping cache maintenance: {str(e)}")

@router.get("/keys/{cache_type}")
async def list_cache_keys(
    cache_type: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of keys to return"),
    pattern: Optional[str] = Query(None, description="Pattern to filter keys")
):
    """List cache keys for a specific cache type"""
    try:
        if cache_type not in cache.config.ttl_mapping:
            raise HTTPException(status_code=404, detail=f"Cache type '{cache_type}' not found")
        
        # Build search pattern
        if pattern:
            search_pattern = f"{cache.config.key_prefix}:{cache_type}:{pattern}"
        else:
            search_pattern = f"{cache.config.key_prefix}:{cache_type}:*"
        
        keys = []
        count = 0
        
        async for key in cache.redis_client.scan_iter(match=search_pattern, count=100):
            if count >= limit:
                break
            
            key_str = key.decode('utf-8')
            # Get TTL for the key
            ttl = await cache.redis_client.ttl(key)
            
            keys.append({
                'key': key_str,
                'ttl': ttl if ttl > 0 else None,
                'expired': ttl == -2
            })
            count += 1
        
        return {
            'cache_type': cache_type,
            'keys': keys,
            'total_returned': len(keys),
            'limit_reached': count >= limit,
            'pattern': pattern
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing cache keys: {str(e)}")

@router.delete("/keys/{cache_type}/{key}")
async def delete_cache_key(
    cache_type: str,
    key: str,
    admin_token: str = Depends(verify_admin_token)
):
    """Delete a specific cache key"""
    try:
        if cache_type not in cache.config.ttl_mapping:
            raise HTTPException(status_code=404, detail=f"Cache type '{cache_type}' not found")
        
        success = await cache.delete(key, cache_type)
        
        if success:
            return {
                'success': True,
                'message': f"Deleted cache key '{key}' from cache type '{cache_type}'"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Cache key '{key}' not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting cache key: {str(e)}")

@router.get("/keys/{cache_type}/{key}")
async def get_cache_key_info(cache_type: str, key: str):
    """Get information about a specific cache key"""
    try:
        if cache_type not in cache.config.ttl_mapping:
            raise HTTPException(status_code=404, detail=f"Cache type '{cache_type}' not found")
        
        # Check if key exists
        exists = await cache.exists(key, cache_type)
        if not exists:
            raise HTTPException(status_code=404, detail=f"Cache key '{key}' not found")
        
        # Get key info
        cache_key = cache._make_key(key, cache_type)
        ttl = await cache.redis_client.ttl(cache_key)
        
        # Get value size (without deserializing)
        raw_value = await cache.redis_client.get(cache_key)
        value_size = len(raw_value) if raw_value else 0
        
        return {
            'cache_type': cache_type,
            'key': key,
            'exists': True,
            'ttl': ttl if ttl > 0 else None,
            'value_size_bytes': value_size,
            'expired': ttl == -2
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache key info: {str(e)}")