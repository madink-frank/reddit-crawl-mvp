"""
Security middleware for headers, CORS, CSRF protection, and general security
"""
import time
import secrets
import hashlib
import re
from typing import Dict, List, Optional

import structlog
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.redis_client import get_redis


logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        security_headers = {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Enable XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),
            
            # Permissions Policy
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            ),
        }
        
        # Add HSTS in production
        if not self.settings.debug:
            security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Apply headers
        for header, value in security_headers.items():
            response.headers[header] = value
        
        # Add server header
        response.headers["Server"] = "Reddit-Ghost-Publisher/1.0"
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate and sanitize incoming requests"""
    
    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_request_size = max_request_size
    
    async def dispatch(self, request: Request, call_next):
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_request_size:
            logger.warning(
                "Request too large",
                content_length=content_length,
                max_size=self.max_request_size,
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown"
            )
            return Response(
                content="Request entity too large",
                status_code=413,
                headers={"Content-Type": "text/plain"}
            )
        
        # Validate request method
        allowed_methods = {"GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"}
        if request.method not in allowed_methods:
            logger.warning(
                "Invalid request method",
                method=request.method,
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown"
            )
            return Response(
                content="Method not allowed",
                status_code=405,
                headers={"Content-Type": "text/plain"}
            )
        
        # Check for suspicious patterns in URL
        suspicious_patterns = [
            "../", "..\\", "<script", "javascript:", "vbscript:",
            "onload=", "onerror=", "eval(", "expression("
        ]
        
        url_path = str(request.url.path).lower()
        query_string = str(request.url.query).lower()
        
        for pattern in suspicious_patterns:
            if pattern in url_path or pattern in query_string:
                logger.warning(
                    "Suspicious request pattern detected",
                    pattern=pattern,
                    path=request.url.path,
                    query=request.url.query,
                    client_ip=request.client.host if request.client else "unknown"
                )
                return Response(
                    content="Bad request",
                    status_code=400,
                    headers={"Content-Type": "text/plain"}
                )
        
        return await call_next(request)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """IP whitelist middleware for admin endpoints"""
    
    def __init__(self, app, whitelist: List[str] = None, protected_paths: List[str] = None):
        super().__init__(app)
        self.whitelist = set(whitelist or ["127.0.0.1", "::1", "localhost"])
        self.protected_paths = protected_paths or ["/api/v1/admin/"]
    
    async def dispatch(self, request: Request, call_next):
        # Check if path requires IP whitelisting
        if not any(request.url.path.startswith(path) for path in self.protected_paths):
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check whitelist
        if client_ip not in self.whitelist:
            logger.warning(
                "IP not whitelisted for admin access",
                client_ip=client_ip,
                path=request.url.path,
                user_agent=request.headers.get("user-agent", "")
            )
            return Response(
                content="Access denied",
                status_code=403,
                headers={"Content-Type": "text/plain"}
            )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check X-Forwarded-For header (from proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header (from Nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Request timeout middleware"""
    
    def __init__(self, app, timeout_seconds: int = 30):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
    
    async def dispatch(self, request: Request, call_next):
        import asyncio
        
        try:
            # Set timeout for request processing
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
            return response
            
        except asyncio.TimeoutError:
            logger.warning(
                "Request timeout",
                timeout=self.timeout_seconds,
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else "unknown"
            )
            return Response(
                content="Request timeout",
                status_code=408,
                headers={"Content-Type": "text/plain"}
            )


def get_cors_settings() -> Dict[str, any]:
    """Get CORS settings based on environment"""
    settings = get_settings()
    
    if settings.debug:
        # Development settings - more permissive
        return {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
            "expose_headers": ["X-Request-ID", "X-Response-Time"],
        }
    else:
        # Production settings - restrictive
        return {
            "allow_origins": [
                "https://example.com",
                "https://www.example.com",
                "https://admin.example.com"
            ],
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": [
                "Accept",
                "Accept-Language",
                "Content-Language",
                "Content-Type",
                "Authorization",
                "X-Request-ID"
            ],
            "expose_headers": ["X-Request-ID", "X-Response-Time"],
            "max_age": 600,  # 10 minutes
        }


