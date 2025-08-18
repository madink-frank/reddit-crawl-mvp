"""
Celery Tasks for Ghost CMS Publishing (MVP Synchronous Version)

Implements the publish_to_ghost task with status tracking and error handling.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import hashlib

from celery import current_task
from celery.exceptions import Retry
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.config import settings
from app.transaction_manager import transaction_with_tracking, get_state_manager
from workers.publisher.ghost_client import get_ghost_client, GhostClient, GhostPost, GhostAPIError
from workers.publisher.template_engine import get_template_engine
from workers.publisher.image_handler import get_image_handler
from workers.publisher.metadata_processor import get_metadata_processor

logger = logging.getLogger(__name__)


class PublishingError(Exception):
    """Base exception for publishing errors"""
    pass


def log_processing_step(
    post_id: str, 
    service_name: str, 
    status: str, 
    error_message: Optional[str] = None,
    processing_time_ms: Optional[int] = None
):
    """Log a processing step to the database (MVP - synchronous)"""
    try:
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        
        with Session() as session:
            session.execute(
                text("""
                INSERT INTO processing_logs (post_id, service_name, status, error_message, processing_time_ms, created_at)
                VALUES (:post_id, :service_name, :status, :error_message, :processing_time_ms, :created_at)
                """),
                {
                    "post_id": post_id,
                    "service_name": service_name,
                    "status": status,
                    "error_message": error_message,
                    "processing_time_ms": processing_time_ms,
                    "created_at": datetime.utcnow()
                }
            )
            session.commit()
            
    except Exception as e:
        logger.error(f"Failed to log processing step: {e}")


def update_post_status(post_id: str, **kwargs):
    """Update post fields in database (MVP - synchronous)"""
    try:
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        
        with Session() as session:
            # Update post with provided fields
            update_fields = {"updated_at": datetime.utcnow()}
            update_fields.update(kwargs)
            
            set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
            
            session.execute(
                text(f"UPDATE posts SET {set_clause} WHERE id = :post_id"),
                {**update_fields, "post_id": post_id}
            )
            session.commit()
            
            logger.info(f"Post updated: {post_id}")
            
    except Exception as e:
        logger.error(f"Failed to update post {post_id}: {e}")
        raise


def get_post_data(post_id: str) -> Dict[str, Any]:
    """Get post data from database"""
    try:
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        
        with Session() as session:
            result = session.execute(
                text("SELECT * FROM posts WHERE id = :post_id"),
                {"post_id": post_id}
            )
            post_row = result.fetchone()
            
            if not post_row:
                raise PublishingError(f"Post {post_id} not found")
            
            # Convert to dict
            return dict(post_row._mapping)
            
    except Exception as e:
        logger.error(f"Failed to get post data {post_id}: {e}")
        raise


@celery_app.task(
    bind=True,
    name="workers.publisher.tasks.publish_to_ghost",
    max_retries=3,
    default_retry_delay=2,  # Start with 2 seconds
    autoretry_for=(GhostAPIError, ConnectionError, TimeoutError)
)
def publish_to_ghost(self, post_id: str) -> Dict[str, Any]:
    """
    Publish processed content to Ghost CMS (MVP - synchronous)
    
    Args:
        post_id: ID of the post to publish
        
    Returns:
        Dict containing publication results
        
    Raises:
        PublishingError: If publishing fails
        Retry: If task should be retried
    """
    start_time = datetime.utcnow()
    
    logger.info(f"Starting Ghost publication: {post_id} (retry {self.request.retries})")
    
    try:
        # 1. Get post data from database
        post_data = get_post_data(post_id)
        
        # 2. Check idempotency - skip if already published with same content
        metadata_processor = get_metadata_processor()
        idempotency_result = metadata_processor.check_publishing_idempotency(post_data)
        
        if not idempotency_result['should_publish']:
            logger.info(f"Skipping publication: {idempotency_result['reason']}")
            return {
                'post_id': post_id,
                'action': 'skipped',
                'reason': idempotency_result['reason']
            }
        
        # 3. Initialize clients
        ghost_client = get_ghost_client()
        template_engine = get_template_engine()
        image_handler = get_image_handler(ghost_client)
        metadata_processor.ghost_client = ghost_client
        
        # 4. Process images and get feature image
        logger.debug(f"Processing images for post: {post_id}")
        
        content = post_data.get('content', '')
        updated_content, image_mapping = image_handler.process_content_images(content)
        
        # Get feature image (with fallback to default OG image)
        feature_image_url = image_handler.get_feature_image(post_data)
        
        # 5. Process metadata and tags
        logger.debug(f"Processing metadata for post: {post_id}")
        
        # Update post data with processed content
        post_data['content'] = updated_content
        if feature_image_url:
            post_data['feature_image'] = feature_image_url
        
        metadata = metadata_processor.process_post_metadata(post_data)
        
        # 6. Render content using Article template
        logger.debug(f"Rendering template for post: {post_id}")
        
        rendered_html = template_engine.render_article(post_data)
        
        # 7. Create Ghost post object
        ghost_post = GhostPost(
            title=post_data.get('title', ''),
            html=rendered_html,
            status='published',  # Publish immediately for MVP
            tags=metadata.get('tags', []),
            feature_image=feature_image_url,
            excerpt=post_data.get('summary_ko', '')[:300] if post_data.get('summary_ko') else None
        )
        
        # 8. Publish to Ghost (create or update based on idempotency)
        logger.debug(f"Publishing to Ghost: {post_id}")
        
        if idempotency_result['action'] == 'update':
            # Update existing post
            existing_ghost_id = post_data.get('ghost_post_id')
            if existing_ghost_id:
                published_post = ghost_client.update_post(existing_ghost_id, ghost_post)
            else:
                # Fallback to create if no ghost_post_id
                published_post = ghost_client.create_post(ghost_post)
        else:
            # Create new post
            published_post = ghost_client.create_post(ghost_post)
        
        ghost_post_id = published_post.get('id')
        ghost_slug = published_post.get('slug')
        ghost_url = published_post.get('url')
        
        # Generate Ghost URL if not provided by API
        if not ghost_url and ghost_slug:
            base_url = settings.ghost_api_url.replace('/ghost/api/v4/admin/', '').rstrip('/')
            ghost_url = f"{base_url}/{ghost_slug}/"
        
        # 9. Update post in database with Ghost information using transaction management
        logger.debug(f"Updating post with Ghost info: {post_id}")
        
        with transaction_with_tracking(
            post_id=post_id,
            service_name="ghost_publisher",
            operation_name="update_post_after_publish"
        ) as (session, tracker):
            
            state_manager = get_state_manager(session, tracker)
            
            # Get current post state
            post_result = session.execute(
                text("SELECT ghost_post_id, ghost_slug, ghost_url, content_hash, published_at FROM posts WHERE id = :post_id"),
                {"post_id": post_id}
            )
            current_post = post_result.fetchone()
            
            if current_post:
                old_state = {
                    'ghost_post_id': current_post.ghost_post_id,
                    'ghost_slug': current_post.ghost_slug,
                    'ghost_url': current_post.ghost_url,
                    'content_hash': current_post.content_hash,
                    'published_at': current_post.published_at
                }
                
                # Update post with Ghost information
                session.execute(
                    text("""UPDATE posts SET 
                       status = :status,
                       ghost_post_id = :ghost_post_id,
                       ghost_slug = :ghost_slug,
                       ghost_url = :ghost_url,
                       content_hash = :content_hash,
                       published_at = :published_at,
                       updated_at = :updated_at
                       WHERE id = :post_id"""),
                    {
                        "post_id": post_id,
                        "status": "published",
                        "ghost_post_id": ghost_post_id,
                        "ghost_slug": ghost_slug,
                        "ghost_url": ghost_url,
                        "content_hash": metadata['content_hash'],
                        "published_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )
                
                # Track the update for potential rollback
                tracker.record_change(
                    "UPDATE", "post", post_id, 
                    old_state=old_state,
                    new_state={
                        'ghost_post_id': ghost_post_id,
                        'ghost_slug': ghost_slug,
                        'ghost_url': ghost_url,
                        'content_hash': metadata['content_hash'],
                        'published_at': datetime.utcnow().isoformat()
                    }
                )
                
                # Check consistency
                consistency_result = state_manager.check_consistency()
                if consistency_result.get("status") != "passed":
                    raise Exception(f"Consistency check failed: {consistency_result}")
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Log successful completion
        log_processing_step(
            post_id=post_id,
            service_name="ghost_publisher",
            status="completed",
            processing_time_ms=processing_time
        )
        
        logger.info(f"Ghost publication completed: {post_id} -> {ghost_url}")
        
        return {
            'post_id': post_id,
            'ghost_post_id': ghost_post_id,
            'ghost_slug': ghost_slug,
            'ghost_url': ghost_url,
            'action': idempotency_result['action'],
            'images_processed': len(image_mapping),
            'tags_applied': len(metadata.get('tags', [])),
            'processing_time_ms': processing_time
        }
        
    except Exception as e:
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Log error
        log_processing_step(
            post_id=post_id,
            service_name="ghost_publisher",
            status="failed",
            error_message=str(e),
            processing_time_ms=processing_time
        )
        
        # Determine if we should retry with exponential backoff
        if isinstance(e, (GhostAPIError, ConnectionError, TimeoutError)) and self.request.retries < self.max_retries:
            # Exponential backoff: 2s, 4s, 8s
            backoff_time = settings.backoff_base ** self.request.retries
            backoff_time = max(settings.backoff_min, min(backoff_time, settings.backoff_max))
            
            logger.warning(f"Retrying Ghost publication {post_id} in {backoff_time}s (attempt {self.request.retries + 1})")
            raise self.retry(countdown=backoff_time, exc=e)
        
        logger.error(f"Ghost publication failed permanently: {post_id} - {e}")
        
        raise PublishingError(f"Failed to publish to Ghost: {e}")


# MVP version only includes the main publish_to_ghost task
# Additional tasks can be added later if needed