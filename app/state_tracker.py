"""
State tracking and change monitoring for Reddit Ghost Publisher

This module provides:
1. State change tracking for entities
2. Audit logging for data modifications
3. State consistency validation
4. Recovery mechanisms for inconsistent states
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from uuid import uuid4
import json

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.infrastructure import get_async_session
from app.redis_client import redis_client
from app.models.post import Post
from app.models.processing_log import ProcessingLog

logger = structlog.get_logger(__name__)


class EntityState(Enum):
    """Possible states for entities"""
    CREATED = "created"
    COLLECTING = "collecting"
    COLLECTED = "collected"
    PROCESSING = "processing"
    PROCESSED = "processed"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


class StateChangeType(Enum):
    """Types of state changes"""
    TRANSITION = "transition"
    UPDATE = "update"
    ROLLBACK = "rollback"
    RECOVERY = "recovery"


@dataclass
class StateChange:
    """Represents a state change event"""
    id: str = field(default_factory=lambda: str(uuid4()))
    entity_type: str = ""
    entity_id: str = ""
    change_type: StateChangeType = StateChangeType.TRANSITION
    from_state: Optional[EntityState] = None
    to_state: Optional[EntityState] = None
    changed_fields: Dict[str, Any] = field(default_factory=dict)
    previous_values: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    service_name: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "change_type": self.change_type.value,
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value if self.to_state else None,
            "changed_fields": self.changed_fields,
            "previous_values": self.previous_values,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "service_name": self.service_name
        }


@dataclass
class EntitySnapshot:
    """Snapshot of an entity at a point in time"""
    entity_type: str
    entity_id: str
    state: EntityState
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "state": self.state.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version
        }


class StateValidator:
    """Validates state transitions and consistency"""
    
    # Valid state transitions for posts
    VALID_TRANSITIONS = {
        EntityState.CREATED: {EntityState.COLLECTING, EntityState.FAILED},
        EntityState.COLLECTING: {EntityState.COLLECTED, EntityState.FAILED},
        EntityState.COLLECTED: {EntityState.PROCESSING, EntityState.FAILED},
        EntityState.PROCESSING: {EntityState.PROCESSED, EntityState.FAILED},
        EntityState.PROCESSED: {EntityState.PUBLISHING, EntityState.FAILED},
        EntityState.PUBLISHING: {EntityState.PUBLISHED, EntityState.FAILED},
        EntityState.PUBLISHED: {EntityState.ARCHIVED},
        EntityState.FAILED: {EntityState.COLLECTING, EntityState.PROCESSING, EntityState.PUBLISHING}
    }
    
    def is_valid_transition(self, from_state: EntityState, to_state: EntityState) -> bool:
        """Check if a state transition is valid"""
        if from_state not in self.VALID_TRANSITIONS:
            return False
        
        return to_state in self.VALID_TRANSITIONS[from_state]
    
    def get_valid_next_states(self, current_state: EntityState) -> Set[EntityState]:
        """Get all valid next states from the current state"""
        return self.VALID_TRANSITIONS.get(current_state, set())
    
    def validate_entity_consistency(self, entity_data: Dict[str, Any]) -> List[str]:
        """Validate entity data consistency"""
        errors = []
        
        # Check required fields based on state
        state = EntityState(entity_data.get("status", "created"))
        
        if state in [EntityState.COLLECTED, EntityState.PROCESSING]:
            if not entity_data.get("title"):
                errors.append("Title is required for collected posts")
            if not entity_data.get("content") and not entity_data.get("url"):
                errors.append("Content or URL is required for collected posts")
        
        if state in [EntityState.PROCESSED, EntityState.PUBLISHING]:
            if not entity_data.get("summary_ko"):
                errors.append("Korean summary is required for processed posts")
            if not entity_data.get("topic_tag"):
                errors.append("Topic tag is required for processed posts")
        
        if state == EntityState.PUBLISHED:
            if not entity_data.get("ghost_url"):
                errors.append("Ghost URL is required for published posts")
            if not entity_data.get("published_at"):
                errors.append("Published timestamp is required for published posts")
        
        return errors


class StateTracker:
    """Tracks and manages entity state changes"""
    
    def __init__(self):
        self.validator = StateValidator()
    
    async def track_state_change(
        self,
        entity_type: str,
        entity_id: str,
        change_type: StateChangeType,
        from_state: Optional[EntityState] = None,
        to_state: Optional[EntityState] = None,
        changed_fields: Optional[Dict[str, Any]] = None,
        previous_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        service_name: str = "system"
    ) -> StateChange:
        """Track a state change event"""
        
        # Validate state transition if it's a transition
        if change_type == StateChangeType.TRANSITION and from_state and to_state:
            if not self.validator.is_valid_transition(from_state, to_state):
                logger.warning(
                    "Invalid state transition attempted",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    from_state=from_state.value,
                    to_state=to_state.value
                )
                raise ValueError(f"Invalid state transition from {from_state.value} to {to_state.value}")
        
        # Create state change record
        state_change = StateChange(
            entity_type=entity_type,
            entity_id=entity_id,
            change_type=change_type,
            from_state=from_state,
            to_state=to_state,
            changed_fields=changed_fields or {},
            previous_values=previous_values or {},
            metadata=metadata or {},
            service_name=service_name
        )
        
        # Store in Redis for fast access
        await self._store_state_change(state_change)
        
        # Log to database for persistence
        await self._log_state_change(state_change)
        
        logger.info(
            "State change tracked",
            entity_type=entity_type,
            entity_id=entity_id,
            change_type=change_type.value,
            from_state=from_state.value if from_state else None,
            to_state=to_state.value if to_state else None,
            service_name=service_name
        )
        
        return state_change
    
    async def _store_state_change(self, state_change: StateChange) -> None:
        """Store state change in Redis"""
        try:
            # Store individual state change
            change_key = f"state_change:{state_change.id}"
            await redis_client.setex(change_key, 86400, state_change.to_dict())  # 24 hours TTL
            
            # Add to entity's state change history
            history_key = f"state_history:{state_change.entity_type}:{state_change.entity_id}"
            await redis_client.lpush(history_key, state_change.id)
            await redis_client.ltrim(history_key, 0, 99)  # Keep last 100 changes
            await redis_client.expire(history_key, 86400)  # 24 hours TTL
            
            # Update current state
            current_state_key = f"current_state:{state_change.entity_type}:{state_change.entity_id}"
            if state_change.to_state:
                await redis_client.setex(current_state_key, 86400, state_change.to_state.value)
            
        except Exception as e:
            logger.error(
                "Failed to store state change in Redis",
                state_change_id=state_change.id,
                error=str(e)
            )
    
    async def _log_state_change(self, state_change: StateChange) -> None:
        """Log state change to database"""
        try:
            async with get_async_session() as session:
                log_entry = ProcessingLog(
                    post_id=state_change.entity_id,
                    service_name=state_change.service_name,
                    status="state_change",
                    metadata={
                        "change_type": state_change.change_type.value,
                        "from_state": state_change.from_state.value if state_change.from_state else None,
                        "to_state": state_change.to_state.value if state_change.to_state else None,
                        "changed_fields": list(state_change.changed_fields.keys()),
                        "state_change_id": state_change.id
                    }
                )
                session.add(log_entry)
                await session.commit()
                
        except Exception as e:
            logger.error(
                "Failed to log state change to database",
                state_change_id=state_change.id,
                error=str(e)
            )
    
    async def get_current_state(self, entity_type: str, entity_id: str) -> Optional[EntityState]:
        """Get the current state of an entity"""
        try:
            current_state_key = f"current_state:{entity_type}:{entity_id}"
            state_value = await redis_client.get(current_state_key)
            
            if state_value:
                return EntityState(state_value)
            
            # Fallback to database
            if entity_type == "post":
                async with get_async_session() as session:
                    post = await session.get(Post, entity_id)
                    if post and post.status:
                        return EntityState(post.status)
            
        except Exception as e:
            logger.error(
                "Failed to get current state",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e)
            )
        
        return None
    
    async def get_state_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[StateChange]:
        """Get state change history for an entity"""
        try:
            history_key = f"state_history:{entity_type}:{entity_id}"
            change_ids = await redis_client.lrange(history_key, 0, limit - 1)
            
            state_changes = []
            for change_id in change_ids:
                change_key = f"state_change:{change_id}"
                change_data = await redis_client.get(change_key)
                
                if change_data:
                    # Reconstruct StateChange object
                    data = json.loads(change_data) if isinstance(change_data, str) else change_data
                    state_change = StateChange(
                        id=data["id"],
                        entity_type=data["entity_type"],
                        entity_id=data["entity_id"],
                        change_type=StateChangeType(data["change_type"]),
                        from_state=EntityState(data["from_state"]) if data["from_state"] else None,
                        to_state=EntityState(data["to_state"]) if data["to_state"] else None,
                        changed_fields=data["changed_fields"],
                        previous_values=data["previous_values"],
                        metadata=data["metadata"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        user_id=data["user_id"],
                        service_name=data["service_name"]
                    )
                    state_changes.append(state_change)
            
            return state_changes
            
        except Exception as e:
            logger.error(
                "Failed to get state history",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e)
            )
            return []
    
    async def create_snapshot(self, entity_type: str, entity_id: str) -> Optional[EntitySnapshot]:
        """Create a snapshot of an entity's current state"""
        try:
            if entity_type == "post":
                async with get_async_session() as session:
                    post = await session.get(Post, entity_id)
                    if post:
                        snapshot = EntitySnapshot(
                            entity_type=entity_type,
                            entity_id=entity_id,
                            state=EntityState(post.status),
                            data={
                                "title": post.title,
                                "content": post.content,
                                "subreddit": post.subreddit,
                                "score": post.score,
                                "comments": post.comments,
                                "summary_ko": post.summary_ko,
                                "topic_tag": post.topic_tag,
                                "pain_points": post.pain_points,
                                "product_ideas": post.product_ideas,
                                "ghost_url": post.ghost_url,
                                "ghost_id": post.ghost_id,
                                "published_at": post.published_at.isoformat() if post.published_at else None
                            }
                        )
                        
                        # Store snapshot in Redis
                        snapshot_key = f"snapshot:{entity_type}:{entity_id}:{int(datetime.utcnow().timestamp())}"
                        await redis_client.setex(snapshot_key, 86400, snapshot.to_dict())
                        
                        return snapshot
            
        except Exception as e:
            logger.error(
                "Failed to create snapshot",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e)
            )
        
        return None
    
    async def detect_inconsistent_states(self) -> List[Dict[str, Any]]:
        """Detect entities with inconsistent states"""
        inconsistencies = []
        
        try:
            async with get_async_session() as session:
                # Find posts with inconsistent states
                query = text("""
                    SELECT id, status, summary_ko, topic_tag, ghost_url, published_at
                    FROM posts
                    WHERE 
                        (status = 'processed' AND (summary_ko IS NULL OR topic_tag IS NULL)) OR
                        (status = 'published' AND (ghost_url IS NULL OR published_at IS NULL)) OR
                        (status = 'collecting' AND created_at < NOW() - INTERVAL '1 hour') OR
                        (status = 'processing' AND updated_at < NOW() - INTERVAL '2 hours') OR
                        (status = 'publishing' AND updated_at < NOW() - INTERVAL '30 minutes')
                """)
                
                result = await session.execute(query)
                rows = result.fetchall()
                
                for row in rows:
                    inconsistency = {
                        "entity_type": "post",
                        "entity_id": row.id,
                        "current_state": row.status,
                        "issues": []
                    }
                    
                    # Check specific inconsistencies
                    if row.status == 'processed' and not row.summary_ko:
                        inconsistency["issues"].append("Missing Korean summary")
                    if row.status == 'processed' and not row.topic_tag:
                        inconsistency["issues"].append("Missing topic tag")
                    if row.status == 'published' and not row.ghost_url:
                        inconsistency["issues"].append("Missing Ghost URL")
                    if row.status == 'published' and not row.published_at:
                        inconsistency["issues"].append("Missing published timestamp")
                    
                    # Check for stuck states (time-based)
                    if row.status in ['collecting', 'processing', 'publishing']:
                        inconsistency["issues"].append(f"Stuck in {row.status} state")
                    
                    inconsistencies.append(inconsistency)
                
        except Exception as e:
            logger.error("Failed to detect inconsistent states", error=str(e))
        
        return inconsistencies
    
    async def recover_inconsistent_state(
        self,
        entity_type: str,
        entity_id: str,
        target_state: EntityState,
        recovery_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Attempt to recover an entity from an inconsistent state"""
        try:
            current_state = await self.get_current_state(entity_type, entity_id)
            
            if not current_state:
                logger.error(
                    "Cannot recover: current state unknown",
                    entity_type=entity_type,
                    entity_id=entity_id
                )
                return False
            
            # Track the recovery attempt
            await self.track_state_change(
                entity_type=entity_type,
                entity_id=entity_id,
                change_type=StateChangeType.RECOVERY,
                from_state=current_state,
                to_state=target_state,
                metadata=recovery_metadata or {"recovery_reason": "inconsistent_state"},
                service_name="state_tracker"
            )
            
            # Update the entity state in database
            if entity_type == "post":
                async with get_async_session() as session:
                    post = await session.get(Post, entity_id)
                    if post:
                        post.status = target_state.value
                        post.updated_at = datetime.utcnow()
                        await session.commit()
                        
                        logger.info(
                            "State recovered successfully",
                            entity_type=entity_type,
                            entity_id=entity_id,
                            from_state=current_state.value,
                            to_state=target_state.value
                        )
                        return True
            
        except Exception as e:
            logger.error(
                "Failed to recover inconsistent state",
                entity_type=entity_type,
                entity_id=entity_id,
                error=str(e)
            )
        
        return False


# Global state tracker instance
state_tracker = StateTracker()


def get_state_tracker() -> StateTracker:
    """Get the global state tracker instance"""
    return state_tracker