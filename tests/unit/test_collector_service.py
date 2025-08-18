"""
Unit tests for Collector service
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from workers.collector.tasks import collect_reddit_posts
from workers.collector.budget_manager import BudgetManager, BudgetExceededError
from workers.collector.content_filter import ContentFilter


class TestBudgetManager:
    """Test budget management functionality"""
    
    @pytest.fixture
    def budget_manager(self):
        """Create budget manager with test settings"""
        return BudgetManager(daily_limit=1000)
    
    @pytest.mark.asyncio
    async def test_check_budget_within_limit(self, budget_manager):
        """Test budget check within daily limit"""
        with patch('workers.collector.budget_manager.redis_client') as mock_redis:
            mock_redis.get_daily_api_calls = AsyncMock(return_value=500)  # 50% of limit
            
            can_proceed = await budget_manager.check_budget(100)  # Request 100 more calls
            
            assert can_proceed is True
    
    @pytest.mark.asyncio
    async def test_check_budget_exceeds_limit(self, budget_manager):
        """Test budget check exceeding daily limit"""
        with patch('workers.collector.budget_manager.redis_client') as mock_redis:
            mock_redis.get_daily_api_calls = AsyncMock(return_value=950)  # 95% of limit
            
            can_proceed = await budget_manager.check_budget(100)  # Would exceed limit
            
            assert can_proceed is False
    
    @pytest.mark.asyncio
    async def test_check_budget_80_percent_warning(self, budget_manager):
        """Test 80% budget warning notification"""
        with patch('workers.collector.budget_manager.redis_client') as mock_redis:
            with patch('workers.collector.budget_manager.send_slack_alert') as mock_slack:
                mock_redis.get_daily_api_calls = AsyncMock(return_value=800)  # Exactly 80%
                
                await budget_manager.check_budget(10)
                
                mock_slack.assert_called_once()
                args = mock_slack.call_args[0]
                assert 'budget' in args[2].lower()  # Message should mention budget
                assert '80%' in args[2]  # Should mention 80% threshold
    
    @pytest.mark.asyncio
    async def test_increment_usage_success(self, budget_manager):
        """Test successful usage increment"""
        with patch('workers.collector.budget_manager.redis_client') as mock_redis:
            mock_redis.increment_daily_api_calls = AsyncMock(return_value=501)
            
            new_count = await budget_manager.increment_usage(1)
            
            assert new_count == 501
            mock_redis.increment_daily_api_calls.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_get_usage_stats(self, budget_manager):
        """Test getting usage statistics"""
        with patch('workers.collector.budget_manager.redis_client') as mock_redis:
            mock_redis.get_daily_api_calls = AsyncMock(return_value=750)
            
            stats = await budget_manager.get_usage_stats()
            
            assert stats['current_usage'] == 750
            assert stats['daily_limit'] == 1000
            assert stats['remaining'] == 250
            assert stats['usage_percentage'] == 75.0
    
    @pytest.mark.asyncio
    async def test_reset_daily_usage(self, budget_manager):
        """Test resetting daily usage counter"""
        with patch('workers.collector.budget_manager.redis_client') as mock_redis:
            mock_redis.reset_daily_counters = AsyncMock()
            
            await budget_manager.reset_daily_usage()
            
            mock_redis.reset_daily_counters.assert_called_once()


class TestContentFilter:
    """Test content filtering functionality"""
    
    @pytest.fixture
    def content_filter(self):
        """Create content filter"""
        return ContentFilter()
    
    def test_filter_nsfw_content(self, content_filter):
        """Test NSFW content filtering"""
        nsfw_post = {
            'id': 'test123',
            'title': 'Test Post',
            'over_18': True,  # NSFW flag
            'score': 100,
            'num_comments': 50,
            'created_utc': datetime.utcnow().timestamp(),
            'subreddit': 'test'
        }
        
        result = content_filter.should_collect(nsfw_post)
        
        assert result is False
    
    def test_filter_low_score_content(self, content_filter):
        """Test low score content filtering"""
        low_score_post = {
            'id': 'test123',
            'title': 'Test Post',
            'over_18': False,
            'score': 5,  # Below minimum threshold
            'num_comments': 2,
            'created_utc': datetime.utcnow().timestamp(),
            'subreddit': 'test'
        }
        
        result = content_filter.should_collect(low_score_post)
        
        assert result is False
    
    def test_filter_old_content(self, content_filter):
        """Test old content filtering"""
        old_time = datetime.utcnow() - timedelta(hours=25)  # Older than 24h
        old_post = {
            'id': 'test123',
            'title': 'Test Post',
            'over_18': False,
            'score': 100,
            'num_comments': 50,
            'created_utc': old_time.timestamp(),
            'subreddit': 'test'
        }
        
        result = content_filter.should_collect(old_post)
        
        assert result is False
    
    def test_filter_blocked_keywords(self, content_filter):
        """Test blocked keyword filtering"""
        blocked_post = {
            'id': 'test123',
            'title': 'Please upvote this post',  # Contains blocked keyword
            'over_18': False,
            'score': 100,
            'num_comments': 50,
            'created_utc': datetime.utcnow().timestamp(),
            'subreddit': 'test'
        }
        
        result = content_filter.should_collect(blocked_post)
        
        assert result is False
    
    def test_filter_valid_content(self, content_filter):
        """Test valid content passes filter"""
        valid_post = {
            'id': 'test123',
            'title': 'Great Technical Discussion About Python',
            'over_18': False,
            'score': 150,
            'num_comments': 75,
            'created_utc': (datetime.utcnow() - timedelta(hours=2)).timestamp(),
            'subreddit': 'programming'
        }
        
        result = content_filter.should_collect(valid_post)
        
        assert result is True
    
    def test_calculate_quality_score(self, content_filter):
        """Test quality score calculation"""
        high_quality_post = {
            'id': 'test123',
            'title': 'Comprehensive Guide to Machine Learning with Python and TensorFlow',
            'over_18': False,
            'score': 500,
            'num_comments': 150,
            'upvote_ratio': 0.95,
            'created_utc': (datetime.utcnow() - timedelta(hours=3)).timestamp(),
            'subreddit': 'MachineLearning',
            'selftext': 'This is a detailed technical post with substantial content that provides value to readers.'
        }
        
        score = content_filter._calculate_quality_score(high_quality_post)
        
        assert score > 10  # Should get a high quality score
        assert isinstance(score, float)
    
    def test_extract_blocked_keywords(self, content_filter):
        """Test blocked keyword extraction"""
        test_cases = [
            ('Please upvote this post', ['upvote']),
            ('Free karma here!', ['karma']),
            ('This is a normal post', []),
            ('Upvote if you agree with karma farming', ['upvote', 'karma'])
        ]
        
        for text, expected_keywords in test_cases:
            found_keywords = content_filter._extract_blocked_keywords(text)
            for keyword in expected_keywords:
                assert keyword in found_keywords


class TestCollectorTasks:
    """Test collector Celery tasks"""
    
    @pytest.mark.asyncio
    async def test_collect_reddit_posts_success(self):
        """Test successful Reddit post collection"""
        with patch('workers.collector.tasks.get_reddit_client') as mock_reddit:
            with patch('workers.collector.tasks.BudgetManager') as mock_budget:
                with patch('workers.collector.tasks.ContentFilter') as mock_filter:
                    with patch('workers.collector.tasks.get_db_session') as mock_db:
                        # Mock Reddit client
                        mock_reddit_client = AsyncMock()
                        mock_reddit.return_value = mock_reddit_client
                        
                        mock_posts = [
                            {
                                'id': 'post1',
                                'title': 'Great Tech Post',
                                'score': 200,
                                'num_comments': 50,
                                'created_utc': datetime.utcnow().timestamp(),
                                'subreddit': 'technology',
                                'selftext': 'Great content',
                                'url': 'https://reddit.com/r/technology/comments/post1/',
                                'over_18': False
                            },
                            {
                                'id': 'post2',
                                'title': 'Another Good Post',
                                'score': 150,
                                'num_comments': 30,
                                'created_utc': datetime.utcnow().timestamp(),
                                'subreddit': 'programming',
                                'selftext': 'More great content',
                                'url': 'https://reddit.com/r/programming/comments/post2/',
                                'over_18': False
                            }
                        ]
                        mock_reddit_client.get_hot_posts.return_value = mock_posts
                        
                        # Mock budget manager
                        mock_budget_manager = AsyncMock()
                        mock_budget.return_value = mock_budget_manager
                        mock_budget_manager.check_budget.return_value = True
                        mock_budget_manager.increment_usage.return_value = 2
                        
                        # Mock content filter
                        mock_content_filter = Mock()
                        mock_filter.return_value = mock_content_filter
                        mock_content_filter.should_collect.return_value = True
                        
                        # Mock database
                        mock_session = Mock()
                        mock_db.return_value.__enter__.return_value = mock_session
                        mock_session.query.return_value.filter_by.return_value.first.return_value = None  # No duplicates
                        
                        # Execute task
                        result = await collect_reddit_posts(['technology', 'programming'], batch_size=10)
                        
                        # Verify results
                        assert result['status'] == 'success'
                        assert result['collected_count'] == 2
                        assert result['subreddits'] == ['technology', 'programming']
                        
                        # Verify database operations
                        assert mock_session.add.call_count == 2  # Two posts added
                        mock_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_collect_reddit_posts_budget_exceeded(self):
        """Test collection when budget is exceeded"""
        with patch('workers.collector.tasks.BudgetManager') as mock_budget:
            mock_budget_manager = AsyncMock()
            mock_budget.return_value = mock_budget_manager
            mock_budget_manager.check_budget.return_value = False  # Budget exceeded
            
            result = await collect_reddit_posts(['technology'], batch_size=10)
            
            assert result['status'] == 'error'
            assert 'budget' in result['error'].lower()
    
    @pytest.mark.asyncio
    async def test_collect_reddit_posts_with_duplicates(self):
        """Test collection with duplicate post filtering"""
        with patch('workers.collector.tasks.get_reddit_client') as mock_reddit:
            with patch('workers.collector.tasks.BudgetManager') as mock_budget:
                with patch('workers.collector.tasks.ContentFilter') as mock_filter:
                    with patch('workers.collector.tasks.get_db_session') as mock_db:
                        # Mock Reddit client
                        mock_reddit_client = AsyncMock()
                        mock_reddit.return_value = mock_reddit_client
                        
                        mock_posts = [
                            {
                                'id': 'existing_post',
                                'title': 'Existing Post',
                                'score': 200,
                                'num_comments': 50,
                                'created_utc': datetime.utcnow().timestamp(),
                                'subreddit': 'technology',
                                'over_18': False
                            },
                            {
                                'id': 'new_post',
                                'title': 'New Post',
                                'score': 150,
                                'num_comments': 30,
                                'created_utc': datetime.utcnow().timestamp(),
                                'subreddit': 'technology',
                                'over_18': False
                            }
                        ]
                        mock_reddit_client.get_hot_posts.return_value = mock_posts
                        
                        # Mock budget manager
                        mock_budget_manager = AsyncMock()
                        mock_budget.return_value = mock_budget_manager
                        mock_budget_manager.check_budget.return_value = True
                        
                        # Mock content filter
                        mock_content_filter = Mock()
                        mock_filter.return_value = mock_content_filter
                        mock_content_filter.should_collect.return_value = True
                        
                        # Mock database - first post exists, second is new
                        mock_session = Mock()
                        mock_db.return_value.__enter__.return_value = mock_session
                        
                        def mock_query_side_effect(reddit_post_id):
                            if reddit_post_id == 'existing_post':
                                return Mock()  # Existing post found
                            else:
                                return None  # New post
                        
                        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
                            Mock(),  # existing_post found
                            None     # new_post not found
                        ]
                        
                        result = await collect_reddit_posts(['technology'], batch_size=10)
                        
                        # Should only collect the new post
                        assert result['status'] == 'success'
                        assert result['collected_count'] == 1
                        assert result['duplicate_count'] == 1
    
    @pytest.mark.asyncio
    async def test_collect_reddit_posts_content_filtered(self):
        """Test collection with content filtering"""
        with patch('workers.collector.tasks.get_reddit_client') as mock_reddit:
            with patch('workers.collector.tasks.BudgetManager') as mock_budget:
                with patch('workers.collector.tasks.ContentFilter') as mock_filter:
                    with patch('workers.collector.tasks.get_db_session') as mock_db:
                        # Mock Reddit client
                        mock_reddit_client = AsyncMock()
                        mock_reddit.return_value = mock_reddit_client
                        
                        mock_posts = [
                            {
                                'id': 'good_post',
                                'title': 'Good Technical Post',
                                'score': 200,
                                'over_18': False
                            },
                            {
                                'id': 'nsfw_post',
                                'title': 'NSFW Post',
                                'score': 100,
                                'over_18': True  # Should be filtered
                            },
                            {
                                'id': 'low_score_post',
                                'title': 'Low Score Post',
                                'score': 5,  # Should be filtered
                                'over_18': False
                            }
                        ]
                        mock_reddit_client.get_hot_posts.return_value = mock_posts
                        
                        # Mock budget manager
                        mock_budget_manager = AsyncMock()
                        mock_budget.return_value = mock_budget_manager
                        mock_budget_manager.check_budget.return_value = True
                        
                        # Mock content filter - only first post passes
                        mock_content_filter = Mock()
                        mock_filter.return_value = mock_content_filter
                        mock_content_filter.should_collect.side_effect = [True, False, False]
                        
                        # Mock database
                        mock_session = Mock()
                        mock_db.return_value.__enter__.return_value = mock_session
                        mock_session.query.return_value.filter_by.return_value.first.return_value = None
                        
                        result = await collect_reddit_posts(['technology'], batch_size=10)
                        
                        assert result['status'] == 'success'
                        assert result['collected_count'] == 1
                        assert result['filtered_count'] == 2
    
    @pytest.mark.asyncio
    async def test_collect_reddit_posts_api_error(self):
        """Test collection with Reddit API error"""
        with patch('workers.collector.tasks.get_reddit_client') as mock_reddit:
            with patch('workers.collector.tasks.BudgetManager') as mock_budget:
                # Mock Reddit client to raise error
                mock_reddit_client = AsyncMock()
                mock_reddit.return_value = mock_reddit_client
                mock_reddit_client.get_hot_posts.side_effect = Exception("Reddit API Error")
                
                # Mock budget manager
                mock_budget_manager = AsyncMock()
                mock_budget.return_value = mock_budget_manager
                mock_budget_manager.check_budget.return_value = True
                
                result = await collect_reddit_posts(['technology'], batch_size=10)
                
                assert result['status'] == 'error'
                assert 'Reddit API Error' in result['error']
    
    @pytest.mark.asyncio
    async def test_collect_reddit_posts_rate_limit_handling(self):
        """Test collection with rate limit handling"""
        with patch('workers.collector.tasks.get_reddit_client') as mock_reddit:
            with patch('workers.collector.tasks.BudgetManager') as mock_budget:
                with patch('workers.collector.tasks.asyncio.sleep') as mock_sleep:
                    # Mock Reddit client to raise rate limit error first, then succeed
                    mock_reddit_client = AsyncMock()
                    mock_reddit.return_value = mock_reddit_client
                    
                    from praw.exceptions import TooManyRequests
                    mock_reddit_client.get_hot_posts.side_effect = [
                        TooManyRequests(Mock()),  # First call hits rate limit
                        []  # Second call succeeds with empty results
                    ]
                    
                    # Mock budget manager
                    mock_budget_manager = AsyncMock()
                    mock_budget.return_value = mock_budget_manager
                    mock_budget_manager.check_budget.return_value = True
                    
                    result = await collect_reddit_posts(['technology'], batch_size=10)
                    
                    # Should handle rate limit and retry
                    assert mock_sleep.called  # Should have waited before retry
                    assert result['status'] == 'success'
                    assert result['collected_count'] == 0  # No posts collected after retry


if __name__ == "__main__":
    pytest.main([__file__])