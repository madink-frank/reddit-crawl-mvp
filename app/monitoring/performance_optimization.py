"""
Performance optimization implementation for Reddit Ghost Publisher MVP
Implements limited caching scope and database index optimization
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy import text, inspect, Index
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine

from app.config import get_settings
from app.caching.redis_cache import cache
from app.infrastructure import get_database
from app.models.post import Post
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage
from app.models.media_file import MediaFile


logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class IndexRecommendation:
    """Database index recommendation"""
    table_name: str
    columns: List[str]
    index_type: str  # 'btree', 'hash', 'gin', etc.
    reason: str
    estimated_benefit: str  # 'high', 'medium', 'low'
    sql_command: str


@dataclass
class QueryPerformanceMetric:
    """Query performance metric"""
    query_pattern: str
    avg_duration_ms: float
    call_count: int
    total_time_ms: float
    slowest_duration_ms: float
    table_scans: int


class LimitedCacheManager:
    """
    Limited cache manager for MVP - only caches status page data
    Collection processes do not use cache to ensure data freshness
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.cache_scope = {
            # Only status and monitoring endpoints are cached
            'status_pages': {
                'queue_status': 300,      # 5 minutes
                'worker_status': 180,     # 3 minutes
                'system_status': 120,     # 2 minutes
                'scaling_status': 60,     # 1 minute
                'health_check': 30,       # 30 seconds
                'metrics': 15             # 15 seconds
            }
        }
    
    async def get_cached_queue_status(self) -> Optional[Dict[str, Any]]:
        """Get cached queue status (status pages only)"""
        try:
            return await cache.get('queue_status', 'status_pages')
        except Exception as e:
            logger.warning(f"Error getting cached queue status: {e}")
            return None
    
    async def cache_queue_status(self, status_data: Dict[str, Any]) -> bool:
        """Cache queue status data"""
        try:
            ttl = self.cache_scope['status_pages']['queue_status']
            return await cache.set('queue_status', status_data, 'status_pages', ttl)
        except Exception as e:
            logger.error(f"Error caching queue status: {e}")
            return False
    
    async def get_cached_worker_status(self) -> Optional[Dict[str, Any]]:
        """Get cached worker status (status pages only)"""
        try:
            return await cache.get('worker_status', 'status_pages')
        except Exception as e:
            logger.warning(f"Error getting cached worker status: {e}")
            return None
    
    async def cache_worker_status(self, status_data: Dict[str, Any]) -> bool:
        """Cache worker status data"""
        try:
            ttl = self.cache_scope['status_pages']['worker_status']
            return await cache.set('worker_status', status_data, 'status_pages', ttl)
        except Exception as e:
            logger.error(f"Error caching worker status: {e}")
            return False
    
    async def get_cached_system_metrics(self) -> Optional[Dict[str, Any]]:
        """Get cached system metrics (status pages only)"""
        try:
            return await cache.get('system_metrics', 'status_pages')
        except Exception as e:
            logger.warning(f"Error getting cached system metrics: {e}")
            return None
    
    async def cache_system_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """Cache system metrics data"""
        try:
            ttl = self.cache_scope['status_pages']['metrics']
            return await cache.set('system_metrics', metrics_data, 'status_pages', ttl)
        except Exception as e:
            logger.error(f"Error caching system metrics: {e}")
            return False
    
    async def get_cached_scaling_status(self) -> Optional[Dict[str, Any]]:
        """Get cached scaling status (status pages only)"""
        try:
            return await cache.get('scaling_status', 'status_pages')
        except Exception as e:
            logger.warning(f"Error getting cached scaling status: {e}")
            return None
    
    async def cache_scaling_status(self, status_data: Dict[str, Any]) -> bool:
        """Cache scaling status data"""
        try:
            ttl = self.cache_scope['status_pages']['scaling_status']
            return await cache.set('scaling_status', status_data, 'status_pages', ttl)
        except Exception as e:
            logger.error(f"Error caching scaling status: {e}")
            return False
    
    async def invalidate_status_cache(self) -> int:
        """Invalidate all status page cache"""
        try:
            return await cache.clear_cache_type('status_pages')
        except Exception as e:
            logger.error(f"Error invalidating status cache: {e}")
            return 0
    
    def is_collection_endpoint(self, endpoint: str) -> bool:
        """
        Check if endpoint is a collection endpoint that should NOT use cache
        Collection processes must always get fresh data
        """
        collection_patterns = [
            '/api/v1/collect',
            '/api/v1/process', 
            '/api/v1/publish',
            '/api/v1/triggers'
        ]
        
        return any(pattern in endpoint for pattern in collection_patterns)
    
    def is_status_endpoint(self, endpoint: str) -> bool:
        """
        Check if endpoint is a status endpoint that CAN use cache
        """
        status_patterns = [
            '/api/v1/status',
            '/api/v1/scaling',
            '/health',
            '/metrics'
        ]
        
        return any(pattern in endpoint for pattern in status_patterns)


