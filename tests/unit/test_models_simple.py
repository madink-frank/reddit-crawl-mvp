"""
Simplified unit tests for database models (without UUID dependency)
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.models.post import Post
from app.models.media_file import MediaFile
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage


class TestPostValidation:
    """Test cases for Post model validation"""
    
    def test_post_validation_success(self):
        """Test successful post validation"""
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.now(),
            status="collected",
            takedown_status="active",
            processing_attempts=0,
            tags=["tech", "startup", "ai"]
        )
        
        errors = post.validate()
        assert len(errors) == 0
    
    def test_post_validation_failures(self):
        """Test post validation failures"""
        post = Post(
            reddit_post_id="",  # Empty reddit_post_id
            title="",  # Empty title
            subreddit="",  # Empty subreddit
            score=-10,  # Negative score
            num_comments=-5,  # Negative comments
            created_ts=datetime.now(),
            status="invalid_status",  # Invalid status
            takedown_status="invalid_takedown",  # Invalid takedown status
            processing_attempts=-1,  # Negative attempts
            tags=["only", "two"]  # Too few tags
        )
        
        errors = post.validate()
        expected_errors = [
            "Reddit post ID is required",
            "Post title is required", 
            "Subreddit is required",
            "Score must be non-negative",
            "Comments count must be non-negative",
            "Status must be one of: collected, processing, processed, published, failed",
            "Takedown status must be one of: active, takedown_pending, removed",
            "Processing attempts must be non-negative",
            "Tags must be a list with 3-5 items if provided"
        ]
        
        assert len(errors) == len(expected_errors)
        for expected_error in expected_errors:
            assert expected_error in errors
    
    def test_post_status_methods(self):
        """Test post status management methods"""
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.now()
        )
        
        # Test initial state
        assert not post.is_processed
        assert not post.is_published
        assert not post.is_takedown_pending
        assert not post.is_removed
        
        # Test processing state
        post.mark_as_processing()
        assert post.status == "processing"
        assert not post.is_processed
        
        # Test processed state
        post.mark_as_processed()
        assert post.status == "processed"
        assert post.is_processed
        assert not post.is_published
        
        # Test published state
        post.mark_as_published("https://ghost.example.com/post/1", "ghost_post_id_123", "test-post-slug")
        assert post.status == "published"
        assert post.is_processed
        assert post.is_published
        assert post.ghost_url == "https://ghost.example.com/post/1"
        assert post.ghost_post_id == "ghost_post_id_123"
        assert post.ghost_slug == "test-post-slug"
        
        # Test failed state
        post.mark_as_failed()
        assert post.status == "failed"
        
        # Test takedown states
        post.mark_takedown_pending()
        assert post.takedown_status == "takedown_pending"
        assert post.is_takedown_pending
        
        post.mark_as_removed()
        assert post.takedown_status == "removed"
        assert post.is_removed
    
    def test_post_processing_attempts(self):
        """Test processing attempts increment"""
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.now(),
            processing_attempts=0
        )
        
        assert post.processing_attempts == 0
        
        post.increment_processing_attempts()
        assert post.processing_attempts == 1
        
        post.increment_processing_attempts()
        assert post.processing_attempts == 2
    
    def test_post_tags_validation(self):
        """Test post tags validation"""
        # Valid tags (3-5 items)
        post_valid = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.now(),
            tags=["tech", "startup", "ai"]
        )
        assert post_valid.validate_tags()
        
        # Too few tags
        post_few = Post(
            reddit_post_id="test_reddit_post_2",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.now(),
            tags=["tech", "startup"]
        )
        assert not post_few.validate_tags()
        
        # Too many tags
        post_many = Post(
            reddit_post_id="test_reddit_post_3",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.now(),
            tags=["tech", "startup", "ai", "productivity", "business", "innovation"]
        )
        assert not post_many.validate_tags()
        
        # No tags (should be valid)
        post_none = Post(
            reddit_post_id="test_reddit_post_4",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.now(),
            tags=None
        )
        assert post_none.validate_tags()


class TestMediaFileValidation:
    """Test cases for MediaFile model validation"""
    
    def test_media_file_validation_success(self):
        """Test successful media file validation"""
        sample_post_id = uuid4()
        media_file = MediaFile(
            post_id=sample_post_id,
            original_url="https://reddit.com/image.jpg",
            file_type="image/jpeg",
            file_size=1024000
        )
        
        errors = media_file.validate()
        assert len(errors) == 0
    
    def test_media_file_validation_failures(self):
        """Test media file validation failures"""
        media_file = MediaFile(
            post_id=None,  # None post ID
            original_url="",  # Empty URL
            file_size=-100  # Negative file size
        )
        
        errors = media_file.validate()
        assert len(errors) == 3
        assert "Post ID is required" in errors
        assert "Original URL is required" in errors
        assert "File size must be positive if provided" in errors
    
    def test_media_file_properties(self):
        """Test media file properties"""
        sample_post_id = uuid4()
        
        # Test image file
        image_file = MediaFile(
            post_id=sample_post_id,
            original_url="https://reddit.com/image.jpg",
            file_type="image/jpeg"
        )
        
        assert image_file.is_image
        assert not image_file.is_video
        assert image_file.filename == "image.jpg"
        
        # Test video file
        video_file = MediaFile(
            post_id=sample_post_id,
            original_url="https://reddit.com/video.mp4?param=value",
            file_type="video/mp4"
        )
        
        assert not video_file.is_image
        assert video_file.is_video
        assert video_file.filename == "video.mp4"
    
    def test_media_file_processing(self):
        """Test media file processing status"""
        sample_post_id = uuid4()
        media_file = MediaFile(
            post_id=sample_post_id,
            original_url="https://reddit.com/image.jpg"
        )
        
        assert not media_file.is_processed
        
        media_file.mark_as_processed("https://ghost.example.com/content/images/image.jpg")
        assert media_file.is_processed
        assert media_file.ghost_url == "https://ghost.example.com/content/images/image.jpg"
        assert media_file.processed_at is not None


class TestProcessingLogValidation:
    """Test cases for ProcessingLog model validation"""
    
    def test_processing_log_validation_success(self):
        """Test successful processing log validation"""
        sample_post_id = uuid4()
        log = ProcessingLog(
            post_id=sample_post_id,
            service_name="collector",
            status="success",
            processing_time_ms=1500
        )
        
        errors = log.validate()
        assert len(errors) == 0
    
    def test_processing_log_validation_failures(self):
        """Test processing log validation failures"""
        log = ProcessingLog(
            post_id=None,  # None post ID
            service_name="",  # Empty service name
            status="",  # Empty status
            processing_time_ms=-100  # Negative processing time
        )
        
        errors = log.validate()
        assert len(errors) == 4
        assert "Post ID is required" in errors
        assert "Service name is required" in errors
        assert "Status is required" in errors
        assert "Processing time must be positive if provided" in errors
    
    def test_processing_log_properties(self):
        """Test processing log properties"""
        sample_post_id = uuid4()
        
        success_log = ProcessingLog(
            post_id=sample_post_id,
            service_name="collector",
            status="success",
            processing_time_ms=1500
        )
        
        assert success_log.is_success
        assert not success_log.is_failure
        assert success_log.processing_time_seconds == 1.5
        
        failure_log = ProcessingLog(
            post_id=sample_post_id,
            service_name="nlp",
            status="failed",
            error_message="API timeout"
        )
        
        assert not failure_log.is_success
        assert failure_log.is_failure
    
    def test_processing_log_factory_methods(self):
        """Test processing log factory methods"""
        sample_post_id = uuid4()
        
        success_log = ProcessingLog.create_success_log(
            post_id=sample_post_id,
            service_name="collector",
            processing_time_ms=1500
        )
        
        assert success_log.post_id == sample_post_id
        assert success_log.service_name == "collector"
        assert success_log.status == "success"
        assert success_log.processing_time_ms == 1500
        
        failure_log = ProcessingLog.create_failure_log(
            post_id=sample_post_id,
            service_name="nlp",
            error_message="API timeout",
            processing_time_ms=5000
        )
        
        assert failure_log.post_id == sample_post_id
        assert failure_log.service_name == "nlp"
        assert failure_log.status == "failed"
        assert failure_log.error_message == "API timeout"
        assert failure_log.processing_time_ms == 5000


class TestTokenUsageValidation:
    """Test cases for TokenUsage model validation"""
    
    def test_token_usage_validation_success(self):
        """Test successful token usage validation"""
        sample_post_id = uuid4()
        token_usage = TokenUsage(
            post_id=sample_post_id,
            service="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=Decimal("0.015")
        )
        
        errors = token_usage.validate()
        assert len(errors) == 0
    
    def test_token_usage_validation_failures(self):
        """Test token usage validation failures"""
        token_usage = TokenUsage(
            post_id=None,  # None post ID
            service="",  # Empty service
            input_tokens=-100,  # Negative input tokens
            output_tokens=-50,  # Negative output tokens
            cost_usd=Decimal("-0.01")  # Negative cost
        )
        
        errors = token_usage.validate()
        assert len(errors) == 4
        assert "Post ID is required" in errors
        assert "Service is required" in errors
        assert "Token counts must be non-negative" in errors
        assert "Cost must be non-negative if provided" in errors
    
    def test_token_usage_properties(self):
        """Test token usage properties"""
        sample_post_id = uuid4()
        
        token_usage = TokenUsage(
            post_id=sample_post_id,
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
            post_id=sample_post_id,
            service="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert token_usage_no_cost.cost_formatted == "$0.00"
    
    def test_token_usage_factory_methods(self):
        """Test token usage factory methods"""
        sample_post_id = uuid4()
        
        openai_usage = TokenUsage.create_openai_usage(
            post_id=sample_post_id,
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert openai_usage.post_id == sample_post_id
        assert openai_usage.service == "openai"
        assert openai_usage.model == "gpt-4o-mini"
        assert openai_usage.input_tokens == 1000
        assert openai_usage.output_tokens == 500
        # Cost should be calculated: (1000 * 0.0000025) + (500 * 0.00001) = 0.0025 + 0.005 = 0.0075
        assert openai_usage.cost_usd == Decimal("0.0075")
        
        gpt4o_usage = TokenUsage.create_gpt4o_usage(
            post_id=sample_post_id,
            input_tokens=1000,
            output_tokens=500
        )
        
        assert gpt4o_usage.post_id == sample_post_id
        assert gpt4o_usage.service == "openai"
        assert gpt4o_usage.model == "gpt-4o"
        assert gpt4o_usage.input_tokens == 1000
        assert gpt4o_usage.output_tokens == 500
        # Cost should be calculated: (1000 * 0.000005) + (500 * 0.000015) = 0.005 + 0.0075 = 0.0125
        assert gpt4o_usage.cost_usd == Decimal("0.0125")
    
    def test_token_usage_cost_update(self):
        """Test updating token usage cost"""
        sample_post_id = uuid4()
        token_usage = TokenUsage(
            post_id=sample_post_id,
            service="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500
        )
        
        assert token_usage.cost_usd is None
        
        token_usage.update_cost(Decimal("0.02"))
        assert token_usage.cost_usd == Decimal("0.02")