"""
API budget tracking and alerting system for Reddit Ghost Publisher
Tracks daily API usage and triggers alerts at threshold levels
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.config import get_settings
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage
from app.monitoring.notifications import send_api_budget_alert


logger = logging.getLogger(__name__)
settings = get_settings()


class BudgetType(Enum):
    """Budget types for tracking"""
    REDDIT_CALLS = "reddit_calls"
    OPENAI_TOKENS = "openai_tokens"


class BudgetTracker:
    """Tracks API budget usage and triggers alerts"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.settings = get_settings()
    
    def get_reddit_daily_usage(self, date: Optional[datetime] = None) -> Tuple[int, float]:
        """
        Get Reddit API daily usage
        
        Args:
            date: Date to check usage for (defaults to today)
            
        Returns:
            Tuple of (calls_made, usage_percentage)
        """
        try:
            if date is None:
                date = datetime.utcnow().date()
            
            # Get start and end of day in UTC
            start_of_day = datetime.combine(date, datetime.min.time())
            end_of_day = start_of_day + timedelta(days=1)
            
            # Count successful Reddit API calls from processing logs
            calls_made = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.service_name == "collector",
                    ProcessingLog.status.in_(["success", "completed"]),
                    ProcessingLog.created_at >= start_of_day,
                    ProcessingLog.created_at < end_of_day
                )
            ).scalar() or 0
            
            # Calculate usage percentage
            daily_limit = self.settings.reddit_daily_calls_limit
            usage_percentage = calls_made / daily_limit if daily_limit > 0 else 0.0
            
            return calls_made, usage_percentage
            
        except Exception as e:
            logger.error(f"Error getting Reddit daily usage: {e}")
            return 0, 0.0
    
    def get_openai_daily_usage(self, date: Optional[datetime] = None) -> Tuple[int, float, float]:
        """
        Get OpenAI token daily usage
        
        Args:
            date: Date to check usage for (defaults to today)
            
        Returns:
            Tuple of (tokens_used, usage_percentage, cost_usd)
        """
        try:
            if date is None:
                date = datetime.utcnow().date()
            
            # Get start and end of day in UTC
            start_of_day = datetime.combine(date, datetime.min.time())
            end_of_day = start_of_day + timedelta(days=1)
            
            # Get token usage from database
            result = self.db_session.query(
                func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens).label('total_tokens'),
                func.sum(TokenUsage.cost_usd).label('total_cost')
            ).filter(
                and_(
                    TokenUsage.created_at >= start_of_day,
                    TokenUsage.created_at < end_of_day
                )
            ).first()
            
            tokens_used = int(result.total_tokens or 0)
            cost_usd = float(result.total_cost or 0.0)
            
            # Calculate usage percentage
            daily_limit = self.settings.openai_daily_tokens_limit
            usage_percentage = tokens_used / daily_limit if daily_limit > 0 else 0.0
            
            return tokens_used, usage_percentage, cost_usd
            
        except Exception as e:
            logger.error(f"Error getting OpenAI daily usage: {e}")
            return 0, 0.0, 0.0
    
    def check_reddit_budget_alert(self, date: Optional[datetime] = None) -> bool:
        """
        Check Reddit API budget and send alert if needed
        
        Args:
            date: Date to check usage for (defaults to today)
            
        Returns:
            True if alert was sent, False otherwise
        """
        try:
            calls_made, usage_percentage = self.get_reddit_daily_usage(date)
            
            # Send alert if usage >= 80%
            if usage_percentage >= 0.8:
                logger.info(f"Reddit API usage at {usage_percentage:.1%}, sending alert")
                return send_api_budget_alert(
                    self.db_session,
                    "reddit",
                    usage_percentage
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking Reddit budget alert: {e}")
            return False
    
    def check_openai_budget_alert(self, date: Optional[datetime] = None) -> bool:
        """
        Check OpenAI token budget and send alert if needed
        
        Args:
            date: Date to check usage for (defaults to today)
            
        Returns:
            True if alert was sent, False otherwise
        """
        try:
            tokens_used, usage_percentage, cost_usd = self.get_openai_daily_usage(date)
            
            # Send alert if usage >= 80%
            if usage_percentage >= 0.8:
                logger.info(f"OpenAI token usage at {usage_percentage:.1%}, sending alert")
                return send_api_budget_alert(
                    self.db_session,
                    "openai",
                    usage_percentage
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking OpenAI budget alert: {e}")
            return False
    
    def is_reddit_budget_exhausted(self, date: Optional[datetime] = None) -> bool:
        """
        Check if Reddit API budget is exhausted (100% used)
        
        Args:
            date: Date to check usage for (defaults to today)
            
        Returns:
            True if budget is exhausted, False otherwise
        """
        try:
            _, usage_percentage = self.get_reddit_daily_usage(date)
            return usage_percentage >= 1.0
            
        except Exception as e:
            logger.error(f"Error checking Reddit budget exhaustion: {e}")
            return False
    
    def is_openai_budget_exhausted(self, date: Optional[datetime] = None) -> bool:
        """
        Check if OpenAI token budget is exhausted (100% used)
        
        Args:
            date: Date to check usage for (defaults to today)
            
        Returns:
            True if budget is exhausted, False otherwise
        """
        try:
            _, usage_percentage, _ = self.get_openai_daily_usage(date)
            return usage_percentage >= 1.0
            
        except Exception as e:
            logger.error(f"Error checking OpenAI budget exhaustion: {e}")
            return False
    
    def get_budget_summary(self, date: Optional[datetime] = None) -> Dict[str, any]:
        """
        Get comprehensive budget summary for reporting
        
        Args:
            date: Date to get summary for (defaults to today)
            
        Returns:
            Dictionary with budget summary
        """
        try:
            if date is None:
                date = datetime.utcnow().date()
            
            # Get Reddit usage
            reddit_calls, reddit_usage_pct = self.get_reddit_daily_usage(date)
            
            # Get OpenAI usage
            openai_tokens, openai_usage_pct, openai_cost = self.get_openai_daily_usage(date)
            
            return {
                "date": date.isoformat(),
                "reddit": {
                    "calls_made": reddit_calls,
                    "daily_limit": self.settings.reddit_daily_calls_limit,
                    "usage_percentage": reddit_usage_pct,
                    "remaining_calls": max(0, self.settings.reddit_daily_calls_limit - reddit_calls),
                    "budget_exhausted": reddit_usage_pct >= 1.0
                },
                "openai": {
                    "tokens_used": openai_tokens,
                    "daily_limit": self.settings.openai_daily_tokens_limit,
                    "usage_percentage": openai_usage_pct,
                    "remaining_tokens": max(0, self.settings.openai_daily_tokens_limit - openai_tokens),
                    "cost_usd": openai_cost,
                    "budget_exhausted": openai_usage_pct >= 1.0
                },
                "total_cost_usd": openai_cost,  # Reddit API is free
                "any_budget_exhausted": reddit_usage_pct >= 1.0 or openai_usage_pct >= 1.0
            }
            
        except Exception as e:
            logger.error(f"Error getting budget summary: {e}")
            return {
                "date": date.isoformat() if date else datetime.utcnow().date().isoformat(),
                "reddit": {
                    "calls_made": 0,
                    "daily_limit": self.settings.reddit_daily_calls_limit,
                    "usage_percentage": 0.0,
                    "remaining_calls": self.settings.reddit_daily_calls_limit,
                    "budget_exhausted": False
                },
                "openai": {
                    "tokens_used": 0,
                    "daily_limit": self.settings.openai_daily_tokens_limit,
                    "usage_percentage": 0.0,
                    "remaining_tokens": self.settings.openai_daily_tokens_limit,
                    "cost_usd": 0.0,
                    "budget_exhausted": False
                },
                "total_cost_usd": 0.0,
                "any_budget_exhausted": False
            }
    
    def check_all_budget_alerts(self, date: Optional[datetime] = None) -> Dict[str, bool]:
        """
        Check all budget alerts and send notifications if needed
        
        Args:
            date: Date to check usage for (defaults to today)
            
        Returns:
            Dictionary with alert status for each service
        """
        results = {
            "reddit_alert_sent": False,
            "openai_alert_sent": False
        }
        
        try:
            # Check Reddit budget
            results["reddit_alert_sent"] = self.check_reddit_budget_alert(date)
            
            # Check OpenAI budget
            results["openai_alert_sent"] = self.check_openai_budget_alert(date)
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking all budget alerts: {e}")
            return results


# Convenience functions for easy integration
def get_reddit_usage(db_session: Session, date: Optional[datetime] = None) -> Tuple[int, float]:
    """Get Reddit API daily usage"""
    tracker = BudgetTracker(db_session)
    return tracker.get_reddit_daily_usage(date)


def get_openai_usage(db_session: Session, date: Optional[datetime] = None) -> Tuple[int, float, float]:
    """Get OpenAI token daily usage"""
    tracker = BudgetTracker(db_session)
    return tracker.get_openai_daily_usage(date)


def check_budget_alerts(db_session: Session, date: Optional[datetime] = None) -> Dict[str, bool]:
    """Check all budget alerts"""
    tracker = BudgetTracker(db_session)
    return tracker.check_all_budget_alerts(date)


def is_reddit_budget_exhausted(db_session: Session, date: Optional[datetime] = None) -> bool:
    """Check if Reddit budget is exhausted"""
    tracker = BudgetTracker(db_session)
    return tracker.is_reddit_budget_exhausted(date)


def is_openai_budget_exhausted(db_session: Session, date: Optional[datetime] = None) -> bool:
    """Check if OpenAI budget is exhausted"""
    tracker = BudgetTracker(db_session)
    return tracker.is_openai_budget_exhausted(date)


def get_budget_summary(db_session: Session, date: Optional[datetime] = None) -> Dict[str, any]:
    """Get comprehensive budget summary"""
    tracker = BudgetTracker(db_session)
    return tracker.get_budget_summary(date)