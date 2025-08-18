"""
Unit tests for Image Handler
"""

import pytest
import io
from unittest.mock import AsyncMock, Mock, patch
from PIL import Image

import httpx

from workers.publisher.image_handler import (
    ImageHandler,
    ImageProcessingError,
    ImageDownloadError,
    ImageUploadError,
    get_image_handler
)


class TestImageHandler:
    """Test ImageHandler functionality"""
    
    @pytest.fixture
    def mock_ghost_client(self):
        """Mock Ghost client"""
        client = AsyncMock()
        client.upload_image.return_value = "https://cdn.ghost.io/uploaded_image.jpg"
        return client
    
    @pytest.fixture
    def image_handler(self, mock_ghost_client):
        """Create ImageHandler with mocked dependencies"""
        return ImageHandler(ghost_client=mock_ghost_client)
    
    @pytest.fixture
    def sample_image_data(self):
        """Create sample image data"""
        # Create a small test image
        image = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        return buffer.getvalue()
    
    def test_is_image_url_valid(self, image_handler):
        """Test image URL validation with valid URLs"""
        valid_urls = [
            'https://i.redd.it/test.jpg',
            'https://preview.redd.it/image.png',
            'https://i.imgur.com/photo.gif',
            'https://example.com/image.webp',
            'https://site.com/path/to/image.jpeg'
        ]
        
        for url in valid_urls:
            assert image_handler.is_image_url(url), f"Should recognize {url} as image URL"
    
    def test_is_image_url_invalid(self, image_handler):
        """Test image URL validation with invalid URLs"""
        invalid_urls = [
            '',
            'https://example.com/page.html',
            'https://site.com/document.pdf',
            'not-a-url',
            'https://example.com/video.mp4'
        ]
        
        for url in invalid_urls:
            assert not image_handler.is_image_url(url), f"Should not recognize {url} as image URL"
    
    def test_extract_image_urls_markdown(self, image_handler):
        """Test extracting image URLs from markdown content"""
        content = """
        Here's an image: ![alt text](https://i.redd.it/test.jpg)
        And another: ![](https://imgur.com/photo.png)
        """
        
        urls = image_handler.extract_image_urls(content)
        
        assert len(urls) == 2
        assert 'https://i.redd.it/test.jpg' in urls
        assert 'https://imgur.com/photo.png' in urls
    
    def test_extract_image_urls_html(self, image_handler):
        """Test extracting image URLs from HTML content"""
        content = '''
        <img src="https://i.redd.it/image1.jpg" alt="test">
        <img class="photo" src="https://imgur.com/image2.png" />
        '''
        
        urls = image_handler.extract_image_urls(content)
        
        assert len(urls) == 2
        assert 'https://i.redd.it/image1.jpg' in urls
        assert 'https://imgur.com/image2.png' in urls
    
    def test_extract_image_urls_plain(self, image_handler):
        """Test extracting plain image URLs from content"""
        content = """
        Check out this image: https://i.redd.it/cool.jpg
        And this one too: https://imgur.com/awesome.png?v=1
        """
        
        urls = image_handler.extract_image_urls(content)
        
        assert len(urls) == 2
        assert 'https://i.redd.it/cool.jpg' in urls
        assert 'https://imgur.com/awesome.png?v=1' in urls
    
    def test_extract_image_urls_mixed(self, image_handler):
        """Test extracting URLs from mixed content"""
        content = """
        ![Markdown image](https://i.redd.it/markdown.jpg)
        <img src="https://imgur.com/html.png" />
        Plain URL: https://i.redd.it/plain.gif
        """
        
        urls = image_handler.extract_image_urls(content)
        
        assert len(urls) == 3
        assert 'https://i.redd.it/markdown.jpg' in urls
        assert 'https://imgur.com/html.png' in urls
        assert 'https://i.redd.it/plain.gif' in urls
    
    def test_extract_image_urls_duplicates(self, image_handler):
        """Test that duplicate URLs are removed"""
        content = """
        ![Image](https://i.redd.it/same.jpg)
        <img src="https://i.redd.it/same.jpg" />
        https://i.redd.it/same.jpg
        """
        
        urls = image_handler.extract_image_urls(content)
        
        assert len(urls) == 1
        assert urls[0] == 'https://i.redd.it/same.jpg'
    
    def test_extract_image_urls_empty(self, image_handler):
        """Test extracting URLs from empty content"""
        assert image_handler.extract_image_urls("") == []
        assert image_handler.extract_image_urls(None) == []
        assert image_handler.extract_image_urls("No images here") == []
    
    @pytest.mark.asyncio
    async def test_download_image_success(self, image_handler, sample_image_data):
        """Test successful image download"""
        mock_response = Mock()
        mock_response.content = sample_image_data
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        
        with patch.object(image_handler.http_client, 'get', return_value=mock_response):
            data, content_type = await image_handler.download_image('https://example.com/test.jpg')
            
            assert data == sample_image_data
            assert content_type == 'image/jpeg'
    
    @pytest.mark.asyncio
    async def test_download_image_invalid_content_type(self, image_handler):
        """Test download with invalid content type"""
        mock_response = Mock()
        mock_response.content = b'not an image'
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.raise_for_status = Mock()
        
        with patch.object(image_handler.http_client, 'get', return_value=mock_response):
            with pytest.raises(ImageDownloadError, match="does not point to an image"):
                await image_handler.download_image('https://example.com/page.html')
    
    @pytest.mark.asyncio
    async def test_download_image_too_large(self, image_handler):
        """Test download with image too large"""
        large_data = b'x' * (11 * 1024 * 1024)  # 11MB
        
        mock_response = Mock()
        mock_response.content = large_data
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        
        with patch.object(image_handler.http_client, 'get', return_value=mock_response):
            with pytest.raises(ImageDownloadError, match="Image too large"):
                await image_handler.download_image('https://example.com/large.jpg')
    
    @pytest.mark.asyncio
    async def test_download_image_http_error(self, image_handler):
        """Test download with HTTP error"""
        with patch.object(image_handler.http_client, 'get', side_effect=httpx.RequestError("Network error")):
            with pytest.raises(ImageDownloadError, match="Failed to download image"):
                await image_handler.download_image('https://example.com/test.jpg')
    
    def test_process_image_basic(self, image_handler, sample_image_data):
        """Test basic image processing"""
        processed_data, content_type = image_handler.process_image(sample_image_data, 'image/jpeg')
        
        assert isinstance(processed_data, bytes)
        assert content_type == 'image/jpeg'
        assert len(processed_data) > 0
    
    def test_process_image_png_to_png(self, image_handler):
        """Test PNG image processing (should remain PNG)"""
        # Create PNG image
        image = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        png_data = buffer.getvalue()
        
        processed_data, content_type = image_handler.process_image(png_data, 'image/png')
        
        assert content_type == 'image/png'
        assert len(processed_data) > 0
    
    def test_process_image_resize_large(self, image_handler):
        """Test resizing large image"""
        # Create large image
        large_image = Image.new('RGB', (3000, 3000), color='blue')
        buffer = io.BytesIO()
        large_image.save(buffer, format='JPEG')
        large_data = buffer.getvalue()
        
        processed_data, content_type = image_handler.process_image(large_data, 'image/jpeg')
        
        # Verify image was resized
        processed_image = Image.open(io.BytesIO(processed_data))
        assert processed_image.size[0] <= 2048
        assert processed_image.size[1] <= 2048
    
    def test_process_image_invalid_data(self, image_handler):
        """Test processing invalid image data"""
        with pytest.raises(ImageProcessingError, match="Failed to process image"):
            image_handler.process_image(b'not an image', 'image/jpeg')
    
    def test_generate_filename(self, image_handler):
        """Test filename generation"""
        url = 'https://i.redd.it/cool_image.jpg'
        filename = image_handler.generate_filename(url, 'image/jpeg')
        
        assert filename.endswith('.jpg')
        assert 'cool_image' in filename
        assert len(filename) > len('cool_image.jpg')  # Should include hash
    
    def test_generate_filename_no_path(self, image_handler):
        """Test filename generation with URL without meaningful path"""
        url = 'https://example.com/'
        filename = image_handler.generate_filename(url, 'image/png')
        
        assert filename.endswith('.png')
        assert 'reddit_image' in filename
    
    def test_generate_filename_special_chars(self, image_handler):
        """Test filename generation with special characters"""
        url = 'https://example.com/image with spaces & symbols!.jpg'
        filename = image_handler.generate_filename(url, 'image/jpeg')
        
        assert filename.endswith('.jpg')
        # Special characters should be replaced with underscores
        assert ' ' not in filename
        assert '&' not in filename
        assert '!' not in filename
    
    @pytest.mark.asyncio
    async def test_upload_to_ghost_success(self, image_handler, sample_image_data):
        """Test successful upload to Ghost"""
        cdn_url = await image_handler.upload_to_ghost(sample_image_data, 'test.jpg')
        
        assert cdn_url == "https://cdn.ghost.io/uploaded_image.jpg"
        image_handler.ghost_client.upload_image.assert_called_once_with(sample_image_data, 'test.jpg')
    
    @pytest.mark.asyncio
    async def test_upload_to_ghost_no_client(self, sample_image_data):
        """Test upload without Ghost client"""
        handler = ImageHandler(ghost_client=None)
        
        with pytest.raises(ImageUploadError, match="Ghost client not initialized"):
            await handler.upload_to_ghost(sample_image_data, 'test.jpg')
    
    @pytest.mark.asyncio
    async def test_upload_to_ghost_api_error(self, image_handler, sample_image_data):
        """Test upload with Ghost API error"""
        from workers.publisher.ghost_client import GhostAPIError
        
        image_handler.ghost_client.upload_image.side_effect = GhostAPIError("Upload failed")
        
        with pytest.raises(ImageUploadError, match="Failed to upload image to Ghost"):
            await image_handler.upload_to_ghost(sample_image_data, 'test.jpg')
    
    @pytest.mark.asyncio
    async def test_process_and_upload_image_success(self, image_handler, sample_image_data):
        """Test complete image processing and upload"""
        url = 'https://i.redd.it/test.jpg'
        
        # Mock download
        mock_response = Mock()
        mock_response.content = sample_image_data
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        
        with patch.object(image_handler.http_client, 'get', return_value=mock_response):
            cdn_url = await image_handler.process_and_upload_image(url)
            
            assert cdn_url == "https://cdn.ghost.io/uploaded_image.jpg"
    
    @pytest.mark.asyncio
    async def test_process_and_upload_image_download_failure(self, image_handler):
        """Test image processing with download failure"""
        url = 'https://i.redd.it/test.jpg'
        
        with patch.object(image_handler.http_client, 'get', side_effect=httpx.RequestError("Network error")):
            cdn_url = await image_handler.process_and_upload_image(url)
            
            assert cdn_url is None
    
    @pytest.mark.asyncio
    async def test_process_content_images_success(self, image_handler, sample_image_data):
        """Test processing all images in content"""
        content = """
        Here's an image: ![alt](https://i.redd.it/test1.jpg)
        And another: https://imgur.com/test2.png
        """
        
        # Mock download
        mock_response = Mock()
        mock_response.content = sample_image_data
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        
        with patch.object(image_handler.http_client, 'get', return_value=mock_response):
            updated_content, url_mapping = await image_handler.process_content_images(content)
            
            assert len(url_mapping) == 2
            assert 'https://i.redd.it/test1.jpg' in url_mapping
            assert 'https://imgur.com/test2.png' in url_mapping
            
            # URLs should be replaced in content
            for original_url, cdn_url in url_mapping.items():
                assert original_url not in updated_content
                assert cdn_url in updated_content
    
    @pytest.mark.asyncio
    async def test_process_content_images_no_images(self, image_handler):
        """Test processing content with no images"""
        content = "This is just text with no images."
        
        updated_content, url_mapping = await image_handler.process_content_images(content)
        
        assert updated_content == content
        assert url_mapping == {}
    
    @pytest.mark.asyncio
    async def test_process_content_images_empty_content(self, image_handler):
        """Test processing empty content"""
        updated_content, url_mapping = await image_handler.process_content_images("")
        
        assert updated_content == ""
        assert url_mapping == {}
    
    @pytest.mark.asyncio
    async def test_get_feature_image_from_content(self, image_handler, sample_image_data):
        """Test getting feature image from post content"""
        post_data = {
            'content': 'Check out this image: ![alt](https://i.redd.it/feature.jpg)'
        }
        
        # Mock download
        mock_response = Mock()
        mock_response.content = sample_image_data
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status = Mock()
        
        with patch.object(image_handler.http_client, 'get', return_value=mock_response):
            feature_url = await image_handler.get_feature_image(post_data)
            
            assert feature_url == "https://cdn.ghost.io/uploaded_image.jpg"
    
    @pytest.mark.asyncio
    async def test_get_feature_image_existing(self, image_handler):
        """Test getting feature image when already specified"""
        post_data = {
            'feature_image': 'https://existing.com/feature.jpg',
            'content': 'Some content with ![alt](https://i.redd.it/other.jpg)'
        }
        
        feature_url = await image_handler.get_feature_image(post_data)
        
        assert feature_url == 'https://existing.com/feature.jpg'
    
    @pytest.mark.asyncio
    async def test_get_feature_image_no_images(self, image_handler):
        """Test getting feature image with no images in content"""
        post_data = {
            'content': 'Just text, no images here.'
        }
        
        feature_url = await image_handler.get_feature_image(post_data)
        
        assert feature_url is None
    
    @pytest.mark.asyncio
    async def test_close(self, image_handler):
        """Test closing the image handler"""
        mock_client = AsyncMock()
        image_handler.http_client = mock_client
        
        await image_handler.close()
        
        mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_get_image_handler_singleton():
    """Test singleton pattern for image handler"""
    handler1 = await get_image_handler()
    handler2 = await get_image_handler()
    
    assert handler1 is handler2


@pytest.mark.asyncio
async def test_get_image_handler_with_client():
    """Test getting image handler with Ghost client"""
    mock_client = AsyncMock()
    
    # Reset singleton
    import workers.publisher.image_handler
    workers.publisher.image_handler._image_handler = None
    
    handler = await get_image_handler(mock_client)
    
    assert handler.ghost_client is mock_client