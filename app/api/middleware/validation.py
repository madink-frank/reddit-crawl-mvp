"""
Input validation middleware for FastAPI with security enhancements
Comprehensive request validation and sanitization
"""
import json
import time
import logging
from typing import Dict, Any, Optional, List
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import ValidationError

from app.security import PIIMasker, mask_sensitive_data, log_reddit_api_usage
from app.logging_config import log_api_access, log_security_event
from app.api.validation import (
    validate_sql_injection,
    validate_xss_injection,
    sanitize_html_input,
    validate_reddit_compliance,
    validate_content_safety,
    mask_sensitive_fields
)

logger = logging.getLogger(__name__)


class SecurityValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for security validation and request sanitization"""
    
    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_request_size = max_request_size
        self.pii_masker = PIIMasker()
        
        # Rate limiting tracking (simple in-memory for MVP)
        self.request_counts: Dict[str, List[float]] = {}
        self.rate_limit_window = 60  # 1 minute window
        self.rate_limit_max_requests = 100  # Max requests per minute per IP
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security validation pipeline"""
        start_time = time.time()
        
        try:
            # Extract client info
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get('user-agent', 'unknown')
            
            # 1. Rate limiting check
            if not self._check_rate_limit(client_ip):
                log_security_event(
                    action='rate_limit_exceeded',
                    service='api',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={'endpoint': str(request.url.path)}
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
            
            # 2. Request size validation
            content_length = request.headers.get('content-length')
            if content_length and int(content_length) > self.max_request_size:
                log_security_event(
                    action='request_too_large',
                    service='api',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        'content_length': int(content_length),
                        'max_size': self.max_request_size
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request too large"
                )
            
            # 3. URL validation
            await self._validate_url_security(request, client_ip, user_agent)
            
            # 4. Header validation
            await self._validate_headers(request, client_ip, user_agent)
            
            # 5. Body validation (if present)
            if request.method in ['POST', 'PUT', 'PATCH']:
                await self._validate_request_body(request, client_ip, user_agent)
            
            # Process request
            response = await call_next(request)
            
            # Log successful request
            response_time = (time.time() - start_time) * 1000
            log_api_access(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                ip_address=client_ip,
                user_agent=user_agent,
                response_time_ms=response_time
            )
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Log unexpected errors
            logger.error(
                "Unexpected error in security validation middleware",
                error=str(e),
                endpoint=request.url.path,
                method=request.method,
                client_ip=client_ip
            )
            
            log_security_event(
                action='validation_error',
                service='api',
                ip_address=client_ip,
                user_agent=user_agent,
                details={
                    'error': str(e),
                    'endpoint': request.url.path
                },
                level=logging.ERROR
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (common in reverse proxy setups)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if hasattr(request.client, 'host'):
            return request.client.host
        
        return 'unknown'
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client IP is within rate limits"""
        current_time = time.time()
        
        # Clean old entries
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                req_time for req_time in self.request_counts[client_ip]
                if current_time - req_time < self.rate_limit_window
            ]
        else:
            self.request_counts[client_ip] = []
        
        # Check current count
        if len(self.request_counts[client_ip]) >= self.rate_limit_max_requests:
            return False
        
        # Add current request
        self.request_counts[client_ip].append(current_time)
        return True
    
    async def _validate_url_security(self, request: Request, client_ip: str, user_agent: str):
        """Validate URL for security issues"""
        url_path = request.url.path
        query_params = str(request.url.query) if request.url.query else ""
        
        # Check for path traversal attempts
        if '..' in url_path or '\\' in url_path:
            log_security_event(
                action='path_traversal_attempt',
                service='api',
                ip_address=client_ip,
                user_agent=user_agent,
                details={'url_path': url_path}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URL path"
            )
        
        # Check for SQL injection in query parameters
        if query_params:
            try:
                validate_sql_injection(query_params)
                validate_xss_injection(query_params)
            except ValueError as e:
                log_security_event(
                    action='malicious_query_params',
                    service='api',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        'query_params': mask_sensitive_data(query_params),
                        'error': str(e)
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid query parameters"
                )
        
        # Check for Reddit API compliance if Reddit-related endpoint
        if 'reddit' in url_path.lower():
            log_reddit_api_usage(url_path, request.method, user_agent)
    
    async def _validate_headers(self, request: Request, client_ip: str, user_agent: str):
        """Validate request headers for security issues"""
        dangerous_headers = [
            'x-forwarded-host',
            'x-forwarded-server',
            'x-forwarded-proto'
        ]
        
        for header_name, header_value in request.headers.items():
            # Check for injection attempts in headers
            try:
                validate_sql_injection(header_value)
                validate_xss_injection(header_value)
            except ValueError as e:
                log_security_event(
                    action='malicious_header',
                    service='api',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        'header_name': header_name,
                        'header_value': mask_sensitive_data(header_value),
                        'error': str(e)
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request headers"
                )
            
            # Check for dangerous forwarded headers (potential host header injection)
            if header_name.lower() in dangerous_headers:
                log_security_event(
                    action='suspicious_header',
                    service='api',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        'header_name': header_name,
                        'header_value': mask_sensitive_data(header_value)
                    }
                )
        
        # Validate User-Agent for Reddit API compliance
        if user_agent and user_agent != 'unknown':
            # Check if this looks like a bot or scraper
            bot_indicators = [
                'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
                'python-requests', 'urllib', 'scrapy'
            ]
            
            user_agent_lower = user_agent.lower()
            if any(indicator in user_agent_lower for indicator in bot_indicators):
                # Allow legitimate bots but log for monitoring
                log_security_event(
                    action='bot_user_agent',
                    service='api',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={'user_agent': user_agent}
                )
    
    async def _validate_request_body(self, request: Request, client_ip: str, user_agent: str):
        """Validate request body for security issues"""
        try:
            # Read body
            body = await request.body()
            if not body:
                return
            
            # Try to parse as JSON
            content_type = request.headers.get('content-type', '').lower()
            
            if 'application/json' in content_type:
                try:
                    json_data = json.loads(body.decode('utf-8'))
                    await self._validate_json_data(json_data, client_ip, user_agent)
                except json.JSONDecodeError:
                    log_security_event(
                        action='invalid_json',
                        service='api',
                        ip_address=client_ip,
                        user_agent=user_agent,
                        details={'content_type': content_type}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid JSON format"
                    )
            
            elif 'application/x-www-form-urlencoded' in content_type:
                # Validate form data
                form_data = body.decode('utf-8')
                try:
                    validate_sql_injection(form_data)
                    validate_xss_injection(form_data)
                except ValueError as e:
                    log_security_event(
                        action='malicious_form_data',
                        service='api',
                        ip_address=client_ip,
                        user_agent=user_agent,
                        details={'error': str(e)}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid form data"
                    )
            
            elif 'multipart/form-data' in content_type:
                # Basic validation for multipart data
                body_str = body.decode('utf-8', errors='ignore')
                if len(body_str) > 1000:  # Only check first 1000 chars for performance
                    body_str = body_str[:1000]
                
                try:
                    validate_xss_injection(body_str)
                except ValueError as e:
                    log_security_event(
                        action='malicious_multipart_data',
                        service='api',
                        ip_address=client_ip,
                        user_agent=user_agent,
                        details={'error': str(e)}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid multipart data"
                    )
            
        except UnicodeDecodeError:
            log_security_event(
                action='invalid_encoding',
                service='api',
                ip_address=client_ip,
                user_agent=user_agent,
                details={'content_type': request.headers.get('content-type')}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request encoding"
            )
    
    async def _validate_json_data(self, data: Any, client_ip: str, user_agent: str):
        """Recursively validate JSON data for security issues"""
        if isinstance(data, dict):
            for key, value in data.items():
                # Validate key
                if isinstance(key, str):
                    try:
                        validate_sql_injection(key)
                        validate_xss_injection(key)
                    except ValueError as e:
                        log_security_event(
                            action='malicious_json_key',
                            service='api',
                            ip_address=client_ip,
                            user_agent=user_agent,
                            details={
                                'key': mask_sensitive_data(key),
                                'error': str(e)
                            }
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid JSON key"
                        )
                
                # Recursively validate value
                await self._validate_json_data(value, client_ip, user_agent)
        
        elif isinstance(data, list):
            for item in data:
                await self._validate_json_data(item, client_ip, user_agent)
        
        elif isinstance(data, str):
            try:
                validate_sql_injection(data)
                validate_xss_injection(data)
                
                # Additional content safety checks
                if len(data) > 100:  # Only check longer strings for performance
                    validate_content_safety(data)
                
            except ValueError as e:
                log_security_event(
                    action='malicious_json_value',
                    service='api',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    details={
                        'value': mask_sensitive_data(data[:100]),  # Only log first 100 chars
                        'error': str(e)
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON value"
                )


class ValidationErrorHandler:
    """Custom validation error handler for Pydantic validation errors"""
    
    @staticmethod
    def create_error_response(exc: ValidationError) -> JSONResponse:
        """Create standardized error response for validation errors"""
        errors = []
        
        for error in exc.errors():
            # Mask sensitive data in error messages
            error_msg = mask_sensitive_data(str(error.get('msg', 'Validation error')))
            
            errors.append({
                'field': '.'.join(str(loc) for loc in error.get('loc', [])),
                'message': error_msg,
                'type': error.get('type', 'validation_error'),
                'input': mask_sensitive_data(str(error.get('input', '')))[:100]  # Limit length
            })
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                'error': 'Validation failed',
                'details': errors,
                'timestamp': time.time()
            }
        )


# Utility functions for manual validation
def validate_request_data(data: Dict[str, Any], client_ip: str = 'unknown') -> Dict[str, Any]:
    """Manually validate request data outside of middleware"""
    try:
        # Apply all security validations
        validated_data = {}
        
        for key, value in data.items():
            # Validate key
            if isinstance(key, str):
                validate_sql_injection(key)
                validate_xss_injection(key)
            
            # Validate and sanitize value
            if isinstance(value, str):
                validate_sql_injection(value)
                validate_xss_injection(value)
                validated_data[key] = sanitize_html_input(value)
            elif isinstance(value, dict):
                validated_data[key] = validate_request_data(value, client_ip)
            elif isinstance(value, list):
                validated_data[key] = [
                    validate_request_data(item, client_ip) if isinstance(item, dict)
                    else sanitize_html_input(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                validated_data[key] = value
        
        return validated_data
        
    except ValueError as e:
        log_security_event(
            action='manual_validation_failed',
            service='api',
            ip_address=client_ip,
            details={'error': str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {str(e)}"
        )


def sanitize_response_data(data: Any) -> Any:
    """Sanitize response data to prevent information leakage"""
    if isinstance(data, dict):
        return {
            key: sanitize_response_data(value)
            for key, value in data.items()
            if not key.startswith('_') and key not in ['password', 'secret', 'token', 'key']
        }
    elif isinstance(data, list):
        return [sanitize_response_data(item) for item in data]
    elif isinstance(data, str):
        return mask_sensitive_data(data)
    else:
        return data