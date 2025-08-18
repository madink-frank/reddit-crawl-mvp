"""
Token usage model for Reddit Ghost Publisher
"""
from typing import Optional
from decimal import Decimal
from uuid import UUID
from sqlalchemy import String, Integer, Text, ForeignKey, DECIMAL, Index
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel


class TokenUsage(BaseModel):
    """Token usage tracking for AI services"""
    
    __tablename__ = "token_usage"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to post
    post_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Service information
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Token usage
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 6), nullable=True)
    
    # Relationship
    post = relationship("Post", back_populates="token_usage")
    
    # Table constraints and indexes
    __table_args__ = (
        Index("idx_token_usage_post_id", "post_id"),
        Index("idx_token_usage_service", "service"),
        Index("idx_token_usage_created_at", "created_at"),
        Index("idx_token_usage_cost_usd", "cost_usd"),
    )
    
    def __repr__(self) -> str:
        return f"TokenUsage(id={self.id}, post_id={self.post_id!r}, service={self.service!r}, cost=${self.cost_usd})"
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens used (input + output)"""
        return self.input_tokens + self.output_tokens
    
    @property
    def cost_formatted(self) -> str:
        """Get formatted cost string"""
        if self.cost_usd is None:
            return "$0.00"
        return f"${self.cost_usd:.6f}"
    
    @classmethod
    def create_openai_usage(
        cls,
        post_id: UUID,
        model: str,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_token: Decimal = Decimal("0.0000025"),  # $2.50/M tokens for gpt-4o-mini
        output_cost_per_token: Decimal = Decimal("0.00001")    # $10/M tokens for gpt-4o-mini
    ) -> "TokenUsage":
        """Create OpenAI token usage record with cost calculation"""
        input_cost = Decimal(input_tokens) * input_cost_per_token
        output_cost = Decimal(output_tokens) * output_cost_per_token
        total_cost = input_cost + output_cost
        
        return cls(
            post_id=post_id,
            service="openai",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=total_cost
        )
    
    @classmethod
    def create_gpt4o_usage(
        cls,
        post_id: UUID,
        input_tokens: int,
        output_tokens: int,
        input_cost_per_token: Decimal = Decimal("0.000005"),   # $5/M tokens for gpt-4o
        output_cost_per_token: Decimal = Decimal("0.000015")   # $15/M tokens for gpt-4o
    ) -> "TokenUsage":
        """Create GPT-4o token usage record with cost calculation"""
        input_cost = Decimal(input_tokens) * input_cost_per_token
        output_cost = Decimal(output_tokens) * output_cost_per_token
        total_cost = input_cost + output_cost
        
        return cls(
            post_id=post_id,
            service="openai",
            model="gpt-4o",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=total_cost
        )
    
    def update_cost(self, cost_usd: Decimal) -> None:
        """Update the cost for this usage record"""
        self.cost_usd = cost_usd
    
    def validate_tokens(self) -> bool:
        """Validate that token counts are non-negative"""
        return self.input_tokens >= 0 and self.output_tokens >= 0
    
    def validate_cost(self) -> bool:
        """Validate that cost is non-negative if provided"""
        return self.cost_usd is None or self.cost_usd >= 0
    
    def validate(self) -> list[str]:
        """Validate the token usage model and return list of validation errors"""
        errors = []
        
        if not self.post_id:
            errors.append("Post ID is required")
        
        if not self.service:
            errors.append("Service is required")
        
        if not self.validate_tokens():
            errors.append("Token counts must be non-negative")
        
        if not self.validate_cost():
            errors.append("Cost must be non-negative if provided")
        
        return errors