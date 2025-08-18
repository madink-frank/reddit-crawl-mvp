"""
Background tasks for Reddit Ghost Publisher

This module manages long-running background tasks including:
1. Resilience monitoring
2. State consistency checks
3. Metrics collection
4. Health checks
5. Cleanup tasks
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import structlog

from app.resilience_monitor import start_resilience_monitoring
from app.state_tracker import get_state_tracker
from app.redis_client import redis_client

logger = structlog.get_logger(__name__)


class BackgroundTaskManager:
    """Manages background tasks"""
    
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.running = False
    
    async def start_all_tasks(self) -> None:
        """Start all background tasks"""
        if self.running:
            logger.warning("Background tasks already running")
            return
        
        self.running = True
        logger.info("Starting background tasks")
        
        # Start resilience monitoring
        self.tasks["resilience_monitoring"] = asyncio.create_task(
            self._run_resilience_monitoring()
        )
        
        # Start state consistency monitoring
        self.tasks["state_consistency"] = asyncio.create_task(
            self._run_state_consistency_monitoring()
        )
        
        # Start cleanup tasks
        self.tasks["cleanup"] = asyncio.create_task(
            self._run_cleanup_tasks()
        )
        
        # Start health check tasks
        self.tasks["health_checks"] = asyncio.create_task(
            self._run_health_checks()
        )
        
        logger.info("All background tasks started", task_count=len(self.tasks))
    
    async def stop_all_tasks(self) -> None:
        """Stop all background tasks"""
        if not self.running:
            return
        
        logger.info("Stopping background tasks")
        self.running = False
        
        # Cancel all tasks
        for task_name, task in self.tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info("Background task cancelled", task_name=task_name)
        
        self.tasks.clear()
        logger.info("All background tasks stopped")
    
    async def _run_resilience_monitoring(self) -> None:
        """Run resilience monitoring task"""
        try:
            await start_resilience_monitoring(interval=60)
        except asyncio.CancelledError:
            logger.info("Resilience monitoring task cancelled")
        except Exception as e:
            logger.error("Resilience monitoring task failed", error=str(e))
    
    async def _run_state_consistency_monitoring(self) -> None:
        """Run state consistency monitoring task"""
        try:
            state_tracker = get_state_tracker()
            
            while self.running:
                try:
                    # Check for inconsistent states
                    inconsistencies = await state_tracker.detect_inconsistent_states()
                    
                    if inconsistencies:
                        logger.warning(
                            "Detected inconsistent states",
                            count=len(inconsistencies)
                        )
                        
                        # Attempt to recover some inconsistencies automatically
                        for inconsistency in inconsistencies:
                            await self._attempt_state_recovery(inconsistency)
                    
                    # Sleep for 5 minutes
                    await asyncio.sleep(300)
                    
                except Exception as e:
                    logger.error("State consistency check failed", error=str(e))
                    await asyncio.sleep(60)  # Shorter retry interval on error
                    
        except asyncio.CancelledError:
            logger.info("State consistency monitoring task cancelled")
    
    async def _attempt_state_recovery(self, inconsistency: Dict) -> None:
        """Attempt to recover from state inconsistency"""
        try:
            entity_type = inconsistency["entity_type"]
            entity_id = inconsistency["entity_id"]
            current_state = inconsistency["current_state"]
            issues = inconsistency["issues"]
            
            state_tracker = get_state_tracker()
            
            # Simple recovery logic based on issues
            if "Stuck in collecting state" in issues:
                # Reset to collected state if stuck in collecting
                from app.state_tracker import EntityState
                await state_tracker.recover_inconsistent_state(
                    entity_type, entity_id, EntityState.COLLECTED,
                    {"recovery_reason": "stuck_in_collecting"}
                )
            
            elif "Stuck in processing state" in issues:
                # Reset to collected state if stuck in processing
                from app.state_tracker import EntityState
                await state_tracker.recover_inconsistent_state(
                    entity_type, entity_id, EntityState.COLLECTED,
                    {"recovery_reason": "stuck_in_processing"}
                )
            
            elif "Stuck in publishing state" in issues:
                # Reset to processed state if stuck in publishing
                from app.state_tracker import EntityState
                await state_tracker.recover_inconsistent_state(
                    entity_type, entity_id, EntityState.PROCESSED,
                    {"recovery_reason": "stuck_in_publishing"}
                )
            
            logger.info(
                "Attempted state recovery",
                entity_type=entity_type,
                entity_id=entity_id,
                current_state=current_state,
                issues=issues
            )
            
        except Exception as e:
            logger.error(
                "State recovery attempt failed",
                inconsistency=inconsistency,
                error=str(e)
            )
    
    async def _run_cleanup_tasks(self) -> None:
        """Run cleanup tasks"""
        try:
            while self.running:
                try:
                    # Clean up old Redis keys
                    await self._cleanup_redis_keys()
                    
                    # Clean up old logs
                    await self._cleanup_old_logs()
                    
                    # Sleep for 1 hour
                    await asyncio.sleep(3600)
                    
                except Exception as e:
                    logger.error("Cleanup task failed", error=str(e))
                    await asyncio.sleep(300)  # Retry in 5 minutes
                    
        except asyncio.CancelledError:
            logger.info("Cleanup task cancelled")
    
    async def _cleanup_redis_keys(self) -> None:
        """Clean up old Redis keys"""
        try:
            # Clean up old state changes (older than 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            cutoff_timestamp = cutoff_time.timestamp()
            
            # Find and delete old state change keys
            pattern = "state_change:*"
            keys = await redis_client.keys(pattern)
            
            deleted_count = 0
            for key in keys:
                # Check if key is old (this is a simplified check)
                ttl = await redis_client.ttl(key)
                if ttl == -1:  # No expiry set, delete if old
                    await redis_client.delete(key)
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info("Cleaned up old Redis keys", deleted_count=deleted_count)
                
        except Exception as e:
            logger.error("Redis cleanup failed", error=str(e))
    
    async def _cleanup_old_logs(self) -> None:
        """Clean up old processing logs from database"""
        try:
            from app.infrastructure import get_async_session
            from sqlalchemy import text
            
            # Delete processing logs older than 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            async with get_async_session() as session:
                result = await session.execute(
                    text("DELETE FROM processing_logs WHERE created_at < :cutoff_date"),
                    {"cutoff_date": cutoff_date}
                )
                
                deleted_count = result.rowcount
                await session.commit()
                
                if deleted_count > 0:
                    logger.info("Cleaned up old processing logs", deleted_count=deleted_count)
                    
        except Exception as e:
            logger.error("Database cleanup failed", error=str(e))
    
    async def _run_health_checks(self) -> None:
        """Run periodic health checks"""
        try:
            while self.running:
                try:
                    # Check database connectivity
                    await self._check_database_health()
                    
                    # Check Redis connectivity
                    await self._check_redis_health()
                    
                    # Check external services
                    await self._check_external_services_health()
                    
                    # Sleep for 2 minutes
                    await asyncio.sleep(120)
                    
                except Exception as e:
                    logger.error("Health check failed", error=str(e))
                    await asyncio.sleep(60)  # Retry in 1 minute
                    
        except asyncio.CancelledError:
            logger.info("Health check task cancelled")
    
    async def _check_database_health(self) -> None:
        """Check database health"""
        try:
            from app.infrastructure import get_async_session
            from sqlalchemy import text
            
            async with get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.fetchone()
                
            # Store health status in Redis
            await redis_client.setex("health:database", 300, "healthy")
            
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            await redis_client.setex("health:database", 300, f"unhealthy: {str(e)}")
    
    async def _check_redis_health(self) -> None:
        """Check Redis health"""
        try:
            await redis_client.ping()
            await redis_client.setex("health:redis", 300, "healthy")
            
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            # Can't store in Redis if Redis is down, so just log
    
    async def _check_external_services_health(self) -> None:
        """Check external services health"""
        try:
            # Check Reddit client
            from workers.collector.reddit_client import get_reddit_client
            reddit_client = get_reddit_client()
            reddit_health = reddit_client.health_check()
            
            await redis_client.setex(
                "health:reddit",
                300,
                "healthy" if reddit_health.get("status") == "healthy" else "unhealthy"
            )
            
            # Check OpenAI client
            from workers.nlp_pipeline.openai_client import get_openai_client
            openai_client = get_openai_client()
            openai_health = await openai_client.health_check()
            
            await redis_client.setex(
                "health:openai",
                300,
                "healthy" if openai_health.get("status") == "healthy" else "unhealthy"
            )
            
            # Check Ghost client
            from workers.publisher.ghost_client import get_ghost_client
            ghost_client = await get_ghost_client()
            ghost_health = await ghost_client.health_check()
            
            await redis_client.setex(
                "health:ghost",
                300,
                "healthy" if ghost_health else "unhealthy"
            )
            
        except Exception as e:
            logger.error("External services health check failed", error=str(e))
    
    def get_task_status(self) -> Dict[str, str]:
        """Get status of all background tasks"""
        status = {}
        
        for task_name, task in self.tasks.items():
            if task.done():
                if task.cancelled():
                    status[task_name] = "cancelled"
                elif task.exception():
                    status[task_name] = f"failed: {task.exception()}"
                else:
                    status[task_name] = "completed"
            else:
                status[task_name] = "running"
        
        return status


# Global background task manager
background_task_manager = BackgroundTaskManager()


def get_background_task_manager() -> BackgroundTaskManager:
    """Get the global background task manager"""
    return background_task_manager


async def start_background_tasks() -> None:
    """Start all background tasks"""
    await background_task_manager.start_all_tasks()


async def stop_background_tasks() -> None:
    """Stop all background tasks"""
    await background_task_manager.stop_all_tasks()