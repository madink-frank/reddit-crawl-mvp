"""
HashiCorp Vault client for secure secret management
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import hvac
from hvac.exceptions import VaultError, InvalidPath, Forbidden, Unauthorized

from app.config import get_settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
settings = get_settings()


class VaultClient:
    """HashiCorp Vault client with caching and error handling"""
    
    def __init__(self):
        self._client: Optional[hvac.Client] = None
        self._authenticated = False
        self._token_expires_at: Optional[datetime] = None
        self._cache_ttl = 300  # 5 minutes default cache TTL
    
    def connect(self) -> None:
        """Initialize Vault client connection"""
        try:
            self._client = hvac.Client(
                url=settings.vault_url,
                token=settings.vault_token,
                verify=True,  # Verify SSL certificates
                timeout=30
            )
            
            # Test authentication
            if self._client.is_authenticated():
                self._authenticated = True
                self._update_token_expiry()
                logger.info("Vault client authenticated successfully")
            else:
                raise VaultError("Vault authentication failed")
                
        except Exception as e:
            logger.error(f"Failed to connect to Vault: {e}")
            self._authenticated = False
            raise
    
    def disconnect(self) -> None:
        """Close Vault client connection"""
        if self._client:
            self._client.adapter.close()
        self._authenticated = False
        self._client = None
        logger.info("Vault client disconnected")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if Vault client is authenticated"""
        return self._authenticated and self._client is not None
    
    def _update_token_expiry(self) -> None:
        """Update token expiry time based on Vault response"""
        try:
            if not self._client:
                return
            
            # Get token info to determine expiry
            token_info = self._client.auth.token.lookup_self()
            ttl = token_info.get("data", {}).get("ttl", 3600)
            
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            logger.debug(f"Vault token expires at: {self._token_expires_at}")
            
        except Exception as e:
            logger.warning(f"Could not determine token expiry: {e}")
            # Default to 1 hour
            self._token_expires_at = datetime.utcnow() + timedelta(hours=1)
    
    def _is_token_expired(self) -> bool:
        """Check if Vault token is expired or will expire soon"""
        if not self._token_expires_at:
            return True
        
        # Consider token expired if it expires within 5 minutes
        return datetime.utcnow() + timedelta(minutes=5) >= self._token_expires_at
    
    async def _refresh_token_if_needed(self) -> None:
        """Refresh Vault token if it's expired or expiring soon"""
        try:
            if not self._is_token_expired():
                return
            
            if not self._client:
                self.connect()
                return
            
            # Try to renew the token
            try:
                self._client.auth.token.renew_self()
                self._update_token_expiry()
                logger.info("Vault token renewed successfully")
            except Exception as e:
                logger.warning(f"Token renewal failed, reconnecting: {e}")
                self.connect()
                
        except Exception as e:
            logger.error(f"Failed to refresh Vault token: {e}")
            raise
    
    async def get_secret(
        self, 
        path: str, 
        mount_point: str = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get secret from Vault with caching support
        
        Args:
            path: Secret path (e.g., "reddit/credentials")
            mount_point: Vault mount point (defaults to settings.vault_mount_point)
            use_cache: Whether to use Redis cache
        
        Returns:
            Dictionary containing secret data
        """
        try:
            await self._refresh_token_if_needed()
            
            if not self.is_authenticated:
                raise VaultError("Vault client not authenticated")
            
            mount_point = mount_point or settings.vault_mount_point
            cache_key = f"vault_secret:{mount_point}:{path}"
            
            # Try cache first
            if use_cache:
                cached_secret = await redis_client.cache_get(cache_key)
                if cached_secret:
                    logger.debug(f"Retrieved secret from cache: {path}")
                    return cached_secret
            
            # Get secret from Vault
            try:
                response = self._client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=mount_point
                )
                
                secret_data = response["data"]["data"]
                
                # Cache the secret
                if use_cache:
                    await redis_client.cache_set(
                        cache_key, 
                        secret_data, 
                        ttl=self._cache_ttl
                    )
                
                logger.info(f"Retrieved secret from Vault: {path}")
                return secret_data
                
            except InvalidPath:
                logger.error(f"Secret not found: {path}")
                raise
            except Forbidden:
                logger.error(f"Access denied to secret: {path}")
                raise
            except Exception as e:
                logger.error(f"Failed to retrieve secret {path}: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Vault get_secret failed for {path}: {e}")
            raise
    
    async def put_secret(
        self, 
        path: str, 
        secret_data: Dict[str, Any],
        mount_point: str = None
    ) -> bool:
        """
        Store secret in Vault
        
        Args:
            path: Secret path
            secret_data: Dictionary containing secret data
            mount_point: Vault mount point
        
        Returns:
            True if successful
        """
        try:
            await self._refresh_token_if_needed()
            
            if not self.is_authenticated:
                raise VaultError("Vault client not authenticated")
            
            mount_point = mount_point or settings.vault_mount_point
            
            # Store secret in Vault
            self._client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=secret_data,
                mount_point=mount_point
            )
            
            # Invalidate cache
            cache_key = f"vault_secret:{mount_point}:{path}"
            await redis_client.cache_delete(cache_key)
            
            logger.info(f"Secret stored in Vault: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store secret {path}: {e}")
            return False
    
    async def delete_secret(
        self, 
        path: str, 
        mount_point: str = None
    ) -> bool:
        """
        Delete secret from Vault
        
        Args:
            path: Secret path
            mount_point: Vault mount point
        
        Returns:
            True if successful
        """
        try:
            await self._refresh_token_if_needed()
            
            if not self.is_authenticated:
                raise VaultError("Vault client not authenticated")
            
            mount_point = mount_point or settings.vault_mount_point
            
            # Delete secret from Vault
            self._client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=mount_point
            )
            
            # Invalidate cache
            cache_key = f"vault_secret:{mount_point}:{path}"
            await redis_client.cache_delete(cache_key)
            
            logger.info(f"Secret deleted from Vault: {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete secret {path}: {e}")
            return False
    
    async def list_secrets(
        self, 
        path: str = "", 
        mount_point: str = None
    ) -> List[str]:
        """
        List secrets at a given path
        
        Args:
            path: Path to list (empty for root)
            mount_point: Vault mount point
        
        Returns:
            List of secret names
        """
        try:
            await self._refresh_token_if_needed()
            
            if not self.is_authenticated:
                raise VaultError("Vault client not authenticated")
            
            mount_point = mount_point or settings.vault_mount_point
            
            response = self._client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=mount_point
            )
            
            return response["data"]["keys"]
            
        except Exception as e:
            logger.error(f"Failed to list secrets at {path}: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Vault health status
        
        Returns:
            Dictionary with health status information
        """
        try:
            if not self._client:
                return {
                    "status": "unhealthy",
                    "error": "Client not initialized",
                    "authenticated": False
                }
            
            # Check if Vault is sealed
            seal_status = self._client.sys.read_seal_status()
            
            if seal_status["sealed"]:
                return {
                    "status": "unhealthy",
                    "error": "Vault is sealed",
                    "authenticated": False,
                    "sealed": True
                }
            
            # Check authentication
            if not self.is_authenticated:
                return {
                    "status": "unhealthy", 
                    "error": "Not authenticated",
                    "authenticated": False,
                    "sealed": False
                }
            
            # Check token validity
            try:
                token_info = self._client.auth.token.lookup_self()
                ttl = token_info.get("data", {}).get("ttl", 0)
                
                return {
                    "status": "healthy",
                    "authenticated": True,
                    "sealed": False,
                    "token_ttl": ttl,
                    "token_expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None
                }
                
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": f"Token validation failed: {e}",
                    "authenticated": False,
                    "sealed": False
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "authenticated": False
            }


