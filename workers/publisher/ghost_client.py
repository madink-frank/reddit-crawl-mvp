"""
Ghost CMS API Client (MVP Synchronous Version)

Handles communication with Ghost Admin API including:
- JWT token generation from environment variables
- Synchronous API calls with exponential backoff retry logic
- Error handling for MVP requirements
"""

import json
import time
import random
import jwt
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class GhostAPIError(Exception):
    """Base exception for Ghost API errors"""
    pass


class GhostAuthError(GhostAPIError):
    """Authentication related errors"""
    pass


class GhostRateLimitError(GhostAPIError):
    """Rate limit exceeded errors"""
    pass


class GhostValidationError(GhostAPIError):
    """Validation errors from Ghost API"""
    pass


class GhostPost:
    """Ghost post data structure for MVP"""
    
    def __init__(
        self,
        title: str,
        html: str,
        status: str = "draft",
        tags: Optional[List[str]] = None,
        feature_image: Optional[str] = None,
        excerpt: Optional[str] = None
    ):
        self.title = title
        self.html = html
        self.status = status
        self.tags = tags or []
        self.feature_image = feature_image
        self.excerpt = excerpt
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Ghost API format"""
        data = {
            "title": self.title,
            "html": self.html,
            "status": self.status
        }
        
        if self.tags:
            data["tags"] = [{"name": tag} for tag in self.tags]
        
        if self.feature_image:
            data["feature_image"] = self.feature_image
            
        if self.excerpt:
            data["excerpt"] = self.excerpt
            
        return data


class GhostClient:
    """Ghost CMS API Client (MVP Synchronous Version)"""
    
    def __init__(self):
        """Initialize Ghost client with environment variables"""
        self.admin_key = settings.ghost_admin_key
        self.base_url = settings.ghost_api_url
        self._jwt_token = None
        self._jwt_expires_at = None
        
        if not self.admin_key:
            raise GhostAuthError("GHOST_ADMIN_KEY environment variable not set")
        if not self.base_url:
            raise GhostAuthError("GHOST_API_URL environment variable not set")
            
        # Ensure base URL ends with /ghost/api/v4/admin/
        if not self.base_url.endswith('/'):
            self.base_url += '/'
        if not self.base_url.endswith('ghost/api/v4/admin/'):
            self.base_url += 'ghost/api/v4/admin/'
            
        logger.info(f"Ghost client initialized with base URL: {self.base_url}")
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for Ghost Admin API
        
        Admin Key format: key_id:secret
        JWT payload: iat=now, exp=now+5m, aud='/admin/'
        Algorithm: HS256
        """
        if not self.admin_key:
            raise GhostAuthError("Admin key not available")
            
        # Split the key (format: key_id:secret)
        try:
            key_id, secret = self.admin_key.split(':')
        except ValueError:
            raise GhostAuthError("Invalid admin key format. Expected 'key_id:secret'")
        
        # Create JWT payload
        iat = int(time.time())
        exp = iat + 300  # 5 minutes (300 seconds)
        
        payload = {
            'iat': iat,
            'exp': exp,
            'aud': '/v4/admin/'
        }
        
        # Generate token with kid header
        token = jwt.encode(
            payload, 
            bytes.fromhex(secret), 
            algorithm='HS256', 
            headers={'kid': key_id}
        )
        
        self._jwt_token = token
        self._jwt_expires_at = datetime.fromtimestamp(exp)
        
        logger.debug(f"Generated new JWT token, expires at: {self._jwt_expires_at}")
        
        return token
    
    def _get_valid_jwt_token(self) -> str:
        """Get a valid JWT token, generating new one if needed"""
        now = datetime.now()
        
        # Check if we need a new token (with 30 second buffer)
        if (not self._jwt_token or 
            not self._jwt_expires_at or 
            now >= (self._jwt_expires_at - timedelta(seconds=30))):
            
            return self._generate_jwt_token()
        
        return self._jwt_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests with Ghost JWT authorization"""
        token = self._get_valid_jwt_token()
        return {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request_with_retry(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Make HTTP request to Ghost API with exponential backoff retry logic
        
        Retry logic: 2s, 4s, 8s (exponential backoff)
        Max retries: 3 attempts
        """
        url = f"{self.base_url}{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        # Remove Content-Type for file uploads
        if files:
            headers.pop('Content-Type', None)
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Making Ghost API request: {method} {url} (attempt {attempt + 1})")
                
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data if not files else None,
                    files=files,
                    timeout=30
                )
                
                # Enhanced rate limiting handling
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    # Cap retry-after to reasonable maximum
                    retry_after = min(retry_after, 300)  # Max 5 minutes
                    
                    logger.warning(f"Ghost API rate limit exceeded, retry after {retry_after}s (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries:
                        # Add small jitter to avoid thundering herd
                        jitter = random.uniform(0.1, 0.3) * retry_after
                        total_wait = retry_after + jitter
                        time.sleep(total_wait)
                        continue
                    raise GhostRateLimitError(f"Rate limit exceeded after {max_retries} retries")
                
                # Enhanced authentication error handling
                if response.status_code == 401:
                    logger.error(f"Ghost API authentication failed (attempt {attempt + 1}/{max_retries})")
                    # Clear cached token to force regeneration
                    self._jwt_token = None
                    self._jwt_expires_at = None
                    
                    if attempt < max_retries:
                        # Exponential backoff with jitter for auth retries
                        backoff_time = 2 ** attempt
                        jitter = random.uniform(0.1, 0.2) * backoff_time
                        total_wait = backoff_time + jitter
                        logger.info(f"Re-authenticating and retrying in {total_wait:.1f}s")
                        time.sleep(total_wait)
                        continue
                    raise GhostAuthError("Authentication failed after retries")
                
                # Handle validation errors (don't retry)
                if response.status_code == 422:
                    try:
                        error_data = response.json()
                        error_details = error_data.get('errors', [])
                        if error_details:
                            error_msg = "; ".join([err.get('message', str(err)) for err in error_details])
                        else:
                            error_msg = str(error_data)
                    except:
                        error_msg = response.text
                    logger.error(f"Ghost API validation error: {error_msg}")
                    raise GhostValidationError(f"Validation error: {error_msg}")
                
                # Handle other client errors (don't retry)
                if 400 <= response.status_code < 500:
                    try:
                        error_data = response.json()
                        error_details = error_data.get('errors', [])
                        if error_details:
                            error_msg = "; ".join([err.get('message', str(err)) for err in error_details])
                        else:
                            error_msg = str(error_data)
                    except:
                        error_msg = response.text
                    logger.error(f"Ghost API client error {response.status_code}: {error_msg}")
                    raise GhostAPIError(f"Client error {response.status_code}: {error_msg}")
                
                # Enhanced server error handling (retry with backoff)
                if response.status_code >= 500:
                    logger.error(f"Ghost API server error {response.status_code} (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries:
                        # Exponential backoff with jitter: 2s, 4s, 8s + jitter
                        backoff_time = 2 ** attempt
                        jitter = random.uniform(0.1, 0.3) * backoff_time
                        total_wait = backoff_time + jitter
                        logger.info(f"Retrying after server error in {total_wait:.1f}s...")
                        time.sleep(total_wait)
                        continue
                    raise GhostAPIError(f"Server error {response.status_code} after {max_retries} retries")
                
                # Success
                response.raise_for_status()
                
                if response.content:
                    result = response.json()
                    logger.debug(f"Ghost API request successful: {response.status_code}")
                    return result
                else:
                    return {}
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Ghost API timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries:
                    # Exponential backoff with jitter for timeouts
                    backoff_time = 2 ** attempt
                    jitter = random.uniform(0.1, 0.2) * backoff_time
                    total_wait = backoff_time + jitter
                    logger.info(f"Retrying after timeout in {total_wait:.1f}s")
                    time.sleep(total_wait)
                    continue
                raise GhostAPIError(f"Request timeout after {max_retries} retries")
                
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Ghost API connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries:
                    # Longer backoff for connection errors
                    backoff_time = min(2 ** attempt, 16)  # Cap at 16 seconds
                    jitter = random.uniform(0.1, 0.3) * backoff_time
                    total_wait = backoff_time + jitter
                    logger.info(f"Retrying after connection error in {total_wait:.1f}s")
                    time.sleep(total_wait)
                    continue
                raise GhostAPIError(f"Connection error after {max_retries} retries: {e}")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Ghost API request error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries:
                    backoff_time = 2 ** attempt
                    jitter = random.uniform(0.1, 0.2) * backoff_time
                    total_wait = backoff_time + jitter
                    logger.info(f"Retrying after request error in {total_wait:.1f}s")
                    time.sleep(total_wait)
                    continue
                raise GhostAPIError(f"Request error after {max_retries} retries: {e}")
                
            except (GhostAuthError, GhostValidationError, GhostRateLimitError):
                # Don't retry these specific errors unless handled above
                raise
                
            except Exception as e:
                logger.error(f"Unexpected error during Ghost API request: {e}")
                if attempt < max_retries:
                    backoff_time = 2 ** attempt
                    time.sleep(backoff_time)
                    continue
                raise GhostAPIError(f"Unexpected error after {max_retries} retries: {e}")
        
        raise GhostAPIError("Maximum retries exceeded")

    def create_post(self, post: GhostPost) -> Dict[str, Any]:
        """Create a new post in Ghost"""
        data = {"posts": [post.to_dict()]}
        
        logger.info(f"Creating Ghost post: {post.title} (status: {post.status})")
        
        result = self._make_request_with_retry("POST", "posts/", data=data)
        
        if "posts" in result and result["posts"]:
            created_post = result["posts"][0]
            logger.info(f"Ghost post created successfully: {created_post.get('id')}")
            return created_post
        else:
            raise GhostAPIError("Unexpected response format from Ghost API")
    
    def update_post(self, post_id: str, post: GhostPost) -> Dict[str, Any]:
        """Update an existing post in Ghost"""
        data = {"posts": [post.to_dict()]}
        
        logger.info(f"Updating Ghost post: {post_id}")
        
        result = self._make_request_with_retry("PUT", f"posts/{post_id}/", data=data)
        
        if "posts" in result and result["posts"]:
            updated_post = result["posts"][0]
            logger.info(f"Ghost post updated successfully: {updated_post.get('id')}")
            return updated_post
        else:
            raise GhostAPIError("Unexpected response format from Ghost API")
    
    def get_post(self, post_id: str) -> Dict[str, Any]:
        """Get a post by ID"""
        result = self._make_request_with_retry("GET", f"posts/{post_id}/")
        
        if "posts" in result and result["posts"]:
            return result["posts"][0]
        else:
            raise GhostAPIError("Post not found")
    
    def get_post_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get a post by slug"""
        try:
            result = self._make_request_with_retry("GET", f"posts/slug/{slug}/")
            if "posts" in result and result["posts"]:
                return result["posts"][0]
        except GhostAPIError:
            pass
        return None
    
    def delete_post(self, post_id: str) -> bool:
        """Delete a post by ID"""
        logger.info(f"Deleting Ghost post: {post_id}")
        
        self._make_request_with_retry("DELETE", f"posts/{post_id}/")
        
        logger.info(f"Ghost post deleted successfully: {post_id}")
        return True
    
    def unpublish_post(self, post_id: str) -> Dict[str, Any]:
        """Unpublish a post (set status to draft)"""
        logger.info(f"Unpublishing Ghost post: {post_id}")
        
        # Get current post data
        current_post = self.get_post(post_id)
        
        # Update status to draft
        post_data = current_post.copy()
        post_data["status"] = "draft"
        
        data = {"posts": [post_data]}
        result = self._make_request_with_retry("PUT", f"posts/{post_id}/", data=data)
        
        if "posts" in result and result["posts"]:
            updated_post = result["posts"][0]
            logger.info(f"Ghost post unpublished successfully: {post_id}")
            return updated_post
        else:
            raise GhostAPIError("Unexpected response format from Ghost API")
    
    def upload_image(self, image_data: bytes, filename: str) -> str:
        """Upload image to Ghost Images API and return URL"""
        logger.info(f"Uploading image to Ghost: {filename}")
        
        files = {
            'file': (filename, image_data, 'image/jpeg')
        }
        
        result = self._make_request_with_retry("POST", "images/upload/", files=files)
        
        if "images" in result and result["images"]:
            image_url = result["images"][0]["url"]
            logger.info(f"Image uploaded successfully: {image_url}")
            return image_url
        else:
            raise GhostAPIError("Unexpected response format from image upload")
    
    def get_tags(self) -> List[Dict[str, Any]]:
        """Get all tags from Ghost"""
        result = self._make_request_with_retry("GET", "tags/", data={"limit": "all"})
        
        if "tags" in result:
            return result["tags"]
        else:
            return []
    
    def create_tag(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new tag in Ghost"""
        data = {
            "tags": [{
                "name": name,
                "description": description
            }]
        }
        
        logger.info(f"Creating Ghost tag: {name}")
        
        result = self._make_request_with_retry("POST", "tags/", data=data)
        
        if "tags" in result and result["tags"]:
            created_tag = result["tags"][0]
            logger.info(f"Ghost tag created successfully: {created_tag.get('id')}")
            return created_tag
        else:
            raise GhostAPIError("Unexpected response format from tag creation")
    
    def health_check(self) -> bool:
        """Check if Ghost API is accessible"""
        try:
            self._make_request_with_retry("GET", "site/")
            logger.info("Ghost API health check passed")
            return True
        except Exception as e:
            logger.error(f"Ghost API health check failed: {e}")
            return False


# Singleton instance for MVP
_ghost_client = None

def get_ghost_client() -> GhostClient:
    """Get singleton Ghost client instance"""
    global _ghost_client
    if _ghost_client is None:
        _ghost_client = GhostClient()
    return _ghost_client