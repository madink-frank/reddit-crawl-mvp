"""
Enhanced metrics endpoints with error classification - MVP version
Provides DB-based metrics aggregation in Prometheus format with error classification
"""
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Response, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.monitoring.metrics import get_all_metrics


logger = logging.getLogger(__name__)
router = APIRouter()


def get_database_session():
    """Get database session dependency"""
    try:
        from app.infrastructure import get_database_session
        db_session = get_database_session()
        try:
            yield db_session
        finally:
            db_session.close()
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Database not available"
        )


@router.get("/metrics")
async def get_metrics(db_session: Session = Depends(get_database_session)):
    """
    Get system metrics in Prometheus format with enhanced error classification
    
    Aggregates metrics from processing_logs and token_usage tables
    Returns metrics in Prometheus text format with proper content-type
    Uses limited caching for performance optimization
    
    Features:
    - Processing metrics (success/failure counts by service)
    - Error classification (429/timeout/5xx/logic_error)
    - Token usage and cost tracking
    - Queue metrics from Redis
    - Recent failure rate (5-minute sliding window)
    """
    try:
        # Try to get from cache first (limited caching scope)
        from app.monitoring.performance_optimization import get_cached_status_data, cache_status_data
        
        cached_metrics = get_cached_status_data('system_metrics')
        if cached_metrics:
            return Response(
                content=cached_metrics.get('prometheus_text', ''),
                media_type="text/plain; version=0.0.4; charset=utf-8"
            )
        
        # Get all metrics using enhanced collector
        prometheus_text = get_all_metrics(db_session)
        
        # Cache the metrics (limited caching scope - status pages only)
        cache_data = {
            'prometheus_text': prometheus_text,
            'generated_at': '2024-01-01T00:00:00Z'  # Will be replaced with actual timestamp
        }
        cache_status_data('system_metrics', cache_data)
        
        # Return with proper content type for Prometheus
        return Response(
            content=prometheus_text,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/metrics/health")
async def get_metrics_health():
    """
    Health check endpoint for metrics service
    
    Returns basic status information about metrics collection capability
    """
    try:
        from app.infrastructure import get_database_session
        
        # Test database connectivity
        db_session = get_database_session()
        try:
            # Simple query to test database
            db_session.execute("SELECT 1")
            db_available = True
        except Exception as e:
            logger.warning(f"Database not available for metrics: {e}")
            db_available = False
        finally:
            db_session.close()
        
        # Test Redis connectivity
        try:
            from app.infrastructure import get_redis_client
            redis_client = get_redis_client()
            redis_client.ping()
            redis_available = True
        except Exception as e:
            logger.warning(f"Redis not available for metrics: {e}")
            redis_available = False
        
        status = "healthy" if (db_available and redis_available) else "degraded"
        
        return {
            "status": status,
            "database": "available" if db_available else "unavailable",
            "redis": "available" if redis_available else "unavailable",
            "timestamp": "2024-01-01T00:00:00Z"  # Will be replaced with actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Metrics health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-01-01T00:00:00Z"
        }