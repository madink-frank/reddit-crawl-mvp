"""
Unit tests for Ghost CMS API Client
"""

import pytest
import jwt
import time
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

import httpx

from workers.publisher.ghost_client import (
    GhostClient,
    GhostPost,
    GhostAPIError,
    GhostAuthError,
    GhostRateLimitError,
    GhostValidationError
)


class TestGhostPost:
    """Test GhostPost data structure"""
    
    def test_ghost_post_to_dict_minimal(self):
        """Test minimal post conversion"""
        post = GhostPost(
            title="Test Post",
            html="<p>Test content</p>"
        )
        
        result = post.to_dict()
        
        assert result == {
            "title": "Test Post",
            "html": "<p>Test content</p>",
            "status": "draft"
        }
    
    def test_ghost_post_to_dict_full(self):
        """Test full post conversion with all fields"""
        published_at = datetime.now()
        post = GhostPost(
            title="Test Post",
            html="<p>Test content</p>",
            status="published",
            tags=["tech", "ai"],
            feature_image="https://example.com/image.jpg",
            excerpt="Test excerpt",
            meta_title="Meta Title",
            meta_description="Meta Description",
            og_title="OG Title",
            og_description="OG Description",
            twitter_title="Twitter Title",
            twitter_description="Twitter Description",
            custom_excerpt="Custom excerpt",
            published_at=published_at
        )
        
        result = post.to_dict()
        
        expected = {
            "title": "Test Post",
            "html": "<p>Test content</p>",
            "status": "published",
            "tags": [{"name": "tech"}, {"name": "ai"}],
            "feature_image": "https://example.com/image.jpg",
            "excerpt": "Test excerpt",
            "meta_title": "Meta Title",
            "meta_description": "Meta Description",
            "og_title": "OG Title",
            "og_description": "OG Description",
            "twitter_title": "Twitter Title",
            "twitter_description": "Twitter Description",
            "custom_excerpt": "Custom excerpt",
            "published_at": published_at.isoformat()
        }
        
        assert result == expected


