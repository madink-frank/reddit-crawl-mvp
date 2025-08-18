"""
Daily API call budget management for Reddit API (MVP)
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import redis
import requests

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DailyBudgetManager:
    """
    Manages daily API call budget for Reddit API
    - Tracks daily call count using Redis counter
    - Sends Slack alerts at 80% and 100% thresholds
    - Blocks collection when 100% reached
    """
    
    def __init__(self):
        self.daily_limit = settings.reddit_daily_calls_limit
        self.alert_threshold_80 = int(self.daily_limit * 0.8)
        self.alert_threshold_100 = self.daily_limit
        self.slack_webhook_url = settings.slack_webhook_url
        
        # Redis keys for tracking
        self.redis_key_prefix = "reddit_api_budget"
        
        # Initialize Redis connection
        try:
            self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            self.redis_client.ping()  # Test connection
        except Exception as e:
            logger.error(f"Failed to connect to Redis for budget management: {e}")
            self.redis_client = None
    
    def _get_today_key(self) -> str:
        """Get Redis key for today's API call count"""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"{self.redis_key_prefix}:calls:{today}"
    
    def _get_alert_key(self, threshold: int) -> str:
        """Get Redis key for alert tracking"""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"{self.redis_key_prefix}:alert:{threshold}:{today}"
    
    def get_daily_usage(self) -> Dict[str, Any]:
        """Get current daily API usage statistics"""
        if not self.redis_client:
            return {
                "calls_made": 0,
                "daily_limit": self.daily_limit,
                "remaining": self.daily_limit,
                "percentage_used": 0.0,
                "status": "unknown",
                "error": "Redis connection unavailable"
            }
        
        try:
            today_key = self._get_today_key()
            calls_made = int(self.redis_client.get(today_key) or 0)
            remaining = max(0, self.daily_limit - calls_made)
            percentage_used = (calls_made / self.daily_limit) * 100 if self.daily_limit > 0 else 0
            
            # Determine status
            if calls_made >= self.daily_limit:
                status = "budget_exceeded"
            elif calls_made >= self.alert_threshold_80:
                status = "budget_warning"
            else:
                status = "budget_ok"
            
            return {
                "calls_made": calls_made,
                "daily_limit": self.daily_limit,
                "remaining": remaining,
                "percentage_used": round(percentage_used, 1),
                "status": status,
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
            }
            
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return {
                "calls_made": 0,
                "daily_limit": self.daily_limit,
                "remaining": self.daily_limit,
                "percentage_used": 0.0,
                "status": "error",
                "error": str(e)
            }
    
    def can_make_request(self) -> bool:
        """Check if we can make an API request without exceeding daily budget"""
        usage = self.get_daily_usage()
        return usage["remaining"] > 0
    
    def record_api_call(self) -> Dict[str, Any]:
        """
        Record an API call and check for budget thresholds
        Returns usage info and any alerts that should be sent
        """
        if not self.redis_client:
            logger.warning("Redis unavailable, cannot track API calls")
            return {"status": "error", "message": "Redis unavailable"}
        
        try:
            today_key = self._get_today_key()
            
            # Increment the counter
            calls_made = self.redis_client.incr(today_key)
            
            # Set expiry for automatic cleanup (25 hours to handle timezone issues)
            self.redis_client.expire(today_key, 25 * 3600)
            
            # Get current usage stats
            usage = self.get_daily_usage()
            
            # Check for alert thresholds
            alert_sent = False
            
            # Check 80% threshold
            if calls_made == self.alert_threshold_80:
                alert_sent = self._send_budget_alert(80, usage)
            
            # Check 100% threshold
            elif calls_made == self.alert_threshold_100:
                alert_sent = self._send_budget_alert(100, usage)
            
            return {
                "status": "success",
                "usage": usage,
                "alert_sent": alert_sent
            }
            
        except Exception as e:
            logger.error(f"Error recording API call: {e}")
            return {"status": "error", "message": str(e)}
    
    def _send_budget_alert(self, threshold_percent: int, usage: Dict[str, Any]) -> bool:
        """Send Slack alert for budget threshold"""
        if not self.slack_webhook_url:
            logger.warning("Slack webhook URL not configured, cannot send budget alert")
            return False
        
        # Check if we already sent this alert today
        alert_key = self._get_alert_key(threshold_percent)
        if self.redis_client and self.redis_client.get(alert_key):
            logger.info(f"Budget alert for {threshold_percent}% already sent today")
            return False
        
        try:
            # Prepare alert message
            if threshold_percent == 80:
                color = "warning"
                title = "⚠️ Reddit API Budget Warning"
                message = f"Daily API budget is at {threshold_percent}% ({usage['calls_made']}/{usage['daily_limit']} calls)"
            else:  # 100%
                color = "danger"
                title = "🚨 Reddit API Budget Exceeded"
                message = f"Daily API budget exceeded! ({usage['calls_made']}/{usage['daily_limit']} calls). Collection will be suspended."
            
            payload = {
                "text": title,
                "attachments": [
                    {
                        "color": color,
                        "fields": [
                            {"title": "Calls Made", "value": str(usage['calls_made']), "short": True},
                            {"title": "Daily Limit", "value": str(usage['daily_limit']), "short": True},
                            {"title": "Remaining", "value": str(usage['remaining']), "short": True},
                            {"title": "Percentage Used", "value": f"{usage['percentage_used']}%", "short": True},
                            {"title": "Date", "value": usage['date'], "short": True},
                            {"title": "Status", "value": usage['status'], "short": True}
                        ],
                        "text": message,
                        "footer": "Reddit Ghost Publisher",
                        "ts": int(time.time())
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(
                self.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Budget alert sent successfully for {threshold_percent}% threshold")
                
                # Mark alert as sent for today
                if self.redis_client:
                    self.redis_client.set(alert_key, "sent", ex=25 * 3600)  # 25 hours
                
                return True
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending budget alert: {e}")
            return False
    
    def reset_daily_budget(self) -> Dict[str, Any]:
        """
        Manually reset daily budget (for testing or manual intervention)
        This should normally happen automatically at UTC 00:00
        """
        if not self.redis_client:
            return {"status": "error", "message": "Redis unavailable"}
        
        try:
            today_key = self._get_today_key()
            
            # Delete the counter
            deleted = self.redis_client.delete(today_key)
            
            # Delete alert flags
            alert_80_key = self._get_alert_key(80)
            alert_100_key = self._get_alert_key(100)
            self.redis_client.delete(alert_80_key, alert_100_key)
            
            logger.info("Daily budget reset successfully")
            
            return {
                "status": "success",
                "message": "Daily budget reset",
                "keys_deleted": deleted,
                "new_usage": self.get_daily_usage()
            }
            
        except Exception as e:
            logger.error(f"Error resetting daily budget: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_budget_history(self, days: int = 7) -> Dict[str, Any]:
        """Get budget usage history for the last N days"""
        if not self.redis_client:
            return {"status": "error", "message": "Redis unavailable"}
        
        try:
            history = {}
            
            for i in range(days):
                # Calculate date
                date = datetime.now(timezone.utc) - timedelta(days=i)
                date_str = date.strftime("%Y%m%d")
                date_display = date.strftime("%Y-%m-%d")
                
                # Get usage for that day
                key = f"{self.redis_key_prefix}:calls:{date_str}"
                calls = int(self.redis_client.get(key) or 0)
                
                history[date_display] = {
                    "calls_made": calls,
                    "percentage_used": round((calls / self.daily_limit) * 100, 1) if self.daily_limit > 0 else 0
                }
            
            return {
                "status": "success",
                "daily_limit": self.daily_limit,
                "history": history
            }
            
        except Exception as e:
            logger.error(f"Error getting budget history: {e}")
            return {"status": "error", "message": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Health check for budget manager"""
        try:
            if not self.redis_client:
                return {
                    "status": "unhealthy",
                    "error": "Redis connection unavailable"
                }
            
            # Test Redis connection
            self.redis_client.ping()
            
            # Get current usage
            usage = self.get_daily_usage()
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "slack_configured": bool(self.slack_webhook_url),
                "current_usage": usage
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global instance
budget_manager = DailyBudgetManager()


def get_budget_manager() -> DailyBudgetManager:
    """Get budget manager instance"""
    return budget_manager