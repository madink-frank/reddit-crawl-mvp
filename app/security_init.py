"""
Security initialization for Reddit Ghost Publisher MVP
Initialize secret management, PII masking, and budget tracking
"""
import logging
import asyncio
from typing import Dict, Any

from app.security import get_secret_manager, create_budget_manager, safe_log
from app.redis_client import redis_client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def initialize_security() -> Dict[str, Any]:
    """Initialize security components and validate configuration"""
    try:
        # Initialize secret manager
        secret_manager = get_secret_manager()
        secret_status = secret_manager.load_all_secrets()
        
        # Initialize budget manager with Redis
        budget_manager = create_budget_manager(redis_client)
        
        # Get initial budget status
        budget_status = await budget_manager.get_budget_status()
        
        # Log initialization (with PII masking)
        safe_log(
            "Security components initialized successfully",
            secret_status=secret_status,
            budget_status={
                'reddit_limit': budget_status['reddit']['daily_limit'],
                'openai_limit': budget_status['openai']['daily_limit'],
                'timezone': budget_status['timezone']
            }
        )
        
        return {
            'status': 'success',
            'secret_manager': secret_manager,
            'budget_manager': budget_manager,
            'secret_status': secret_status,
            'budget_status': budget_status
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize security components: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'secret_manager': None,
            'budget_manager': None
        }


async def check_budget_alerts(budget_manager) -> Dict[str, Any]:
    """Check budget status and return alert information"""
    try:
        budget_status = await budget_manager.get_budget_status()
        alerts = []
        
        # Check Reddit budget
        reddit_budget = budget_status['reddit']
        if reddit_budget['warning_threshold_100']:
            alerts.append({
                'service': 'reddit',
                'level': 'critical',
                'message': f"Reddit API daily limit exceeded: {reddit_budget['current_usage']}/{reddit_budget['daily_limit']} calls",
                'usage_percent': reddit_budget['usage_percent']
            })
        elif reddit_budget['warning_threshold_80']:
            alerts.append({
                'service': 'reddit',
                'level': 'warning',
                'message': f"Reddit API usage at 80%: {reddit_budget['current_usage']}/{reddit_budget['daily_limit']} calls",
                'usage_percent': reddit_budget['usage_percent']
            })
        
        # Check OpenAI budget
        openai_budget = budget_status['openai']
        if openai_budget['warning_threshold_100']:
            alerts.append({
                'service': 'openai',
                'level': 'critical',
                'message': f"OpenAI token daily limit exceeded: {openai_budget['current_usage']}/{openai_budget['daily_limit']} tokens",
                'usage_percent': openai_budget['usage_percent']
            })
        elif openai_budget['warning_threshold_80']:
            alerts.append({
                'service': 'openai',
                'level': 'warning',
                'message': f"OpenAI token usage at 80%: {openai_budget['current_usage']}/{openai_budget['daily_limit']} tokens",
                'usage_percent': openai_budget['usage_percent']
            })
        
        return {
            'alerts': alerts,
            'budget_status': budget_status,
            'has_critical_alerts': any(alert['level'] == 'critical' for alert in alerts),
            'has_warning_alerts': any(alert['level'] == 'warning' for alert in alerts)
        }
        
    except Exception as e:
        logger.error(f"Failed to check budget alerts: {e}")
        return {
            'alerts': [],
            'budget_status': {},
            'has_critical_alerts': False,
            'has_warning_alerts': False,
            'error': str(e)
        }


def validate_timezone_config() -> bool:
    """Validate that timezone is set to UTC"""
    import os
    
    tz_env = os.getenv('TZ', '').upper()
    celery_tz = settings.celery_timezone.upper()
    app_tz = settings.timezone.upper()
    
    # Check all timezone settings are UTC
    if tz_env != 'UTC':
        logger.warning(f"TZ environment variable is not UTC: {tz_env}")
        return False
    
    if celery_tz != 'UTC':
        logger.warning(f"Celery timezone is not UTC: {celery_tz}")
        return False
    
    if app_tz != 'UTC':
        logger.warning(f"Application timezone is not UTC: {app_tz}")
        return False
    
    logger.info("All timezone settings validated as UTC")
    return True


async def get_daily_reset_info() -> Dict[str, Any]:
    """Get information about daily usage reset timing"""
    from datetime import datetime, timezone
    
    now_utc = datetime.now(timezone.utc)
    next_reset = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # If it's already past midnight, next reset is tomorrow
    if now_utc.hour > 0 or now_utc.minute > 0 or now_utc.second > 0:
        from datetime import timedelta
        next_reset += timedelta(days=1)
    
    seconds_until_reset = int((next_reset - now_utc).total_seconds())
    
    return {
        'current_time_utc': now_utc.isoformat(),
        'next_reset_utc': next_reset.isoformat(),
        'seconds_until_reset': seconds_until_reset,
        'hours_until_reset': round(seconds_until_reset / 3600, 2),
        'timezone': 'UTC'
    }


# Global security state
_security_initialized = False
_budget_manager = None


async def get_budget_manager():
    """Get initialized budget manager"""
    global _budget_manager, _security_initialized
    
    if not _security_initialized:
        init_result = await initialize_security()
        _budget_manager = init_result.get('budget_manager')
        _security_initialized = True
    
    return _budget_manager


def is_security_initialized() -> bool:
    """Check if security components are initialized"""
    return _security_initialized