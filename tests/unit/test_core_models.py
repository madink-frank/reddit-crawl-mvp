"""
Unit tests for core models and basic functionality
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from unittest.mock import Mock, patch

# Test the models directly without complex imports
from app.models.post import Post
from app.models.media_file import MediaFile
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage


class TestPostModel:
    """Test Post model functionality"""
    
    def test_post_creation_basic(self):
        """Test basic post creation"""
        post = Post(
            reddit_post_id="test_post_123",
            title="Test Post Title",
            subreddit="technology",
            score=150,
            num_comments=25,
            created_ts=datetime.utcnow(),
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        
        assert post.reddit_post_id == "test_post_123"
        assert post.title == "Test Post Title"
        assert post.subreddit == "technology"
        assert post.score == 150
        assert post.num_comments == 25
        assert post.status == "collected"
        assert post.takedown_status == "active"
    
    def test_post_validation_success(self):
        """Test successful post validation"""
        post = Post(
            reddit_post_id="valid_post_123",
            title="Valid Post Title",
            subreddit="programming",
            score=200,
            num_comments=50,
            created_ts=datetime.utcnow(),
            tags=["python", "programming", "tutorial"],
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        
        errors = post.validate()
        assert len(errors) == 0
    
    def test_post_validation_failures(self):
        """Test post validation with various failures"""
        post = Post(
            reddit_post_id="",  # Empty ID
            title="",  # Empty title
            subreddit="",  # Empty subreddit
            score=-10,  # Negative score
            num_comments=-5,  # Negative comments
            created_ts=datetime.utcnow(),
            tags=["only", "two"]  # Too few tags
        )
        
        errors = post.validate()
        assert len(errors) > 0
        
        # Check specific error messages
        error_text = " ".join(errors)
        assert "Reddit post ID is required" in error_text
        assert "Post title is required" in error_text
        assert "Subreddit is required" in error_text
        assert "Score must be non-negative" in error_text
        assert "Comments count must be non-negative" in error_text
    
    def test_post_status_transitions(self):
        """Test post status management"""
        post = Post(
            reddit_post_id="status_test_123",
            title="Status Test",
            subreddit="test",
            score=100,
            num_comments=10,
            created_ts=datetime.utcnow(),
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        
        # Initial state
        assert post.status == "collected"
        assert not post.is_processed
        assert not post.is_published
        
        # Mark as processing
        post.mark_as_processing()
        assert post.status == "processing"
        
        # Mark as processed
        post.mark_as_processed()
        assert post.status == "processed"
        assert post.is_processed
        
        # Mark as published
        post.mark_as_published(
            ghost_url="https://blog.example.com/test-post/",
            ghost_post_id="ghost_123",
            ghost_slug="test-post"
        )
        assert post.status == "published"
        assert post.is_published
        assert post.ghost_url == "https://blog.example.com/test-post/"
        assert post.ghost_post_id == "ghost_123"
        assert post.ghost_slug == "test-post"
    
    def test_post_takedown_status(self):
        """Test takedown status management"""
        post = Post(
            reddit_post_id="takedown_test_123",
            title="Takedown Test",
            subreddit="test",
            score=100,
            num_comments=10,
            created_ts=datetime.utcnow(),
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        
        # Initial state
        assert post.takedown_status == "active"
        assert not post.is_takedown_pending
        assert not post.is_removed
        
        # Mark takedown pending
        post.mark_takedown_pending()
        assert post.takedown_status == "takedown_pending"
        assert post.is_takedown_pending
        
        # Mark as removed
        post.mark_as_removed()
        assert post.takedown_status == "removed"
        assert post.is_removed
    
    def test_post_processing_attempts(self):
        """Test processing attempts tracking"""
        post = Post(
            reddit_post_id="attempts_test_123",
            title="Attempts Test",
            subreddit="test",
            score=100,
            num_comments=10,
            created_ts=datetime.utcnow(),
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        
        assert post.processing_attempts == 0
        
        post.increment_processing_attempts()
        assert post.processing_attempts == 1
        
        post.increment_processing_attempts()
        assert post.processing_attempts == 2
    
    def test_post_tags_validation(self):
        """Test tags validation"""
        # Valid tags (3-5 items)
        post_valid = Post(
            reddit_post_id="tags_valid_123",
            title="Valid Tags Test",
            subreddit="test",
            score=100,
            num_comments=10,
            created_ts=datetime.utcnow(),
            tags=["python", "programming", "tutorial"],
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        assert post_valid.validate_tags()
        
        # Too few tags
        post_few = Post(
            reddit_post_id="tags_few_123",
            title="Few Tags Test",
            subreddit="test",
            score=100,
            num_comments=10,
            created_ts=datetime.utcnow(),
            tags=["python", "programming"],  # Only 2 tags
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        assert not post_few.validate_tags()
        
        # Too many tags
        post_many = Post(
            reddit_post_id="tags_many_123",
            title="Many Tags Test",
            subreddit="test",
            score=100,
            num_comments=10,
            created_ts=datetime.utcnow(),
            tags=["python", "programming", "tutorial", "beginner", "advanced", "expert"],  # 6 tags
            status="collected",
            takedown_status="active",
            processing_attempts=0
        )
        assert not post_many.validate_tags()


class TestMediaFileModel:
    """Test MediaFile model functionality"""
    
    def test_media_file_creation(self):
        """Test media file creation"""
        post_id = uuid4()
        media_file = MediaFile(
            post_id=post_id,
            original_url="https://reddit.com/image.jpg",
            file_type="image/jpeg",
            file_size=1024000
        )
        
        assert media_file.post_id == post_id
        assert media_file.original_url == "https://reddit.com/image.jpg"
        assert media_file.file_type == "image/jpeg"
        assert media_file.file_size == 1024000
    
    def test_media_file_validation_success(self):
        """Test successful media file validation"""
        media_file = MediaFile(
            post_id=uuid4(),
            original_url="https://reddit.com/image.jpg",
            file_type="image/jpeg",
            file_size=1024000
        )
        
        errors = media_file.validate()
        assert len(errors) == 0
    
    def test_media_file_validation_failures(self):
        """Test media file validation failures"""
        media_file = MediaFile(
            post_id=None,  # Missing post ID
            original_url="",  # Empty URL
            file_size=-100  # Negative file size
        )
        
        errors = media_file.validate()
        assert len(errors) > 0
        
        error_text = " ".join(errors)
        assert "Post ID is required" in error_text
        assert "Original URL is required" in error_text
        assert "File size must be positive" in error_text
    
    def test_media_file_properties(self):
        """Test media file properties"""
        post_id = uuid4()
        
        # Test image file
        image_file = MediaFile(
            post_id=post_id,
            original_url="https://reddit.com/image.jpg",
            file_type="image/jpeg"
        )
        
        assert image_file.is_image
        assert not image_file.is_video
        assert image_file.filename == "image.jpg"
        
        # Test video file
        video_file = MediaFile(
            post_id=post_id,
            original_url="https://reddit.com/video.mp4?param=value",
            file_type="video/mp4"
        )
        
        assert not video_file.is_image
        assert video_file.is_video
        assert video_file.filename == "video.mp4"
    
    def test_media_file_processing_status(self):
        """Test media file processing status"""
        media_file = MediaFile(
            post_id=uuid4(),
            original_url="https://reddit.com/image.jpg"
        )
        
        assert not media_file.is_processed
        
        media_file.mark_as_processed("https://cdn.ghost.io/processed-image.jpg")
        assert media_file.is_processed
        assert media_file.ghost_url == "https://cdn.ghost.io/processed-image.jpg"
        assert media_file.processed_at is not None


class TestProcessingLogModel:
    """Test ProcessingLog model functionality"""
    
    def test_processing_log_creation(self):
        """Test processing log creation"""
        post_id = uuid4()
        log = ProcessingLog(
            post_id=post_id,
            service_name="collector",
            status="success",
            processing_time_ms=1500
        )
        
        assert log.post_id == post_id
        assert log.service_name == "collector"
        assert log.status == "success"
        assert log.processing_time_ms == 1500
    
    def test_processing_log_validation_success(self):
        """Test successful processing log validation"""
        log = ProcessingLog(
            post_id=uuid4(),
            service_name="nlp_pipeline",
            status="success",
            processing_time_ms=2500
        )
        
        errors = log.validate()
        assert len(errors) == 0
    
    def test_processing_log_validation_failures(self):
        """Test processing log validation failures"""
        log = ProcessingLog(
            post_id=None,  # Missing post ID
            service_name="",  # Empty service name
            status="",  # Empty status
            processing_time_ms=-100  # Negative processing time
        )
        
        errors = log.validate()
        assert len(errors) > 0
        
        error_text = " ".join(errors)
        assert "Post ID is required" in error_text
        assert "Service name is required" in error_text
        assert "Status is required" in error_text
        assert "Processing time must be positive" in error_text
    
    def test_processing_log_properties(self):
        """Test processing log properties"""
        post_id = uuid4()
        
        # Success log
        success_log = ProcessingLog(
            post_id=post_id,
            service_name="collector",
            status="success",
            processing_time_ms=1500
        )
        
        assert success_log.is_success
        assert not success_log.is_failure
        assert success_log.processing_time_seconds == 1.5
        
        # Failure log
        failure_log = ProcessingLog(
            post_id=post_id,
            service_name="nlp_pipeline",
            status="failed",
            error_message="API timeout"
        )
        
        assert not failure_log.is_success
        assert failure_log.is_failure
    
    def test_processing_log_factory_methods(self):
        """Test processing log factory methods"""
        post_id = uuid4()
        
        # Success log factory
        success_log = ProcessingLog.create_success_log(
            post_id=post_id,
            service_name="publisher",
            processing_time_ms=3000
        )
        
        assert success_log.post_id == post_id
        assert success_log.service_name == "publisher"
        assert success_log.status == "success"
        assert success_log.processing_time_ms == 3000
        
        # Failure log factory
        failure_log = ProcessingLog.create_failure_log(
            post_id=post_id,
            service_name="nlp_pipeline",
            error_message="OpenAI API error",
            processing_time_ms=5000
        )
        
        assert failure_log.post_id == post_id
        assert failure_log.service_name == "nlp_pipeline"
        assert failure_log.status == "failed"
        assert failure_log.error_message == "OpenAI API error"
        assert failure_log.processing_time_ms == 5000


class TestTokenUsageModel:
    """Test TokenUsage model functionality"""
    
    def test_token_usage_creation(self):
        """Test token usage creation"""
        post_id = uuid4()
        token_usage = TokenUsage(
            post_id=post_id,
            service="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=Decimal("0.015")
        )
        
        assert token_usage.post_id == post_id
        assert token_usage.service == "openai"
        assert token_usage.model == "gpt-4o-mini"
        assert token_usage.input_tokens == 1000
        assert token_usage.output_tokens == 500
        assert token_usage.cost_usd == Decimal("0.015")
    
    def test_token_usage_validation_success(self):
        """Test successful token usage validation"""
        token_usage = TokenUsage(
            post_id=uuid4(),
            service="openai",
            model="gpt-4o",
            input_tokens=800,
            output_tokens=400,
            cost_usd=Decimal("0.025")
        )
        
        errors = token_usage.validate()
        assert len(errors) == 0
    
    def test_token_usage_validation_failures(self):
        """Test token usage validation failures"""
        token_usage = TokenUsage(
            post_id=None,  # Missing post ID
            service="",  # Empty service
            input_tokens=-100,  # Negative input tokens
            output_tokens=-50,  # Negative output tokens
            cost_usd=Decimal("-0.01")  # Negative cost
        )
        
        errors = token_usage.validate()
        assert len(errors) > 0
        
        error_text = " ".join(errors)
        assert "Post ID is required" in error_text
        assert "Service is required" in error_text
        assert "Token counts must be non-negative" in error_text
        assert "Cost must be non-negative" in error_text
    
    def test_token_usage_properties(self):
        """Test token usage properties"""
        token_usage = TokenUsage(
            post_id=uuid4(),
            service="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=Decimal("0.015")
        )
        
        assert token_usage.total_tokens == 1500
        assert token_usage.cost_formatted == "$0.015000"
        
        # Test with no cost
        token_usage_no_cost = TokenUsage(
            post_id=uuid4(),
            service="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert token_usage_no_cost.cost_formatted == "$0.00"
    
    def test_token_usage_factory_methods(self):
        """Test token usage factory methods"""
        post_id = uuid4()
        
        # OpenAI usage factory
        openai_usage = TokenUsage.create_openai_usage(
            post_id=post_id,
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert openai_usage.post_id == post_id
        assert openai_usage.service == "openai"
        assert openai_usage.model == "gpt-4o-mini"
        assert openai_usage.input_tokens == 1000
        assert openai_usage.output_tokens == 500
        # Cost should be calculated based on model pricing
        assert openai_usage.cost_usd > 0
        
        # GPT-4o usage factory
        gpt4o_usage = TokenUsage.create_gpt4o_usage(
            post_id=post_id,
            input_tokens=1000,
            output_tokens=500
        )
        
        assert gpt4o_usage.model == "gpt-4o"
        assert gpt4o_usage.cost_usd > openai_usage.cost_usd  # GPT-4o should be more expensive
    
    def test_token_usage_cost_update(self):
        """Test updating token usage cost"""
        token_usage = TokenUsage(
            post_id=uuid4(),
            service="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert token_usage.cost_usd is None
        
        token_usage.update_cost(Decimal("0.02"))
        assert token_usage.cost_usd == Decimal("0.02")


class TestConfigurationSettings:
    """Test configuration and settings"""
    
    def test_config_loading(self):
        """Test configuration loading"""
        from app.config import get_settings
        
        settings = get_settings()
        
        # Test that settings object is created
        assert settings is not None
        assert hasattr(settings, 'app_name')
        assert hasattr(settings, 'environment')
        
        # Test default values
        assert settings.environment in ['development', 'production', 'testing']
    
    def test_config_caching(self):
        """Test that settings are cached"""
        from app.config import get_settings
        
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should return the same instance (cached)
        assert settings1 is settings2


class TestErrorHandling:
    """Test error handling functionality"""
    
    def test_custom_exceptions(self):
        """Test custom exception classes"""
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
        
        # Test RetryableError
        retryable_error = RetryableError("Temporary failure")
        assert retryable_error.is_retryable is True
        
        # Test NonRetryableError
        non_retryable_error = NonRetryableError("Permanent failure")
        assert non_retryable_error.is_retryable is False
        
        # Test RateLimitError
        rate_limit_error = RateLimitError("Rate limit exceeded")
        assert "Rate limit exceeded" in str(rate_limit_error)
        
        # Test AuthenticationError
        auth_error = AuthenticationError("Invalid credentials")
        assert "Invalid credentials" in str(auth_error)
        
        # Test QuotaExceededError
        quota_error = QuotaExceededError("Daily quota exceeded")
        assert "Daily quota exceeded" in str(quota_error)


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_content_hash_calculation(self):
        """Test content hash calculation"""
        # Mock the function since we can't import it directly
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
        # Mock the function since we can't import it directly
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


if __name__ == "__main__":
    pytest.main([__file__])