"""
Simple unit tests for core functionality
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

# Test basic imports and functionality
from app.config import get_settings
from app.models.post import Post
from app.models.media_file import MediaFile
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage


class TestBasicFunctionality:
    """Test basic system functionality"""
    
    def test_settings_loading(self):
        """Test that settings can be loaded"""
        settings = get_settings()
        assert settings is not None
        assert hasattr(settings, 'app_name')
        assert hasattr(settings, 'environment')
    
    def test_post_model_basic_creation(self):
        """Test basic post model creation"""
        post = Post()
        post.reddit_post_id = "test123"
        post.title = "Test Post"
        post.subreddit = "test"
        post.score = 100
        post.num_comments = 10
        post.created_ts = datetime.utcnow()
        
        assert post.reddit_post_id == "test123"
        assert post.title == "Test Post"
        assert post.subreddit == "test"
        assert post.score == 100
        assert post.num_comments == 10
    
    def test_media_file_model_basic_creation(self):
        """Test basic media file model creation"""
        media_file = MediaFile()
        media_file.post_id = uuid4()
        media_file.original_url = "https://example.com/image.jpg"
        media_file.file_type = "image/jpeg"
        media_file.file_size = 1024
        
        assert media_file.original_url == "https://example.com/image.jpg"
        assert media_file.file_type == "image/jpeg"
        assert media_file.file_size == 1024
    
    def test_processing_log_model_basic_creation(self):
        """Test basic processing log model creation"""
        log = ProcessingLog()
        log.post_id = uuid4()
        log.service_name = "collector"
        log.status = "success"
        log.processing_time_ms = 1500
        
        assert log.service_name == "collector"
        assert log.status == "success"
        assert log.processing_time_ms == 1500
    
    def test_token_usage_model_basic_creation(self):
        """Test basic token usage model creation"""
        token_usage = TokenUsage()
        token_usage.post_id = uuid4()
        token_usage.service = "openai"
        token_usage.model = "gpt-4o-mini"
        token_usage.input_tokens = 1000
        token_usage.output_tokens = 500
        token_usage.cost_usd = Decimal("0.015")
        
        assert token_usage.service == "openai"
        assert token_usage.model == "gpt-4o-mini"
        assert token_usage.input_tokens == 1000
        assert token_usage.output_tokens == 500
        assert token_usage.cost_usd == Decimal("0.015")
    
    def test_post_model_properties(self):
        """Test post model properties"""
        post = Post()
        post.status = "collected"
        
        # Test status properties
        assert not post.is_processed
        assert not post.is_published
        
        post.status = "processed"
        assert post.is_processed
        assert not post.is_published
        
        post.status = "published"
        post.ghost_url = "https://example.com/post"  # Need ghost_url for is_published
        assert post.is_processed
        assert post.is_published
    
    def test_media_file_properties(self):
        """Test media file properties"""
        media_file = MediaFile()
        media_file.original_url = "https://example.com/image.jpg"
        media_file.file_type = "image/jpeg"
        
        assert media_file.is_image
        assert not media_file.is_video
        assert media_file.filename == "image.jpg"
        
        # Test video file
        media_file.original_url = "https://example.com/video.mp4"
        media_file.file_type = "video/mp4"
        
        assert not media_file.is_image
        assert media_file.is_video
        assert media_file.filename == "video.mp4"
    
    def test_processing_log_properties(self):
        """Test processing log properties"""
        log = ProcessingLog()
        log.status = "success"
        log.processing_time_ms = 1500
        
        assert log.is_success
        assert not log.is_failure
        assert log.processing_time_seconds == 1.5
        
        log.status = "failed"
        assert not log.is_success
        assert log.is_failure
    
    def test_token_usage_properties(self):
        """Test token usage properties"""
        token_usage = TokenUsage()
        token_usage.input_tokens = 1000
        token_usage.output_tokens = 500
        token_usage.cost_usd = Decimal("0.015")
        
        assert token_usage.total_tokens == 1500
        assert token_usage.cost_formatted == "$0.015000"


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_content_hash_calculation(self):
        """Test content hash calculation"""
        import hashlib
        
        def calculate_content_hash(title, content, media_urls=None):
            """Calculate SHA256 hash of content"""
            content_str = f"{title}{content}"
            if media_urls:
                content_str += "".join(sorted(media_urls))
            return hashlib.sha256(content_str.encode()).hexdigest()
        
        # Test basic hash calculation
        hash1 = calculate_content_hash("Title", "Content")
        hash2 = calculate_content_hash("Title", "Content")
        assert hash1 == hash2  # Same content should produce same hash
        
        # Test different content produces different hash
        hash3 = calculate_content_hash("Different Title", "Content")
        assert hash1 != hash3
        
        # Test with media URLs
        hash4 = calculate_content_hash("Title", "Content", ["url1", "url2"])
        hash5 = calculate_content_hash("Title", "Content", ["url2", "url1"])  # Different order
        assert hash4 == hash5  # Order shouldn't matter (sorted)
    
    def test_pii_masking(self):
        """Test PII masking functionality"""
        import re
        
        def mask_sensitive_data(text):
            """Mask sensitive information in text"""
            # API keys
            text = re.sub(r'(api[_-]?key["\s]*[:=]["\s]*)([a-zA-Z0-9-_]{10,})', r'\1****', text, flags=re.IGNORECASE)
            # Tokens
            text = re.sub(r'(token["\s]*[:=]["\s]*)([a-zA-Z0-9-_]{10,})', r'\1****', text, flags=re.IGNORECASE)
            # Emails
            text = re.sub(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'****@\2', text)
            return text
        
        # Test API key masking
        text_with_api_key = 'API_KEY=sk-1234567890abcdef'
        masked = mask_sensitive_data(text_with_api_key)
        assert 'sk-1234567890abcdef' not in masked
        assert '****' in masked
        
        # Test email masking
        text_with_email = 'Contact: user@example.com for support'
        masked = mask_sensitive_data(text_with_email)
        assert 'user@example.com' not in masked
        assert '****@example.com' in masked
        
        # Test token masking
        text_with_token = 'Bearer token: abc123def456'
        masked = mask_sensitive_data(text_with_token)
        assert 'abc123def456' not in masked
        assert '****' in masked
    
    def test_daily_key_generation(self):
        """Test daily key generation for Redis"""
        from datetime import datetime
        
        def generate_daily_key(prefix, date=None):
            """Generate daily key with date suffix"""
            if date is None:
                date = datetime.utcnow()
            date_str = date.strftime('%Y%m%d')
            return f"{prefix}:{date_str}"
        
        # Test with current date
        key1 = generate_daily_key('api_calls')
        today = datetime.utcnow().strftime('%Y%m%d')
        assert key1 == f"api_calls:{today}"
        
        # Test with specific date
        test_date = datetime(2024, 1, 15)
        key2 = generate_daily_key('token_usage', test_date)
        assert key2 == "token_usage:20240115"
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        def generate_cache_key(namespace, *args, **kwargs):
            """Generate cache key from namespace and arguments"""
            key_parts = [namespace]
            key_parts.extend(str(arg) for arg in args)
            if kwargs:
                sorted_kwargs = sorted(kwargs.items())
                key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
            return ":".join(key_parts)
        
        # Test basic cache key
        key1 = generate_cache_key('subreddit', 'technology', 'hot')
        assert key1 == 'subreddit:technology:hot'
        
        # Test with kwargs
        key2 = generate_cache_key('posts', 'technology', limit=10, sort='hot')
        assert key2 == 'posts:technology:limit=10:sort=hot'
        
        # Test kwargs ordering consistency
        key3 = generate_cache_key('posts', 'technology', sort='hot', limit=10)
        assert key2 == key3  # Should be same regardless of kwargs order


class TestModelValidation:
    """Test model validation logic"""
    
    def test_post_validation_basic(self):
        """Test basic post validation"""
        post = Post()
        post.reddit_post_id = "valid_post_123"
        post.title = "Valid Post Title"
        post.subreddit = "programming"
        post.score = 200
        post.num_comments = 50
        post.created_ts = datetime.utcnow()
        post.status = "collected"
        post.takedown_status = "active"
        post.processing_attempts = 0
        post.tags = ["python", "programming", "tutorial"]
        
        # Should not raise any validation errors
        errors = post.validate()
        assert len(errors) == 0
    
    def test_media_file_validation_basic(self):
        """Test basic media file validation"""
        media_file = MediaFile()
        media_file.post_id = uuid4()
        media_file.original_url = "https://example.com/image.jpg"
        media_file.file_type = "image/jpeg"
        media_file.file_size = 1024
        
        # Should not raise any validation errors
        errors = media_file.validate()
        assert len(errors) == 0
    
    def test_processing_log_validation_basic(self):
        """Test basic processing log validation"""
        log = ProcessingLog()
        log.post_id = uuid4()
        log.service_name = "collector"
        log.status = "success"
        log.processing_time_ms = 1500
        
        # Should not raise any validation errors
        errors = log.validate()
        assert len(errors) == 0
    
    def test_token_usage_validation_basic(self):
        """Test basic token usage validation"""
        token_usage = TokenUsage()
        token_usage.post_id = uuid4()
        token_usage.service = "openai"
        token_usage.model = "gpt-4o-mini"
        token_usage.input_tokens = 1000
        token_usage.output_tokens = 500
        token_usage.cost_usd = Decimal("0.015")
        
        # Should not raise any validation errors
        errors = token_usage.validate()
        assert len(errors) == 0


class TestErrorHandling:
    """Test error handling functionality"""
    
    def test_import_error_handling(self):
        """Test that we can import error classes"""
        from app.error_handling import (
            ServiceError,
            RetryableError,
            NonRetryableError,
            RateLimitError,
            AuthenticationError,
            QuotaExceededError
        )
        
        # Test ServiceError
        service_error = ServiceError("Test service error", service="test_service")
        assert str(service_error) == "Test service error"
        assert service_error.service == "test_service"
        assert service_error.timestamp is not None
        
        # Test basic error properties
        retryable_error = RetryableError("Temporary failure", service="test_service")
        assert "Temporary failure" in str(retryable_error)
        
        non_retryable_error = NonRetryableError("Permanent failure", service="test_service")
        assert "Permanent failure" in str(non_retryable_error)


class TestConfigurationHandling:
    """Test configuration handling"""
    
    def test_settings_singleton(self):
        """Test that settings are cached (singleton pattern)"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should return the same instance (cached)
        assert settings1 is settings2
    
    def test_settings_basic_properties(self):
        """Test basic settings properties"""
        settings = get_settings()
        
        # Test that basic properties exist
        assert hasattr(settings, 'app_name')
        assert hasattr(settings, 'environment')
        assert hasattr(settings, 'debug')
        
        # Test that environment is valid
        assert settings.environment in ['development', 'production', 'testing']


if __name__ == "__main__":
    pytest.main([__file__])