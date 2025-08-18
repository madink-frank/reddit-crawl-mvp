"""
Simplified content filtering and validation logic for Reddit posts (MVP)
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.config import get_settings
from workers.collector.reddit_client import RedditPost

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class FilterResult:
    """Result of content filtering"""
    passed: bool
    reason: Optional[str] = None
    
    def __bool__(self) -> bool:
        return self.passed


class ContentFilter:
    """Simplified content filtering for MVP (NSFW, duplicates, basic quality)"""
    
    def __init__(self):
        self.min_score = settings.content_min_score
        self.min_comments = settings.content_min_comments
    
    def filter_post(self, post: RedditPost) -> FilterResult:
        """
        Apply simplified filters to a Reddit post (synchronous MVP version)
        
        Args:
            post: RedditPost to filter
        
        Returns:
            FilterResult indicating if post passed filters
        """
        try:
            # 1. Check NSFW content (Reddit over_18 flag - fixed criterion)
            nsfw_result = self._check_nsfw(post)
            if not nsfw_result.passed:
                return nsfw_result
            
            # 2. Basic quality validation (title, content existence)
            quality_result = self._check_basic_quality(post)
            if not quality_result.passed:
                return quality_result
            
            # Note: Duplicate prevention is handled at database level with UNIQUE constraint
            # on reddit_post_id, so we don't need to check here
            
            return FilterResult(
                passed=True,
                reason="All filters passed"
            )
            
        except Exception as e:
            logger.error(f"Error filtering post {post.id}: {e}")
            return FilterResult(
                passed=False,
                reason=f"Filter error: {e}"
            )
    
    def _check_nsfw(self, post: RedditPost) -> FilterResult:
        """Check if post is NSFW (Reddit over_18 flag basis - fixed)"""
        if post.over_18:
            return FilterResult(
                passed=False,
                reason="NSFW content filtered (over_18 flag)"
            )
        
        return FilterResult(passed=True)
    
    def _check_basic_quality(self, post: RedditPost) -> FilterResult:
        """Basic quality validation (title, content existence)"""
        # Check if title exists and is not empty
        if not post.title or not post.title.strip():
            return FilterResult(
                passed=False,
                reason="Missing or empty title"
            )
        
        # Check if title is too short (less than 10 characters)
        if len(post.title.strip()) < 10:
            return FilterResult(
                passed=False,
                reason="Title too short (less than 10 characters)"
            )
        
        # For self posts, check if content exists
        if post.is_self:
            if not post.selftext or not post.selftext.strip():
                return FilterResult(
                    passed=False,
                    reason="Self post missing content"
                )
            
            # Check if self post content is too short
            if len(post.selftext.strip()) < 50:
                return FilterResult(
                    passed=False,
                    reason="Self post content too short (less than 50 characters)"
                )
        
        # Check for deleted/removed content
        if post.author == "[deleted]" or "[removed]" in (post.selftext or ""):
            return FilterResult(
                passed=False,
                reason="Deleted or removed content"
            )
        
        # Check for locked/archived posts (they can't generate engagement)
        if post.locked or post.archived:
            return FilterResult(
                passed=False,
                reason="Locked or archived post"
            )
        
        # Check for stickied posts (usually announcements, not suitable for republishing)
        if post.stickied:
            return FilterResult(
                passed=False,
                reason="Stickied post (announcement)"
            )
        
        return FilterResult(passed=True)
    
    def get_filter_stats(self) -> Dict[str, Any]:
        """Get filtering statistics (simplified for MVP)"""
        return {
            "min_score": self.min_score,
            "min_comments": self.min_comments,
            "nsfw_filtering": "enabled (over_18 flag)",
            "duplicate_prevention": "database UNIQUE constraint on reddit_post_id",
            "basic_quality_checks": "title/content existence validation"
        }


# Global instance
content_filter = ContentFilter()


def get_content_filter() -> ContentFilter:
    """Get content filter instance"""
    return content_filter