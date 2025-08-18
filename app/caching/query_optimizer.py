"""
Database query optimization and caching strategies
"""

import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

from sqlalchemy import text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from prometheus_client import Counter, Histogram, Gauge

from app.caching.redis_cache import cache, cached
from app.infrastructure import get_database

logger = logging.getLogger(__name__)

# Prometheus metrics for query optimization
query_duration = Histogram('db_query_duration_seconds', 'Database query duration', ['query_type', 'table'])
query_count = Counter('db_queries_total', 'Total database queries', ['query_type', 'table', 'cached'])
slow_query_count = Counter('db_slow_queries_total', 'Slow database queries', ['query_type', 'table'])
connection_pool_size = Gauge('db_connection_pool_size', 'Database connection pool size')
connection_pool_checked_out = Gauge('db_connection_pool_checked_out', 'Checked out database connections')

@dataclass
class QueryStats:
    """Statistics for database queries"""
    query_type: str
    table: str
    duration: float
    cached: bool
    timestamp: datetime

class QueryOptimizer:
    """Database query optimization and caching"""
    
    def __init__(self):
        self.database = get_database()
        self.slow_query_threshold = 1.0  # 1 second
        self.query_stats: List[QueryStats] = []
        self.max_stats_size = 1000
        
        # Setup query logging
        self._setup_query_logging()
    
    def _setup_query_logging(self):
        """Setup SQLAlchemy query logging for monitoring"""
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(Engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - context._query_start_time
            
            # Extract query type and table
            query_type = self._extract_query_type(statement)
            table = self._extract_table_name(statement)
            
            # Record metrics
            query_duration.labels(query_type=query_type, table=table).observe(total)
            query_count.labels(query_type=query_type, table=table, cached='false').inc()
            
            # Log slow queries
            if total > self.slow_query_threshold:
                slow_query_count.labels(query_type=query_type, table=table).inc()
                logger.warning(
                    "Slow query detected",
                    duration=total,
                    query_type=query_type,
                    table=table,
                    statement=statement[:200] + "..." if len(statement) > 200 else statement
                )
            
            # Store stats
            self._add_query_stat(QueryStats(
                query_type=query_type,
                table=table,
                duration=total,
                cached=False,
                timestamp=datetime.utcnow()
            ))
    
    def _extract_query_type(self, statement: str) -> str:
        """Extract query type from SQL statement"""
        statement_upper = statement.strip().upper()
        if statement_upper.startswith('SELECT'):
            return 'SELECT'
        elif statement_upper.startswith('INSERT'):
            return 'INSERT'
        elif statement_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif statement_upper.startswith('DELETE'):
            return 'DELETE'
        elif statement_upper.startswith('CREATE'):
            return 'CREATE'
        elif statement_upper.startswith('ALTER'):
            return 'ALTER'
        elif statement_upper.startswith('DROP'):
            return 'DROP'
        else:
            return 'OTHER'
    
    def _extract_table_name(self, statement: str) -> str:
        """Extract primary table name from SQL statement"""
        try:
            statement_upper = statement.strip().upper()
            
            if 'FROM ' in statement_upper:
                # Extract table after FROM
                from_index = statement_upper.find('FROM ')
                after_from = statement_upper[from_index + 5:].strip()
                table_name = after_from.split()[0].strip('`"[]')
                return table_name.lower()
            elif statement_upper.startswith('INSERT INTO'):
                # Extract table after INSERT INTO
                into_index = statement_upper.find('INTO ')
                after_into = statement_upper[into_index + 5:].strip()
                table_name = after_into.split()[0].strip('`"[]')
                return table_name.lower()
            elif statement_upper.startswith('UPDATE '):
                # Extract table after UPDATE
                after_update = statement_upper[7:].strip()
                table_name = after_update.split()[0].strip('`"[]')
                return table_name.lower()
            elif statement_upper.startswith('DELETE FROM'):
                # Extract table after DELETE FROM
                from_index = statement_upper.find('FROM ')
                after_from = statement_upper[from_index + 5:].strip()
                table_name = after_from.split()[0].strip('`"[]')
                return table_name.lower()
            
            return 'unknown'
            
        except Exception:
            return 'unknown'
    
    def _add_query_stat(self, stat: QueryStats):
        """Add query statistics"""
        self.query_stats.append(stat)
        if len(self.query_stats) > self.max_stats_size:
            self.query_stats.pop(0)
    
    @cached(cache_type='reddit_posts', ttl=900)  # 15 minutes
    async def get_recent_posts(self, limit: int = 100, subreddit: Optional[str] = None) -> List[Dict]:
        """Get recent posts with caching"""
        with self.database.connect() as conn:
            query = """
            SELECT id, title, subreddit, score, comments, created_ts, 
                   summary_ko, topic_tag, ghost_url, status
            FROM posts 
            WHERE status IN ('processed', 'published')
            """
            
            params = {}
            if subreddit:
                query += " AND subreddit = :subreddit"
                params['subreddit'] = subreddit
            
            query += " ORDER BY created_ts DESC LIMIT :limit"
            params['limit'] = limit
            
            result = conn.execute(text(query), params)
            posts = [dict(row._mapping) for row in result]
            
            # Record cache miss
            query_count.labels(query_type='SELECT', table='posts', cached='true').inc()
            
            return posts
    
    @cached(cache_type='processed_content', ttl=7200)  # 2 hours
    async def get_post_by_id(self, post_id: str) -> Optional[Dict]:
        """Get post by ID with caching"""
        with self.database.connect() as conn:
            query = """
            SELECT p.*, 
                   COALESCE(
                       JSON_AGG(
                           JSON_BUILD_OBJECT(
                               'id', m.id,
                               'original_url', m.original_url,
                               'ghost_url', m.ghost_url,
                               'file_type', m.file_type
                           )
                       ) FILTER (WHERE m.id IS NOT NULL), 
                       '[]'
                   ) as media_files
            FROM posts p
            LEFT JOIN media_files m ON p.id = m.post_id
            WHERE p.id = :post_id
            GROUP BY p.id
            """
            
            result = conn.execute(text(query), {'post_id': post_id})
            row = result.fetchone()
            
            if row:
                query_count.labels(query_type='SELECT', table='posts', cached='true').inc()
                return dict(row._mapping)
            
            return None
    
    @cached(cache_type='subreddit_info', ttl=3600)  # 1 hour
    async def get_subreddit_stats(self, subreddit: str) -> Dict:
        """Get subreddit statistics with caching"""
        with self.database.connect() as conn:
            query = """
            SELECT 
                subreddit,
                COUNT(*) as total_posts,
                AVG(score) as avg_score,
                AVG(comments) as avg_comments,
                COUNT(CASE WHEN status = 'published' THEN 1 END) as published_count,
                MAX(created_ts) as latest_post,
                MIN(created_ts) as earliest_post
            FROM posts 
            WHERE subreddit = :subreddit
            GROUP BY subreddit
            """
            
            result = conn.execute(text(query), {'subreddit': subreddit})
            row = result.fetchone()
            
            if row:
                stats = dict(row._mapping)
                # Convert datetime objects to ISO strings
                if stats.get('latest_post'):
                    stats['latest_post'] = stats['latest_post'].isoformat()
                if stats.get('earliest_post'):
                    stats['earliest_post'] = stats['earliest_post'].isoformat()
                
                query_count.labels(query_type='SELECT', table='posts', cached='true').inc()
                return stats
            
            return {}
    
    async def get_trending_topics(self, days: int = 7, limit: int = 20) -> List[Dict]:
        """Get trending topics (not cached due to frequent changes)"""
        with self.database.connect() as conn:
            query = """
            SELECT 
                topic_tag,
                COUNT(*) as post_count,
                AVG(score) as avg_score,
                SUM(score) as total_score,
                MAX(created_ts) as latest_post
            FROM posts 
            WHERE topic_tag IS NOT NULL 
                AND created_ts >= NOW() - INTERVAL ':days days'
                AND status IN ('processed', 'published')
            GROUP BY topic_tag
            ORDER BY post_count DESC, total_score DESC
            LIMIT :limit
            """
            
            result = conn.execute(text(query), {'days': days, 'limit': limit})
            topics = []
            
            for row in result:
                topic = dict(row._mapping)
                if topic.get('latest_post'):
                    topic['latest_post'] = topic['latest_post'].isoformat()
                topics.append(topic)
            
            return topics
    
    async def optimize_table_indexes(self) -> Dict[str, Any]:
        """Analyze and suggest index optimizations"""
        suggestions = []
        
        with self.database.connect() as conn:
            # Check for missing indexes on frequently queried columns
            
            # 1. Check posts table queries
            query_patterns = [
                ("posts", "status", "Frequently filtered by status"),
                ("posts", "subreddit", "Frequently filtered by subreddit"),
                ("posts", "created_ts", "Frequently ordered by creation time"),
                ("posts", "score", "Frequently filtered by score"),
                ("processing_logs", "post_id", "Foreign key lookups"),
                ("media_files", "post_id", "Foreign key lookups"),
                ("token_usage", "created_at", "Time-based queries")
            ]
            
            for table, column, reason in query_patterns:
                # Check if index exists
                index_query = """
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = :table 
                    AND indexdef LIKE '%' || :column || '%'
                """
                
                result = conn.execute(text(index_query), {
                    'table': table, 
                    'column': column
                })
                
                if not result.fetchone():
                    suggestions.append({
                        'type': 'missing_index',
                        'table': table,
                        'column': column,
                        'reason': reason,
                        'sql': f"CREATE INDEX idx_{table}_{column} ON {table}({column});"
                    })
            
            # 2. Check for unused indexes
            unused_indexes_query = """
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes 
            WHERE idx_scan = 0 
                AND schemaname = 'public'
            """
            
            result = conn.execute(text(unused_indexes_query))
            for row in result:
                suggestions.append({
                    'type': 'unused_index',
                    'table': row.tablename,
                    'index': row.indexname,
                    'reason': 'Index never used',
                    'sql': f"DROP INDEX {row.indexname};"
                })
            
            # 3. Check table statistics
            table_stats_query = """
            SELECT 
                schemaname,
                tablename,
                n_tup_ins,
                n_tup_upd,
                n_tup_del,
                n_live_tup,
                n_dead_tup,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables 
            WHERE schemaname = 'public'
            """
            
            result = conn.execute(text(table_stats_query))
            table_stats = [dict(row._mapping) for row in result]
            
            # Check for tables that need VACUUM or ANALYZE
            for stats in table_stats:
                dead_ratio = (stats['n_dead_tup'] / max(stats['n_live_tup'], 1)) if stats['n_live_tup'] else 0
                
                if dead_ratio > 0.2:  # More than 20% dead tuples
                    suggestions.append({
                        'type': 'maintenance',
                        'table': stats['tablename'],
                        'reason': f'High dead tuple ratio: {dead_ratio:.2%}',
                        'sql': f"VACUUM ANALYZE {stats['tablename']};"
                    })
        
        return {
            'suggestions': suggestions,
            'total_suggestions': len(suggestions),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_query_performance_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get query performance statistics"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_stats = [s for s in self.query_stats if s.timestamp >= cutoff_time]
        
        if not recent_stats:
            return {'error': 'No query statistics available'}
        
        # Group by query type and table
        performance_by_type = {}
        for stat in recent_stats:
            key = f"{stat.query_type}:{stat.table}"
            if key not in performance_by_type:
                performance_by_type[key] = {
                    'query_type': stat.query_type,
                    'table': stat.table,
                    'count': 0,
                    'total_duration': 0,
                    'min_duration': float('inf'),
                    'max_duration': 0,
                    'cached_count': 0
                }
            
            perf = performance_by_type[key]
            perf['count'] += 1
            perf['total_duration'] += stat.duration
            perf['min_duration'] = min(perf['min_duration'], stat.duration)
            perf['max_duration'] = max(perf['max_duration'], stat.duration)
            
            if stat.cached:
                perf['cached_count'] += 1
        
        # Calculate averages and cache hit rates
        for perf in performance_by_type.values():
            perf['avg_duration'] = perf['total_duration'] / perf['count']
            perf['cache_hit_rate'] = perf['cached_count'] / perf['count']
            perf['min_duration'] = perf['min_duration'] if perf['min_duration'] != float('inf') else 0
        
        # Sort by average duration (slowest first)
        sorted_performance = sorted(
            performance_by_type.values(),
            key=lambda x: x['avg_duration'],
            reverse=True
        )
        
        return {
            'period_hours': hours,
            'total_queries': len(recent_stats),
            'performance_by_type': sorted_performance,
            'overall_stats': {
                'avg_duration': sum(s.duration for s in recent_stats) / len(recent_stats),
                'max_duration': max(s.duration for s in recent_stats),
                'min_duration': min(s.duration for s in recent_stats),
                'cache_hit_rate': sum(1 for s in recent_stats if s.cached) / len(recent_stats)
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def update_table_statistics(self) -> Dict[str, bool]:
        """Update table statistics for query optimization"""
        results = {}
        tables = ['posts', 'media_files', 'processing_logs', 'token_usage']
        
        with self.database.connect() as conn:
            for table in tables:
                try:
                    conn.execute(text(f"ANALYZE {table}"))
                    results[table] = True
                    logger.info(f"Updated statistics for table: {table}")
                except Exception as e:
                    logger.error(f"Error updating statistics for table {table}: {e}")
                    results[table] = False
        
        return results

def query_cache_key(func_name: str, *args, **kwargs) -> str:
    """Generate cache key for query functions"""
    key_parts = [func_name]
    key_parts.extend([str(arg) for arg in args])
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    return ":".join(key_parts)

def optimized_query(cache_type: str = 'default', ttl: Optional[int] = None):
    """Decorator for optimized database queries with caching"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = query_cache_key(func.__name__, *args, **kwargs)
            
            # Try cache first
            cached_result = await cache.get(cache_key, cache_type)
            if cached_result is not None:
                query_count.labels(
                    query_type='SELECT', 
                    table='cached', 
                    cached='true'
                ).inc()
                return cached_result
            
            # Execute query
            start_time = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Cache result
            await cache.set(cache_key, result, cache_type, ttl)
            
            # Record metrics
            query_duration.labels(query_type='SELECT', table='optimized').observe(duration)
            query_count.labels(
                query_type='SELECT', 
                table='optimized', 
                cached='false'
            ).inc()
            
            return result
        
        return wrapper
    return decorator

# Global query optimizer instance
query_optimizer = QueryOptimizer()