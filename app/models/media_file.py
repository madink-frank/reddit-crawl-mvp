"""
Media file model for Reddit Ghost Publisher
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class MediaFile(BaseModel):
    """Media file associated with Reddit posts"""
    
    __tablename__ = "media_files"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to post
    post_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), 
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Media file information
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    ghost_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationship
    post = relationship("Post", back_populates="media_files")
    
    # Table constraints and indexes
    __table_args__ = (
        Index("idx_media_files_post_id", "post_id"),
        Index("idx_media_files_processed_at", "processed_at"),
        Index("idx_media_files_file_type", "file_type"),
    )
    
    def __repr__(self) -> str:
        return f"MediaFile(id={self.id}, post_id={self.post_id!r}, file_type={self.file_type!r})"
    
    @property
    def is_processed(self) -> bool:
        """Check if media file has been processed and uploaded to Ghost"""
        return self.ghost_url is not None and self.processed_at is not None
    
    def mark_as_processed(self, ghost_url: str) -> None:
        """Mark media file as processed and uploaded to Ghost"""
        self.ghost_url = ghost_url
        self.processed_at = datetime.utcnow()
    
    @property
    def filename(self) -> Optional[str]:
        """Extract filename from original URL"""
        if not self.original_url:
            return None
        return self.original_url.split("/")[-1].split("?")[0]
    
    @property
    def is_image(self) -> bool:
        """Check if file is an image"""
        if not self.file_type:
            return False
        return self.file_type.lower().startswith("image/")
    
    @property
    def is_video(self) -> bool:
        """Check if file is a video"""
        if not self.file_type:
            return False
        return self.file_type.lower().startswith("video/")
    
    def validate_file_size(self) -> bool:
        """Validate that file size is positive if provided"""
        return self.file_size is None or self.file_size > 0
    
    def validate_urls(self) -> bool:
        """Validate that original URL is provided"""
        return bool(self.original_url and self.original_url.strip())
    
    def validate(self) -> list[str]:
        """Validate the media file model and return list of validation errors"""
        errors = []
        
        if not self.post_id:
            errors.append("Post ID is required")
        
        if not self.validate_urls():
            errors.append("Original URL is required")
        
        if not self.validate_file_size():
            errors.append("File size must be positive if provided")
        
        return errors