"""
Unit tests for NLP Pipeline service
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

from workers.nlp_pipeline.openai_client import OpenAIClient, OpenAIError, TokenUsageTracker
from workers.nlp_pipeline.tasks import process_content_with_ai


class TestOpenAIClient:
    """Test OpenAI client functionality"""
    
    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response"""
        return {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'summary_ko': '이것은 한국어 요약입니다.',
                        'tags': ['기술', '인공지능', '프로그래밍'],
                        'pain_points': {
                            'main_issues': ['성능 문제', '사용성 문제'],
                            'severity': 'medium'
                        },
                        'product_ideas': {
                            'suggestions': ['모바일 앱', 'API 개선'],
                            'priority': 'high'
                        }
                    })
                }
            }],
            'usage': {
                'prompt_tokens': 1000,
                'completion_tokens': 500,
                'total_tokens': 1500
            }
        }
    
    @pytest.fixture
    def openai_client(self):
        """Create OpenAI client with mocked dependencies"""
        with patch('workers.nlp_pipeline.openai_client.openai') as mock_openai:
            client = OpenAIClient()
            client.client = mock_openai
            return client
    
    @pytest.mark.asyncio
    async def test_generate_summary_success(self, openai_client, mock_openai_response):
        """Test successful summary generation"""
        openai_client.client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
        
        post_data = {
            'title': 'Test Post Title',
            'content': 'This is test content about AI and machine learning.',
            'subreddit': 'MachineLearning'
        }
        
        result = await openai_client.generate_summary(post_data)
        
        assert result['summary_ko'] == '이것은 한국어 요약입니다.'
        assert result['tags'] == ['기술', '인공지능', '프로그래밍']
        assert 'pain_points' in result
        assert 'product_ideas' in result
        assert result['usage']['total_tokens'] == 1500
    
    @pytest.mark.asyncio
    async def test_generate_summary_with_fallback(self, openai_client):
        """Test summary generation with GPT-4o fallback"""
        # First call fails with GPT-4o-mini
        openai_client.client.chat.completions.create = AsyncMock(
            side_effect=[
                OpenAIError("Rate limit exceeded"),
                {
                    'choices': [{
                        'message': {
                            'content': json.dumps({
                                'summary_ko': 'GPT-4o로 생성된 요약입니다.',
                                'tags': ['기술', '인공지능'],
                                'pain_points': {'main_issues': ['성능']},
                                'product_ideas': {'suggestions': ['개선']}
                            })
                        }
                    }],
                    'usage': {'prompt_tokens': 800, 'completion_tokens': 400, 'total_tokens': 1200}
                }
            ]
        )
        
        post_data = {
            'title': 'Test Post',
            'content': 'Test content',
            'subreddit': 'test'
        }
        
        result = await openai_client.generate_summary(post_data)
        
        assert result['summary_ko'] == 'GPT-4o로 생성된 요약입니다.'
        assert result['model_used'] == 'gpt-4o'  # Should indicate fallback was used
        assert openai_client.client.chat.completions.create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_generate_summary_invalid_json(self, openai_client):
        """Test handling of invalid JSON response"""
        openai_client.client.chat.completions.create = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': 'Invalid JSON response'
                }
            }],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}
        })
        
        post_data = {
            'title': 'Test Post',
            'content': 'Test content',
            'subreddit': 'test'
        }
        
        with pytest.raises(ValueError, match="Invalid JSON response"):
            await openai_client.generate_summary(post_data)
    
    @pytest.mark.asyncio
    async def test_generate_summary_missing_fields(self, openai_client):
        """Test handling of response with missing required fields"""
        openai_client.client.chat.completions.create = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'summary_ko': '요약만 있는 응답',
                        # Missing tags, pain_points, product_ideas
                    })
                }
            }],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}
        })
        
        post_data = {
            'title': 'Test Post',
            'content': 'Test content',
            'subreddit': 'test'
        }
        
        result = await openai_client.generate_summary(post_data)
        
        assert result['summary_ko'] == '요약만 있는 응답'
        assert result['tags'] == []  # Should provide default empty list
        assert result['pain_points'] == {}  # Should provide default empty dict
        assert result['product_ideas'] == {}
    
    def test_validate_tags_success(self, openai_client):
        """Test successful tag validation"""
        valid_tags = ['기술', '인공지능', '프로그래밍']
        
        result = openai_client._validate_tags(valid_tags)
        
        assert result == valid_tags
        assert len(result) == 3
    
    def test_validate_tags_too_many(self, openai_client):
        """Test tag validation with too many tags"""
        too_many_tags = ['tag1', 'tag2', 'tag3', 'tag4', 'tag5', 'tag6']
        
        result = openai_client._validate_tags(too_many_tags)
        
        assert len(result) == 5  # Should be truncated to 5
        assert result == too_many_tags[:5]
    
    def test_validate_tags_too_few(self, openai_client):
        """Test tag validation with too few tags"""
        too_few_tags = ['tag1', 'tag2']
        
        result = openai_client._validate_tags(too_few_tags)
        
        assert len(result) >= 3  # Should be padded to at least 3
        assert 'general' in result  # Should add generic tags
    
    def test_validate_tags_empty(self, openai_client):
        """Test tag validation with empty list"""
        empty_tags = []
        
        result = openai_client._validate_tags(empty_tags)
        
        assert len(result) >= 3
        assert 'general' in result
        assert 'reddit' in result
    
    def test_calculate_cost_gpt4o_mini(self, openai_client):
        """Test cost calculation for GPT-4o-mini"""
        usage = {
            'prompt_tokens': 1000,
            'completion_tokens': 500,
            'total_tokens': 1500
        }
        
        cost = openai_client._calculate_cost(usage, 'gpt-4o-mini')
        
        # GPT-4o-mini: $0.0000025 per input token, $0.00001 per output token
        expected_cost = (1000 * 0.0000025) + (500 * 0.00001)
        assert cost == Decimal(str(expected_cost))
    
    def test_calculate_cost_gpt4o(self, openai_client):
        """Test cost calculation for GPT-4o"""
        usage = {
            'prompt_tokens': 1000,
            'completion_tokens': 500,
            'total_tokens': 1500
        }
        
        cost = openai_client._calculate_cost(usage, 'gpt-4o')
        
        # GPT-4o: $0.000005 per input token, $0.000015 per output token
        expected_cost = (1000 * 0.000005) + (500 * 0.000015)
        assert cost == Decimal(str(expected_cost))
    
    def test_build_prompt(self, openai_client):
        """Test prompt building"""
        post_data = {
            'title': 'Test AI Post',
            'content': 'This is about artificial intelligence and machine learning.',
            'subreddit': 'MachineLearning'
        }
        
        prompt = openai_client._build_prompt(post_data)
        
        assert 'Test AI Post' in prompt
        assert 'artificial intelligence' in prompt
        assert 'MachineLearning' in prompt
        assert '한국어로 요약' in prompt  # Should contain Korean instruction
        assert 'JSON' in prompt  # Should mention JSON format


