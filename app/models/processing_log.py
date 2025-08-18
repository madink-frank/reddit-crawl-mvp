"""
Processing log model for Reddit Ghost Publisher
"""
from typing import Optional
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class ProcessingLog(BaseModel):
    """Log entries for post processing activities"""
    
    __tablename__ = "processing_logs"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to post
    post_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Processing information
    service_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Relationship
    post = relationship("Post", back_populates="processing_logs")
    
    # Table constraints and indexes
    __table_args__ = (
        Index("idx_processing_logs_post_id", "post_id"),
        Index("idx_processing_logs_service_name", "service_name"),
        Index("idx_processing_logs_status", "status"),
        Index("idx_processing_logs_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"ProcessingLog(id={self.id}, post_id={self.post_id!r}, service={self.service_name!r}, status={self.status!r})"
    
    @property
    def is_success(self) -> bool:
        """Check if processing was successful"""
        return self.status.lower() in ("success", "completed", "processed")
    
    @property
    def is_failure(self) -> bool:
        """Check if processing failed"""
        return self.status.lower() in ("failed", "error", "exception")
    
    @property
    def processing_time_seconds(self) -> Optional[float]:
        """Get processing time in seconds"""
        if self.processing_time_ms is None:
            return None
        return self.processing_time_ms / 1000.0
    
    @classmethod
    def create_success_log(
        cls, 
        post_id: str, 
        service_name: str, 
        processing_time_ms: Optional[int] = None
    ) -> "ProcessingLog":
        """Create a success log entry"""
        return cls(
            post_id=post_id,
            service_name=service_name,
            status="success",
            processing_time_ms=processing_time_ms
        )
    
    @classmethod
    def create_failure_log(
        cls,
        post_id: str,
        service_name: str,
        error_message: str,
        processing_time_ms: Optional[int] = None
    ) -> "ProcessingLog":
        """Create a failure log entry"""
        return cls(
            post_id=post_id,
            service_name=service_name,
            status="failed",
            error_message=error_message,
            processing_time_ms=processing_time_ms
        )
    
    def validate_processing_time(self) -> bool:
        """Validate that processing time is positive if provided"""
        return self.processing_time_ms is None or self.processing_time_ms > 0
    
    def validate(self) -> list[str]:
        """Validate the processing log model and return list of validation errors"""
        errors = []
        
        if not self.post_id:
            errors.append("Post ID is required")
        
        if not self.service_name:
            errors.append("Service name is required")
        
        if not self.status:
            errors.append("Status is required")
        
        if not self.validate_processing_time():
            errors.append("Processing time must be positive if provided")
        
        return errors