def get_trusted_hosts() -> List[str]:
    """Get trusted hosts based on environment"""
    settings = get_settings()
    
    if settings.debug:
        return ["*"]
    else:
        return [
            "localhost",
            "127.0.0.1",
            "api.example.com",
            "admin.example.com"
        ]


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware"""
    
    def __init__(self, app, secret_key: str = None):
        super().__init__(app)
        self.secret_key = secret_key or get_settings().jwt_secret_key
        self.safe_methods = {"GET", "HEAD", "OPTIONS", "TRACE"}
    
    async def dispatch(self, request: Request, call_next):
        # Skip CSRF protection for safe methods and API endpoints using API keys
        if (request.method in self.safe_methods or 
            request.url.path.startswith("/api/") or
            request.url.path in ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]):
            return await call_next(request)
        
        # Check for CSRF token
        csrf_token = self._get_csrf_token(request)
        if not csrf_token:
            logger.warning(
                "Missing CSRF token",
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "CSRF token missing"}
            )
        
        # Validate CSRF token
        if not self._validate_csrf_token(csrf_token, request):
            logger.warning(
                "Invalid CSRF token",
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "CSRF token invalid"}
            )
        
        return await call_next(request)
    
    def _get_csrf_token(self, request: Request) -> Optional[str]:
        """Extract CSRF token from request"""
        # Try header first
        token = request.headers.get("X-CSRF-Token")
        if token:
            return token
        
        # Try form data (for multipart/form-data)
        if hasattr(request, '_form'):
            form_data = getattr(request, '_form', {})
            return form_data.get("csrf_token")
        
        return None
    
    def _validate_csrf_token(self, token: str, request: Request) -> bool:
        """Validate CSRF token"""
        try:
            # Simple HMAC-based validation
            expected_token = self._generate_csrf_token(request)
            return secrets.compare_digest(token, expected_token)
        except Exception as e:
            logger.error("CSRF token validation error", error=str(e))
            return False
    
    def _generate_csrf_token(self, request: Request) -> str:
        """Generate CSRF token for session"""
        # Use session ID or user ID if available
        session_id = getattr(request.state, 'session_id', 'anonymous')
        if hasattr(request.state, 'user') and request.state.user:
            session_id = request.state.user.get('sub', session_id)
        
        # Create HMAC-based token
        message = f"{session_id}:{request.client.host if request.client else 'unknown'}"
        token = hashlib.pbkdf2_hmac('sha256', 
                                   message.encode(), 
                                   self.secret_key.encode(), 
                                   100000)
        return token.hex()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis with sliding window"""
    
    def __init__(self, app, requests_per_minute: int = 100, burst_limit: int = 20):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/health/ready", "/health/live", "/metrics"]:
            return await call_next(request)
        
        # Get client identifier and rate limit
        client_id = self._get_client_id(request)
        rate_limit = self._get_rate_limit(request)
        
        # Check rate limit
        try:
            remaining, reset_time = await self._check_rate_limit(client_id, rate_limit)
            
            if remaining < 0:
                logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    path=request.url.path,
                    method=request.method,
                    rate_limit=rate_limit
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {rate_limit} requests per minute allowed"
                    },
                    headers={
                        "Retry-After": str(int(reset_time - time.time())),
                        "X-RateLimit-Limit": str(rate_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(reset_time))
                    }
                )
            
            # Add rate limit headers to successful responses
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(reset_time))
            
            return response
            
        except Exception as e:
            logger.error("Rate limiting error", error=str(e))
            # Continue without rate limiting if Redis is down
            return await call_next(request)
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get authenticated user ID first
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.get('sub')
            if user_id:
                return f"user:{user_id}"
        
        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _get_rate_limit(self, request: Request) -> int:
        """Get rate limit for request (may be overridden by API key)"""
        # Check if user has custom rate limit (from API key)
        if hasattr(request.state, 'user') and request.state.user:
            rate_limit_override = request.state.user.get('rate_limit_override')
            if rate_limit_override:
                return rate_limit_override
        
        return self.requests_per_minute
    
    async def _check_rate_limit(self, client_id: str, rate_limit: int) -> tuple[int, float]:
        """Check rate limit using sliding window algorithm"""
        async with get_redis() as redis:
            current_time = time.time()
            window_start = current_time - 60  # 1 minute window
            
            # Use sliding window rate limiting with Redis sorted sets
            pipe = redis.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(f"rate_limit:{client_id}", 0, window_start)
            
            # Count current requests
            pipe.zcard(f"rate_limit:{client_id}")
            
            # Add current request
            pipe.zadd(f"rate_limit:{client_id}", {str(current_time): current_time})
            
            # Set expiry
            pipe.expire(f"rate_limit:{client_id}", 120)  # 2 minutes
            
            results = pipe.execute()
            current_requests = results[1]
            
            remaining = rate_limit - current_requests - 1  # -1 for current request
            reset_time = current_time + 60  # Reset in 1 minute
            
            return remaining, reset_time


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware to sanitize input data"""
    
    async def dispatch(self, request: Request, call_next):
        # Only process POST, PUT, PATCH requests with JSON content
        if (request.method in ["POST", "PUT", "PATCH"] and 
            request.headers.get("content-type", "").startswith("application/json")):
            
            try:
                # Read and sanitize request body
                body = await request.body()
                if body:
                    import json
                    from app.api.validation import validate_json_input
                    
                    # Parse and sanitize JSON
                    data = json.loads(body.decode())
                    sanitized_data = validate_json_input(data)
                    
                    # Replace request body with sanitized data
                    sanitized_body = json.dumps(sanitized_data).encode()
                    
                    # Create new request with sanitized body
                    async def receive():
                        return {"type": "http.request", "body": sanitized_body}
                    
                    request._receive = receive
                    
            except Exception as e:
                logger.warning("Input sanitization failed", error=str(e))
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Invalid input data"}
                )
        
        return await call_next(request)


class SQLInjectionProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware to detect and prevent SQL injection attempts"""
    
    def __init__(self, app):
        super().__init__(app)
        # Common SQL injection patterns
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
            r"(--|#|/\*|\*/)",
            r"(\bxp_|\bsp_)",
            r"(\bCAST\s*\(|\bCONVERT\s*\()",
            r"(\bUNION\s+SELECT)",
            r"(\bINTO\s+OUTFILE)",
            r"(\bLOAD_FILE\s*\()",
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Check query parameters
        for key, value in request.query_params.items():
            if self._contains_sql_injection(value):
                logger.warning(
                    "SQL injection attempt detected in query params",
                    param=key,
                    value=value[:100],
                    client_ip=request.client.host if request.client else "unknown"
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Invalid request parameters"}
                )
        
        # Check path parameters
        if self._contains_sql_injection(str(request.url.path)):
            logger.warning(
                "SQL injection attempt detected in path",
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid request path"}
            )
        
        return await call_next(request)
    
    def _contains_sql_injection(self, value: str) -> bool:
        """Check if value contains SQL injection patterns"""
        if not isinstance(value, str):
            return False
        
        for pattern in self.sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        
        return False


def setup_cors_middleware(app):
    """Setup CORS middleware with secure defaults"""
    settings = get_settings()
    
    # Allow origins based on environment
    if settings.environment == "development":
        allowed_origins = [
            "http://localhost:3000", 
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000"
        ]
    else:
        # In production, specify exact origins
        allowed_origins = [
            "https://yourdomain.com",
            "https://api.yourdomain.com",
            "https://admin.yourdomain.com"
        ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language", 
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-CSRF-Token",
            "X-Requested-With"
        ],
        expose_headers=[
            "X-RateLimit-Limit", 
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-CSRF-Token"
        ]
    )