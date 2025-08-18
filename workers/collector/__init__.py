"""
Reddit Collector Service

This service handles:
- Reddit API integration with rate limiting
- Content filtering and validation
- Velocity calculation and trend analysis
- Celery task management for collection workflow
"""

from .reddit_client import reddit_client, RedditClient, RedditPost, get_reddit_client, init_reddit_client
from .content_filter import content_filter, ContentFilter, FilterResult
from .trend_analyzer import (
    velocity_calculator, 
    trend_analyzer, 
    VelocityCalculator, 
    TrendAnalyzer, 
    VelocityMetrics,
    TrendDirection
)
from .tasks import (
    collect_reddit_posts,
    calculate_velocity,
    analyze_subreddit_trends,
    get_trending_posts,
    health_check,
    cleanup_old_results,
    get_task_status
)

__all__ = [
    # Reddit client
    "reddit_client",
    "RedditClient", 
    "RedditPost",
    "get_reddit_client",
    "init_reddit_client",
    
    # Content filtering
    "content_filter",
    "ContentFilter",
    "FilterResult",
    
    # Trend analysis
    "velocity_calculator",
    "trend_analyzer",
    "VelocityCalculator",
    "TrendAnalyzer", 
    "VelocityMetrics",
    "TrendDirection",
    
    # Celery tasks
    "collect_reddit_posts",
    "calculate_velocity", 
    "analyze_subreddit_trends",
    "get_trending_posts",
    "health_check",
    "cleanup_old_results",
    "get_task_status"
]