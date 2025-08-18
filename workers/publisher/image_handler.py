"""
Image Processing and Upload Handler for Ghost CMS (MVP Synchronous Version)

Handles downloading Reddit media URLs locally and uploading to Ghost Images API
with fallback to default OG image.
"""

import hashlib
import mimetypes
import io
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import re
import logging

import requests
from PIL import Image, ImageOps

from workers.publisher.ghost_client import GhostClient, GhostAPIError
from app.config import settings

logger = logging.getLogger(__name__)


class ImageProcessingError(Exception):
    """Base exception for image processing errors"""
    pass


class ImageDownloadError(ImageProcessingError):
    """Error downloading image from URL"""
    pass


class ImageUploadError(ImageProcessingError):
    """Error uploading image to Ghost"""
    pass


class ImageHandler:
    """Handles image processing and upload for Ghost CMS (MVP Synchronous Version)"""
    
    def __init__(self, ghost_client: Optional[GhostClient] = None):
        self.ghost_client = ghost_client
        
        # Supported image formats
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        
        # Image processing settings
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        self.max_dimensions = (1920, 1080)  # Max width/height for MVP
        self.quality = 85  # JPEG quality
        
        # Default OG image from environment
        self.default_og_image_url = settings.default_og_image_url
        
        # Reddit-specific URL patterns
        self.reddit_image_patterns = [
            r'https?://i\.redd\.it/.*\.(jpg|jpeg|png|gif|webp)',
            r'https?://preview\.redd\.it/.*\.(jpg|jpeg|png|gif|webp)',
            r'https?://external-preview\.redd\.it/.*\.(jpg|jpeg|png|gif|webp)',
            r'https?://i\.imgur\.com/.*\.(jpg|jpeg|png|gif|webp)',
            r'https?://imgur\.com/.*\.(jpg|jpeg|png|gif|webp)'
        ]
    
    def is_image_url(self, url: str) -> bool:
        """Check if URL points to an image"""
        if not url:
            return False
        
        # Check file extension
        parsed_url = urlparse(url.lower())
        path = parsed_url.path
        
        # Check for direct image extensions
        for ext in self.supported_formats:
            if path.endswith(ext):
                return True
        
        # Check Reddit-specific patterns
        for pattern in self.reddit_image_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        
        return False
    
    def extract_image_urls(self, content: str) -> List[str]:
        """Extract image URLs from content"""
        if not content:
            return []
        
        image_urls = []
        
        # Find markdown image syntax: ![alt](url)
        markdown_pattern = r'!\[.*?\]\((https?://[^\s\)]+)\)'
        markdown_matches = re.findall(markdown_pattern, content)
        image_urls.extend(markdown_matches)
        
        # Find HTML img tags: <img src="url">
        html_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        html_matches = re.findall(html_pattern, content, re.IGNORECASE)
        image_urls.extend(html_matches)
        
        # Find plain URLs that look like images
        url_pattern = r'https?://[^\s<>"]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s<>"]*)?'
        url_matches = re.findall(url_pattern, content, re.IGNORECASE)
        image_urls.extend(url_matches)
        
        # Filter and validate URLs
        valid_urls = []
        for url in image_urls:
            if self.is_image_url(url):
                valid_urls.append(url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in valid_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        logger.debug(
            "Extracted image URLs from content",
            total_found=len(image_urls),
            valid_urls=len(unique_urls)
        )
        
        return unique_urls
    
    def download_image(self, url: str) -> Tuple[bytes, str]:
        """Download image from URL locally and return data with content type"""
        try:
            logger.debug(f"Downloading image: {url}")
            
            headers = {
                'User-Agent': 'Reddit-Ghost-Publisher/1.0 (Image Processor)'
            }
            
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                # Try to guess from URL
                parsed_url = urlparse(url)
                guessed_type, _ = mimetypes.guess_type(parsed_url.path)
                if guessed_type and guessed_type.startswith('image/'):
                    content_type = guessed_type
                else:
                    raise ImageDownloadError(f"URL does not point to an image: {content_type}")
            
            # Check file size
            content_length = len(response.content)
            if content_length > self.max_image_size:
                raise ImageDownloadError(f"Image too large: {content_length} bytes")
            
            logger.info(f"Image downloaded successfully: {url} ({content_length} bytes)")
            
            return response.content, content_type
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download image {url}: {e}")
            raise ImageDownloadError(f"Failed to download image: {e}")
    
    def process_image(self, image_data: bytes, content_type: str) -> Tuple[bytes, str]:
        """Process image data (resize, optimize, etc.)"""
        try:
            # Open image with PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary (for JPEG output)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Auto-orient based on EXIF data
            image = ImageOps.exif_transpose(image)
            
            # Resize if too large
            if image.size[0] > self.max_dimensions[0] or image.size[1] > self.max_dimensions[1]:
                logger.debug(
                    "Resizing image",
                    original_size=image.size,
                    max_dimensions=self.max_dimensions
                )
                image.thumbnail(self.max_dimensions, Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = io.BytesIO()
            
            # Determine output format
            if content_type in ('image/png', 'image/gif'):
                # Keep original format for PNG/GIF
                if content_type == 'image/png':
                    image.save(output, format='PNG', optimize=True)
                    output_content_type = 'image/png'
                else:
                    # For GIF, convert to PNG to avoid animation issues
                    image.save(output, format='PNG', optimize=True)
                    output_content_type = 'image/png'
            else:
                # Convert to JPEG for other formats
                image.save(output, format='JPEG', quality=self.quality, optimize=True)
                output_content_type = 'image/jpeg'
            
            processed_data = output.getvalue()
            
            logger.debug(
                "Image processed successfully",
                original_size=len(image_data),
                processed_size=len(processed_data),
                dimensions=image.size,
                output_format=output_content_type
            )
            
            return processed_data, output_content_type
            
        except Exception as e:
            logger.error("Failed to process image", error=str(e))
            raise ImageProcessingError(f"Failed to process image: {e}")
    
    def generate_filename(self, url: str, content_type: str) -> str:
        """Generate a filename for the image"""
        # Create hash of URL for uniqueness
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Get extension from content type
        extension_map = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp'
        }
        
        extension = extension_map.get(content_type, '.jpg')
        
        # Try to get a meaningful name from URL
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        
        if path_parts and path_parts[-1]:
            # Use the last part of the path
            base_name = path_parts[-1]
            # Remove existing extension
            base_name = re.sub(r'\.[^.]+$', '', base_name)
            # Clean up the name
            base_name = re.sub(r'[^a-zA-Z0-9_-]', '_', base_name)[:20]
        else:
            base_name = 'reddit_image'
        
        return f"{base_name}_{url_hash}{extension}"
    
    def upload_to_ghost(self, image_data: bytes, filename: str) -> str:
        """Upload image to Ghost Images API and return CDN URL"""
        if not self.ghost_client:
            raise ImageUploadError("Ghost client not initialized")
        
        try:
            logger.debug(f"Uploading image to Ghost: {filename} ({len(image_data)} bytes)")
            
            cdn_url = self.ghost_client.upload_image(image_data, filename)
            
            logger.info(f"Image uploaded to Ghost successfully: {cdn_url}")
            
            return cdn_url
            
        except GhostAPIError as e:
            logger.error(f"Failed to upload image to Ghost {filename}: {e}")
            raise ImageUploadError(f"Failed to upload image to Ghost: {e}")
    
    def process_and_upload_image(self, url: str) -> Optional[str]:
        """Download, process, and upload a single image with fallback"""
        try:
            # Download image
            image_data, content_type = self.download_image(url)
            
            # Process image
            processed_data, processed_content_type = self.process_image(image_data, content_type)
            
            # Generate filename
            filename = self.generate_filename(url, processed_content_type)
            
            # Upload to Ghost
            cdn_url = self.upload_to_ghost(processed_data, filename)
            
            return cdn_url
            
        except (ImageDownloadError, ImageProcessingError, ImageUploadError) as e:
            logger.warning(f"Failed to process image {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing image {url}: {e}")
            return None
    
    def process_content_images(self, content: str) -> Tuple[str, Dict[str, str]]:
        """Process all images in content and return updated content with URL mapping"""
        if not content:
            return content, {}
        
        # Extract image URLs
        image_urls = self.extract_image_urls(content)
        
        if not image_urls:
            logger.debug("No images found in content")
            return content, {}
        
        logger.info(f"Processing {len(image_urls)} images from content")
        
        # Process images sequentially (MVP - no concurrency)
        url_mapping = {}
        successful_uploads = 0
        
        for url in image_urls:
            cdn_url = self.process_and_upload_image(url)
            if cdn_url:
                url_mapping[url] = cdn_url
                successful_uploads += 1
        
        logger.info(f"Image processing completed: {successful_uploads}/{len(image_urls)} successful")
        
        # Replace URLs in content
        updated_content = content
        for original_url, cdn_url in url_mapping.items():
            updated_content = updated_content.replace(original_url, cdn_url)
        
        return updated_content, url_mapping
    
    def get_feature_image(self, post_data: Dict) -> str:
        """Get feature image for the post with fallback to default OG image
        
        MVP requirement: Always return an image URL (use default if no media)
        """
        # Check if there's already a feature image specified
        if post_data.get('feature_image'):
            return post_data['feature_image']
        
        # Extract first image from content
        content = post_data.get('content', '')
        image_urls = self.extract_image_urls(content)
        
        if image_urls:
            # Use the first image as feature image
            first_image_url = image_urls[0]
            
            logger.info(f"Processing feature image: {first_image_url}")
            
            cdn_url = self.process_and_upload_image(first_image_url)
            
            if cdn_url:
                logger.info(f"Feature image processed successfully: {cdn_url}")
                return cdn_url
            else:
                logger.warning("Failed to process feature image, using default")
        
        # Fallback to default OG image
        if self.default_og_image_url:
            logger.info(f"Using default OG image: {self.default_og_image_url}")
            return self.default_og_image_url
        else:
            logger.warning("No default OG image configured")
            return ""
    
    def validate_post_images(self, post_data: Dict) -> bool:
        """Validate that post has images or default OG image is available
        
        MVP requirement: Ensure all posts have feature images before publishing
        """
        # Check if there's already a feature image
        if post_data.get('feature_image'):
            return True
        
        # Check if content has images
        content = post_data.get('content', '')
        image_urls = self.extract_image_urls(content)
        
        if image_urls:
            return True
        
        # Check if default OG image is configured
        if self.default_og_image_url:
            return True
        
        logger.warning("Post has no images and no default OG image configured")
        return False


# Singleton instance for MVP
_image_handler = None

def get_image_handler(ghost_client: Optional[GhostClient] = None) -> ImageHandler:
    """Get singleton image handler instance"""
    global _image_handler
    if _image_handler is None:
        _image_handler = ImageHandler(ghost_client)
    elif ghost_client and _image_handler.ghost_client != ghost_client:
        # Update ghost client if provided
        _image_handler.ghost_client = ghost_client
    return _image_handler