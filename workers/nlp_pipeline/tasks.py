"""
Celery tasks for NLP pipeline processing (MVP simplified)
"""
import logging
from typing import Dict, Any
from datetime import datetime
import hashlib
import json

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import get_settings
from app.infrastructure import get_database_session
from app.models.post import Post
from app.models.processing_log import ProcessingLog
from app.transaction_manager import transaction_with_tracking, get_state_manager
from .openai_client import get_openai_client

logger = logging.getLogger(__name__)
settings = get_settings()

# Retry constants (상수화된 설정)
RETRY_MAX = 3
BACKOFF_BASE = 2
BACKOFF_MIN = 2  # seconds
BACKOFF_MAX = 8  # seconds


class NLPTask(Task):
    """Base task class for NLP processing with simplified error handling"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        post_id = kwargs.get('post_id') or (args[0] if args else 'unknown')
        
        logger.error(f"NLP task {self.name} failed for post {post_id}: {exc}")
        
        # Log failure to database
        try:
            with get_db_session() as db:
                processing_log = ProcessingLog(
                    post_id=post_id,
                    service_name='nlp_pipeline',
                    status="failed",
                    error_message=str(exc),
                    processing_time_ms=0
                )
                db.add(processing_log)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to log task failure: {e}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        post_id = kwargs.get('post_id') or (args[0] if args else 'unknown')
        logger.info(f"NLP task {self.name} completed successfully for post {post_id}")


@celery_app.task(
    bind=True,
    base=NLPTask,
    max_retries=RETRY_MAX,
    queue='process'
)
def process_content_with_ai(self, post_id: str) -> Dict[str, Any]:
    """
    Main Celery task for processing Reddit post content with AI (동기 I/O)
    
    Args:
        post_id: ID of the post to process
    
    Returns:
        Dictionary with processing results
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info(f"Starting AI processing for post {post_id}")
        
        # Get post from database
        db = get_database_session()
        try:
            post = db.query(Post).filter(Post.id == post_id).first()
            if not post:
                raise ValueError(f"Post {post_id} not found in database")
            
            # Generate content_hash = sha256(title+body+media_urls)
            media_urls = json.dumps(post.media_urls or [], sort_keys=True) if hasattr(post, 'media_urls') else ""
            content_for_hash = f"{post.title}{post.content}{media_urls}"
            content_hash = hashlib.sha256(content_for_hash.encode('utf-8')).hexdigest()
            
            # Update post with content_hash and status
            post.content_hash = content_hash
            post.status = 'processing'
            db.commit()
        finally:
            db.close()
        
        # Initialize OpenAI client
        openai_client = get_openai_client()
        if not openai_client._client:
            openai_client.initialize()
        
        # Process with AI (Korean summary, tags, analysis)
        summary_result = openai_client.generate_korean_summary(
            post.title, post.content, post_id
        )
        
        tags_result = openai_client.extract_tags_llm(
            post.title, post.content, post_id
        )
        
        analysis_result = openai_client.analyze_pain_points_and_ideas(
            post.title, post.content, post_id
        )
        
        # Update database with results using transaction management
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        with transaction_with_tracking(
            post_id=post_id,
            service_name="nlp_pipeline", 
            operation_name="process_content_with_ai"
        ) as (session, tracker):
            
            state_manager = get_state_manager(session, tracker)
            
            post = session.query(Post).filter(Post.id == post_id).first()
            if not post:
                raise ValueError(f"Post {post_id} not found during update")
            
            # Capture old state for rollback tracking
            old_state = {
                'summary_ko': post.summary_ko,
                'tags': post.tags,
                'pain_points': post.pain_points,
                'product_ideas': post.product_ideas,
                'status': post.status,
                'updated_at': post.updated_at
            }
            
            # Update post with AI results
            post.summary_ko = summary_result.get('summary')
            post.tags = tags_result.get('tags')
            post.pain_points = analysis_result.get('analysis', {}).get('pain_points', [])
            post.product_ideas = analysis_result.get('analysis', {}).get('product_ideas', [])
            post.status = 'processed'
            post.updated_at = datetime.utcnow()
            
            # Track the update
            state_manager.update_entity(post, "post", post_id, old_state)
            
            # Calculate totals for logging
            total_tokens = (summary_result.get('total_tokens', 0) + 
                           tags_result.get('total_tokens', 0) + 
                           analysis_result.get('total_tokens', 0))
            total_cost = (summary_result.get('cost_usd', 0) + 
                         tags_result.get('cost_usd', 0) + 
                         analysis_result.get('cost_usd', 0))
            
            # Add processing log
            processing_log = ProcessingLog(
                post_id=post_id,
                service_name='nlp_pipeline',
                status='success',
                processing_time_ms=processing_time_ms,
                metadata={
                    'total_tokens': total_tokens,
                    'total_cost': float(total_cost),
                    'models_used': {
                        'summary': summary_result.get('model'),
                        'tags': tags_result.get('model'),
                        'analysis': analysis_result.get('model')
                    }
                }
            )
            
            state_manager.create_entity(processing_log, "processing_log", f"nlp_{post_id}")
            
            # Check consistency before commit
            consistency_result = state_manager.check_consistency()
            if consistency_result.get("status") != "passed":
                logger.error(f"Consistency check failed for post {post_id}: {consistency_result}")
                raise Exception(f"Consistency check failed: {consistency_result}")
        
        # Totals already calculated above for logging
        
        logger.info(
            f"AI processing completed for post {post_id}",
            extra={
                "post_id": post_id,
                "processing_time_ms": processing_time_ms,
                "total_tokens": total_tokens,
                "total_cost": float(total_cost),
                "content_hash": content_hash
            }
        )
        
        return {
            "status": "completed",
            "post_id": post_id,
            "processing_time_ms": processing_time_ms,
            "total_tokens": total_tokens,
            "total_cost": float(total_cost),
            "content_hash": content_hash
        }
        
    except Exception as e:
        # Update post status to failed with transaction management
        try:
            with transaction_with_tracking(
                post_id=post_id,
                service_name="nlp_pipeline",
                operation_name="handle_processing_error"
            ) as (session, tracker):
                
                state_manager = get_state_manager(session, tracker)
                
                post = session.query(Post).filter(Post.id == post_id).first()
                if post:
                    old_state = {'status': post.status, 'updated_at': post.updated_at}
                    
                    post.status = 'failed'
                    post.updated_at = datetime.utcnow()
                    
                    state_manager.update_entity(post, "post", post_id, old_state)
                    
                    # Add error log
                    processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    processing_log = ProcessingLog(
                        post_id=post_id,
                        service_name='nlp_pipeline',
                        status='failed',
                        error_message=str(e),
                        processing_time_ms=processing_time_ms,
                        metadata={'retry_count': self.request.retries}
                    )
                    
                    state_manager.create_entity(processing_log, "processing_log", f"nlp_error_{post_id}")
                    
        except Exception as db_error:
            logger.error(f"Failed to update post status after error: {db_error}")
        
        # Exponential backoff retry logic (상수화된 설정 사용)
        if self.request.retries < RETRY_MAX:
            # Calculate backoff delay: min(BACKOFF_MAX, BACKOFF_MIN * BACKOFF_BASE^retry_count)
            backoff_delay = min(BACKOFF_MAX, BACKOFF_MIN * (BACKOFF_BASE ** self.request.retries))
            
            logger.warning(
                f"AI processing failed for post {post_id}, retrying in {backoff_delay}s "
                f"({self.request.retries + 1}/{RETRY_MAX}): {e}"
            )
            raise self.retry(exc=e, countdown=backoff_delay)
        else:
            logger.error(f"AI processing failed permanently for post {post_id}: {e}")
            raise


