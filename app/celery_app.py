"""
Celery application configuration for Reddit Ghost Publisher MVP
Simplified configuration with Redis broker and task_routes based queues
"""
import os
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()


def _parse_cron_schedule(cron_expr: str) -> crontab:
    """Parse cron expression into Celery crontab schedule"""
    try:
        # Parse standard cron format: minute hour day month day_of_week
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            # Default to hourly if invalid format
            return crontab(minute="0")
        
        minute, hour, day, month, day_of_week = parts
        
        return crontab(
            minute=minute if minute != "*" else None,
            hour=hour if hour != "*" else None,
            day_of_month=day if day != "*" else None,
            month_of_year=month if month != "*" else None,
            day_of_week=day_of_week if day_of_week != "*" else None
        )
    except Exception:
        # Default to hourly collection if parsing fails
        return crontab(minute="0")

# Create Celery instance with Redis broker
celery_app = Celery(
    "reddit_ghost_publisher",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.collector.tasks",
        "workers.nlp_pipeline.tasks", 
        "workers.publisher.tasks",
        "app.monitoring.tasks",
        "app.backup_tasks"
    ]
)

# Simplified task routes (no AMQP attributes)
celery_app.conf.task_routes = {
    "workers.collector.tasks.*": {"queue": settings.queue_collect_name},
    "workers.nlp_pipeline.tasks.*": {"queue": settings.queue_process_name},
    "workers.publisher.tasks.*": {"queue": settings.queue_publish_name},
    "app.monitoring.tasks.*": {"queue": "monitoring"},
    "app.backup_tasks.*": {"queue": "backup"},
}

# Simplified Celery configuration for MVP
celery_app.conf.update(
    # Serialization
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    
    # Timezone (UTC unified)
    timezone=settings.celery_timezone,
    enable_utc=True,
    
    # Task execution
    task_always_eager=False,
    task_ignore_result=False,
    
    # Retry configuration (constants from settings)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Worker configuration (single node)
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Result backend configuration
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Task routing (simplified)
    task_default_queue=settings.queue_collect_name,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Beat schedule with COLLECT_CRON environment variable
    beat_schedule={
        "collect-reddit-posts": {
            "task": "workers.collector.tasks.collect_reddit_posts",
            "schedule": _parse_cron_schedule(settings.collect_cron),
            "options": {"queue": settings.queue_collect_name}
        },
        "health-check": {
            "task": "workers.collector.tasks.health_check", 
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {"queue": settings.queue_collect_name}
        },
        # Backup tasks (BACKUP_CRON environment variable)
        "scheduled-database-backup": {
            "task": "app.backup_tasks.scheduled_backup_workflow",
            "schedule": _parse_cron_schedule(settings.backup_cron),
            "options": {"queue": "backup"}
        },
        # Monitoring tasks
        "run-health-checks": {
            "task": "app.monitoring.tasks.run_health_checks",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {"queue": "monitoring"}
        },
        "send-daily-report": {
            "task": "app.monitoring.tasks.send_daily_report",
            "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM UTC
            "options": {"queue": "monitoring"}
        }
    },
    beat_schedule_filename="celerybeat-schedule",
)

# Task annotations for retry behavior (using constants from settings)
celery_app.conf.task_annotations = {
    "workers.collector.tasks.collect_reddit_posts": {
        "rate_limit": f"{settings.reddit_rate_limit_rpm}/m",  # Reddit API limit
        "max_retries": settings.retry_max,
        "default_retry_delay": settings.backoff_min,
        "autoretry_for": (Exception,),
        "retry_kwargs": {"max_retries": settings.retry_max, "countdown": settings.backoff_min}
    },
    "workers.nlp_pipeline.tasks.process_content_with_ai": {
        "max_retries": settings.retry_max,
        "default_retry_delay": settings.backoff_base * settings.backoff_min,
        "autoretry_for": (Exception,),
        "retry_kwargs": {"max_retries": settings.retry_max, "countdown": settings.backoff_base * settings.backoff_min}
    },
    "workers.publisher.tasks.publish_to_ghost": {
        "max_retries": settings.retry_max,
        "default_retry_delay": settings.backoff_min,
        "autoretry_for": (Exception,),
        "retry_kwargs": {"max_retries": settings.retry_max, "countdown": settings.backoff_min}
    },
    # Backup tasks
    "app.backup_tasks.scheduled_backup_workflow": {
        "max_retries": 1,
        "default_retry_delay": 300,
        "autoretry_for": (Exception,)
    },
    "app.backup_tasks.create_database_backup": {
        "max_retries": 3,
        "default_retry_delay": 300,
        "autoretry_for": (Exception,)
    },
    "app.backup_tasks.verify_backup": {
        "max_retries": 2,
        "default_retry_delay": 60,
        "autoretry_for": (Exception,)
    },
    # Monitoring tasks
    "app.monitoring.tasks.run_health_checks": {
        "max_retries": 2,
        "default_retry_delay": 60,
        "autoretry_for": (Exception,)
    },
    "app.monitoring.tasks.send_daily_report": {
        "max_retries": 3,
        "default_retry_delay": 300,
        "autoretry_for": (Exception,)
    }
}

# Error handling configuration
celery_app.conf.task_soft_time_limit = 300  # 5 minutes
celery_app.conf.task_time_limit = 600  # 10 minutes hard limit

if __name__ == "__main__":
    celery_app.start()