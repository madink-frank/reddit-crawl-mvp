"""
Synchronous SQLAlchemy transaction management with state tracking and rollback logic
"""
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Generator
from functools import wraps

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

from app.infrastructure import get_database_session
from app.models.processing_log import ProcessingLog

logger = logging.getLogger(__name__)


class TransactionError(Exception):
    """Base exception for transaction errors"""
    pass


class TransactionRollbackError(TransactionError):
    """Error during transaction rollback"""
    pass


class TransactionStateTracker:
    """Track state changes during transaction for rollback purposes"""
    
    def __init__(self):
        self.changes: Dict[str, Any] = {}
        self.operations: list = []
        self.start_time = datetime.utcnow()
    
    def record_change(self, operation: str, entity_type: str, entity_id: str, 
                     old_state: Optional[Dict] = None, new_state: Optional[Dict] = None):
        """Record a state change for potential rollback"""
        change_record = {
            "operation": operation,  # CREATE, UPDATE, DELETE
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_state": old_state,
            "new_state": new_state,
            "timestamp": datetime.utcnow()
        }
        
        self.operations.append(change_record)
        logger.debug(f"Recorded transaction change: {operation} {entity_type}:{entity_id}")
    
    def get_rollback_operations(self) -> list:
        """Get operations needed to rollback changes (in reverse order)"""
        rollback_ops = []
        
        for op in reversed(self.operations):
            if op["operation"] == "CREATE":
                # Rollback CREATE with DELETE
                rollback_ops.append({
                    "operation": "DELETE",
                    "entity_type": op["entity_type"],
                    "entity_id": op["entity_id"]
                })
            elif op["operation"] == "UPDATE":
                # Rollback UPDATE with previous state
                rollback_ops.append({
                    "operation": "UPDATE",
                    "entity_type": op["entity_type"],
                    "entity_id": op["entity_id"],
                    "restore_state": op["old_state"]
                })
            elif op["operation"] == "DELETE":
                # Rollback DELETE with CREATE (if we have old state)
                if op["old_state"]:
                    rollback_ops.append({
                        "operation": "CREATE",
                        "entity_type": op["entity_type"],
                        "entity_id": op["entity_id"],
                        "restore_state": op["old_state"]
                    })
        
        return rollback_ops
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of tracked changes"""
        return {
            "total_operations": len(self.operations),
            "operations_by_type": {
                op_type: len([op for op in self.operations if op["operation"] == op_type])
                for op_type in ["CREATE", "UPDATE", "DELETE"]
            },
            "entities_affected": len(set(f"{op['entity_type']}:{op['entity_id']}" for op in self.operations)),
            "duration_ms": int((datetime.utcnow() - self.start_time).total_seconds() * 1000)
        }


@contextmanager
def transaction_with_tracking(
    post_id: Optional[str] = None,
    service_name: str = "unknown",
    operation_name: str = "transaction"
) -> Generator[tuple[Session, TransactionStateTracker], None, None]:
    """
    Context manager for database transactions with state tracking and rollback logic
    
    Args:
        post_id: Optional post ID for logging
        service_name: Service performing the transaction
        operation_name: Name of the operation for logging
    
    Yields:
        Tuple of (session, state_tracker)
    """
    session = get_database_session()
    state_tracker = TransactionStateTracker()
    start_time = datetime.utcnow()
    
    logger.info(f"Starting transaction: {service_name}.{operation_name} (post_id: {post_id})")
    
    try:
        # Begin transaction (session.begin() is automatic for synchronous sessions)
        
        yield session, state_tracker
        
        # Commit transaction
        session.commit()
        
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        summary = state_tracker.get_summary()
        
        logger.info(
            f"Transaction committed successfully: {service_name}.{operation_name}",
            extra={
                "post_id": post_id,
                "processing_time_ms": processing_time_ms,
                "operations_count": summary["total_operations"],
                "entities_affected": summary["entities_affected"]
            }
        )
        
        # Log successful transaction
        _log_transaction_result(
            session, post_id, service_name, operation_name, 
            "success", None, processing_time_ms, summary
        )
        
    except Exception as e:
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        logger.error(
            f"Transaction failed: {service_name}.{operation_name}: {e}",
            extra={
                "post_id": post_id,
                "error_type": type(e).__name__,
                "processing_time_ms": processing_time_ms
            }
        )
        
        try:
            # Rollback transaction
            session.rollback()
            logger.info(f"Transaction rolled back successfully: {service_name}.{operation_name}")
            
            # Log failed transaction
            _log_transaction_result(
                session, post_id, service_name, operation_name,
                "failed", str(e), processing_time_ms, state_tracker.get_summary()
            )
            
        except Exception as rollback_error:
            logger.error(f"Transaction rollback failed: {rollback_error}")
            raise TransactionRollbackError(f"Rollback failed: {rollback_error}") from e
        
        raise
    
    finally:
        session.close()


def _log_transaction_result(
    session: Session,
    post_id: Optional[str],
    service_name: str,
    operation_name: str,
    status: str,
    error_message: Optional[str],
    processing_time_ms: int,
    summary: Dict[str, Any]
):
    """Log transaction result to processing_logs table"""
    try:
        # Create a new session for logging to avoid issues with the main transaction
        log_session = get_database_session()
        
        log_entry = ProcessingLog(
            post_id=post_id,
            service_name=service_name,
            status=status,
            error_message=error_message,
            processing_time_ms=processing_time_ms,
            metadata={
                "operation": operation_name,
                "transaction_summary": summary
            },
            created_at=datetime.utcnow()
        )
        
        log_session.add(log_entry)
        log_session.commit()
        log_session.close()
        
    except Exception as log_error:
        logger.error(f"Failed to log transaction result: {log_error}")


def transactional(
    service_name: str,
    operation_name: Optional[str] = None,
    post_id_param: str = "post_id"
):
    """
    Decorator for automatic transaction management with state tracking
    
    Args:
        service_name: Name of the service
        operation_name: Name of the operation (defaults to function name)
        post_id_param: Parameter name that contains post_id
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract post_id from parameters
            post_id = kwargs.get(post_id_param)
            if not post_id and args:
                # Try to get from first positional argument if it looks like a post_id
                if isinstance(args[0], str):
                    post_id = args[0]
            
            op_name = operation_name or func.__name__
            
            with transaction_with_tracking(post_id, service_name, op_name) as (session, tracker):
                # Inject session and tracker into function
                if 'session' in func.__code__.co_varnames:
                    kwargs['session'] = session
                if 'state_tracker' in func.__code__.co_varnames:
                    kwargs['state_tracker'] = tracker
                
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