# Utility functions for manual task triggering
def trigger_post_processing(post_id: str) -> str:
    """Trigger processing for a specific post"""
    task = process_content_with_ai.delay(post_id)
    return task.id


def get_nlp_task_status(task_id: str) -> Dict[str, Any]:
    """Get status of an NLP task"""
    try:
        result = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "unknown",
            "error": str(e)
        }


@celery_app.task(
    bind=True,
    base=NLPTask,
    max_retries=RETRY_MAX,
    queue='process'
)
def batch_process_posts(self, post_ids: list) -> Dict[str, Any]:
    """
    Batch process multiple posts with AI
    
    Args:
        post_ids: List of post IDs to process
    
    Returns:
        Dictionary with batch processing results
    """
    try:
        logger.info(f"Starting batch processing for {len(post_ids)} posts")
        
        results = []
        for post_id in post_ids:
            try:
                result = process_content_with_ai.delay(post_id)
                results.append({
                    "post_id": post_id,
                    "task_id": result.id,
                    "status": "queued"
                })
            except Exception as e:
                logger.error(f"Failed to queue processing for post {post_id}: {e}")
                results.append({
                    "post_id": post_id,
                    "task_id": None,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "batch_id": self.request.id,
            "total_posts": len(post_ids),
            "queued_posts": len([r for r in results if r["status"] == "queued"]),
            "failed_posts": len([r for r in results if r["status"] == "failed"]),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=NLPTask,
    queue='process'
)
def train_bertopic_model(self, documents: list) -> Dict[str, Any]:
    """
    Train BERTopic model (removed for MVP - using LLM prompts only)
    
    Args:
        documents: List of documents for training
    
    Returns:
        Dictionary with training results
    """
    logger.info("BERTopic training skipped - using LLM prompts only for MVP")
    return {
        "status": "skipped",
        "message": "BERTopic training removed for MVP - using LLM prompts only",
        "documents_count": len(documents) if documents else 0
    }


@celery_app.task(
    bind=True,
    base=NLPTask,
    queue='process'
)
def health_check_nlp_services(self) -> Dict[str, Any]:
    """
    Health check for NLP services
    
    Returns:
        Dictionary with health status
    """
    try:
        openai_client = get_openai_client()
        
        health_status = {
            "service": "nlp_pipeline",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Check OpenAI client
        openai_health = openai_client.health_check()
        health_status["checks"]["openai_client"] = openai_health
        
        # Check database connection
        try:
            session = get_database_session()
            try:
                result = session.query(Post.id).limit(1).first()
                health_status["checks"]["database"] = {
                    "status": "healthy",
                    "connected": True
                }
            finally:
                session.close()
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Determine overall health
        unhealthy_checks = [
            check for check in health_status["checks"].values()
            if check.get("status") == "unhealthy"
        ]
        
        if unhealthy_checks:
            health_status["status"] = "unhealthy"
            health_status["unhealthy_checks"] = len(unhealthy_checks)
        
        return health_status
        
    except Exception as e:
        logger.error(f"NLP health check failed: {e}")
        return {
            "service": "nlp_pipeline",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


def trigger_batch_processing(post_ids: list) -> str:
    """Trigger batch processing for multiple posts"""
    task = batch_process_posts.delay(post_ids)
    return task.id


def trigger_model_training(documents: list) -> str:
    """Trigger model training (skipped for MVP)"""
    task = train_bertopic_model.delay(documents)
    return task.id