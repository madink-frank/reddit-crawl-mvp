"""
Integration tests for database operations
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.post import Post
from app.models.media_file import MediaFile
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage


class TestDatabaseIntegration:
    """Test database integration scenarios"""
    
    @pytest.fixture
    def db_engine(self):
        """Create test database engine"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        Base.metadata.create_all(engine)
        return engine
    
    @pytest.fixture
    def db_session(self, db_engine):
        """Create database session"""
        Session = sessionmaker(bind=db_engine)
        session = Session()
        yield session
        session.close()
    
    def test_post_crud_operations(self, db_session):
        """Test complete CRUD operations for posts"""
        # Create
        post = Post(
            id="integration_test_1",
            title="Integration Test Post",
            subreddit="technology",
            score=150,
            comments=45,
            created_ts=datetime.utcnow(),
            url="https://reddit.com/test",
            content="Test content for integration testing",
            author="test_author"
        )
        
        db_session.add(post)
        db_session.commit()
        
        # Read
        retrieved_post = db_session.query(Post).filter_by(id="integration_test_1").first()
        assert retrieved_post is not None
        assert retrieved_post.title == "Integration Test Post"
        assert retrieved_post.subreddit == "technology"
        assert retrieved_post.score == 150
        
        # Update
        retrieved_post.score = 200
        retrieved_post.summary_ko = "한국어 요약"
        retrieved_post.topic_tag = "technology,ai"
        db_session.commit()
        
        updated_post = db_session.query(Post).filter_by(id="integration_test_1").first()
        assert updated_post.score == 200
        assert updated_post.summary_ko == "한국어 요약"
        assert updated_post.topic_tag == "technology,ai"
        
        # Delete
        db_session.delete(updated_post)
        db_session.commit()
        
        deleted_post = db_session.query(Post).filter_by(id="integration_test_1").first()
        assert deleted_post is None
    
    def test_post_status_workflow(self, db_session):
        """Test post status workflow"""
        post = Post(
            id="status_test_1",
            title="Status Test Post",
            subreddit="test",
            score=100,
            comments=20,
            created_ts=datetime.utcnow()
        )
        
        db_session.add(post)
        db_session.commit()
        
        # Initial status should be 'collected'
        assert post.status == "collected"
        assert not post.is_processed
        assert not post.is_published
        
        # Mark as processing
        post.mark_as_processing()
        db_session.commit()
        
        assert post.status == "processing"
        assert not post.is_processed
        
        # Mark as processed
        post.mark_as_processed()
        db_session.commit()
        
        assert post.status == "processed"
        assert post.is_processed
        assert not post.is_published
        
        # Mark as published
        post.mark_as_published("https://ghost.example.com/post/1", "ghost_123")
        db_session.commit()
        
        assert post.status == "published"
        assert post.is_processed
        assert post.is_published
        assert post.ghost_url == "https://ghost.example.com/post/1"
        assert post.ghost_id == "ghost_123"
        assert post.published_at is not None
    
    def test_post_with_json_fields(self, db_session):
        """Test post with JSON fields"""
        pain_points = {
            "main_issues": ["slow loading", "poor UX"],
            "severity": "high",
            "frequency": "often"
        }
        
        product_ideas = {
            "suggestions": ["mobile app", "better search"],
            "priority": "medium",
            "feasibility": "high"
        }
        
        post = Post(
            id="json_test_1",
            title="JSON Test Post",
            subreddit="test",
            score=75,
            comments=15,
            created_ts=datetime.utcnow(),
            pain_points=pain_points,
            product_ideas=product_ideas
        )
        
        db_session.add(post)
        db_session.commit()
        
        retrieved_post = db_session.query(Post).filter_by(id="json_test_1").first()
        assert retrieved_post.pain_points == pain_points
        assert retrieved_post.product_ideas == product_ideas
        assert retrieved_post.pain_points["severity"] == "high"
        assert len(retrieved_post.product_ideas["suggestions"]) == 2
    
    def test_media_file_relationships(self, db_session):
        """Test media file relationships with posts"""
        # Create post
        post = Post(
            id="media_test_1",
            title="Media Test Post",
            subreddit="test",
            score=100,
            comments=20,
            created_ts=datetime.utcnow()
        )
        
        db_session.add(post)
        db_session.commit()
        
        # Create media files
        media_files = [
            MediaFile(
                post_id="media_test_1",
                original_url="https://reddit.com/image1.jpg",
                file_type="image/jpeg",
                file_size=1024000
            ),
            MediaFile(
                post_id="media_test_1",
                original_url="https://reddit.com/image2.png",
                file_type="image/png",
                file_size=512000
            )
        ]
        
        db_session.add_all(media_files)
        db_session.commit()
        
        # Test relationships
        retrieved_post = db_session.query(Post).filter_by(id="media_test_1").first()
        assert len(retrieved_post.media_files) == 2
        
        # Test media file properties
        image_file = retrieved_post.media_files[0]
        assert image_file.is_image
        assert not image_file.is_video
        assert image_file.filename == "image1.jpg"
        
        # Test processing media files
        image_file.mark_as_processed("https://ghost.example.com/content/images/image1.jpg")
        db_session.commit()
        
        assert image_file.is_processed
        assert image_file.ghost_url == "https://ghost.example.com/content/images/image1.jpg"
        assert image_file.processed_at is not None
    
    def test_processing_logs(self, db_session):
        """Test processing logs"""
        # Create post
        post = Post(
            id="log_test_1",
            title="Log Test Post",
            subreddit="test",
            score=100,
            comments=20,
            created_ts=datetime.utcnow()
        )
        
        db_session.add(post)
        db_session.commit()
        
        # Create processing logs
        logs = [
            ProcessingLog.create_success_log(
                post_id="log_test_1",
                service_name="collector",
                processing_time_ms=1500
            ),
            ProcessingLog.create_success_log(
                post_id="log_test_1",
                service_name="nlp_pipeline",
                processing_time_ms=5000
            ),
            ProcessingLog.create_failure_log(
                post_id="log_test_1",
                service_name="publisher",
                error_message="Ghost API timeout",
                processing_time_ms=10000
            )
        ]
        
        db_session.add_all(logs)
        db_session.commit()
        
        # Test relationships
        retrieved_post = db_session.query(Post).filter_by(id="log_test_1").first()
        assert len(retrieved_post.processing_logs) == 3
        
        # Test log properties
        success_logs = [log for log in retrieved_post.processing_logs if log.is_success]
        failure_logs = [log for log in retrieved_post.processing_logs if log.is_failure]
        
        assert len(success_logs) == 2
        assert len(failure_logs) == 1
        
        failure_log = failure_logs[0]
        assert failure_log.service_name == "publisher"
        assert failure_log.error_message == "Ghost API timeout"
        assert failure_log.processing_time_seconds == 10.0
    
    def test_token_usage_tracking(self, db_session):
        """Test token usage tracking"""
        # Create post
        post = Post(
            id="token_test_1",
            title="Token Test Post",
            subreddit="test",
            score=100,
            comments=20,
            created_ts=datetime.utcnow()
        )
        
        db_session.add(post)
        db_session.commit()
        
        # Create token usage records
        usage_records = [
            TokenUsage.create_openai_usage(
                post_id="token_test_1",
                input_tokens=1000,
                output_tokens=500
            ),
            TokenUsage.create_langsmith_usage(
                post_id="token_test_1",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=Decimal("0.01")
            )
        ]
        
        db_session.add_all(usage_records)
        db_session.commit()
        
        # Test relationships
        retrieved_post = db_session.query(Post).filter_by(id="token_test_1").first()
        assert len(retrieved_post.token_usage) == 2
        
        # Test usage calculations
        openai_usage = next(u for u in retrieved_post.token_usage if u.service == "openai")
        langsmith_usage = next(u for u in retrieved_post.token_usage if u.service == "langsmith")
        
        assert openai_usage.total_tokens == 1500
        assert openai_usage.cost_usd == Decimal("0.0075")  # Calculated cost
        
        assert langsmith_usage.total_tokens == 1500
        assert langsmith_usage.cost_usd == Decimal("0.01")  # Provided cost
    
    def test_complex_queries(self, db_session):
        """Test complex database queries"""
        # Create test data
        posts = []
        for i in range(10):
            post = Post(
                id=f"query_test_{i}",
                title=f"Query Test Post {i}",
                subreddit="technology" if i % 2 == 0 else "programming",
                score=100 + i * 10,
                comments=20 + i * 5,
                created_ts=datetime.utcnow() - timedelta(hours=i),
                status="published" if i < 5 else "processed"
            )
            posts.append(post)
        
        db_session.add_all(posts)
        db_session.commit()
        
        # Query 1: Get published posts from technology subreddit
        tech_published = db_session.query(Post).filter(
            Post.subreddit == "technology",
            Post.status == "published"
        ).all()
        
        assert len(tech_published) == 3  # Posts 0, 2, 4
        
        # Query 2: Get posts with score > 150
        high_score_posts = db_session.query(Post).filter(
            Post.score > 150
        ).order_by(Post.score.desc()).all()
        
        assert len(high_score_posts) == 4  # Posts 6-9 (score 160, 170, 180, 190)
        assert high_score_posts[0].score == 190  # Post 9
        
        # Query 3: Get recent posts (last 5 hours)
        recent_posts = db_session.query(Post).filter(
            Post.created_ts > datetime.utcnow() - timedelta(hours=5)
        ).all()
        
        assert len(recent_posts) == 5  # Posts 0-4
        
        # Query 4: Count posts by subreddit
        tech_count = db_session.query(Post).filter(Post.subreddit == "technology").count()
        prog_count = db_session.query(Post).filter(Post.subreddit == "programming").count()
        
        assert tech_count == 5
        assert prog_count == 5
    
    def test_transaction_rollback(self, db_session):
        """Test transaction rollback"""
        # Create initial post
        post = Post(
            id="rollback_test_1",
            title="Rollback Test Post",
            subreddit="test",
            score=100,
            comments=20,
            created_ts=datetime.utcnow()
        )
        
        db_session.add(post)
        db_session.commit()
        
        # Start transaction that will fail
        original_score = post.score
        try:
            post.score = 200
            
            # Force an error by trying to commit invalid data
            # Create a post with invalid data that will cause constraint violation
            duplicate_post = Post(
                id="rollback_test_1",  # Same ID as existing post
                title="Duplicate Post",
                subreddit="test",
                score=300,
                comments=30,
                created_ts=datetime.utcnow()
            )
            
            db_session.add(duplicate_post)
            db_session.commit()
            
        except Exception:
            db_session.rollback()
        
        # Verify rollback worked - check the original post wasn't updated
        retrieved_post = db_session.query(Post).filter_by(id="rollback_test_1").first()
        assert retrieved_post.score == original_score  # Should not be updated due to rollback
        
        media_count = db_session.query(MediaFile).filter_by(post_id="rollback_test_1").count()
        assert media_count == 0  # Should not be created
    
    def test_concurrent_access(self, db_engine):
        """Test concurrent database access"""
        # Create two separate sessions
        Session = sessionmaker(bind=db_engine)
        session1 = Session()
        session2 = Session()
        
        try:
            # Create post in session1
            post1 = Post(
                id="concurrent_test_1",
                title="Concurrent Test Post",
                subreddit="test",
                score=100,
                comments=20,
                created_ts=datetime.utcnow()
            )
            
            session1.add(post1)
            session1.commit()
            
            # Read from session2
            post2 = session2.query(Post).filter_by(id="concurrent_test_1").first()
            assert post2 is not None
            assert post2.title == "Concurrent Test Post"
            
            # Update from both sessions
            post1.score = 150
            post2.score = 200
            
            session1.commit()
            
            # Session2 commit should work (last writer wins in SQLite)
            session2.commit()
            
            # Verify final state
            final_post = session1.query(Post).filter_by(id="concurrent_test_1").first()
            assert final_post.score == 200
            
        finally:
            session1.close()
            session2.close()
    
    def test_database_constraints(self, db_session):
        """Test database constraints"""
        # Test unique constraint on post ID
        post1 = Post(
            id="constraint_test_1",
            title="First Post",
            subreddit="test",
            score=100,
            comments=20,
            created_ts=datetime.utcnow()
        )
        
        post2 = Post(
            id="constraint_test_1",  # Same ID
            title="Second Post",
            subreddit="test",
            score=200,
            comments=30,
            created_ts=datetime.utcnow()
        )
        
        db_session.add(post1)
        db_session.commit()
        
        # Adding second post with same ID should fail
        db_session.add(post2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()
        
        db_session.rollback()
        
        # Verify only first post exists
        posts = db_session.query(Post).filter_by(id="constraint_test_1").all()
        assert len(posts) == 1
        assert posts[0].title == "First Post"


if __name__ == "__main__":
    pytest.main([__file__])