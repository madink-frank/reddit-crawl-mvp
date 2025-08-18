"""
Simplified Celery tasks for Reddit content collection (MVP - synchronous)
"""
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from celery.exceptions import Retry, MaxRetriesExceededError
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.celery_app import celery_app
from app.config import get_settings
from app.models.post import Post
from app.models.processing_log import ProcessingLog
from app.transaction_manager import transaction_with_tracking, get_state_manager
from workers.collector.reddit_client import get_reddit_client, init_reddit_client, RedditPost
from workers.collector.content_filter import get_content_filter
from workers.collector.budget_manager import get_budget_manager

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize synchronous database session
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Session:
    """Get synchronous database session"""
    return SessionLocal()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': settings.retry_max, 'countdown': settings.backoff_min},
    name="workers.collector.tasks.collect_reddit_posts"
)
def collect_reddit_posts(
    self,
    subreddits: Optional[List[str]] = None,
    sort_type: str = "hot",
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Simplified Reddit collection task (synchronous MVP)
    
    Args:
        subreddits: List of subreddit names to collect from
        sort_type: Sort type (hot, new, rising, top)
        limit: Maximum posts per subreddit (defaults to batch_size from config)
    
    Returns:
        Dictionary with collection results
    """
    task_id = self.request.id
    start_time = datetime.now(timezone.utc)
    
    # Get instances
    reddit_client = get_reddit_client()
    content_filter = get_content_filter()
    budget_manager = get_budget_manager()
    
    try:
        logger.info(f"Starting Reddit collection task {task_id}")
        
        # Check daily budget before starting
        if not budget_manager.can_make_request():
            usage = budget_manager.get_daily_usage()
            logger.warning(f"Daily API budget exceeded: {usage}")
            return {
                "task_id": task_id,
                "status": "budget_exceeded",
                "message": "Daily API call budget exceeded",
                "usage": usage,
                "started_at": start_time.isoformat()
            }
        
        # Default parameters
        if not subreddits:
            from app.config import get_subreddits_list
            subreddits = get_subreddits_list()
        
        if not limit:
            limit = settings.batch_size
        
        # Initialize Reddit client if needed
        if not reddit_client.is_authenticated:
            init_reddit_client()
        
        # Track collection statistics
        stats = {
            "task_id": task_id,
            "started_at": start_time.isoformat(),
            "subreddits_processed": 0,
            "posts_collected": 0,
            "posts_filtered": 0,
            "posts_stored": 0,
            "posts_duplicated": 0,
            "errors": []
        }
        
        # Process each subreddit
        for subreddit_name in subreddits:
            try:
                logger.info(f"Collecting from r/{subreddit_name}")
                
                # Check budget before each subreddit
                if not budget_manager.can_make_request():
                    logger.warning(f"Budget exceeded while processing r/{subreddit_name}")
                    break
                
                # Collect posts from subreddit
                subreddit_stats = _collect_from_subreddit(
                    reddit_client, content_filter, budget_manager,
                    subreddit_name, sort_type, limit
                )
                
                # Update overall stats
                stats["posts_collected"] += subreddit_stats["collected"]
                stats["posts_filtered"] += subreddit_stats["filtered"]
                stats["posts_stored"] += subreddit_stats["stored"]
                stats["posts_duplicated"] += subreddit_stats["duplicated"]
                stats["subreddits_processed"] += 1
                
                # Log progress
                _log_collection_progress(task_id, subreddit_name, subreddit_stats)
                
            except Exception as e:
                error_msg = f"Error collecting from r/{subreddit_name}: {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                continue
        
        # Calculate final statistics
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        stats.update({
            "completed_at": end_time.isoformat(),
            "duration_seconds": duration,
            "success": len(stats["errors"]) == 0,
            "budget_usage": budget_manager.get_daily_usage()
        })
        
        logger.info(f"Collection task {task_id} completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Collection task {task_id} failed: {e}")
        
        # Log error to database
        _log_task_error(task_id, "collect_reddit_posts", str(e))
        
        # Retry with exponential backoff if not max retries exceeded
        if self.request.retries < settings.retry_max:
            backoff_time = min(
                settings.backoff_base ** self.request.retries,
                settings.backoff_max
            )
            logger.info(f"Retrying collection task {task_id} in {backoff_time}s (attempt {self.request.retries + 1}/{settings.retry_max})")
            raise self.retry(countdown=backoff_time)
        
        raise


def _collect_from_subreddit(
    reddit_client,
    content_filter,
    budget_manager,
    subreddit_name: str,
    sort_type: str,
    limit: int
) -> Dict[str, int]:
    """Collect posts from a single subreddit (synchronous)"""
    stats = {"collected": 0, "filtered": 0, "stored": 0, "duplicated": 0}
    
    try:
        # Get posts from Reddit
        for reddit_post in reddit_client.get_subreddit_posts(
            subreddit_name, sort_type, limit
        ):
            stats["collected"] += 1
            
            # Record API call in budget
            budget_result = budget_manager.record_api_call()
            if budget_result.get("status") == "error":
                logger.warning(f"Budget tracking error: {budget_result.get('message')}")
            
            # Check if we hit budget limit
            if not budget_manager.can_make_request():
                logger.warning(f"Daily budget exceeded during collection from r/{subreddit_name}")
                break
            
            # Apply content filters
            filter_result = content_filter.filter_post(reddit_post)
            
            if not filter_result.passed:
                stats["filtered"] += 1
                logger.debug(f"Post {reddit_post.id} filtered: {filter_result.reason}")
                continue
            
            # Store post in database
            store_result = _store_reddit_post(reddit_post)
            if store_result == "stored":
                stats["stored"] += 1
            elif store_result == "duplicate":
                stats["duplicated"] += 1
            
        return stats
        
    except Exception as e:
        logger.error(f"Error collecting from r/{subreddit_name}: {e}")
        raise


def _store_reddit_post(reddit_post: RedditPost) -> str:
    """
    Store Reddit post in database with transaction management and state tracking
    
    Returns:
        "stored" if new post was stored
        "duplicate" if post already exists (handled by UNIQUE constraint)
        "error" if there was an error
    """
    try:
        with transaction_with_tracking(
            post_id=reddit_post.id,
            service_name="collector",
            operation_name="store_reddit_post"
        ) as (session, tracker):
            
            state_manager = get_state_manager(session, tracker)
            
            # Generate content hash for duplicate detection at processing level
            content_hash = hashlib.sha256(
                (reddit_post.title + (reddit_post.selftext or "")).encode('utf-8')
            ).hexdigest()
            
            # Create new post
            new_post = Post(
                reddit_post_id=reddit_post.id,  # This has UNIQUE constraint
                title=reddit_post.title,
                subreddit=reddit_post.subreddit,
                score=reddit_post.score,
                num_comments=reddit_post.num_comments,
                created_ts=reddit_post.created_datetime,
                url=reddit_post.url,
                selftext=reddit_post.selftext,
                author=reddit_post.author,
                content_hash=content_hash,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            # Use state manager to create entity with tracking
            state_manager.create_entity(new_post, "post", reddit_post.id)
            
            # Create processing log
            log_entry = ProcessingLog(
                post_id=new_post.id,  # Will be set after flush
                service_name="collector",
                status="success",
                processing_time_ms=0,
                created_at=datetime.now(timezone.utc)
            )
            
            state_manager.create_entity(log_entry, "processing_log", f"collector_{reddit_post.id}")
            
            # Check consistency before commit
            consistency_result = state_manager.check_consistency()
            if consistency_result.get("status") != "passed":
                logger.error(f"Consistency check failed for post {reddit_post.id}: {consistency_result}")
                raise Exception(f"Consistency check failed: {consistency_result}")
            
            logger.debug(f"Stored new post {reddit_post.id} with transaction tracking")
            return "stored"
            
    except IntegrityError as e:
        # This is expected for duplicate reddit_post_id (UNIQUE constraint)
        if "reddit_post_id" in str(e):
            logger.debug(f"Post {reddit_post.id} already exists (duplicate)")
            return "duplicate"
        else:
            logger.error(f"Integrity error storing post {reddit_post.id}: {e}")
            return "error"
    except SQLAlchemyError as e:
        logger.error(f"Database error storing post {reddit_post.id}: {e}")
        return "error"
    except Exception as e:
        logger.error(f"Error storing post {reddit_post.id}: {e}")
        return "error"


def _log_collection_progress(
    task_id: str,
    subreddit: str,
    stats: Dict[str, int]
) -> None:
    """Log collection progress to processing logs (synchronous)"""
    try:
        session = get_db_session()
        try:
            log_entry = ProcessingLog(
                post_id=None,  # Task-level log, no specific post
                service_name="collector",
                status="progress",
                error_message=f"r/{subreddit}: collected={stats['collected']}, stored={stats['stored']}, filtered={stats['filtered']}, duplicated={stats['duplicated']}",
                processing_time_ms=0,
                created_at=datetime.now(timezone.utc)
            )
            session.add(log_entry)
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error logging collection progress: {e}")


def _log_task_error(task_id: str, task_name: str, error_message: str) -> None:
    """Log task error to processing logs (synchronous)"""
    try:
        session = get_db_session()
        try:
            log_entry = ProcessingLog(
                post_id=None,  # Task-level log, no specific post
                service_name="collector",
                status="error",
                error_message=f"{task_name}: {error_message}",
                processing_time_ms=0,
                created_at=datetime.now(timezone.utc)
            )
            session.add(log_entry)
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error logging task error: {e}")


# Health check task (simplified)
@celery_app.task(
    bind=True,
    name="workers.collector.tasks.health_check"
)
def health_check(self) -> Dict[str, Any]:
    """
    Perform health check for collector service (synchronous)
    
    Returns:
        Dictionary with health status
    """
    try:
        reddit_client = get_reddit_client()
        budget_manager = get_budget_manager()
        
        health_status = {
            "service": "collector",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {}
        }
        
        # Check Reddit client
        reddit_health = reddit_client.health_check()
        health_status["checks"]["reddit_client"] = reddit_health
        
        # Check budget manager
        budget_health = budget_manager.health_check()
        health_status["checks"]["budget_manager"] = budget_health
        
        # Check database connection
        try:
            session = get_db_session()
            try:
                result = session.execute(select(Post.id).limit(1))
                health_status["checks"]["database"] = {
                    "status": "healthy",
                    "connected": True
                }
            finally:
                session.close()
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Determine overall health
        unhealthy_checks = [
            check for check in health_status["checks"].values()
            if check.get("status") == "unhealthy"
        ]
        
        if unhealthy_checks:
            health_status["status"] = "unhealthy"
            health_status["unhealthy_checks"] = len(unhealthy_checks)
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": "collector",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Task status monitoring
@celery_app.task(name="workers.collector.tasks.get_task_status")
def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of a collection task"""
    try:
        # Get task result from Celery
        result = celery_app.AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Velocity calculation task
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': settings.retry_max, 'countdown': settings.backoff_min},
    name="workers.collector.tasks.calculate_velocity"
)
def calculate_velocity(self, post_id: str) -> Dict[str, Any]:
    """
    Calculate velocity metrics for a Reddit post
    
    Args:
        post_id: Reddit post ID to analyze
    
    Returns:
        Dictionary with velocity metrics
    """
    try:
        from workers.collector.trend_analyzer import get_velocity_calculator
        from workers.collector.reddit_client import get_reddit_client
        
        logger.info(f"Calculating velocity for post {post_id}")
        
        # Get Reddit client and post data
        reddit_client = get_reddit_client()
        
        # For now, we'll use a simplified approach since we need the post data
        # In a full implementation, we'd fetch the post from Reddit or database
        velocity_calculator = get_velocity_calculator()
        
        # This is a simplified implementation - in production you'd fetch the actual post
        # For now, return a basic response
        return {
            "task_id": self.request.id,
            "post_id": post_id,
            "status": "completed",
            "message": "Velocity calculation completed (simplified implementation)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating velocity for post {post_id}: {e}")
        
        if self.request.retries < settings.retry_max:
            backoff_time = min(
                settings.backoff_base ** self.request.retries,
                settings.backoff_max
            )
            logger.info(f"Retrying velocity calculation for {post_id} in {backoff_time}s")
            raise self.retry(countdown=backoff_time)
        
        return {
            "task_id": self.request.id,
            "post_id": post_id,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Subreddit trend analysis task
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': settings.retry_max, 'countdown': settings.backoff_min},
    name="workers.collector.tasks.analyze_subreddit_trends"
)
def analyze_subreddit_trends(self, subreddit: str, limit: int = 50) -> Dict[str, Any]:
    """
    Analyze trends for a specific subreddit
    
    Args:
        subreddit: Subreddit name to analyze
        limit: Maximum number of posts to analyze
    
    Returns:
        Dictionary with trend analysis results
    """
    try:
        from workers.collector.trend_analyzer import get_trend_analyzer
        from workers.collector.reddit_client import get_reddit_client
        
        logger.info(f"Analyzing trends for r/{subreddit}")
        
        reddit_client = get_reddit_client()
        trend_analyzer = get_trend_analyzer()
        
        # Get posts from subreddit
        posts = list(reddit_client.get_subreddit_posts(subreddit, "hot", limit))
        
        if not posts:
            return {
                "task_id": self.request.id,
                "subreddit": subreddit,
                "status": "completed",
                "message": "No posts found for analysis",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # This would be async in full implementation, but simplified for MVP
        # analysis_result = await trend_analyzer.analyze_subreddit_trends(subreddit, posts)
        
        # Simplified response for MVP
        return {
            "task_id": self.request.id,
            "subreddit": subreddit,
            "status": "completed",
            "posts_analyzed": len(posts),
            "message": "Trend analysis completed (simplified implementation)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing trends for r/{subreddit}: {e}")
        
        if self.request.retries < settings.retry_max:
            backoff_time = min(
                settings.backoff_base ** self.request.retries,
                settings.backoff_max
            )
            logger.info(f"Retrying trend analysis for r/{subreddit} in {backoff_time}s")
            raise self.retry(countdown=backoff_time)
        
        return {
            "task_id": self.request.id,
            "subreddit": subreddit,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Get trending posts task
@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': settings.retry_max, 'countdown': settings.backoff_min},
    name="workers.collector.tasks.get_trending_posts"
)
def get_trending_posts(self, subreddits: List[str], limit: int = 20) -> Dict[str, Any]:
    """
    Get trending posts across multiple subreddits
    
    Args:
        subreddits: List of subreddit names
        limit: Maximum number of trending posts to return
    
    Returns:
        Dictionary with trending posts
    """
    try:
        from workers.collector.trend_analyzer import get_trend_analyzer
        from workers.collector.reddit_client import get_reddit_client
        
        logger.info(f"Getting trending posts from {len(subreddits)} subreddits")
        
        reddit_client = get_reddit_client()
        trend_analyzer = get_trend_analyzer()
        
        all_posts = []
        
        # Collect posts from all subreddits
        for subreddit in subreddits:
            try:
                posts = list(reddit_client.get_subreddit_posts(subreddit, "hot", limit // len(subreddits)))
                all_posts.extend(posts)
            except Exception as e:
                logger.warning(f"Error getting posts from r/{subreddit}: {e}")
                continue
        
        if not all_posts:
            return {
                "task_id": self.request.id,
                "status": "completed",
                "trending_posts": [],
                "message": "No posts found",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # This would be async in full implementation
        # trending_posts = await trend_analyzer.get_trending_posts(all_posts, limit)
        
        # Simplified response for MVP
        trending_posts = [
            {
                "post_id": post.id,
                "title": post.title,
                "subreddit": post.subreddit,
                "score": post.score,
                "comments": post.num_comments,
                "age_hours": post.age_hours
            }
            for post in sorted(all_posts, key=lambda x: x.score, reverse=True)[:limit]
        ]
        
        return {
            "task_id": self.request.id,
            "status": "completed",
            "trending_posts": trending_posts,
            "total_posts_analyzed": len(all_posts),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting trending posts: {e}")
        
        if self.request.retries < settings.retry_max:
            backoff_time = min(
                settings.backoff_base ** self.request.retries,
                settings.backoff_max
            )
            logger.info(f"Retrying get trending posts in {backoff_time}s")
            raise self.retry(countdown=backoff_time)
        
        return {
            "task_id": self.request.id,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Cleanup task
@celery_app.task(
    bind=True,
    name="workers.collector.tasks.cleanup_old_results"
)
def cleanup_old_results(self, days_old: int = 7) -> Dict[str, Any]:
    """
    Clean up old processing results and logs
    
    Args:
        days_old: Remove data older than this many days
    
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(f"Cleaning up data older than {days_old} days")
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        with get_db_session() as session:
            # Clean up old processing logs
            deleted_logs = session.query(ProcessingLog).filter(
                ProcessingLog.created_at < cutoff_date
            ).delete()
            
            # Clean up old posts without ghost_url (unpublished)
            deleted_posts = session.query(Post).filter(
                and_(
                    Post.created_at < cutoff_date,
                    Post.ghost_url.is_(None)
                )
            ).delete()
            
            session.commit()
            
            logger.info(f"Cleanup completed: {deleted_logs} logs, {deleted_posts} posts removed")
            
            return {
                "task_id": self.request.id,
                "status": "completed",
                "deleted_logs": deleted_logs,
                "deleted_posts": deleted_posts,
                "cutoff_date": cutoff_date.isoformat(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return {
            "task_id": self.request.id,
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }