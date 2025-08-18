"""
Reddit API client with simplified rate limiting and error handling (MVP)
"""
import logging
import time
import threading
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Generator
from dataclasses import dataclass

import praw
from praw.exceptions import PRAWException, RedditAPIException
from praw.models import Submission
from prawcore.exceptions import (
    ResponseException, 
    RequestException, 
    ServerError,
    TooManyRequests,
    Forbidden,
    NotFound
)
import redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Rate limiting constants (as per task requirements)
RETRY_MAX = settings.retry_max
BACKOFF_BASE = settings.backoff_base
BACKOFF_MIN = settings.backoff_min
BACKOFF_MAX = settings.backoff_max


@dataclass
class RedditPost:
    """Reddit post data structure"""
    id: str
    title: str
    subreddit: str
    author: str
    score: int
    upvote_ratio: float
    num_comments: int
    created_utc: float
    url: str
    selftext: str
    is_self: bool
    over_18: bool
    stickied: bool
    locked: bool
    archived: bool
    permalink: str
    thumbnail: Optional[str] = None
    media_url: Optional[str] = None
    
    @property
    def created_datetime(self) -> datetime:
        """Convert UTC timestamp to datetime"""
        return datetime.fromtimestamp(self.created_utc)
    
    @property
    def age_hours(self) -> float:
        """Get post age in hours"""
        return (datetime.utcnow() - self.created_datetime).total_seconds() / 3600
    
    @property
    def velocity_score(self) -> float:
        """Calculate velocity score (score/time ratio)"""
        if self.age_hours <= 0:
            return 0.0
        return self.score / self.age_hours
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'id': self.id,
            'title': self.title,
            'subreddit': self.subreddit,
            'author': self.author,
            'score': self.score,
            'upvote_ratio': self.upvote_ratio,
            'num_comments': self.num_comments,
            'created_utc': self.created_utc,
            'url': self.url,
            'selftext': self.selftext,
            'is_self': self.is_self,
            'over_18': self.over_18,
            'stickied': self.stickied,
            'locked': self.locked,
            'archived': self.archived,
            'permalink': self.permalink,
            'thumbnail': self.thumbnail,
            'media_url': self.media_url,
            'age_hours': self.age_hours,
            'velocity_score': self.velocity_score
        }


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for Reddit API (60 requests per minute)
    Thread-safe implementation with Redis backing
    """
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis_key = "reddit_api_rate_limit"
        self._lock = threading.Lock()
        
        # Initialize Redis connection
        try:
            self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self.redis_client.ping()  # Test connection
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            self.redis_client = None
    
    def can_make_request(self) -> bool:
        """Check if we can make a request without exceeding rate limit"""
        if not self.redis_client:
            # Fallback to local rate limiting if Redis unavailable
            return True
            
        try:
            current_time = int(time.time())
            window_start = current_time - self.window_seconds
            
            # Remove old entries
            self.redis_client.zremrangebyscore(self.redis_key, 0, window_start)
            
            # Count current requests
            current_count = self.redis_client.zcard(self.redis_key)
            
            return current_count < self.max_requests
            
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}")
            return True  # Allow request if Redis fails
    
    def record_request(self) -> None:
        """Record a request in the rate limiter"""
        if not self.redis_client:
            return
            
        try:
            current_time = int(time.time())
            # Add current request with timestamp as score
            self.redis_client.zadd(self.redis_key, {str(current_time): current_time})
            # Set expiry for cleanup
            self.redis_client.expire(self.redis_key, self.window_seconds * 2)
            
        except Exception as e:
            logger.warning(f"Failed to record request in rate limiter: {e}")
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded (synchronous)"""
        with self._lock:
            if not self.can_make_request():
                # Calculate wait time
                try:
                    current_time = int(time.time())
                    window_start = current_time - self.window_seconds
                    
                    # Get oldest request timestamp
                    oldest_requests = self.redis_client.zrange(
                        self.redis_key, 0, 0, withscores=True
                    )
                    
                    if oldest_requests:
                        oldest_time = int(oldest_requests[0][1])
                        wait_time = self.window_seconds - (current_time - oldest_time) + 1
                        
                        if wait_time > 0:
                            logger.info(f"Rate limit reached, waiting {wait_time} seconds")
                            time.sleep(wait_time)
                            
                except Exception as e:
                    logger.warning(f"Rate limit wait calculation failed: {e}")
                    # Fallback wait
                    time.sleep(1)
    
    def get_remaining_requests(self) -> int:
        """Get number of remaining requests in current window"""
        if not self.redis_client:
            return self.max_requests
            
        try:
            current_count = self.redis_client.zcard(self.redis_key)
            return max(0, self.max_requests - current_count)
        except Exception as e:
            logger.warning(f"Failed to get remaining requests: {e}")
            return self.max_requests


class RedditClient:
    """Simplified synchronous Reddit API client with token bucket rate limiting"""
    
    def __init__(self):
        self._reddit: Optional[praw.Reddit] = None
        self._authenticated = False
        self._rate_limiter = TokenBucketRateLimiter(
            max_requests=settings.reddit_rate_limit_rpm,
            window_seconds=60
        )
        self._credentials: Optional[Dict[str, str]] = None
    
    def authenticate(self) -> None:
        """Authenticate with Reddit API using environment variables"""
        try:
            # Get credentials from environment variables
            client_id = settings.reddit_client_id
            client_secret = settings.reddit_client_secret
            user_agent = settings.reddit_user_agent
            
            if not client_id or not client_secret:
                raise ValueError("Missing required Reddit credentials in environment variables")
            
            self._credentials = {
                'client_id': client_id,
                'client_secret': client_secret,
                'user_agent': user_agent
            }
            
            # Initialize PRAW client (synchronous)
            self._reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                ratelimit_seconds=0  # We handle rate limiting ourselves
            )
            
            # Test authentication with a simple API call
            try:
                # Test with a simple subreddit access (read-only)
                test_sub = self._reddit.subreddit('python')
                _ = list(test_sub.hot(limit=1))
                
                self._authenticated = True
                logger.info("Reddit API authentication successful (read-only mode)")
                
            except Exception as auth_error:
                logger.error(f"Reddit API test failed: {auth_error}")
                self._authenticated = False
                raise
                
        except Exception as e:
            logger.error(f"Reddit API authentication failed: {e}")
            self._authenticated = False
            raise
    
    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        return self._authenticated and self._reddit is not None
    
    def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated"""
        if not self.is_authenticated:
            self.authenticate()
    
    def _handle_api_error(self, error: Exception, operation: str, attempt: int = 1) -> None:
        """Enhanced Reddit API error handling with dynamic rate limiting and backoff"""
        client_id_masked = self._credentials.get('client_id', 'unknown')[:8] + "..." if self._credentials else None
        
        logger.error(
            f"Reddit API error during {operation} (attempt {attempt}): {error}",
            extra={
                'operation': operation,
                'attempt': attempt,
                'client_id': client_id_masked,
                'error_type': type(error).__name__
            }
        )
        
        if isinstance(error, TooManyRequests):
            # Dynamic rate limit handling with header inspection
            retry_after = getattr(error, 'retry_after', None)
            
            # Try to extract retry-after from response headers if available
            if hasattr(error, 'response') and error.response:
                headers = getattr(error.response, 'headers', {})
                if 'retry-after' in headers:
                    retry_after = int(headers['retry-after'])
                elif 'x-ratelimit-reset' in headers:
                    # Calculate wait time from reset timestamp
                    reset_time = int(headers['x-ratelimit-reset'])
                    retry_after = max(1, reset_time - int(time.time()))
            
            if retry_after and retry_after > 0:
                # Use server-provided retry-after value
                wait_time = min(retry_after, BACKOFF_MAX)  # Cap at max backoff
                logger.warning(f"Reddit API rate limit exceeded, server says retry after {retry_after}s, waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                # Fallback to exponential backoff with jitter
                base_backoff = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
                jitter = random.uniform(0.1, 0.3) * base_backoff  # Add 10-30% jitter
                backoff_time = base_backoff + jitter
                logger.warning(f"Reddit API rate limit exceeded, backing off for {backoff_time:.1f}s (attempt {attempt})")
                time.sleep(backoff_time)
            raise
            
        elif isinstance(error, Forbidden):
            logger.error(f"Reddit API access forbidden during {operation}: {error}")
            # Check if this is an auth issue that might be recoverable
            if "invalid_grant" in str(error).lower() or "unauthorized" in str(error).lower():
                logger.info("Attempting to re-authenticate due to auth error")
                try:
                    self.authenticate()  # Try to re-authenticate
                except Exception as auth_error:
                    logger.error(f"Re-authentication failed: {auth_error}")
            raise  # Don't retry forbidden errors
            
        elif isinstance(error, NotFound):
            logger.warning(f"Reddit resource not found during {operation}: {error}")
            raise  # Don't retry not found errors
            
        elif isinstance(error, ServerError):
            logger.error(f"Reddit server error during {operation}: {error}")
            # Server errors are retryable with exponential backoff
            backoff_time = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
            jitter = random.uniform(0.1, 0.2) * backoff_time  # Add jitter
            total_wait = backoff_time + jitter
            logger.info(f"Retrying after server error in {total_wait:.1f}s")
            time.sleep(total_wait)
            raise
            
        elif isinstance(error, (RequestException, ResponseException)):
            logger.error(f"Reddit API request failed during {operation}: {error}")
            # Network errors are retryable with exponential backoff
            backoff_time = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
            jitter = random.uniform(0.1, 0.2) * backoff_time  # Add jitter
            total_wait = backoff_time + jitter
            logger.info(f"Retrying after network error in {total_wait:.1f}s")
            time.sleep(total_wait)
            raise
            
        else:
            logger.error(f"Unexpected error during {operation}: {error}")
            # Unknown errors get exponential backoff with jitter
            backoff_time = min(BACKOFF_BASE ** attempt, BACKOFF_MAX)
            jitter = random.uniform(0.1, 0.2) * backoff_time
            total_wait = backoff_time + jitter
            logger.info(f"Retrying after unexpected error in {total_wait:.1f}s")
            time.sleep(total_wait)
            raise
    
    def get_subreddit_posts(
        self,
        subreddit_name: str,
        sort_type: str = "hot",
        limit: int = 100,
        time_filter: str = "day"
    ) -> Generator[RedditPost, None, None]:
        """
        Get posts from a subreddit with rate limiting (synchronous)
        
        Args:
            subreddit_name: Name of the subreddit
            sort_type: Sort type (hot, new, rising, top)
            limit: Maximum number of posts to fetch
            time_filter: Time filter for 'top' sort (hour, day, week, month, year, all)
        
        Yields:
            RedditPost objects
        """
        self._ensure_authenticated()
        
        for attempt in range(1, RETRY_MAX + 1):
            try:
                # Wait for rate limit if needed
                self._rate_limiter.wait_if_needed()
                self._rate_limiter.record_request()
                
                subreddit = self._reddit.subreddit(subreddit_name)
                
                # Get posts based on sort type
                if sort_type == "hot":
                    submissions = subreddit.hot(limit=limit)
                elif sort_type == "new":
                    submissions = subreddit.new(limit=limit)
                elif sort_type == "rising":
                    submissions = subreddit.rising(limit=limit)
                elif sort_type == "top":
                    submissions = subreddit.top(time_filter=time_filter, limit=limit)
                else:
                    raise ValueError(f"Invalid sort type: {sort_type}")
                
                # Process submissions
                for submission in submissions:
                    try:
                        # Convert submission to RedditPost
                        post = self._submission_to_post(submission)
                        if post:
                            yield post
                            
                    except Exception as e:
                        logger.error(f"Error processing submission {submission.id}: {e}")
                        continue
                
                # If we get here, the operation was successful
                return
                        
            except (TooManyRequests, ServerError, RequestException, ResponseException) as e:
                if attempt < RETRY_MAX:
                    logger.warning(f"Retrying get_subreddit_posts for {subreddit_name} (attempt {attempt + 1}/{RETRY_MAX})")
                    self._handle_api_error(e, f"get_subreddit_posts({subreddit_name})", attempt)
                else:
                    logger.error(f"Failed to get subreddit posts after {RETRY_MAX} attempts")
                    raise
            except (Forbidden, NotFound) as e:
                # Don't retry these errors
                self._handle_api_error(e, f"get_subreddit_posts({subreddit_name})", attempt)
                raise
            except Exception as e:
                if attempt < RETRY_MAX:
                    logger.warning(f"Unexpected error, retrying get_subreddit_posts for {subreddit_name} (attempt {attempt + 1}/{RETRY_MAX})")
                    self._handle_api_error(e, f"get_subreddit_posts({subreddit_name})", attempt)
                else:
                    logger.error(f"Failed to get subreddit posts after {RETRY_MAX} attempts")
                    raise
    
    def _submission_to_post(self, submission: Submission) -> Optional[RedditPost]:
        """Convert PRAW Submission to RedditPost (synchronous)"""
        try:
            # Extract media URL if available
            media_url = None
            if hasattr(submission, 'url') and submission.url:
                # Check if URL is an image or video
                if any(submission.url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    media_url = submission.url
                elif hasattr(submission, 'media') and submission.media:
                    # Handle Reddit video or other media
                    if 'reddit_video' in submission.media:
                        media_url = submission.media['reddit_video'].get('fallback_url')
            
            return RedditPost(
                id=submission.id,
                title=submission.title,
                subreddit=submission.subreddit.display_name,
                author=str(submission.author) if submission.author else "[deleted]",
                score=submission.score,
                upvote_ratio=submission.upvote_ratio,
                num_comments=submission.num_comments,
                created_utc=submission.created_utc,
                url=submission.url,
                selftext=submission.selftext,
                is_self=submission.is_self,
                over_18=submission.over_18,
                stickied=submission.stickied,
                locked=submission.locked,
                archived=submission.archived,
                permalink=f"https://reddit.com{submission.permalink}",
                thumbnail=submission.thumbnail if submission.thumbnail != "self" else None,
                media_url=media_url
            )
            
        except Exception as e:
            logger.error(f"Error converting submission to RedditPost: {e}")
            return None
    
    def get_post_by_id(self, post_id: str) -> Optional[RedditPost]:
        """Get a specific post by ID (synchronous)"""
        self._ensure_authenticated()
        
        for attempt in range(1, RETRY_MAX + 1):
            try:
                self._rate_limiter.wait_if_needed()
                self._rate_limiter.record_request()
                
                submission = self._reddit.submission(id=post_id)
                return self._submission_to_post(submission)
                
            except (TooManyRequests, ServerError, RequestException, ResponseException) as e:
                if attempt < RETRY_MAX:
                    logger.warning(f"Retrying get_post_by_id for {post_id} (attempt {attempt + 1}/{RETRY_MAX})")
                    self._handle_api_error(e, f"get_post_by_id({post_id})", attempt)
                else:
                    logger.error(f"Failed to get post by ID after {RETRY_MAX} attempts")
                    return None
            except (Forbidden, NotFound) as e:
                logger.warning(f"Post {post_id} not accessible: {e}")
                return None
            except Exception as e:
                if attempt < RETRY_MAX:
                    logger.warning(f"Unexpected error, retrying get_post_by_id for {post_id} (attempt {attempt + 1}/{RETRY_MAX})")
                    self._handle_api_error(e, f"get_post_by_id({post_id})", attempt)
                else:
                    logger.error(f"Failed to get post by ID after {RETRY_MAX} attempts")
                    return None
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        remaining = self._rate_limiter.get_remaining_requests()
        
        return {
            "max_requests": self._rate_limiter.max_requests,
            "window_seconds": self._rate_limiter.window_seconds,
            "remaining_requests": remaining,
            "requests_used": self._rate_limiter.max_requests - remaining
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check Reddit client health (synchronous)"""
        try:
            if not self.is_authenticated:
                return {
                    "status": "unhealthy",
                    "error": "Not authenticated",
                    "authenticated": False
                }
            
            # Test basic API access
            try:
                test_sub = self._reddit.subreddit('python')
                _ = list(test_sub.hot(limit=1))
                
                return {
                    "status": "healthy",
                    "authenticated": True,
                    "client_id": self._credentials.get('client_id', 'unknown')[:8] + "..." if self._credentials else None
                }
                
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": f"API test failed: {e}",
                    "authenticated": True
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "authenticated": False
            }


# Global Reddit client instance
reddit_client = RedditClient()


def init_reddit_client() -> None:
    """Initialize Reddit client (synchronous)"""
    reddit_client.authenticate()


def get_reddit_client() -> RedditClient:
    """Get Reddit client instance"""
    return reddit_client