"""
Takedown workflow module for Reddit Ghost Publisher

This module implements a 2-stage takedown process:
1. Stage 1: Unpublish from Ghost CMS and mark as takedown_pending
2. Stage 2: 72 hours later, delete from Ghost and mark as removed

Features:
- Audit logging for compliance
- SLA tracking (72-hour completion target)
- Transaction management with rollback capability
- Celery task scheduling for delayed deletion
- Monitoring and alerting for SLA violations
"""

from .takedown_manager import TakedownManager, get_takedown_manager
from .tasks import (
    initiate_takedown,
    complete_takedown_deletion,
    cancel_takedown,
    get_takedown_status,
    get_pending_takedowns,
    monitor_sla_compliance,
    trigger_takedown,
    trigger_takedown_cancellation,
    get_task_status
)

__all__ = [
    "TakedownManager",
    "get_takedown_manager",
    "initiate_takedown",
    "complete_takedown_deletion", 
    "cancel_takedown",
    "get_takedown_status",
    "get_pending_takedowns",
    "monitor_sla_compliance",
    "trigger_takedown",
    "trigger_takedown_cancellation",
    "get_task_status"
]