class SecretManager:
    """High-level secret management with predefined secret paths"""
    
    def __init__(self, vault_client: VaultClient):
        self.vault = vault_client
    
    async def get_reddit_credentials(self) -> Dict[str, str]:
        """Get Reddit API credentials"""
        try:
            return await self.vault.get_secret("reddit/credentials")
        except Exception as e:
            logger.error(f"Failed to get Reddit credentials: {e}")
            # Fallback to environment variables
            return {
                "client_id": settings.reddit_client_id,
                "client_secret": settings.reddit_client_secret,
                "user_agent": settings.reddit_user_agent
            }
    
    async def get_openai_credentials(self) -> Dict[str, str]:
        """Get OpenAI API credentials"""
        try:
            return await self.vault.get_secret("openai/credentials")
        except Exception as e:
            logger.error(f"Failed to get OpenAI credentials: {e}")
            # Fallback to environment variables
            return {
                "api_key": settings.openai_api_key
            }
    
    async def get_ghost_credentials(self) -> Dict[str, str]:
        """Get Ghost CMS credentials"""
        try:
            return await self.vault.get_secret("ghost/credentials")
        except Exception as e:
            logger.error(f"Failed to get Ghost credentials: {e}")
            # Fallback to environment variables
            return {
                "admin_key": settings.ghost_admin_key,
                "content_key": settings.ghost_content_key,
                "api_url": settings.ghost_api_url
            }
    
    async def get_database_credentials(self) -> Dict[str, str]:
        """Get database credentials"""
        try:
            return await self.vault.get_secret("database/credentials")
        except Exception as e:
            logger.error(f"Failed to get database credentials: {e}")
            # Fallback to environment variables
            return {
                "url": settings.database_url
            }
    
    async def get_langsmith_credentials(self) -> Dict[str, str]:
        """Get LangSmith credentials"""
        try:
            return await self.vault.get_secret("langsmith/credentials")
        except Exception as e:
            logger.error(f"Failed to get LangSmith credentials: {e}")
            # Fallback to environment variables
            return {
                "api_key": settings.langsmith_api_key,
                "project": settings.langsmith_project
            }
    
    async def rotate_secret(
        self, 
        path: str, 
        new_secret_data: Dict[str, Any]
    ) -> bool:
        """
        Rotate a secret by updating it with new values
        
        Args:
            path: Secret path
            new_secret_data: New secret data
        
        Returns:
            True if successful
        """
        try:
            # Store new secret
            success = await self.vault.put_secret(path, new_secret_data)
            
            if success:
                logger.info(f"Secret rotated successfully: {path}")
                
                # Trigger cache invalidation across all services
                await self._notify_secret_rotation(path)
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to rotate secret {path}: {e}")
            return False
    
    async def _notify_secret_rotation(self, path: str) -> None:
        """Notify services about secret rotation"""
        try:
            # Store rotation notification in Redis
            rotation_data = {
                "path": path,
                "rotated_at": datetime.utcnow().isoformat(),
                "action": "rotated"
            }
            
            await redis_client.lpush("secret_rotations", rotation_data)
            await redis_client.expire("secret_rotations", 86400)  # Keep for 24 hours
            
            logger.info(f"Secret rotation notification sent: {path}")
            
        except Exception as e:
            logger.error(f"Failed to notify secret rotation: {e}")


