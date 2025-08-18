"""
API Key model for authentication
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text

from app.models.base import Base


class APIKey(Base):
    """API Key model for authentication"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    key_prefix = Column(String(10), nullable=False)  # First 8 chars for identification
    role = Column(String(50), nullable=False, default="viewer")
    status = Column(String(20), nullable=False, default="active")
    
    # Metadata
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    
    # Permissions and restrictions
    allowed_ips = Column(Text, nullable=True)  # JSON array of allowed IPs
    rate_limit_override = Column(Integer, nullable=True)  # Custom rate limit
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, role={self.role}, status={self.status})>"