class TestTokenUsageTracker:
    """Test token usage tracking functionality"""
    
    @pytest.fixture
    def token_tracker(self):
        """Create token usage tracker"""
        return TokenUsageTracker()
    
    @pytest.mark.asyncio
    async def test_track_usage_success(self, token_tracker):
        """Test successful token usage tracking"""
        with patch('workers.nlp_pipeline.openai_client.redis_client') as mock_redis:
            mock_redis.increment_daily_usage = AsyncMock(return_value=1500)
            
            usage = {
                'prompt_tokens': 1000,
                'completion_tokens': 500,
                'total_tokens': 1500
            }
            
            await token_tracker.track_usage('gpt-4o-mini', usage, Decimal('0.0075'))
            
            mock_redis.increment_daily_usage.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_budget_within_limit(self, token_tracker):
        """Test budget check within limit"""
        with patch('workers.nlp_pipeline.openai_client.redis_client') as mock_redis:
            mock_redis.get_daily_token_usage = AsyncMock(return_value=50000)  # 50% of 100k limit
            
            can_proceed = await token_tracker.check_budget(10000)  # Request 10k more tokens
            
            assert can_proceed is True
    
    @pytest.mark.asyncio
    async def test_check_budget_exceeds_limit(self, token_tracker):
        """Test budget check exceeding limit"""
        with patch('workers.nlp_pipeline.openai_client.redis_client') as mock_redis:
            mock_redis.get_daily_token_usage = AsyncMock(return_value=95000)  # 95% of 100k limit
            
            can_proceed = await token_tracker.check_budget(10000)  # Would exceed limit
            
            assert can_proceed is False
    
    @pytest.mark.asyncio
    async def test_check_budget_80_percent_warning(self, token_tracker):
        """Test 80% budget warning"""
        with patch('workers.nlp_pipeline.openai_client.redis_client') as mock_redis:
            with patch('workers.nlp_pipeline.openai_client.send_slack_alert') as mock_slack:
                mock_redis.get_daily_token_usage = AsyncMock(return_value=80000)  # Exactly 80%
                
                await token_tracker.check_budget(1000)
                
                mock_slack.assert_called_once()
                args = mock_slack.call_args[0]
                assert 'budget' in args[2].lower()  # Message should mention budget


