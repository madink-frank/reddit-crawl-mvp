"""
Metadata Processor for Ghost CMS Publishing (MVP Version)

Handles LLM tag mapping to Ghost tags and publishing idempotency.
"""

import re
import json
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from workers.publisher.ghost_client import GhostClient, GhostAPIError
from app.config import settings

logger = logging.getLogger(__name__)


class MetadataProcessor:
    """Processes metadata for Ghost CMS posts (MVP Version)"""
    
    def __init__(self, ghost_client: Optional[GhostClient] = None):
        self.ghost_client = ghost_client
        self._tag_cache = {}
        self._tag_cache_timestamp = None
        self._cache_ttl = 3600  # 1 hour
        
        # Tag normalization rules for MVP (simplified)
        self.tag_normalizations = {
            'artificial intelligence': 'ai',
            'machine learning': 'ml',
            'user experience': 'ux',
            'user interface': 'ui',
            'programming': 'coding',
            'development': 'dev',
            'technology': 'tech',
            'business': 'biz',
            'startup': 'startups'
        }
    
    def normalize_tag(self, tag: str) -> str:
        """Normalize a tag name (MVP - simplified rules)"""
        if not tag:
            return ""
        
        # Convert to lowercase and strip whitespace
        normalized = tag.lower().strip()
        
        # Apply specific normalizations
        if normalized in self.tag_normalizations:
            normalized = self.tag_normalizations[normalized]
        
        # Remove special characters except hyphens
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        
        # Replace spaces with hyphens
        normalized = re.sub(r'\s+', '-', normalized)
        
        # Remove multiple consecutive hyphens
        normalized = re.sub(r'-+', '-', normalized)
        
        # Remove leading/trailing hyphens
        normalized = normalized.strip('-')
        
        return normalized
    
    def extract_tags_from_llm(self, llm_tags: Any) -> List[str]:
        """Extract and normalize tags from LLM output (MVP - 3-5 tags limit)"""
        tags = []
        
        if not llm_tags:
            return tags
        
        # Handle different input formats
        if isinstance(llm_tags, str):
            try:
                # Try to parse as JSON
                llm_tags = json.loads(llm_tags)
            except json.JSONDecodeError:
                # Treat as comma-separated string
                llm_tags = [tag.strip() for tag in llm_tags.split(',')]
        
        if isinstance(llm_tags, list):
            for tag_item in llm_tags:
                if isinstance(tag_item, str):
                    tag = self.normalize_tag(tag_item)
                    if tag and len(tag) >= 2:  # Minimum tag length
                        tags.append(tag)
        
        elif isinstance(llm_tags, dict):
            # Handle dictionary format
            for key in llm_tags.keys():
                tag = self.normalize_tag(str(key))
                if tag and len(tag) >= 2:
                    tags.append(tag)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        
        # MVP requirement: 3-5 tags limit
        return unique_tags[:5]
    
    def generate_content_hash(self, post_data: Dict[str, Any]) -> str:
        """Generate content hash for idempotency checking
        
        MVP requirement: content_hash = sha256(title + body + media_urls)
        """
        title = post_data.get('title', '')
        body = post_data.get('content', '')
        
        # Get media URLs from content
        media_urls = []
        if body:
            # Extract image URLs (handle None body)
            import re
            url_pattern = r'https?://[^\s<>"]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s<>"]*)?'
            media_urls = re.findall(url_pattern, body or '', re.IGNORECASE)
        
        # Create hash input (handle None values)
        title_str = title or ''
        body_str = body or ''
        hash_input = title_str + body_str + ''.join(sorted(media_urls))
        
        # Generate SHA256 hash
        content_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        logger.debug(f"Generated content hash: {content_hash[:8]}...")
        
        return content_hash
    
    def get_existing_ghost_tags(self) -> Dict[str, str]:
        """Get existing tags from Ghost CMS with caching (MVP - synchronous)"""
        now = datetime.now()
        
        # Check cache
        if (self._tag_cache and self._tag_cache_timestamp and 
            (now - self._tag_cache_timestamp).seconds < self._cache_ttl):
            return self._tag_cache
        
        if not self.ghost_client:
            logger.warning("Ghost client not available for tag fetching")
            return {}
        
        try:
            tags = self.ghost_client.get_tags()
            
            # Build name -> id mapping
            tag_mapping = {}
            for tag in tags:
                tag_name = tag.get('name', '').lower()
                tag_id = tag.get('id')
                if tag_name and tag_id:
                    tag_mapping[tag_name] = tag_id
            
            # Update cache
            self._tag_cache = tag_mapping
            self._tag_cache_timestamp = now
            
            logger.debug(f"Fetched {len(tag_mapping)} existing Ghost tags")
            
            return tag_mapping
            
        except Exception as e:
            logger.error(f"Failed to fetch Ghost tags: {e}")
            return {}
    
    def create_missing_tags(self, tag_names: List[str]) -> Dict[str, str]:
        """Create missing tags in Ghost CMS (MVP - synchronous)"""
        if not self.ghost_client:
            return {}
        
        existing_tags = self.get_existing_ghost_tags()
        created_tags = {}
        
        for tag_name in tag_names:
            normalized_name = tag_name.lower()
            
            if normalized_name not in existing_tags:
                try:
                    # Create the tag
                    created_tag = self.ghost_client.create_tag(
                        name=tag_name,
                        description=f"Auto-generated tag from Reddit content"
                    )
                    
                    tag_id = created_tag.get('id')
                    if tag_id:
                        created_tags[normalized_name] = tag_id
                        # Update cache
                        self._tag_cache[normalized_name] = tag_id
                        
                        logger.info(f"Created new Ghost tag: {tag_name}")
                
                except GhostAPIError as e:
                    logger.warning(f"Failed to create Ghost tag {tag_name}: {e}")
                    continue
        
        return created_tags
    
    def map_llm_tags_to_ghost(self, llm_tags: Any) -> List[str]:
        """Map LLM tags to Ghost tag names (MVP - simplified)"""
        # Extract tags from LLM output
        extracted_tags = self.extract_tags_from_llm(llm_tags)
        
        if not extracted_tags:
            logger.warning("No tags extracted from LLM output")
            return []
        
        # Ensure tags exist in Ghost (create if necessary)
        self.create_missing_tags(extracted_tags)
        
        logger.info(f"Mapped {len(extracted_tags)} LLM tags to Ghost: {extracted_tags}")
        
        return extracted_tags
    
    def check_publishing_idempotency(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if post should be published based on content hash
        
        MVP requirement: Compare content_hash, skip if same, update if different
        """
        reddit_post_id = post_data.get('reddit_post_id')
        if not reddit_post_id:
            return {'should_publish': True, 'action': 'create', 'reason': 'no_reddit_post_id'}
        
        # Generate current content hash
        current_hash = self.generate_content_hash(post_data)
        
        # Check if post already exists in Ghost by reddit_post_id
        # This would typically involve checking the database or Ghost API
        # For MVP, we'll assume this is handled by the calling code
        
        existing_hash = post_data.get('existing_content_hash')
        
        if not existing_hash:
            # No existing post, should create
            return {
                'should_publish': True,
                'action': 'create',
                'reason': 'new_post',
                'content_hash': current_hash
            }
        
        if existing_hash == current_hash:
            # Content unchanged, skip
            return {
                'should_publish': False,
                'action': 'skip',
                'reason': 'content_unchanged',
                'content_hash': current_hash
            }
        else:
            # Content changed, should update
            return {
                'should_publish': True,
                'action': 'update',
                'reason': 'content_changed',
                'content_hash': current_hash
            }
    
    def process_post_metadata(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process metadata for a post (MVP - simplified)"""
        logger.info(f"Processing post metadata: {post_data.get('title', '')[:50]}")
        
        # Check idempotency first
        idempotency_result = self.check_publishing_idempotency(post_data)
        
        # Map LLM tags to Ghost
        llm_tags = post_data.get('tags', [])  # From NLP pipeline
        ghost_tags = self.map_llm_tags_to_ghost(llm_tags)
        
        # Generate content hash
        content_hash = self.generate_content_hash(post_data)
        
        # Combine metadata
        processed_metadata = {
            'tags': ghost_tags,
            'content_hash': content_hash,
            'idempotency': idempotency_result
        }
        
        logger.info(f"Post metadata processed: {len(ghost_tags)} tags, action: {idempotency_result['action']}")
        
        return processed_metadata
    
    def validate_tags(self, tags: List[str]) -> Dict[str, List[str]]:
        """Validate tags for MVP requirements"""
        errors = []
        warnings = []
        
        # Check tag count (MVP: 3-5 tags)
        if len(tags) < 3:
            warnings.append(f"Few tags ({len(tags)}), recommended 3-5")
        elif len(tags) > 5:
            warnings.append(f"Many tags ({len(tags)}), recommended 3-5")
        
        # Check tag format
        for tag in tags:
            if not tag or len(tag) < 2:
                errors.append(f"Tag too short: '{tag}'")
            elif len(tag) > 50:
                errors.append(f"Tag too long: '{tag}'")
            elif not re.match(r'^[a-z0-9-]+$', tag):
                warnings.append(f"Tag format may be invalid: '{tag}'")
        
        return {
            'errors': errors,
            'warnings': warnings
        }


# Singleton instance for MVP
_metadata_processor = None

def get_metadata_processor(ghost_client: Optional[GhostClient] = None) -> MetadataProcessor:
    """Get singleton metadata processor instance"""
    global _metadata_processor
    if _metadata_processor is None:
        _metadata_processor = MetadataProcessor(ghost_client)
    elif ghost_client and _metadata_processor.ghost_client != ghost_client:
        # Update ghost client if provided
        _metadata_processor.ghost_client = ghost_client
    return _metadata_processor