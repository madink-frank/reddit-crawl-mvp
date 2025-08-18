"""
Unit tests for security utilities
"""
import pytest
import os
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from app.security import SecretManager, PIIMasker, BudgetManager, mask_sensitive_data


class TestSecretManager:
    """Test secret management functionality"""
    
    def test_get_secret_with_value(self):
        """Test getting secret that exists"""
        with patch.dict(os.environ, {'TEST_SECRET': 'test_value'}):
            manager = SecretManager()
            result = manager.get_secret('TEST_SECRET')
            assert result == 'test_value'
    
    def test_get_secret_with_default(self):
        """Test getting secret with default value"""
        manager = SecretManager()
        result = manager.get_secret('NONEXISTENT_SECRET', 'default_value')
        assert result == 'default_value'
    
    def test_load_all_secrets(self):
        """Test loading all secrets"""
        with patch.dict(os.environ, {
            'REDDIT_CLIENT_ID': 'test_id',
            'REDDIT_CLIENT_SECRET': 'test_secret',
            'OPENAI_API_KEY': 'test_key',
            'GHOST_ADMIN_KEY': 'test_ghost_key',
            'DATABASE_URL': 'postgresql://test',
            'REDIS_URL': 'redis://test'
        }):
            manager = SecretManager()
            status = manager.load_all_secrets()
            
            assert status['REDDIT_CLIENT_ID'] is True
            assert status['REDDIT_CLIENT_SECRET'] is True
            assert status['OPENAI_API_KEY'] is True
            assert status['GHOST_ADMIN_KEY'] is True
            assert status['DATABASE_URL'] is True
            assert status['REDIS_URL'] is True
            assert manager.is_loaded() is True


class TestPIIMasker:
    """Test PII masking functionality"""
    
    def test_mask_api_key(self):
        """Test masking API keys"""
        text = "api_key=sk-1234567890abcdef"
        result = PIIMasker.mask_sensitive_data(text)
        assert "sk-1234567890abcdef" not in result
        assert "api_key=****" in result
    
    def test_mask_token(self):
        """Test masking tokens"""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = PIIMasker.mask_sensitive_data(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Authorization: Bearer ****" in result
    
    def test_mask_email(self):
        """Test masking email addresses"""
        text = "Contact: user@example.com"
        result = PIIMasker.mask_sensitive_data(text)
        assert "user@example.com" not in result
        assert "****@example.com" in result
    
    def test_mask_url_credentials(self):
        """Test masking URL credentials"""
        text = "postgresql://user:password@localhost:5432/db"
        result = PIIMasker.mask_sensitive_data(text)
        assert "password" not in result
        assert "postgresql://user:****@localhost:5432/db" in result
    
    def test_mask_dict(self):
        """Test masking dictionary data"""
        data = {
            "api_key": "sk-1234567890abcdef",
            "email": "user@example.com",
            "normal_field": "normal_value"
        }
        result = PIIMasker.mask_dict(data)
        
        assert result["api_key"] == "****"  # Key name triggers masking
        assert "user@example.com" not in str(result)
        assert result["normal_field"] == "normal_value"


class TestBudgetManager:
    """Test budget management functionality"""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        redis_mock.incr.return_value = 1
        redis_mock.expire.return_value = True
        return redis_mock
    
    def test_get_daily_key(self, mock_redis):
        """Test daily key generation"""
        manager = BudgetManager(mock_redis)
        key = manager.get_daily_key('reddit')
        
        # Should contain service name and date
        assert 'reddit' in key
        assert 'usage:' in key
        assert datetime.now(timezone.utc).strftime('%Y%m%d') in key
    
    @pytest.mark.asyncio
    async def test_get_daily_usage_empty(self, mock_redis):
        """Test getting daily usage when empty"""
        mock_redis.get.return_value = None
        manager = BudgetManager(mock_redis)
        
        usage = await manager.get_daily_usage('reddit')
        assert usage == 0
    
    @pytest.mark.asyncio
    async def test_get_daily_usage_with_value(self, mock_redis):
        """Test getting daily usage with existing value"""
        mock_redis.get.return_value = "150"
        manager = BudgetManager(mock_redis)
        
        usage = await manager.get_daily_usage('reddit')
        assert usage == 150
    
    @pytest.mark.asyncio
    async def test_increment_usage(self, mock_redis):
        """Test incrementing usage counter"""
        mock_redis.incr.return_value = 5
        manager = BudgetManager(mock_redis)
        
        new_usage = await manager.increment_usage('reddit', 2)
        assert new_usage == 5
        
        # Verify Redis calls
        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_reddit_budget(self, mock_redis):
        """Test Reddit budget checking"""
        mock_redis.get.return_value = "4000"  # 80% of 5000 default limit
        manager = BudgetManager(mock_redis)
        
        budget = await manager.check_reddit_budget()
        
        assert budget['service'] == 'reddit'
        assert budget['current_usage'] == 4000
        assert budget['daily_limit'] == 5000
        assert budget['usage_percent'] == 80.0
        assert budget['remaining'] == 1000
        assert budget['budget_exceeded'] is False
        assert budget['warning_threshold_80'] is True
        assert budget['warning_threshold_100'] is False
    
    @pytest.mark.asyncio
    async def test_check_openai_budget_exceeded(self, mock_redis):
        """Test OpenAI budget when exceeded"""
        mock_redis.get.return_value = "150000"  # 150% of 100000 default limit
        manager = BudgetManager(mock_redis)
        
        budget = await manager.check_openai_budget()
        
        assert budget['service'] == 'openai'
        assert budget['current_usage'] == 150000
        assert budget['daily_limit'] == 100000
        assert budget['usage_percent'] == 150.0
        assert budget['remaining'] == 0
        assert budget['budget_exceeded'] is True
        assert budget['warning_threshold_80'] is True
        assert budget['warning_threshold_100'] is True
    
    def test_calculate_token_cost(self, mock_redis):
        """Test token cost calculation"""
        manager = BudgetManager(mock_redis)
        
        # Test GPT-4o-mini cost
        cost = manager.calculate_token_cost('gpt-4o-mini', 1000, 500)
        expected_cost = (1500 / 1000.0) * 0.00015  # 1500 tokens * $0.00015 per 1K
        assert abs(cost - expected_cost) < 0.000001
        
        # Test GPT-4o cost
        cost = manager.calculate_token_cost('gpt-4o', 1000, 500)
        expected_cost = (1500 / 1000.0) * 0.005  # 1500 tokens * $0.005 per 1K
        assert abs(cost - expected_cost) < 0.000001
    
    @pytest.mark.asyncio
    async def test_should_block_request(self, mock_redis):
        """Test request blocking logic"""
        # Test when under budget
        mock_redis.get.return_value = "3000"  # Under 5000 limit
        manager = BudgetManager(mock_redis)
        
        should_block = await manager.should_block_request('reddit')
        assert should_block is False
        
        # Test when over budget
        mock_redis.get.return_value = "6000"  # Over 5000 limit
        should_block = await manager.should_block_request('reddit')
        assert should_block is True


def test_mask_sensitive_data_convenience_function():
    """Test convenience function for masking"""
    text = "api_key=secret123"
    result = mask_sensitive_data(text)
    assert "secret123" not in result
    assert "api_key=****" in result