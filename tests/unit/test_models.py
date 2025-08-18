"""
Unit tests for database models
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4, UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.post import Post
from app.models.media_file import MediaFile
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    # Use SQLite for unit tests (PostgreSQL for integration tests)
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_post_id():
    """Generate a sample UUID for testing"""
    return uuid4()


class TestPost:
    """Test cases for Post model"""
    
    def test_post_creation(self, db_session, sample_post_id):
        """Test creating a new post"""
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow()
        )
        
        db_session.add(post)
        db_session.commit()
        
        retrieved_post = db_session.query(Post).filter_by(reddit_post_id="test_reddit_post_1").first()
        assert retrieved_post is not None
        assert retrieved_post.title == "Test Post Title"
        assert retrieved_post.subreddit == "test"
        assert retrieved_post.score == 100
        assert retrieved_post.num_comments == 25
        assert retrieved_post.status == "collected"  # default value
        assert retrieved_post.takedown_status == "active"  # default value
    
    def test_post_validation_success(self):
        """Test successful post validation"""
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow(),
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
            created_ts=datetime.utcnow(),
            status="invalid_status",  # Invalid status
            takedown_status="invalid_takedown",  # Invalid takedown status
            processing_attempts=-1,  # Negative attempts
            tags=["only", "two"]  # Too few tags
        )
        
        errors = post.validate()
        assert len(errors) == 8
        assert "Reddit post ID is required" in errors
        assert "Post title is required" in errors
        assert "Subreddit is required" in errors
        assert "Score must be non-negative" in errors
        assert "Comments count must be non-negative" in errors
        assert "Status must be one of: collected, processing, processed, published, failed" in errors
        assert "Takedown status must be one of: active, takedown_pending, removed" in errors
        assert "Processing attempts must be non-negative" in errors
        assert "Tags must be a list with 3-5 items if provided" in errors
    
    def test_post_status_methods(self):
        """Test post status management methods"""
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow()
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
            created_ts=datetime.utcnow(),
            processing_attempts=0
        )
        
        assert post.processing_attempts == 0
        
        post.increment_processing_attempts()
        assert post.processing_attempts == 1
        
        post.increment_processing_attempts()
        assert post.processing_attempts == 2
    
    def test_post_with_json_fields(self, db_session):
        """Test post with JSONB fields (tags, pain_points and product_ideas)"""
        tags = ["tech", "startup", "ai", "productivity"]
        pain_points = {
            "main_issues": ["slow performance", "poor UI"],
            "severity": "high"
        }
        product_ideas = {
            "suggestions": ["mobile app", "API integration"],
            "priority": "medium"
        }
        
        post = Post(
            reddit_post_id="test_reddit_post_json",
            title="Test Post with JSON",
            subreddit="test",
            score=50,
            num_comments=10,
            created_ts=datetime.utcnow(),
            tags=tags,
            pain_points=pain_points,
            product_ideas=product_ideas
        )
        
        db_session.add(post)
        db_session.commit()
        
        retrieved_post = db_session.query(Post).filter_by(reddit_post_id="test_reddit_post_json").first()
        assert retrieved_post.tags == tags
        assert retrieved_post.pain_points == pain_points
        assert retrieved_post.product_ideas == product_ideas
    
    def test_post_tags_validation(self):
        """Test post tags validation"""
        # Valid tags (3-5 items)
        post_valid = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow(),
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
            created_ts=datetime.utcnow(),
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
            created_ts=datetime.utcnow(),
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
            created_ts=datetime.utcnow(),
            tags=None
        )
        assert post_none.validate_tags()


class TestMediaFile:
    """Test cases for MediaFile model"""
    
    def test_media_file_creation(self, db_session, sample_post_id):
        """Test creating a new media file"""
        # First create a post
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        # Create media file
        media_file = MediaFile(
            post_id=post.id,
            original_url="https://reddit.com/image.jpg",
            file_type="image/jpeg",
            file_size=1024000
        )
        
        db_session.add(media_file)
        db_session.commit()
        
        retrieved_file = db_session.query(MediaFile).filter_by(post_id=post.id).first()
        assert retrieved_file is not None
        assert retrieved_file.original_url == "https://reddit.com/image.jpg"
        assert retrieved_file.file_type == "image/jpeg"
        assert retrieved_file.file_size == 1024000
    
    def test_media_file_validation_success(self, sample_post_id):
        """Test successful media file validation"""
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
    
    def test_media_file_properties(self, sample_post_id):
        """Test media file properties"""
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
    
    def test_media_file_processing(self, sample_post_id):
        """Test media file processing status"""
        media_file = MediaFile(
            post_id=sample_post_id,
            original_url="https://reddit.com/image.jpg"
        )
        
        assert not media_file.is_processed
        
        media_file.mark_as_processed("https://ghost.example.com/content/images/image.jpg")
        assert media_file.is_processed
        assert media_file.ghost_url == "https://ghost.example.com/content/images/image.jpg"
        assert media_file.processed_at is not None


class TestProcessingLog:
    """Test cases for ProcessingLog model"""
    
    def test_processing_log_creation(self, db_session):
        """Test creating a new processing log"""
        # First create a post
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        # Create processing log
        log = ProcessingLog(
            post_id=post.id,
            service_name="collector",
            status="success",
            processing_time_ms=1500
        )
        
        db_session.add(log)
        db_session.commit()
        
        retrieved_log = db_session.query(ProcessingLog).filter_by(post_id=post.id).first()
        assert retrieved_log is not None
        assert retrieved_log.service_name == "collector"
        assert retrieved_log.status == "success"
        assert retrieved_log.processing_time_ms == 1500
    
    def test_processing_log_validation_success(self, sample_post_id):
        """Test successful processing log validation"""
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
    
    def test_processing_log_properties(self, sample_post_id):
        """Test processing log properties"""
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
    
    def test_processing_log_factory_methods(self, sample_post_id):
        """Test processing log factory methods"""
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


class TestTokenUsage:
    """Test cases for TokenUsage model"""
    
    def test_token_usage_creation(self, db_session):
        """Test creating a new token usage record"""
        # First create a post
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        # Create token usage
        token_usage = TokenUsage(
            post_id=post.id,
            service="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=Decimal("0.015")
        )
        
        db_session.add(token_usage)
        db_session.commit()
        
        retrieved_usage = db_session.query(TokenUsage).filter_by(post_id=post.id).first()
        assert retrieved_usage is not None
        assert retrieved_usage.service == "openai"
        assert retrieved_usage.model == "gpt-4o-mini"
        assert retrieved_usage.input_tokens == 1000
        assert retrieved_usage.output_tokens == 500
        assert retrieved_usage.cost_usd == Decimal("0.015")
    
    def test_token_usage_validation_success(self, sample_post_id):
        """Test successful token usage validation"""
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
    
    def test_token_usage_properties(self, sample_post_id):
        """Test token usage properties"""
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
    
    def test_token_usage_factory_methods(self, sample_post_id):
        """Test token usage factory methods"""
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
    
    def test_token_usage_cost_update(self, sample_post_id):
        """Test updating token usage cost"""
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


class TestModelRelationships:
    """Test cases for model relationships"""
    
    def test_post_relationships(self, db_session):
        """Test post relationships with other models"""
        # Create post
        post = Post(
            reddit_post_id="test_reddit_post_1",
            title="Test Post Title",
            subreddit="test",
            score=100,
            num_comments=25,
            created_ts=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()
        
        # Create related records
        media_file = MediaFile(
            post_id=post.id,
            original_url="https://reddit.com/image.jpg"
        )
        
        processing_log = ProcessingLog(
            post_id=post.id,
            service_name="collector",
            status="success"
        )
        
        token_usage = TokenUsage(
            post_id=post.id,
            service="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500
        )
        
        db_session.add_all([media_file, processing_log, token_usage])
        db_session.commit()
        
        # Test relationships
        retrieved_post = db_session.query(Post).filter_by(reddit_post_id="test_reddit_post_1").first()
        assert len(retrieved_post.media_files) == 1
        assert len(retrieved_post.processing_logs) == 1
        assert len(retrieved_post.token_usage) == 1
        
        assert retrieved_post.media_files[0].original_url == "https://reddit.com/image.jpg"
        assert retrieved_post.processing_logs[0].service_name == "collector"
        assert retrieved_post.token_usage[0].service == "openai"
        assert retrieved_post.token_usage[0].model == "gpt-4o-mini"