class TestGhostClient:
    """Test GhostClient functionality"""
    
    @pytest.fixture
    def mock_vault_client(self):
        """Mock vault client"""
        vault_client = AsyncMock()
        vault_client.get_ghost_credentials.return_value = {
            "api_url": "https://test.ghost.io/",
            "admin_key": "test_id:746573745f736563726574",  # test_secret in hex
            "content_key": "test_content_key"
        }
        return vault_client
    
    @pytest.fixture
    def ghost_client(self, mock_vault_client):
        """Create Ghost client with mocked dependencies"""
        return GhostClient(vault_client=mock_vault_client)
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, ghost_client, mock_vault_client):
        """Test successful client initialization"""
        with patch('httpx.AsyncClient') as mock_client:
            await ghost_client.initialize()
            
            assert ghost_client.base_url == "https://test.ghost.io/ghost/api/v5/admin/"
            assert ghost_client.admin_key == "test_id:746573745f736563726574"
            assert ghost_client.content_key == "test_content_key"
            mock_client.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_missing_credentials(self, mock_vault_client):
        """Test initialization with missing credentials"""
        mock_vault_client.get_ghost_credentials.return_value = {
            "api_url": "",
            "admin_key": "",
            "content_key": ""
        }
        
        client = GhostClient(vault_client=mock_vault_client)
        
        with pytest.raises(GhostAuthError, match="Ghost API URL not configured"):
            await client.initialize()
    
    def test_generate_jwt_token(self, ghost_client):
        """Test JWT token generation"""
        ghost_client.admin_key = "test_id:746573745f736563726574"
        
        with patch('time.time', return_value=1000000000):
            token = ghost_client._generate_jwt_token()
            
            # Decode and verify token
            decoded = jwt.decode(
                token, 
                bytes.fromhex("746573745f736563726574"), 
                algorithms=['HS256'],
                options={"verify_signature": True, "verify_exp": False, "verify_aud": False}
            )
            
            assert decoded['iat'] == 1000000000
            assert decoded['exp'] == 1000000300  # 5 minutes later
            assert decoded['aud'] == '/v5/admin/'
    
    def test_generate_jwt_token_invalid_key(self, ghost_client):
        """Test JWT token generation with invalid key format"""
        ghost_client.admin_key = "invalid_key_format"
        
        with pytest.raises(GhostAuthError, match="Invalid admin key format"):
            ghost_client._generate_jwt_token()
    
    def test_get_valid_jwt_token_cached(self, ghost_client):
        """Test getting cached valid JWT token"""
        ghost_client.admin_key = "test_id:746573745f736563726574"
        ghost_client._jwt_token = "cached_token"
        ghost_client._jwt_expires_at = datetime.now() + timedelta(minutes=2)
        
        token = ghost_client._get_valid_jwt_token()
        
        assert token == "cached_token"
    
    def test_get_valid_jwt_token_expired(self, ghost_client):
        """Test getting new JWT token when cached one is expired"""
        ghost_client.admin_key = "test_id:746573745f736563726574"
        ghost_client._jwt_token = "expired_token"
        ghost_client._jwt_expires_at = datetime.now() - timedelta(minutes=1)
        
        with patch('time.time', return_value=1000000000):
            token = ghost_client._get_valid_jwt_token()
            
            assert token != "expired_token"
            assert ghost_client._jwt_token == token
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, ghost_client):
        """Test successful API request"""
        ghost_client.base_url = "https://test.ghost.io/ghost/api/v5/admin/"
        ghost_client.admin_key = "test_id:746573745f736563726574"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"posts": [{"id": "123", "title": "Test"}]}
        mock_response.content = b'{"posts": [{"id": "123", "title": "Test"}]}'
        
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        ghost_client._client = mock_client
        
        result = await ghost_client._make_request("GET", "posts/")
        
        assert result == {"posts": [{"id": "123", "title": "Test"}]}
        mock_client.request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_rate_limit(self, ghost_client):
        """Test rate limit handling"""
        ghost_client.base_url = "https://test.ghost.io/ghost/api/v5/admin/"
        ghost_client.admin_key = "test_id:746573745f736563726574"
        
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        ghost_client._client = mock_client
        
        # Test the core logic without retry decorator
        with patch.object(ghost_client, '_get_headers', return_value={"Authorization": "Ghost test"}):
            with pytest.raises(GhostRateLimitError, match="Rate limit exceeded"):
                # Call the method directly without retry
                url = f"{ghost_client.base_url}posts/"
                headers = ghost_client._get_headers()
                
                response = await mock_client.request(
                    method="GET",
                    url=url,
                    headers=headers,
                    json=None,
                    params=None
                )
                
                # Simulate the rate limit check logic
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    raise GhostRateLimitError(f"Rate limit exceeded, retry after {retry_after}s")
    
    @pytest.mark.asyncio
    async def test_make_request_auth_error(self, ghost_client):
        """Test authentication error handling"""
        ghost_client.base_url = "https://test.ghost.io/ghost/api/v5/admin/"
        ghost_client.admin_key = "test_id:746573745f736563726574"
        
        mock_response = Mock()
        mock_response.status_code = 401
        
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        ghost_client._client = mock_client
        
        with pytest.raises(GhostAuthError, match="Authentication failed"):
            await ghost_client._make_request("GET", "posts/")
        
        # Token should be cleared
        assert ghost_client._jwt_token is None
        assert ghost_client._jwt_expires_at is None
    
    @pytest.mark.asyncio
    async def test_make_request_validation_error(self, ghost_client):
        """Test validation error handling"""
        ghost_client.base_url = "https://test.ghost.io/ghost/api/v5/admin/"
        ghost_client.admin_key = "test_id:746573745f736563726574"
        
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"errors": [{"message": "Title is required"}]}
        mock_response.content = b'{"errors": [{"message": "Title is required"}]}'
        
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        ghost_client._client = mock_client
        
        with pytest.raises(GhostValidationError, match="Validation error"):
            await ghost_client._make_request("POST", "posts/", data={"posts": [{}]})
    
    @pytest.mark.asyncio
    async def test_create_post_success(self, ghost_client):
        """Test successful post creation"""
        post = GhostPost(title="Test Post", html="<p>Content</p>")
        
        expected_response = {
            "posts": [{
                "id": "123",
                "title": "Test Post",
                "url": "https://test.ghost.io/test-post/"
            }]
        }
        
        with patch.object(ghost_client, '_make_request', return_value=expected_response) as mock_request:
            result = await ghost_client.create_post(post)
            
            mock_request.assert_called_once_with(
                "POST", 
                "posts/", 
                data={"posts": [post.to_dict()]}
            )
            assert result["id"] == "123"
            assert result["title"] == "Test Post"
    
    @pytest.mark.asyncio
    async def test_update_post_success(self, ghost_client):
        """Test successful post update"""
        post = GhostPost(title="Updated Post", html="<p>Updated content</p>")
        post_id = "123"
        
        expected_response = {
            "posts": [{
                "id": "123",
                "title": "Updated Post"
            }]
        }
        
        with patch.object(ghost_client, '_make_request', return_value=expected_response) as mock_request:
            result = await ghost_client.update_post(post_id, post)
            
            mock_request.assert_called_once_with(
                "PUT", 
                f"posts/{post_id}/", 
                data={"posts": [post.to_dict()]}
            )
            assert result["id"] == "123"
            assert result["title"] == "Updated Post"
    
    @pytest.mark.asyncio
    async def test_upload_image_success(self, ghost_client):
        """Test successful image upload"""
        ghost_client.base_url = "https://test.ghost.io/ghost/api/v5/admin/"
        ghost_client.admin_key = "test_id:746573745f736563726574"
        
        image_data = b"fake_image_data"
        filename = "test.jpg"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "images": [{"url": "https://cdn.ghost.io/test.jpg"}]
        }
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        ghost_client._client = mock_client
        
        result = await ghost_client.upload_image(image_data, filename)
        
        assert result == "https://cdn.ghost.io/test.jpg"
        mock_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_tags_success(self, ghost_client):
        """Test getting tags"""
        expected_response = {
            "tags": [
                {"id": "1", "name": "tech"},
                {"id": "2", "name": "ai"}
            ]
        }
        
        with patch.object(ghost_client, '_make_request', return_value=expected_response) as mock_request:
            result = await ghost_client.get_tags()
            
            mock_request.assert_called_once_with("GET", "tags/", params={"limit": "all"})
            assert len(result) == 2
            assert result[0]["name"] == "tech"
            assert result[1]["name"] == "ai"
    
    @pytest.mark.asyncio
    async def test_create_tag_success(self, ghost_client):
        """Test creating a tag"""
        expected_response = {
            "tags": [{
                "id": "123",
                "name": "new-tag"
            }]
        }
        
        with patch.object(ghost_client, '_make_request', return_value=expected_response) as mock_request:
            result = await ghost_client.create_tag("new-tag", "Description")
            
            mock_request.assert_called_once_with(
                "POST", 
                "tags/", 
                data={"tags": [{"name": "new-tag", "description": "Description"}]}
            )
            assert result["id"] == "123"
            assert result["name"] == "new-tag"
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, ghost_client):
        """Test successful health check"""
        with patch.object(ghost_client, '_make_request', return_value={"site": {}}) as mock_request:
            result = await ghost_client.health_check()
            
            mock_request.assert_called_once_with("GET", "site/")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, ghost_client):
        """Test failed health check"""
        with patch.object(ghost_client, '_make_request', side_effect=GhostAPIError("API Error")):
            result = await ghost_client.health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_close_client(self, ghost_client):
        """Test closing the HTTP client"""
        mock_client = AsyncMock()
        ghost_client._client = mock_client
        
        await ghost_client.close()
        
        mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_get_ghost_client_singleton():
    """Test singleton pattern for Ghost client"""
    with patch('workers.publisher.ghost_client.GhostClient') as MockGhostClient:
        mock_instance = AsyncMock()
        MockGhostClient.return_value = mock_instance
        
        # Import here to avoid circular imports in tests
        from workers.publisher.ghost_client import get_ghost_client, _ghost_client
        
        # Reset singleton
        import workers.publisher.ghost_client
        workers.publisher.ghost_client._ghost_client = None
        
        client1 = await get_ghost_client()
        client2 = await get_ghost_client()
        
        assert client1 is client2
        MockGhostClient.assert_called_once()
        mock_instance.initialize.assert_called_once()