"""
Post model for Reddit Ghost Publisher
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import String, Integer, Text, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import BaseModel


class Post(BaseModel):
    """Reddit post model with AI processing results"""
    
    __tablename__ = "posts"
    
    # Primary key - UUID
    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), 
        primary_key=True, 
        server_default=func.uuid_generate_v4()
    )
    
    # Reddit post identifier (unique)
    reddit_post_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    
    # Basic Reddit post information
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subreddit: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    num_comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_ts: Mapped[datetime] = mapped_column(nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selftext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Processing status
    status: Mapped[str] = mapped_column(
        String(20), 
        default="collected", 
        nullable=False
    )
    
    # Takedown status for compliance
    takedown_status: Mapped[str] = mapped_column(
        Text,
        default="active",
        nullable=False
    )
    
    # AI processing results
    summary_ko: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    pain_points: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    product_ideas: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Ghost publishing information
    ghost_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ghost_post_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)
    ghost_slug: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Metadata
    content_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    media_files = relationship("MediaFile", back_populates="post", cascade="all, delete-orphan")
    processing_logs = relationship("ProcessingLog", back_populates="post", cascade="all, delete-orphan")
    token_usage = relationship("TokenUsage", back_populates="post", cascade="all, delete-orphan")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('collected', 'processing', 'processed', 'published', 'failed')",
            name="check_post_status"
        ),
        CheckConstraint(
            "takedown_status IN ('active', 'takedown_pending', 'removed')",
            name="check_takedown_status"
        ),
        CheckConstraint(
            "score >= 0",
            name="check_post_score_positive"
        ),
        CheckConstraint(
            "num_comments >= 0", 
            name="check_post_comments_positive"
        ),
        CheckConstraint(
            "processing_attempts >= 0",
            name="check_processing_attempts_positive"
        ),
        # Unique constraints
        UniqueConstraint("reddit_post_id", name="uq_posts_reddit_post_id"),
        UniqueConstraint("ghost_post_id", name="uq_posts_ghost_post_id"),
        # Indexes
        Index("idx_posts_status", "status"),
        Index("idx_posts_created_ts", "created_ts"),
        Index("idx_posts_subreddit", "subreddit"),
        Index("idx_posts_score", "score"),
        Index("idx_posts_published_at", "published_at"),
        Index("idx_posts_takedown_status", "takedown_status"),
    )
    
    def __repr__(self) -> str:
        return f"Post(id={self.id!r}, reddit_post_id={self.reddit_post_id!r}, title={self.title[:50]!r}, subreddit={self.subreddit!r}, status={self.status!r})"
    
    @property
    def is_processed(self) -> bool:
        """Check if post has been processed by AI"""
        return self.status in ("processed", "published")
    
    @property
    def is_published(self) -> bool:
        """Check if post has been published to Ghost"""
        return self.status == "published" and self.ghost_url is not None
    
    @property
    def is_takedown_pending(self) -> bool:
        """Check if post is pending takedown"""
        return self.takedown_status == "takedown_pending"
    
    @property
    def is_removed(self) -> bool:
        """Check if post has been removed"""
        return self.takedown_status == "removed"
    
    def increment_processing_attempts(self) -> None:
        """Increment processing attempts counter"""
        self.processing_attempts += 1
    
    def mark_as_processing(self) -> None:
        """Mark post as currently being processed"""
        self.status = "processing"
    
    def mark_as_processed(self) -> None:
        """Mark post as successfully processed"""
        self.status = "processed"
    
    def mark_as_published(self, ghost_url: str, ghost_post_id: str, ghost_slug: str) -> None:
        """Mark post as successfully published to Ghost"""
        self.status = "published"
        self.ghost_url = ghost_url
        self.ghost_post_id = ghost_post_id
        self.ghost_slug = ghost_slug
        self.published_at = func.now()
    
    def mark_as_failed(self) -> None:
        """Mark post as failed processing"""
        self.status = "failed"
    
    def mark_takedown_pending(self) -> None:
        """Mark post as pending takedown"""
        self.takedown_status = "takedown_pending"
    
    def mark_as_removed(self) -> None:
        """Mark post as removed"""
        self.takedown_status = "removed"
    
    def validate_score(self) -> bool:
        """Validate that score is non-negative"""
        return self.score >= 0
    
    def validate_comments(self) -> bool:
        """Validate that comments count is non-negative"""
        return self.num_comments >= 0
    
    def validate_status(self) -> bool:
        """Validate that status is one of allowed values"""
        allowed_statuses = {"collected", "processing", "processed", "published", "failed"}
        return self.status in allowed_statuses
    
    def validate_takedown_status(self) -> bool:
        """Validate that takedown_status is one of allowed values"""
        allowed_statuses = {"active", "takedown_pending", "removed"}
        return self.takedown_status in allowed_statuses
    
    def is_takedown_in_progress(self) -> bool:
        """Check if takedown is currently in progress"""
        return self.takedown_status == "takedown_pending"
    
    def validate_processing_attempts(self) -> bool:
        """Validate that processing attempts is non-negative"""
        return self.processing_attempts is not None and self.processing_attempts >= 0
    
    def validate_tags(self) -> bool:
        """Validate that tags is a list with 3-5 items if provided"""
        if self.tags is None:
            return True
        if not isinstance(self.tags, list):
            return False
        return 3 <= len(self.tags) <= 5
    
    def validate(self) -> list[str]:
        """Validate the post model and return list of validation errors"""
        errors = []
        
        if not self.reddit_post_id:
            errors.append("Reddit post ID is required")
        
        if not self.title:
            errors.append("Post title is required")
        
        if not self.subreddit:
            errors.append("Subreddit is required")
        
        if not self.validate_score():
            errors.append("Score must be non-negative")
        
        if not self.validate_comments():
            errors.append("Comments count must be non-negative")
        
        if not self.validate_status():
            errors.append("Status must be one of: collected, processing, processed, published, failed")
        
        if not self.validate_takedown_status():
            errors.append("Takedown status must be one of: active, takedown_pending, removed")
        
        if not self.validate_processing_attempts():
            errors.append("Processing attempts must be non-negative")
        
        if not self.validate_tags():
            errors.append("Tags must be a list with 3-5 items if provided")
        
        return errors