class DatabaseIndexOptimizer:
    """
    Database index optimizer for performance improvements
    Analyzes query patterns and suggests index optimizations
    """
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.engine = db_session.bind
    
    def get_existing_indexes(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all existing indexes in the database"""
        try:
            inspector = inspect(self.engine)
            indexes = {}
            
            # Get indexes for each table
            for table_name in ['posts', 'processing_logs', 'token_usage', 'media_files']:
                table_indexes = inspector.get_indexes(table_name)
                indexes[table_name] = table_indexes
            
            return indexes
            
        except Exception as e:
            logger.error(f"Error getting existing indexes: {e}")
            return {}
    
    def analyze_query_performance(self, hours: int = 24) -> List[QueryPerformanceMetric]:
        """
        Analyze query performance from PostgreSQL statistics
        """
        try:
            # Query PostgreSQL's pg_stat_statements if available
            query = text("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    max_time,
                    rows
                FROM pg_stat_statements 
                WHERE query NOT LIKE '%pg_stat_statements%'
                    AND calls > 10
                ORDER BY total_time DESC
                LIMIT 20
            """)
            
            result = self.db_session.execute(query)
            metrics = []
            
            for row in result:
                metrics.append(QueryPerformanceMetric(
                    query_pattern=row.query[:100] + "..." if len(row.query) > 100 else row.query,
                    avg_duration_ms=float(row.mean_time),
                    call_count=int(row.calls),
                    total_time_ms=float(row.total_time),
                    slowest_duration_ms=float(row.max_time),
                    table_scans=0  # Would need additional analysis
                ))
            
            return metrics
            
        except Exception as e:
            logger.warning(f"pg_stat_statements not available or error: {e}")
            # Fallback to basic analysis
            return self._basic_performance_analysis()
    
    def _basic_performance_analysis(self) -> List[QueryPerformanceMetric]:
        """Basic performance analysis without pg_stat_statements"""
        # Simulate common query patterns based on application usage
        return [
            QueryPerformanceMetric(
                query_pattern="SELECT * FROM posts WHERE created_at >= ?",
                avg_duration_ms=15.0,
                call_count=100,
                total_time_ms=1500.0,
                slowest_duration_ms=45.0,
                table_scans=1
            ),
            QueryPerformanceMetric(
                query_pattern="SELECT * FROM processing_logs WHERE created_at >= ?",
                avg_duration_ms=8.0,
                call_count=200,
                total_time_ms=1600.0,
                slowest_duration_ms=25.0,
                table_scans=1
            )
        ]
    
    def generate_index_recommendations(self) -> List[IndexRecommendation]:
        """
        Generate index recommendations based on query patterns and table structure
        """
        recommendations = []
        
        # Analyze posts table
        recommendations.extend(self._analyze_posts_table())
        
        # Analyze processing_logs table
        recommendations.extend(self._analyze_processing_logs_table())
        
        # Analyze token_usage table
        recommendations.extend(self._analyze_token_usage_table())
        
        # Analyze media_files table
        recommendations.extend(self._analyze_media_files_table())
        
        return recommendations
    
    def _analyze_posts_table(self) -> List[IndexRecommendation]:
        """Analyze posts table for index opportunities"""
        recommendations = []
        
        # Check if indexes exist
        existing_indexes = self.get_existing_indexes().get('posts', [])
        existing_columns = set()
        for idx in existing_indexes:
            existing_columns.update(idx.get('column_names', []))
        
        # Recommend indexes based on common query patterns
        if 'subreddit' not in existing_columns:
            recommendations.append(IndexRecommendation(
                table_name='posts',
                columns=['subreddit'],
                index_type='btree',
                reason='Frequent filtering by subreddit in collection queries',
                estimated_benefit='medium',
                sql_command='CREATE INDEX idx_posts_subreddit ON posts(subreddit);'
            ))
        
        if 'created_ts' not in existing_columns:
            recommendations.append(IndexRecommendation(
                table_name='posts',
                columns=['created_ts'],
                index_type='btree',
                reason='Time-based queries for recent posts',
                estimated_benefit='high',
                sql_command='CREATE INDEX idx_posts_created_ts ON posts(created_ts);'
            ))
        
        if 'takedown_status' not in existing_columns:
            recommendations.append(IndexRecommendation(
                table_name='posts',
                columns=['takedown_status'],
                index_type='btree',
                reason='Filtering by takedown status',
                estimated_benefit='low',
                sql_command='CREATE INDEX idx_posts_takedown_status ON posts(takedown_status);'
            ))
        
        # Composite index for common query patterns
        composite_exists = any(
            set(idx.get('column_names', [])) == {'subreddit', 'created_ts'}
            for idx in existing_indexes
        )
        
        if not composite_exists:
            recommendations.append(IndexRecommendation(
                table_name='posts',
                columns=['subreddit', 'created_ts'],
                index_type='btree',
                reason='Common query pattern: recent posts by subreddit',
                estimated_benefit='high',
                sql_command='CREATE INDEX idx_posts_subreddit_created_ts ON posts(subreddit, created_ts);'
            ))
        
        return recommendations
    
    def _analyze_processing_logs_table(self) -> List[IndexRecommendation]:
        """Analyze processing_logs table for index opportunities"""
        recommendations = []
        
        existing_indexes = self.get_existing_indexes().get('processing_logs', [])
        existing_columns = set()
        for idx in existing_indexes:
            existing_columns.update(idx.get('column_names', []))
        
        if 'service_name' not in existing_columns:
            recommendations.append(IndexRecommendation(
                table_name='processing_logs',
                columns=['service_name'],
                index_type='btree',
                reason='Filtering by service type in monitoring queries',
                estimated_benefit='medium',
                sql_command='CREATE INDEX idx_processing_logs_service_name ON processing_logs(service_name);'
            ))
        
        if 'status' not in existing_columns:
            recommendations.append(IndexRecommendation(
                table_name='processing_logs',
                columns=['status'],
                index_type='btree',
                reason='Filtering by processing status for error analysis',
                estimated_benefit='medium',
                sql_command='CREATE INDEX idx_processing_logs_status ON processing_logs(status);'
            ))
        
        # Composite index for metrics queries
        composite_exists = any(
            set(idx.get('column_names', [])) == {'created_at', 'service_name', 'status'}
            for idx in existing_indexes
        )
        
        if not composite_exists:
            recommendations.append(IndexRecommendation(
                table_name='processing_logs',
                columns=['created_at', 'service_name', 'status'],
                index_type='btree',
                reason='Metrics queries: recent logs by service and status',
                estimated_benefit='high',
                sql_command='CREATE INDEX idx_processing_logs_metrics ON processing_logs(created_at, service_name, status);'
            ))
        
        return recommendations
    
    def _analyze_token_usage_table(self) -> List[IndexRecommendation]:
        """Analyze token_usage table for index opportunities"""
        recommendations = []
        
        existing_indexes = self.get_existing_indexes().get('token_usage', [])
        existing_columns = set()
        for idx in existing_indexes:
            existing_columns.update(idx.get('column_names', []))
        
        if 'model' not in existing_columns:
            recommendations.append(IndexRecommendation(
                table_name='token_usage',
                columns=['model'],
                index_type='btree',
                reason='Filtering by AI model for cost analysis',
                estimated_benefit='medium',
                sql_command='CREATE INDEX idx_token_usage_model ON token_usage(model);'
            ))
        
        # Composite index for cost tracking
        composite_exists = any(
            set(idx.get('column_names', [])) == {'created_at', 'model'}
            for idx in existing_indexes
        )
        
        if not composite_exists:
            recommendations.append(IndexRecommendation(
                table_name='token_usage',
                columns=['created_at', 'model'],
                index_type='btree',
                reason='Daily cost tracking by model',
                estimated_benefit='high',
                sql_command='CREATE INDEX idx_token_usage_cost_tracking ON token_usage(created_at, model);'
            ))
        
        return recommendations
    
    def _analyze_media_files_table(self) -> List[IndexRecommendation]:
        """Analyze media_files table for index opportunities"""
        recommendations = []
        
        existing_indexes = self.get_existing_indexes().get('media_files', [])
        existing_columns = set()
        for idx in existing_indexes:
            existing_columns.update(idx.get('column_names', []))
        
        if 'post_id' not in existing_columns:
            recommendations.append(IndexRecommendation(
                table_name='media_files',
                columns=['post_id'],
                index_type='btree',
                reason='Foreign key relationship with posts table',
                estimated_benefit='high',
                sql_command='CREATE INDEX idx_media_files_post_id ON media_files(post_id);'
            ))
        
        return recommendations
    
    def apply_index_recommendations(self, recommendations: List[IndexRecommendation]) -> Dict[str, Any]:
        """
        Apply index recommendations to the database
        """
        results = {
            'applied': [],
            'failed': [],
            'skipped': []
        }
        
        for rec in recommendations:
            try:
                # Check if index already exists
                existing_indexes = self.get_existing_indexes().get(rec.table_name, [])
                index_exists = any(
                    set(idx.get('column_names', [])) == set(rec.columns)
                    for idx in existing_indexes
                )
                
                if index_exists:
                    results['skipped'].append({
                        'recommendation': rec.__dict__,
                        'reason': 'Index already exists'
                    })
                    continue
                
                # Apply the index
                self.db_session.execute(text(rec.sql_command))
                self.db_session.commit()
                
                results['applied'].append(rec.__dict__)
                logger.info(f"Applied index: {rec.sql_command}")
                
            except Exception as e:
                results['failed'].append({
                    'recommendation': rec.__dict__,
                    'error': str(e)
                })
                logger.error(f"Failed to apply index {rec.sql_command}: {e}")
                self.db_session.rollback()
        
        return results
    
    def update_table_statistics(self) -> Dict[str, Any]:
        """
        Update PostgreSQL table statistics for better query planning
        """
        results = {
            'analyzed_tables': [],
            'failed_tables': []
        }
        
        tables = ['posts', 'processing_logs', 'token_usage', 'media_files']
        
        for table in tables:
            try:
                # Run ANALYZE on the table
                self.db_session.execute(text(f"ANALYZE {table}"))
                self.db_session.commit()
                
                results['analyzed_tables'].append(table)
                logger.info(f"Updated statistics for table: {table}")
                
            except Exception as e:
                results['failed_tables'].append({
                    'table': table,
                    'error': str(e)
                })
                logger.error(f"Failed to analyze table {table}: {e}")
                self.db_session.rollback()
        
        return results


