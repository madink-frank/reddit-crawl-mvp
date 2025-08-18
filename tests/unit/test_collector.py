"""
Unit tests for Reddit collector service
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from workers.collector.reddit_client import RedditPost, RedditClient, RateLimiter
from workers.collector.content_filter import ContentFilter, FilterResult
from workers.collector.trend_analyzer import VelocityCalculator, VelocityMetrics, TrendDirection


class TestRedditPost:
    """Test RedditPost data structure"""
    
    def test_reddit_post_creation(self):
        """Test creating a RedditPost"""
        post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=100,
            upvote_ratio=0.8,
            num_comments=25,
            created_utc=datetime.utcnow().timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        assert post.id == "test123"
        assert post.title == "Test Post"
        assert post.subreddit == "test"
        assert post.score == 100
        assert post.num_comments == 25
    
    def test_velocity_score_calculation(self):
        """Test velocity score calculation"""
        # Create a post that's 2 hours old with score 200
        created_time = datetime.utcnow() - timedelta(hours=2)
        
        post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=200,
            upvote_ratio=0.8,
            num_comments=25,
            created_utc=created_time.timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        # Velocity should be score/age_hours = 200/2 = 100
        assert post.velocity_score == 100.0
        assert post.age_hours == pytest.approx(2.0, abs=0.1)
    
    def test_to_dict_conversion(self):
        """Test converting RedditPost to dictionary"""
        post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=100,
            upvote_ratio=0.8,
            num_comments=25,
            created_utc=datetime.utcnow().timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        post_dict = post.to_dict()
        
        assert post_dict["id"] == "test123"
        assert post_dict["title"] == "Test Post"
        assert post_dict["score"] == 100
        assert "velocity_score" in post_dict
        assert "age_hours" in post_dict


class TestRateLimiter:
    """Test rate limiting functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test that rate limiter allows requests within limit"""
        with patch('workers.collector.reddit_client.redis_client') as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=True)
            
            rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
            
            can_make_request = await rate_limiter.can_make_request()
            assert can_make_request is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self):
        """Test that rate limiter blocks requests over limit"""
        with patch('workers.collector.reddit_client.redis_client') as mock_redis:
            mock_redis.check_rate_limit = AsyncMock(return_value=False)
            
            rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
            
            can_make_request = await rate_limiter.can_make_request()
            assert can_make_request is False


class TestContentFilter:
    """Test content filtering logic"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.content_filter = ContentFilter()
    
    def test_nsfw_filter(self):
        """Test NSFW content filtering"""
        nsfw_post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=100,
            upvote_ratio=0.8,
            num_comments=25,
            created_utc=datetime.utcnow().timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=True,  # NSFW
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        result = self.content_filter._check_nsfw(nsfw_post)
        assert result.passed is False
        assert "NSFW" in result.reason
    
    def test_quality_filter_low_score(self):
        """Test quality filter for low score posts"""
        low_score_post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=5,  # Below minimum
            upvote_ratio=0.8,
            num_comments=25,
            created_utc=datetime.utcnow().timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        result = self.content_filter._check_quality(low_score_post)
        assert result.passed is False
        assert "below minimum" in result.reason
    
    def test_age_filter_too_old(self):
        """Test age filter for old posts"""
        old_time = datetime.utcnow() - timedelta(hours=30)  # Older than 24h default
        
        old_post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=100,
            upvote_ratio=0.8,
            num_comments=25,
            created_utc=old_time.timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        result = self.content_filter._check_age(old_post)
        assert result.passed is False
        assert "exceeds maximum" in result.reason
    
    def test_blocked_content_filter(self):
        """Test blocked content filtering"""
        blocked_post = RedditPost(
            id="test123",
            title="Please upvote this post",  # Contains blocked keyword
            subreddit="test",
            author="testuser",
            score=100,
            upvote_ratio=0.8,
            num_comments=25,
            created_utc=datetime.utcnow().timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        result = self.content_filter._check_blocked_content(blocked_post)
        assert result.passed is False
        assert "Blocked keyword" in result.reason
    
    def test_quality_score_calculation(self):
        """Test quality score calculation"""
        good_post = RedditPost(
            id="test123",
            title="High Quality Technical Discussion About Python Programming",
            subreddit="programming",
            author="testuser",
            score=500,
            upvote_ratio=0.9,
            num_comments=100,
            created_utc=(datetime.utcnow() - timedelta(hours=3)).timestamp(),
            url="https://reddit.com/test",
            selftext="This is a substantial technical post with good content that should score well.",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        score = self.content_filter._calculate_quality_score(good_post)
        assert score > 10  # Should get a good score
        assert isinstance(score, float)


class TestVelocityCalculator:
    """Test velocity calculation and trend analysis"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.velocity_calculator = VelocityCalculator()
    
    def test_basic_velocity_calculation(self):
        """Test basic velocity calculation"""
        post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=200,
            upvote_ratio=0.8,
            num_comments=50,
            created_utc=(datetime.utcnow() - timedelta(hours=2)).timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        velocity = self.velocity_calculator._calculate_basic_velocity(post)
        assert velocity > 0
        assert isinstance(velocity, float)
    
    def test_comment_velocity_calculation(self):
        """Test comment velocity calculation"""
        post = RedditPost(
            id="test123",
            title="Test Post",
            subreddit="test",
            author="testuser",
            score=200,
            upvote_ratio=0.8,
            num_comments=50,
            created_utc=(datetime.utcnow() - timedelta(hours=2)).timestamp(),
            url="https://reddit.com/test",
            selftext="Test content",
            is_self=True,
            over_18=False,
            stickied=False,
            locked=False,
            archived=False,
            permalink="/r/test/comments/test123/"
        )
        
        comment_velocity = self.velocity_calculator._calculate_comment_velocity(post)
        assert comment_velocity == 25.0  # 50 comments / 2 hours
    
    @pytest.mark.asyncio
    async def test_velocity_metrics_creation(self):
        """Test creating velocity metrics"""
        with patch.object(self.velocity_calculator, '_store_data_point') as mock_store:
            with patch.object(self.velocity_calculator, '_get_historical_data') as mock_history:
                mock_store.return_value = None
                mock_history.return_value = []  # No historical data
                
                post = RedditPost(
                    id="test123",
                    title="Test Post",
                    subreddit="test",
                    author="testuser",
                    score=200,
                    upvote_ratio=0.8,
                    num_comments=50,
                    created_utc=(datetime.utcnow() - timedelta(hours=2)).timestamp(),
                    url="https://reddit.com/test",
                    selftext="Test content",
                    is_self=True,
                    over_18=False,
                    stickied=False,
                    locked=False,
                    archived=False,
                    permalink="/r/test/comments/test123/"
                )
                
                metrics = await self.velocity_calculator.calculate_velocity(post)
                
                assert isinstance(metrics, VelocityMetrics)
                assert metrics.post_id == "test123"
                assert metrics.current_score == 200
                assert metrics.current_comments == 50
                assert metrics.velocity_score > 0
                assert metrics.comment_velocity == 25.0
                assert metrics.trend_direction == TrendDirection.STABLE  # No historical data


@pytest.mark.asyncio
async def test_reddit_client_authentication():
    """Test Reddit client authentication"""
    with patch('workers.collector.reddit_client.secret_manager') as mock_secret_manager:
        with patch('praw.Reddit') as mock_praw:
            # Mock credentials
            mock_secret_manager.get_reddit_credentials.return_value = {
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'user_agent': 'test_user_agent'
            }
            
            # Mock PRAW Reddit instance
            mock_reddit_instance = Mock()
            mock_reddit_instance.user.me.return_value = Mock()
            mock_praw.return_value = mock_reddit_instance
            
            client = RedditClient()
            await client.authenticate()
            
            assert client.is_authenticated is True
            mock_secret_manager.get_reddit_credentials.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])