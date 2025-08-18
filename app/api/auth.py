"""
Authentication and API key management system
Handles JWT tokens, API keys, and role-based access control
"""
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

import jwt
import structlog
from fastapi import HTTPException, status
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.api_key import APIKey


logger = structlog.get_logger(__name__)


class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class APIKeyStatus(str, Enum):
    """API key status"""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"





class JWTManager:
    """JWT token management"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def create_token(
        self,
        user_id: str,
        role: UserRole = UserRole.VIEWER,
        expires_in_hours: Optional[int] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create JWT token with user claims"""
        expires_in_hours = expires_in_hours or self.settings.jwt_expiry_hours
        now = int(time.time())
        
        payload = {
            "sub": user_id,
            "role": role.value,
            "iat": now,
            "exp": now + (expires_in_hours * 3600),
            "iss": "reddit-ghost-publisher",
            "aud": "api"
        }
        
        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm
        )
        
        logger.info(
            "JWT token created",
            user_id=user_id,
            role=role.value,
            expires_in_hours=expires_in_hours,
            additional_claims=list(additional_claims.keys()) if additional_claims else None
        )
        
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
                audience="api",
                issuer="reddit-ghost-publisher"
            )
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    def refresh_token(self, token: str) -> str:
        """Refresh JWT token if it's close to expiry"""
        try:
            payload = self.verify_token(token)
            
            # Check if token is within refresh window (last 25% of lifetime)
            exp = payload.get("exp", 0)
            iat = payload.get("iat", 0)
            lifetime = exp - iat
            refresh_threshold = exp - (lifetime * 0.25)
            
            if time.time() >= refresh_threshold:
                # Create new token with same claims
                return self.create_token(
                    user_id=payload["sub"],
                    role=UserRole(payload["role"]),
                    additional_claims={
                        k: v for k, v in payload.items() 
                        if k not in ["sub", "role", "iat", "exp", "iss", "aud"]
                    }
                )
            
            return token
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Token refresh failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token refresh failed"
            )


class APIKeyManager:
    """API key management system"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def generate_api_key(
        self,
        name: str,
        role: UserRole,
        created_by: str,
        expires_in_days: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        rate_limit_override: Optional[int] = None
    ) -> tuple[str, APIKey]:
        """Generate new API key"""
        # Generate secure random key
        key = f"rgp_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(key)
        key_prefix = key[:8]
        
        # Calculate expiry
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create API key record
        api_key = APIKey(
            id=secrets.token_urlsafe(16),
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            role=role.value,
            created_by=created_by,
            expires_at=expires_at,
            allowed_ips=",".join(allowed_ips) if allowed_ips else None,
            rate_limit_override=rate_limit_override
        )
        
        self.db.add(api_key)
        self.db.commit()
        
        logger.info(
            "API key generated",
            key_id=api_key.id,
            name=name,
            role=role.value,
            created_by=created_by,
            expires_at=expires_at.isoformat() if expires_at else None
        )
        
        return key, api_key
    
    def verify_api_key(self, key: str, client_ip: Optional[str] = None) -> APIKey:
        """Verify API key and return key info"""
        key_hash = self._hash_key(key)
        
        api_key = self.db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.status == APIKeyStatus.ACTIVE.value
        ).first()
        
        if not api_key:
            logger.warning("Invalid API key used", key_prefix=key[:8])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # Check expiry
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            logger.warning("Expired API key used", key_id=api_key.id)
            api_key.status = APIKeyStatus.EXPIRED.value
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired"
            )
        
        # Check IP restrictions
        if api_key.allowed_ips and client_ip:
            allowed_ips = api_key.allowed_ips.split(",")
            if client_ip not in allowed_ips:
                logger.warning(
                    "API key used from unauthorized IP",
                    key_id=api_key.id,
                    client_ip=client_ip,
                    allowed_ips=allowed_ips
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key not authorized for this IP address"
                )
        
        # Update usage statistics
        api_key.last_used_at = datetime.utcnow()
        api_key.usage_count += 1
        self.db.commit()
        
        logger.info(
            "API key verified",
            key_id=api_key.id,
            role=api_key.role,
            usage_count=api_key.usage_count
        )
        
        return api_key
    
    def revoke_api_key(self, key_id: str, revoked_by: str) -> bool:
        """Revoke API key"""
        api_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        
        if not api_key:
            return False
        
        api_key.status = APIKeyStatus.REVOKED.value
        self.db.commit()
        
        logger.info(
            "API key revoked",
            key_id=key_id,
            name=api_key.name,
            revoked_by=revoked_by
        )
        
        return True
    
    def list_api_keys(self, include_revoked: bool = False) -> List[APIKey]:
        """List all API keys"""
        query = self.db.query(APIKey)
        
        if not include_revoked:
            query = query.filter(APIKey.status != APIKeyStatus.REVOKED.value)
        
        return query.order_by(APIKey.created_at.desc()).all()
    
    def rotate_api_key(self, key_id: str, rotated_by: str) -> tuple[str, APIKey]:
        """Rotate API key (revoke old, create new with same permissions)"""
        old_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        
        if not old_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Create new key with same permissions
        allowed_ips = old_key.allowed_ips.split(",") if old_key.allowed_ips else None
        expires_in_days = None
        if old_key.expires_at:
            expires_in_days = (old_key.expires_at - datetime.utcnow()).days
        
        new_key, new_api_key = self.generate_api_key(
            name=f"{old_key.name} (rotated)",
            role=UserRole(old_key.role),
            created_by=rotated_by,
            expires_in_days=expires_in_days,
            allowed_ips=allowed_ips,
            rate_limit_override=old_key.rate_limit_override
        )
        
        # Revoke old key
        old_key.status = APIKeyStatus.REVOKED.value
        self.db.commit()
        
        logger.info(
            "API key rotated",
            old_key_id=key_id,
            new_key_id=new_api_key.id,
            rotated_by=rotated_by
        )
        
        return new_key, new_api_key
    
    def _hash_key(self, key: str) -> str:
        """Hash API key for secure storage"""
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()


class RolePermissionManager:
    """Role-based access control manager"""
    
    # Define role permissions
    ROLE_PERMISSIONS = {
        UserRole.ADMIN: [
            "*"  # Admin can access everything
        ],
        UserRole.OPERATOR: [
            "/api/v1/collect/trigger",
            "/api/v1/process/trigger", 
            "/api/v1/publish/trigger",
            "/api/v1/status/*",
            "/api/v1/auth/keys/list",
            "/api/v1/auth/keys/*/revoke"
        ],
        UserRole.VIEWER: [
            "/api/v1/status/*",
            "/health",
            "/metrics"
        ]
    }
    
    @classmethod
    def has_permission(cls, role: UserRole, path: str, method: str = "GET") -> bool:
        """Check if role has permission for path and method"""
        permissions = cls.ROLE_PERMISSIONS.get(role, [])
        
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
    
    @classmethod
    def get_role_permissions(cls, role: UserRole) -> List[str]:
        """Get all permissions for a role"""
        return cls.ROLE_PERMISSIONS.get(role, [])


# Global instances
jwt_manager = JWTManager()


def get_api_key_manager(db: Session) -> APIKeyManager:
    """Get API key manager instance"""
    return APIKeyManager(db)