# Global Vault client instance
vault_client = VaultClient()
secret_manager = SecretManager(vault_client)


@asynccontextmanager
async def get_vault():
    """Context manager for Vault operations"""
    if not vault_client.is_authenticated:
        vault_client.connect()
    
    try:
        yield vault_client
    except Exception as e:
        logger.error(f"Vault operation failed: {e}")
        raise
    finally:
        # Connection stays open for reuse
        pass


async def init_vault() -> None:
    """Initialize Vault connection"""
    vault_client.connect()


def close_vault() -> None:
    """Close Vault connection"""
    vault_client.disconnect()


# Utility functions for common secret operations
async def get_secret_with_fallback(
    vault_path: str, 
    env_var: str, 
    default: Optional[str] = None
) -> Optional[str]:
    """
    Get secret from Vault with environment variable fallback
    
    Args:
        vault_path: Path to secret in Vault
        env_var: Environment variable name as fallback
        default: Default value if both Vault and env var fail
    
    Returns:
        Secret value or None
    """
    try:
        # Try Vault first
        secret_data = await vault_client.get_secret(vault_path)
        if secret_data and "value" in secret_data:
            return secret_data["value"]
    except Exception as e:
        logger.debug(f"Vault lookup failed for {vault_path}: {e}")
    
    # Fallback to environment variable
    import os
    env_value = os.getenv(env_var)
    if env_value:
        return env_value
    
    # Return default
    return default


async def ensure_secrets_exist() -> Dict[str, bool]:
    """
    Ensure all required secrets exist in Vault
    
    Returns:
        Dictionary showing which secrets exist
    """
    required_secrets = [
        "reddit/credentials",
        "openai/credentials", 
        "ghost/credentials",
        "database/credentials",
        "langsmith/credentials"
    ]
    
    results = {}
    
    for secret_path in required_secrets:
        try:
            await vault_client.get_secret(secret_path, use_cache=False)
            results[secret_path] = True
        except Exception:
            results[secret_path] = False
    
    return results


# Health check function
async def vault_health_check() -> Dict[str, Any]:
    """Check Vault health status"""
    try:
        return vault_client.health_check()
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "authenticated": False
        }