class TestNLPPipelineTasks:
    """Test NLP pipeline Celery tasks"""
    
    @pytest.mark.asyncio
    async def test_process_content_with_ai_success(self):
        """Test successful content processing"""
        with patch('workers.nlp_pipeline.tasks.get_db_session') as mock_db:
            with patch('workers.nlp_pipeline.tasks.OpenAIClient') as mock_client_class:
                # Mock database
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                
                mock_post = Mock()
                mock_post.id = 'test-uuid'
                mock_post.title = 'Test Post'
                mock_post.content = 'Test content'
                mock_post.subreddit = 'test'
                mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                
                # Mock OpenAI client
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                mock_client.generate_summary.return_value = {
                    'summary_ko': '테스트 요약',
                    'tags': ['테스트', '기술'],
                    'pain_points': {'issues': ['문제1']},
                    'product_ideas': {'ideas': ['아이디어1']},
                    'usage': {'total_tokens': 1000},
                    'cost': Decimal('0.005'),
                    'model_used': 'gpt-4o-mini'
                }
                
                # Execute task
                result = await process_content_with_ai('test-reddit-id')
                
                # Verify results
                assert result['status'] == 'success'
                assert result['summary_ko'] == '테스트 요약'
                assert result['tags'] == ['테스트', '기술']
                
                # Verify database updates
                assert mock_post.summary_ko == '테스트 요약'
                assert mock_post.tags == ['테스트', '기술']
                mock_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_content_with_ai_post_not_found(self):
        """Test processing with non-existent post"""
        with patch('workers.nlp_pipeline.tasks.get_db_session') as mock_db:
            mock_session = Mock()
            mock_db.return_value.__enter__.return_value = mock_session
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            result = await process_content_with_ai('non-existent-id')
            
            assert result['status'] == 'error'
            assert 'not found' in result['error'].lower()
    
    @pytest.mark.asyncio
    async def test_process_content_with_ai_openai_error(self):
        """Test processing with OpenAI API error"""
        with patch('workers.nlp_pipeline.tasks.get_db_session') as mock_db:
            with patch('workers.nlp_pipeline.tasks.OpenAIClient') as mock_client_class:
                # Mock database
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                
                mock_post = Mock()
                mock_post.id = 'test-uuid'
                mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                
                # Mock OpenAI client to raise error
                mock_client = AsyncMock()
                mock_client_class.return_value = mock_client
                mock_client.generate_summary.side_effect = OpenAIError("API Error")
                
                result = await process_content_with_ai('test-reddit-id')
                
                assert result['status'] == 'error'
                assert 'API Error' in result['error']
    
    @pytest.mark.asyncio
    async def test_process_content_with_ai_budget_exceeded(self):
        """Test processing when budget is exceeded"""
        with patch('workers.nlp_pipeline.tasks.get_db_session') as mock_db:
            with patch('workers.nlp_pipeline.tasks.TokenUsageTracker') as mock_tracker_class:
                # Mock database
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                
                mock_post = Mock()
                mock_post.id = 'test-uuid'
                mock_session.query.return_value.filter_by.return_value.first.return_value = mock_post
                
                # Mock token tracker to indicate budget exceeded
                mock_tracker = AsyncMock()
                mock_tracker_class.return_value = mock_tracker
                mock_tracker.check_budget.return_value = False
                
                result = await process_content_with_ai('test-reddit-id')
                
                assert result['status'] == 'error'
                assert 'budget' in result['error'].lower()


if __name__ == "__main__":
    pytest.main([__file__])