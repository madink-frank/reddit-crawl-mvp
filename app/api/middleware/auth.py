"""
Authentication and authorization middleware
JWT token verification and role-based access control
"""
import time
from typing import Optional, List, Dict, Any

import jwt
import structlog
from fastapi import HTTPException, Request, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.infrastructure import get_db


logger = structlog.get_logger(__name__)

# JWT Security scheme
security = HTTPBearer(auto_error=False)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication Middleware supporting JWT and API keys"""
    
    def __init__(self, app, protected_paths: List[str] = None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/api/v1/"]
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next):
        # Check if path requires authentication
        if not self._requires_auth(request.url.path):
            return await call_next(request)
        
        # Try to authenticate with JWT or API key
        try:
            user_info = await self._authenticate_request(request)
            
            # Add user info to request state
            request.state.user = user_info
            request.state.authenticated = True
            
            logger.info(
                "User authenticated",
                user_id=user_info.get("sub"),
                auth_type=user_info.get("auth_type", "jwt"),
                path=request.url.path,
                method=request.method
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Authentication error",
                error=str(e),
                path=request.url.path,
                method=request.method
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return await call_next(request)
    
    async def _authenticate_request(self, request: Request) -> Dict[str, Any]:
        """Authenticate request using JWT or API key"""
        # Try JWT authentication first
        jwt_token = self._extract_jwt_token(request)
        if jwt_token:
            payload = self._verify_jwt_token(jwt_token)
            payload["auth_type"] = "jwt"
            return payload
        
        # Try API key authentication
        api_key = self._extract_api_key(request)
        if api_key:
            return await self._verify_api_key(api_key, request)
        
        # No authentication method found
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token or API key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    async def _verify_api_key(self, api_key: str, request: Request) -> Dict[str, Any]:
        """Verify API key and return user info"""
        from app.api.auth import get_api_key_manager
        from app.infrastructure import get_db
        
        # Get database session
        db = next(get_db())
        try:
            key_manager = get_api_key_manager(db)
            client_ip = self._get_client_ip(request)
            
            # Verify API key
            key_info = key_manager.verify_api_key(api_key, client_ip)
            
            return {
                "sub": f"api_key:{key_info.id}",
                "role": key_info.role,
                "auth_type": "api_key",
                "key_id": key_info.id,
                "key_name": key_info.name,
                "rate_limit_override": key_info.rate_limit_override
            }
        finally:
            db.close()
    
    def _requires_auth(self, path: str) -> bool:
        """Check if path requires authentication"""
        # Skip authentication for health checks and metrics
        if path in ["/health", "/health/ready", "/health/live", "/metrics", "/docs", "/redoc", "/openapi.json"]:
            return False
        
        # Skip authentication for auth endpoints
        if path.startswith("/api/v1/auth/"):
            return False
        
        # Check protected paths
        return any(path.startswith(protected_path) for protected_path in self.protected_paths)
    
    def _extract_jwt_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request"""
        # Try Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            # Check if it's a JWT (contains dots) vs API key
            if "." in token:
                return token
        
        # Try query parameter as fallback
        token = request.query_params.get("token")
        if token and "." in token:
            return token
        
        return None
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request"""
        # Try Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            # Check if it's an API key (no dots) vs JWT
            if "." not in token and token.startswith("rgp_"):
                return token
        
        # Try X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key and api_key.startswith("rgp_"):
            return api_key
        
        # Try query parameter as fallback
        api_key = request.query_params.get("api_key")
        if api_key and api_key.startswith("rgp_"):
            return api_key
        
        return None
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return request.client.host if request.client else "unknown"
    
    def _verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm]
            )
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            
            return payload
            
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )


class RoleBasedAccessMiddleware(BaseHTTPMiddleware):
    """Role-based access control middleware"""
    
    def __init__(self, app, role_permissions: Dict[str, List[str]] = None):
        super().__init__(app)
        self.role_permissions = role_permissions or {
            "admin": ["*"],  # Admin can access everything
            "operator": ["/api/v1/collect/trigger", "/api/v1/process/trigger", "/api/v1/publish/trigger"],
            "viewer": ["/api/v1/status/*"]
        }
    
    async def dispatch(self, request: Request, call_next):
        # Skip if not authenticated
        if not getattr(request.state, "authenticated", False):
            return await call_next(request)
        
        user = getattr(request.state, "user", {})
        user_role = user.get("role", "viewer")
        
        # Check permissions
        if not self._has_permission(user_role, request.url.path, request.method):
            logger.warning(
                "Access denied",
                user_id=user.get("sub"),
                role=user_role,
                path=request.url.path,
                method=request.method
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return await call_next(request)
    
    def _has_permission(self, role: str, path: str, method: str) -> bool:
        """Check if role has permission for path and method"""
        permissions = self.role_permissions.get(role, [])
        
        # Admin has access to everything
        if "*" in permissions:
            return True
        
        # Check specific path permissions
        for permission in permissions:
            if permission.endswith("*"):
                # Wildcard permission
                if path.startswith(permission[:-1]):
                    return True
            elif path == permission:
                # Exact match
                return True
        
        return False


def create_jwt_token(user_id: str, role: str = "viewer", expires_in_hours: int = None) -> str:
    """Create JWT token for user"""
    settings = get_settings()
    expires_in_hours = expires_in_hours or settings.jwt_expiry_hours
    
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + (expires_in_hours * 3600)
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    logger.info(
        "JWT token created",
        user_id=user_id,
        role=role,
        expires_in_hours=expires_in_hours
    )
    
    return token


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify JWT token and return payload"""
    settings = get_settings()
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        
        return payload
        
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# Dependency for protected routes
async def get_current_user(credentials: HTTPAuthorizationCredentials = security) -> Dict[str, Any]:
    """Get current authenticated user from JWT token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return verify_jwt_token(credentials.credentials)


async def get_admin_user(current_user: Dict[str, Any] = get_current_user) -> Dict[str, Any]:
    """Get current user and verify admin role"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user