class APIResponseTimeMonitor:
    """
    Monitor API response times for performance optimization
    """
    
    def __init__(self):
        self.response_times = {}
        self.slow_query_threshold_ms = 300  # 300ms threshold
    
    def record_response_time(self, endpoint: str, method: str, duration_ms: float):
        """Record API response time"""
        key = f"{method}:{endpoint}"
        
        if key not in self.response_times:
            self.response_times[key] = {
                'count': 0,
                'total_time': 0.0,
                'min_time': float('inf'),
                'max_time': 0.0,
                'slow_requests': 0
            }
        
        stats = self.response_times[key]
        stats['count'] += 1
        stats['total_time'] += duration_ms
        stats['min_time'] = min(stats['min_time'], duration_ms)
        stats['max_time'] = max(stats['max_time'], duration_ms)
        
        if duration_ms > self.slow_query_threshold_ms:
            stats['slow_requests'] += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get API performance summary"""
        summary = {
            'endpoints': {},
            'overall_stats': {
                'total_requests': 0,
                'total_slow_requests': 0,
                'avg_response_time': 0.0
            }
        }
        
        total_requests = 0
        total_time = 0.0
        total_slow = 0
        
        for endpoint, stats in self.response_times.items():
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            slow_percentage = (stats['slow_requests'] / stats['count'] * 100) if stats['count'] > 0 else 0
            
            summary['endpoints'][endpoint] = {
                'request_count': stats['count'],
                'avg_response_time_ms': round(avg_time, 2),
                'min_response_time_ms': round(stats['min_time'], 2),
                'max_response_time_ms': round(stats['max_time'], 2),
                'slow_requests': stats['slow_requests'],
                'slow_percentage': round(slow_percentage, 2)
            }
            
            total_requests += stats['count']
            total_time += stats['total_time']
            total_slow += stats['slow_requests']
        
        summary['overall_stats'] = {
            'total_requests': total_requests,
            'total_slow_requests': total_slow,
            'avg_response_time': round(total_time / total_requests, 2) if total_requests > 0 else 0,
            'slow_percentage': round(total_slow / total_requests * 100, 2) if total_requests > 0 else 0
        }
        
        return summary
    
    def get_slow_endpoints(self, threshold_ms: Optional[float] = None) -> List[Dict[str, Any]]:
        """Get endpoints with slow response times"""
        threshold = threshold_ms or self.slow_query_threshold_ms
        slow_endpoints = []
        
        for endpoint, stats in self.response_times.items():
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            
            if avg_time > threshold:
                slow_endpoints.append({
                    'endpoint': endpoint,
                    'avg_response_time_ms': round(avg_time, 2),
                    'max_response_time_ms': round(stats['max_time'], 2),
                    'request_count': stats['count'],
                    'slow_requests': stats['slow_requests']
                })
        
        # Sort by average response time (slowest first)
        slow_endpoints.sort(key=lambda x: x['avg_response_time_ms'], reverse=True)
        
        return slow_endpoints


# Global instances
limited_cache_manager = LimitedCacheManager()
api_response_monitor = APIResponseTimeMonitor()


# Convenience functions
def get_cached_status_data(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached status data (limited scope)"""
    import asyncio
    loop = asyncio.get_event_loop()
    
    if cache_key == 'queue_status':
        return loop.run_until_complete(limited_cache_manager.get_cached_queue_status())
    elif cache_key == 'worker_status':
        return loop.run_until_complete(limited_cache_manager.get_cached_worker_status())
    elif cache_key == 'system_metrics':
        return loop.run_until_complete(limited_cache_manager.get_cached_system_metrics())
    elif cache_key == 'scaling_status':
        return loop.run_until_complete(limited_cache_manager.get_cached_scaling_status())
    
    return None


