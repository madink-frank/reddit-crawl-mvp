"""
Basic security middleware for MVP
Simplified security implementation without JWT/Vault
"""
import re
from typing import List, Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add basic security headers"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Disable CSP for dashboard functionality in production
        # response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        # Remove server header
        if "server" in response.headers:
            del response.headers["server"]
            
        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Basic input validation and sanitization"""
    
    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_request_size = max_request_size
    
    async def dispatch(self, request: Request, call_next):
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request too large"
            )
        
        # Basic SQL injection protection in query parameters
        query_string = str(request.query_params)
        if self._contains_sql_injection(query_string):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request parameters"
            )
        
        return await call_next(request)
    
    def _contains_sql_injection(self, text: str) -> bool:
        """Basic SQL injection detection"""
        sql_patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
            r"(--|#|/\*|\*/)",
            r"(\b(or|and)\s+\d+\s*=\s*\d+)",
            r"(\b(or|and)\s+['\"].*['\"])",
        ]
        
        text_lower = text.lower()
        for pattern in sql_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False


class EnvironmentAuthMiddleware(BaseHTTPMiddleware):
    """Environment variable-based authentication for MVP"""
    
    def __init__(self, app, protected_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/api/v1/"]
        self.settings = get_settings()
        
        # Simple API key from environment (for MVP)
        self.api_key = self.settings.api_key or self.settings.jwt_secret_key  # Use API key or fallback to JWT secret
    
    async def dispatch(self, request: Request, call_next):
        # Check if path requires authentication
        path = request.url.path
        requires_auth = any(path.startswith(protected) for protected in self.protected_paths)
        
        # Skip auth for health checks and public endpoints
        if path in ["/health", "/health/ready", "/health/live", "/docs", "/openapi.json"]:
            requires_auth = False
        
        if requires_auth:
            # Check for API key in header
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key != self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing API key",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        return await call_next(request)


def setup_cors_middleware(app):
    """Setup CORS middleware with enhanced Ghost dashboard integration"""
    from fastapi.middleware.cors import CORSMiddleware
    
    settings = get_settings()
    
    # Enhanced CORS settings for Ghost dashboard integration
    allowed_origins = [
        "https://american-trends.ghost.io",
        "https://www.american-trends.ghost.io",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8083",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8083"
    ]
    
    # Add wildcard for development
    if settings.debug:
        allowed_origins.append("*")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Requested-With",
            "X-CSRF-Token",
            "Cache-Control"
        ],
        expose_headers=["X-Total-Count", "X-Page-Count", "X-Rate-Limit", "X-Rate-Limit-Remaining"],
        max_age=86400  # 24 hours
    )


# Pydantic models for input validation
from pydantic import BaseModel, Field, validator
from typing import Optional, List


class TriggerRequest(BaseModel):
    """Request model for manual triggers"""
    subreddits: Optional[List[str]] = Field(None, description="List of subreddits to process")
    batch_size: Optional[int] = Field(None, ge=1, le=100, description="Number of posts to process")
    force: Optional[bool] = Field(False, description="Force processing even if recently processed")
    
    @validator('subreddits')
    def validate_subreddits(cls, v):
        if v:
            # Basic validation for subreddit names
            for subreddit in v:
                if not re.match(r'^[a-zA-Z0-9_]{1,21}$', subreddit):
                    raise ValueError(f"Invalid subreddit name: {subreddit}")
        return v


class TakedownRequest(BaseModel):
    """Request model for takedown requests"""
    reason: str = Field(..., min_length=10, max_length=500, description="Reason for takedown")
    contact_email: Optional[str] = Field(None, description="Contact email for follow-up")
    
    @validator('contact_email')
    def validate_email(cls, v):
        if v:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError("Invalid email format")
        return v


class StatusResponse(BaseModel):
    """Response model for status endpoints"""
    status: str
    timestamp: str
    data: dict


class QueueStatusResponse(BaseModel):
    """Response model for queue status"""
    queue_name: str
    active: int
    pending: int
    scheduled: int
    failed: int


class WorkerStatusResponse(BaseModel):
    """Response model for worker status"""
    worker_name: str
    status: str
    active_tasks: int
    processed_tasks: int
    last_heartbeat: str