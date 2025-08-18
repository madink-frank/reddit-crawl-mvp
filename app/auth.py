"""
Authentication and Authorization for Reddit Ghost Publisher MVP
Environment variable-based authentication with JWT support
"""
import os
import jwt
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.security import SecretManager, PIIMasker

logger = logging.getLogger(__name__)

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """Authentication related errors"""
    pass


class AuthorizationError(Exception):
    """Authorization related errors"""
    pass


class GhostJWTManager:
    """Ghost Admin API JWT token management"""
    
    def __init__(self, admin_key: Optional[str] = None):
        """Initialize with Ghost Admin Key from environment"""
        self.admin_key = admin_key or settings.ghost_admin_key
        self._cached_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        if not self.admin_key:
            raise AuthenticationError("GHOST_ADMIN_KEY environment variable not set")
    
    def _parse_admin_key(self) -> tuple[str, str]:
        """Parse Ghost Admin Key format: key_id:secret"""
        try:
            key_id, secret = self.admin_key.split(':', 1)
            if not key_id or not secret:
                raise ValueError("Empty key_id or secret")
            return key_id, secret
        except ValueError as e:
            raise AuthenticationError(f"Invalid Ghost Admin Key format. Expected 'key_id:secret': {e}")
    
    def generate_jwt_token(self, expiry_seconds: int = 300) -> str:
        """Generate JWT token for Ghost Admin API
        
        Args:
            expiry_seconds: Token expiry time in seconds (default: 5 minutes)
            
        Returns:
            JWT token string
            
        Raises:
            AuthenticationError: If admin key is invalid or token generation fails
        """
        try:
            key_id, secret = self._parse_admin_key()
            
            # Create JWT payload
            iat = int(time.time())
            exp = iat + expiry_seconds
            
            payload = {
                'iat': iat,
                'exp': exp,
                'aud': '/admin/'
            }
            
            # Generate token with kid header
            token = jwt.encode(
                payload,
                bytes.fromhex(secret),
                algorithm='HS256',
                headers={'kid': key_id}
            )
            
            # Cache token and expiry
            self._cached_token = token
            self._token_expires_at = datetime.fromtimestamp(exp)
            
            logger.debug(f"Generated Ghost JWT token, expires at: {self._token_expires_at}")
            
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate Ghost JWT token: {e}")
            raise AuthenticationError(f"JWT token generation failed: {e}")
    
    def get_valid_token(self, buffer_seconds: int = 30) -> str:
        """Get a valid JWT token, generating new one if needed
        
        Args:
            buffer_seconds: Refresh token this many seconds before expiry
            
        Returns:
            Valid JWT token string
        """
        now = datetime.now()
        
        # Check if we need a new token
        if (not self._cached_token or 
            not self._token_expires_at or 
            now >= (self._token_expires_at - timedelta(seconds=buffer_seconds))):
            
            return self.generate_jwt_token()
        
        return self._cached_token
    
    def get_ghost_headers(self) -> Dict[str, str]:
        """Get headers for Ghost API requests with JWT authorization
        
        Returns:
            Dictionary with Authorization header and other required headers
        """
        token = self.get_valid_token()
        return {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def clear_cache(self) -> None:
        """Clear cached token (for testing or forced refresh)"""
        self._cached_token = None
        self._token_expires_at = None
        logger.debug("Ghost JWT token cache cleared")


class APIKeyManager:
    """API key management for external services"""
    
    def __init__(self):
        """Initialize with secret manager"""
        self.secret_manager = SecretManager()
        self.pii_masker = PIIMasker()
        self._api_keys_cache: Dict[str, str] = {}
        self._cache_loaded = False
    
    @lru_cache(maxsize=32)
    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service with caching
        
        Args:
            service: Service name (reddit, openai, ghost, slack)
            
        Returns:
            API key string or None if not found
        """
        key_mapping = {
            'reddit_client_id': 'REDDIT_CLIENT_ID',
            'reddit_client_secret': 'REDDIT_CLIENT_SECRET',
            'openai': 'OPENAI_API_KEY',
            'ghost': 'GHOST_ADMIN_KEY',
            'slack': 'SLACK_WEBHOOK_URL'
        }
        
        env_key = key_mapping.get(service)
        if not env_key:
            logger.warning(f"Unknown service for API key: {service}")
            return None
        
        api_key = self.secret_manager.get_secret(env_key)
        
        if api_key:
            # Cache non-sensitive metadata
            self._api_keys_cache[f"{service}_loaded"] = True
            logger.debug(f"API key loaded for service: {service}")
        else:
            logger.warning(f"API key not found for service: {service}")
        
        return api_key
    
    def get_reddit_credentials(self) -> Dict[str, Optional[str]]:
        """Get Reddit API credentials
        
        Returns:
            Dictionary with client_id and client_secret
        """
        return {
            'client_id': self.get_api_key('reddit_client_id'),
            'client_secret': self.get_api_key('reddit_client_secret'),
            'user_agent': settings.reddit_user_agent
        }
    
    def get_openai_key(self) -> Optional[str]:
        """Get OpenAI API key"""
        return self.get_api_key('openai')
    
    def get_ghost_admin_key(self) -> Optional[str]:
        """Get Ghost Admin Key"""
        return self.get_api_key('ghost')
    
    def get_slack_webhook_url(self) -> Optional[str]:
        """Get Slack webhook URL"""
        return self.get_api_key('slack')
    
    def validate_all_keys(self) -> Dict[str, bool]:
        """Validate all required API keys are present
        
        Returns:
            Dictionary with validation status for each service
        """
        services = ['reddit_client_id', 'reddit_client_secret', 'openai', 'ghost']
        optional_services = ['slack']
        
        validation_status = {}
        
        # Check required services
        for service in services:
            key = self.get_api_key(service)
            validation_status[service] = bool(key and len(key.strip()) > 0)
            
            if not validation_status[service]:
                logger.error(f"Required API key missing for service: {service}")
        
        # Check optional services
        for service in optional_services:
            key = self.get_api_key(service)
            validation_status[service] = bool(key and len(key.strip()) > 0)
            
            if not validation_status[service]:
                logger.info(f"Optional API key not configured for service: {service}")
        
        return validation_status
    
    def get_masked_status(self) -> Dict[str, str]:
        """Get masked status of API keys for logging/debugging
        
        Returns:
            Dictionary with masked key status
        """
        services = ['reddit_client_id', 'reddit_client_secret', 'openai', 'ghost', 'slack']
        status = {}
        
        for service in services:
            key = self.get_api_key(service)
            if key:
                # Show first 4 and last 4 characters with masking
                if len(key) > 8:
                    masked = f"{key[:4]}****{key[-4:]}"
                else:
                    masked = "****"
                status[service] = f"configured ({masked})"
            else:
                status[service] = "not configured"
        
        return status


class SimpleJWTManager:
    """Simple JWT manager for internal API authentication (MVP)"""
    
    def __init__(self):
        """Initialize with settings"""
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        
        if not self.secret_key or self.secret_key == "dev-secret-key":
            if settings.environment == "production":
                raise AuthenticationError("JWT_SECRET_KEY must be set in production")
            logger.warning("Using default JWT secret key in development")
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token
        
        Args:
            data: Data to encode in token
            expires_delta: Token expiry time (default: 1 hour)
            
        Returns:
            JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=1)
        
        to_encode.update({"exp": expire})
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Failed to create JWT token: {e}")
            raise AuthenticationError(f"Token creation failed: {e}")
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.JWTError as e:
            raise AuthenticationError(f"Token validation failed: {e}")


# Global instances
_ghost_jwt_manager: Optional[GhostJWTManager] = None
_api_key_manager: Optional[APIKeyManager] = None
_simple_jwt_manager: Optional[SimpleJWTManager] = None


def get_ghost_jwt_manager() -> GhostJWTManager:
    """Get singleton Ghost JWT manager instance"""
    global _ghost_jwt_manager
    if _ghost_jwt_manager is None:
        _ghost_jwt_manager = GhostJWTManager()
    return _ghost_jwt_manager


def get_api_key_manager() -> APIKeyManager:
    """Get singleton API key manager instance"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_simple_jwt_manager() -> SimpleJWTManager:
    """Get singleton simple JWT manager instance"""
    global _simple_jwt_manager
    if _simple_jwt_manager is None:
        _simple_jwt_manager = SimpleJWTManager()
    return _simple_jwt_manager


# FastAPI Dependencies
async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict[str, Any]:
    """FastAPI dependency to get current authenticated user
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        User information from token
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        jwt_manager = get_simple_jwt_manager()
        payload = jwt_manager.verify_token(credentials.credentials)
        return payload
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """FastAPI dependency to get optional authenticated user
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        User information from token or None if not authenticated
    """
    if not credentials:
        return None
    
    try:
        jwt_manager = get_simple_jwt_manager()
        payload = jwt_manager.verify_token(credentials.credentials)
        return payload
    except AuthenticationError:
        return None


# Convenience functions
def create_ghost_jwt_token() -> str:
    """Create Ghost JWT token (convenience function)"""
    manager = get_ghost_jwt_manager()
    return manager.generate_jwt_token()


def get_ghost_auth_headers() -> Dict[str, str]:
    """Get Ghost API headers with authentication (convenience function)"""
    manager = get_ghost_jwt_manager()
    return manager.get_ghost_headers()


def validate_api_keys() -> Dict[str, bool]:
    """Validate all API keys (convenience function)"""
    manager = get_api_key_manager()
    return manager.validate_all_keys()


def get_api_key_status() -> Dict[str, str]:
    """Get masked API key status (convenience function)"""
    manager = get_api_key_manager()
    return manager.get_masked_status()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create access token (convenience function)"""
    manager = get_simple_jwt_manager()
    return manager.create_access_token(data, expires_delta)