def cache_status_data(cache_key: str, data: Dict[str, Any]) -> bool:
    """Cache status data (limited scope)"""
    import asyncio
    loop = asyncio.get_event_loop()
    
    if cache_key == 'queue_status':
        return loop.run_until_complete(limited_cache_manager.cache_queue_status(data))
    elif cache_key == 'worker_status':
        return loop.run_until_complete(limited_cache_manager.cache_worker_status(data))
    elif cache_key == 'system_metrics':
        return loop.run_until_complete(limited_cache_manager.cache_system_metrics(data))
    elif cache_key == 'scaling_status':
        return loop.run_until_complete(limited_cache_manager.cache_scaling_status(data))
    
    return False


def optimize_database_indexes(db_session: Session) -> Dict[str, Any]:
    """Optimize database indexes"""
    optimizer = DatabaseIndexOptimizer(db_session)
    
    # Get recommendations
    recommendations = optimizer.generate_index_recommendations()
    
    # Apply high-benefit recommendations automatically
    high_benefit_recs = [rec for rec in recommendations if rec.estimated_benefit == 'high']
    
    results = {
        'recommendations': [rec.__dict__ for rec in recommendations],
        'applied_automatically': [],
        'manual_review_needed': []
    }
    
    if high_benefit_recs:
        apply_results = optimizer.apply_index_recommendations(high_benefit_recs)
        results['applied_automatically'] = apply_results
    
    # Medium/low benefit recommendations need manual review
    manual_recs = [rec for rec in recommendations if rec.estimated_benefit in ['medium', 'low']]
    results['manual_review_needed'] = [rec.__dict__ for rec in manual_recs]
    
    return results


def update_database_statistics(db_session: Session) -> Dict[str, Any]:
    """Update database table statistics"""
    optimizer = DatabaseIndexOptimizer(db_session)
    return optimizer.update_table_statistics()


def get_api_performance_summary() -> Dict[str, Any]:
    """Get API performance summary"""
    return api_response_monitor.get_performance_summary()


def record_api_response_time(endpoint: str, method: str, duration_ms: float):
    """Record API response time for monitoring"""
    api_response_monitor.record_response_time(endpoint, method, duration_ms)