class DatabaseStateManager:
    """Manage database state changes with consistency checks"""
    
    def __init__(self, session: Session, tracker: TransactionStateTracker):
        self.session = session
        self.tracker = tracker
    
    def create_entity(self, entity, entity_type: str, entity_id: str):
        """Create entity with state tracking"""
        try:
            self.session.add(entity)
            self.session.flush()  # Get ID without committing
            
            self.tracker.record_change(
                "CREATE", entity_type, entity_id,
                old_state=None,
                new_state=self._entity_to_dict(entity)
            )
            
            logger.debug(f"Created {entity_type}:{entity_id}")
            
        except IntegrityError as e:
            logger.error(f"Integrity error creating {entity_type}:{entity_id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating {entity_type}:{entity_id}: {e}")
            raise
    
    def update_entity(self, entity, entity_type: str, entity_id: str, old_state: Dict):
        """Update entity with state tracking"""
        try:
            self.tracker.record_change(
                "UPDATE", entity_type, entity_id,
                old_state=old_state,
                new_state=self._entity_to_dict(entity)
            )
            
            # Entity is already attached to session, changes will be persisted on commit
            logger.debug(f"Updated {entity_type}:{entity_id}")
            
        except SQLAlchemyError as e:
            logger.error(f"Database error updating {entity_type}:{entity_id}: {e}")
            raise
    
    def delete_entity(self, entity, entity_type: str, entity_id: str):
        """Delete entity with state tracking"""
        try:
            old_state = self._entity_to_dict(entity)
            
            self.session.delete(entity)
            
            self.tracker.record_change(
                "DELETE", entity_type, entity_id,
                old_state=old_state,
                new_state=None
            )
            
            logger.debug(f"Deleted {entity_type}:{entity_id}")
            
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting {entity_type}:{entity_id}: {e}")
            raise
    
    def _entity_to_dict(self, entity) -> Dict[str, Any]:
        """Convert SQLAlchemy entity to dictionary for state tracking"""
        try:
            # Get all column attributes
            result = {}
            for column in entity.__table__.columns:
                value = getattr(entity, column.name, None)
                # Convert datetime to ISO string for JSON serialization
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value
            return result
        except Exception as e:
            logger.warning(f"Failed to convert entity to dict: {e}")
            return {"error": "failed_to_serialize"}
    
    def check_consistency(self) -> Dict[str, Any]:
        """Check database consistency after operations"""
        consistency_checks = {
            "foreign_key_violations": [],
            "orphaned_records": [],
            "duplicate_constraints": []
        }
        
        try:
            # Check for foreign key violations (basic check)
            # This would be expanded based on specific schema requirements
            
            # For now, just verify session is in good state
            self.session.flush()
            
            consistency_checks["status"] = "passed"
            
        except IntegrityError as e:
            consistency_checks["status"] = "failed"
            consistency_checks["integrity_errors"] = [str(e)]
            logger.error(f"Consistency check failed: {e}")
            
        except Exception as e:
            consistency_checks["status"] = "error"
            consistency_checks["unexpected_errors"] = [str(e)]
            logger.error(f"Consistency check error: {e}")
        
        return consistency_checks


def get_state_manager(session: Session, tracker: TransactionStateTracker) -> DatabaseStateManager:
    """Get database state manager instance"""
    return DatabaseStateManager(session, tracker)