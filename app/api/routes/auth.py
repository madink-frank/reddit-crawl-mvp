"""
Authentication API routes
Handles JWT tokens, API keys, and authentication endpoints
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import (
    APIKeyManager, JWTManager, UserRole, APIKeyStatus,
    get_api_key_manager, jwt_manager
)
from app.api.middleware.auth import get_current_user, get_admin_user
from app.infrastructure import get_db
import structlog


logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
security = HTTPBearer()


# Pydantic models for API requests/responses
class TokenRequest(BaseModel):
    """Request model for token creation"""
    user_id: str = Field(..., description="User identifier")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role")
    expires_in_hours: Optional[int] = Field(default=None, description="Token expiry in hours")


class TokenResponse(BaseModel):
    """Response model for token creation"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiry in seconds")
    role: str = Field(..., description="User role")


class APIKeyCreateRequest(BaseModel):
    """Request model for API key creation"""
    name: str = Field(..., description="API key name", max_length=255)
    role: UserRole = Field(..., description="API key role")
    expires_in_days: Optional[int] = Field(default=None, description="Expiry in days")
    allowed_ips: Optional[List[str]] = Field(default=None, description="Allowed IP addresses")
    rate_limit_override: Optional[int] = Field(default=None, description="Custom rate limit")


class APIKeyResponse(BaseModel):
    """Response model for API key"""
    id: str
    name: str
    key_prefix: str
    role: str
    status: str
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: int
    allowed_ips: Optional[str]
    rate_limit_override: Optional[int]


class APIKeyCreateResponse(BaseModel):
    """Response model for API key creation"""
    api_key: str = Field(..., description="The actual API key (only shown once)")
    key_info: APIKeyResponse = Field(..., description="API key metadata")


@router.post("/token", response_model=TokenResponse)
async def create_token(
    request: TokenRequest,
    current_user: dict = Depends(get_admin_user)
):
    """Create JWT token (admin only)"""
    try:
        token = jwt_manager.create_token(
            user_id=request.user_id,
            role=request.role,
            expires_in_hours=request.expires_in_hours
        )
        
        expires_in = (request.expires_in_hours or 24) * 3600
        
        logger.info(
            "JWT token created via API",
            user_id=request.user_id,
            role=request.role.value,
            created_by=current_user.get("sub")
        )
        
        return TokenResponse(
            access_token=token,
            expires_in=expires_in,
            role=request.role.value
        )
        
    except Exception as e:
        logger.error("Token creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token creation failed"
        )


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Refresh JWT token"""
    try:
        new_token = jwt_manager.refresh_token(credentials.credentials)
        payload = jwt_manager.verify_token(new_token)
        
        logger.info(
            "JWT token refreshed",
            user_id=payload.get("sub")
        )
        
        return TokenResponse(
            access_token=new_token,
            expires_in=24 * 3600,  # Default 24 hours
            role=payload.get("role", "viewer")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    current_user: dict = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Create new API key (admin only)"""
    try:
        key_manager = get_api_key_manager(db)
        
        api_key, key_info = key_manager.generate_api_key(
            name=request.name,
            role=request.role,
            created_by=current_user.get("sub"),
            expires_in_days=request.expires_in_days,
            allowed_ips=request.allowed_ips,
            rate_limit_override=request.rate_limit_override
        )
        
        return APIKeyCreateResponse(
            api_key=api_key,
            key_info=APIKeyResponse(
                id=key_info.id,
                name=key_info.name,
                key_prefix=key_info.key_prefix,
                role=key_info.role,
                status=key_info.status,
                created_by=key_info.created_by,
                created_at=key_info.created_at,
                expires_at=key_info.expires_at,
                last_used_at=key_info.last_used_at,
                usage_count=key_info.usage_count,
                allowed_ips=key_info.allowed_ips,
                rate_limit_override=key_info.rate_limit_override
            )
        )
        
    except Exception as e:
        logger.error("API key creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key creation failed"
        )


@router.get("/keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    include_revoked: bool = False,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List API keys"""
    try:
        key_manager = get_api_key_manager(db)
        
        # Only admin can see all keys, others see only their own
        if current_user.get("role") != "admin":
            # For non-admin users, we would need to filter by created_by
            # For now, only allow admin to list keys
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        keys = key_manager.list_api_keys(include_revoked=include_revoked)
        
        return [
            APIKeyResponse(
                id=key.id,
                name=key.name,
                key_prefix=key.key_prefix,
                role=key.role,
                status=key.status,
                created_by=key.created_by,
                created_at=key.created_at,
                expires_at=key.expires_at,
                last_used_at=key.last_used_at,
                usage_count=key.usage_count,
                allowed_ips=key.allowed_ips,
                rate_limit_override=key.rate_limit_override
            )
            for key in keys
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API key listing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key listing failed"
        )


@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Revoke API key (admin only)"""
    try:
        key_manager = get_api_key_manager(db)
        
        success = key_manager.revoke_api_key(
            key_id=key_id,
            revoked_by=current_user.get("sub")
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API key revocation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key revocation failed"
        )


@router.post("/keys/{key_id}/rotate", response_model=APIKeyCreateResponse)
async def rotate_api_key(
    key_id: str,
    current_user: dict = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Rotate API key (admin only)"""
    try:
        key_manager = get_api_key_manager(db)
        
        new_key, key_info = key_manager.rotate_api_key(
            key_id=key_id,
            rotated_by=current_user.get("sub")
        )
        
        return APIKeyCreateResponse(
            api_key=new_key,
            key_info=APIKeyResponse(
                id=key_info.id,
                name=key_info.name,
                key_prefix=key_info.key_prefix,
                role=key_info.role,
                status=key_info.status,
                created_by=key_info.created_by,
                created_at=key_info.created_at,
                expires_at=key_info.expires_at,
                last_used_at=key_info.last_used_at,
                usage_count=key_info.usage_count,
                allowed_ips=key_info.allowed_ips,
                rate_limit_override=key_info.rate_limit_override
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API key rotation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key rotation failed"
        )


@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """Get current user information"""
    return {
        "user_id": current_user.get("sub"),
        "role": current_user.get("role"),
        "issued_at": current_user.get("iat"),
        "expires_at": current_user.get("exp")
    }


@router.post("/verify")
async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Verify JWT token"""
    try:
        payload = jwt_manager.verify_token(credentials.credentials)
        
        return {
            "valid": True,
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "expires_at": payload.get("exp")
        }
        
    except HTTPException as e:
        return {
            "valid": False,
            "error": e.detail
        }