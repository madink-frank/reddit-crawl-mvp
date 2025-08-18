"""
Daily report system for Reddit Ghost Publisher
Generates comprehensive daily reports with metrics aggregation and cost estimation
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.config import get_settings
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage
from app.models.post import Post
from app.monitoring.notifications import SlackNotifier


logger = logging.getLogger(__name__)
settings = get_settings()


class DailyReportGenerator:
    """Generates comprehensive daily reports with metrics and cost analysis"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.settings = get_settings()
        self.notifier = SlackNotifier()
    
    def generate_daily_report(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate comprehensive daily report
        
        Args:
            date: Date to generate report for (defaults to yesterday)
            
        Returns:
            Dictionary with complete daily report data
        """
        try:
            # Default to yesterday for daily reports
            if date is None:
                date = (datetime.utcnow() - timedelta(days=1)).date()
            elif isinstance(date, datetime):
                date = date.date()
            
            logger.info(f"Generating daily report for {date}")
            
            # Get time boundaries for the day
            start_of_day = datetime.combine(date, datetime.min.time())
            end_of_day = start_of_day + timedelta(days=1)
            
            # Collect all metrics
            collection_metrics = self._get_collection_metrics(start_of_day, end_of_day)
            processing_metrics = self._get_processing_metrics(start_of_day, end_of_day)
            publishing_metrics = self._get_publishing_metrics(start_of_day, end_of_day)
            token_metrics = self._get_token_usage_metrics(start_of_day, end_of_day)
            error_metrics = self._get_error_metrics(start_of_day, end_of_day)
            performance_metrics = self._get_performance_metrics(start_of_day, end_of_day)
            
            # Calculate costs
            cost_analysis = self._calculate_cost_analysis(token_metrics)
            
            # Determine overall status
            overall_status = self._determine_overall_status(
                collection_metrics, processing_metrics, publishing_metrics, error_metrics
            )
            
            # Build comprehensive report
            report = {
                "report_date": date.isoformat(),
                "generated_at": datetime.utcnow().isoformat(),
                "overall_status": overall_status,
                
                # Core metrics
                "collection": collection_metrics,
                "processing": processing_metrics,
                "publishing": publishing_metrics,
                "token_usage": token_metrics,
                "errors": error_metrics,
                "performance": performance_metrics,
                "costs": cost_analysis,
                
                # Summary statistics
                "summary": {
                    "total_posts_collected": collection_metrics.get("posts_collected", 0),
                    "total_posts_processed": processing_metrics.get("posts_processed", 0),
                    "total_posts_published": publishing_metrics.get("posts_published", 0),
                    "total_failures": error_metrics.get("total_failures", 0),
                    "success_rate": self._calculate_success_rate(collection_metrics, publishing_metrics),
                    "total_cost_usd": cost_analysis.get("total_cost_usd", 0.0),
                    "avg_processing_time_minutes": performance_metrics.get("avg_processing_time_minutes", 0.0)
                }
            }
            
            logger.info(f"Daily report generated successfully for {date}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            return self._get_empty_report(date)
    
    def send_daily_report(self, date: Optional[datetime] = None) -> bool:
        """
        Generate and send daily report to Slack
        
        Args:
            date: Date to generate report for (defaults to yesterday)
            
        Returns:
            True if report sent successfully, False otherwise
        """
        try:
            # Generate report
            report = self.generate_daily_report(date)
            
            # Send to Slack
            success = self._send_slack_report(report)
            
            if success:
                logger.info(f"Daily report sent successfully for {report['report_date']}")
            else:
                logger.error(f"Failed to send daily report for {report['report_date']}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False
    
    def _get_collection_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get Reddit collection metrics for the time period"""
        try:
            # Count successful collections
            posts_collected = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.service_name == "collector",
                    ProcessingLog.status.in_(["success", "completed"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).scalar() or 0
            
            # Count collection failures
            collection_failures = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.service_name == "collector",
                    ProcessingLog.status.in_(["failed", "error"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).scalar() or 0
            
            # Get unique subreddits collected from
            subreddits_collected = self.db_session.query(
                func.count(func.distinct(Post.subreddit))
            ).filter(
                and_(
                    Post.created_at >= start_time,
                    Post.created_at < end_time
                )
            ).scalar() or 0
            
            return {
                "posts_collected": posts_collected,
                "collection_failures": collection_failures,
                "subreddits_collected": subreddits_collected,
                "collection_success_rate": posts_collected / (posts_collected + collection_failures) if (posts_collected + collection_failures) > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error getting collection metrics: {e}")
            return {"posts_collected": 0, "collection_failures": 0, "subreddits_collected": 0, "collection_success_rate": 0.0}
    
    def _get_processing_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get AI processing metrics for the time period"""
        try:
            # Count successful processing
            posts_processed = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.service_name == "nlp_pipeline",
                    ProcessingLog.status.in_(["success", "completed"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).scalar() or 0
            
            # Count processing failures
            processing_failures = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.service_name == "nlp_pipeline",
                    ProcessingLog.status.in_(["failed", "error"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).scalar() or 0
            
            # Get average processing time
            avg_processing_time = self.db_session.query(
                func.avg(ProcessingLog.processing_time_ms)
            ).filter(
                and_(
                    ProcessingLog.service_name == "nlp_pipeline",
                    ProcessingLog.status.in_(["success", "completed"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time,
                    ProcessingLog.processing_time_ms.isnot(None)
                )
            ).scalar() or 0
            
            return {
                "posts_processed": posts_processed,
                "processing_failures": processing_failures,
                "avg_processing_time_ms": float(avg_processing_time),
                "processing_success_rate": posts_processed / (posts_processed + processing_failures) if (posts_processed + processing_failures) > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error getting processing metrics: {e}")
            return {"posts_processed": 0, "processing_failures": 0, "avg_processing_time_ms": 0.0, "processing_success_rate": 0.0}
    
    def _get_publishing_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get Ghost publishing metrics for the time period"""
        try:
            # Count successful publishing
            posts_published = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.service_name == "publisher",
                    ProcessingLog.status.in_(["success", "completed"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).scalar() or 0
            
            # Count publishing failures
            publishing_failures = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.service_name == "publisher",
                    ProcessingLog.status.in_(["failed", "error"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).scalar() or 0
            
            # Count posts with Ghost URLs (successfully published)
            posts_with_ghost_urls = self.db_session.query(
                func.count(Post.id)
            ).filter(
                and_(
                    Post.ghost_url.isnot(None),
                    Post.created_at >= start_time,
                    Post.created_at < end_time
                )
            ).scalar() or 0
            
            return {
                "posts_published": posts_published,
                "publishing_failures": publishing_failures,
                "posts_with_ghost_urls": posts_with_ghost_urls,
                "publishing_success_rate": posts_published / (posts_published + publishing_failures) if (posts_published + publishing_failures) > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error getting publishing metrics: {e}")
            return {"posts_published": 0, "publishing_failures": 0, "posts_with_ghost_urls": 0, "publishing_success_rate": 0.0}
    
    def _get_token_usage_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get OpenAI token usage metrics for the time period"""
        try:
            # Get token usage by model
            token_usage_query = self.db_session.query(
                TokenUsage.model,
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens'),
                func.sum(TokenUsage.cost_usd).label('cost_usd'),
                func.count(TokenUsage.id).label('api_calls')
            ).filter(
                and_(
                    TokenUsage.created_at >= start_time,
                    TokenUsage.created_at < end_time
                )
            ).group_by(TokenUsage.model).all()
            
            # Process results
            total_tokens = 0
            total_cost = 0.0
            total_api_calls = 0
            model_breakdown = {}
            
            for row in token_usage_query:
                model, input_tokens, output_tokens, cost, api_calls = row
                input_tokens = input_tokens or 0
                output_tokens = output_tokens or 0
                cost = cost or 0.0
                api_calls = api_calls or 0
                
                model_tokens = input_tokens + output_tokens
                total_tokens += model_tokens
                total_cost += cost
                total_api_calls += api_calls
                
                model_breakdown[model] = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": model_tokens,
                    "cost_usd": cost,
                    "api_calls": api_calls
                }
            
            return {
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost,
                "total_api_calls": total_api_calls,
                "model_breakdown": model_breakdown,
                "avg_tokens_per_call": total_tokens / total_api_calls if total_api_calls > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error getting token usage metrics: {e}")
            return {"total_tokens": 0, "total_cost_usd": 0.0, "total_api_calls": 0, "model_breakdown": {}, "avg_tokens_per_call": 0.0}
    
    def _get_error_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get error metrics for the time period"""
        try:
            # Count total failures by service
            error_query = self.db_session.query(
                ProcessingLog.service_name,
                func.count(ProcessingLog.id).label('error_count')
            ).filter(
                and_(
                    ProcessingLog.status.in_(["failed", "error"]),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).group_by(ProcessingLog.service_name).all()
            
            # Process results
            total_failures = 0
            service_failures = {}
            
            for service_name, error_count in error_query:
                total_failures += error_count
                service_failures[service_name] = error_count
            
            # Get most common error types
            common_errors = self.db_session.query(
                ProcessingLog.error_message,
                func.count(ProcessingLog.id).label('count')
            ).filter(
                and_(
                    ProcessingLog.status.in_(["failed", "error"]),
                    ProcessingLog.error_message.isnot(None),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).group_by(ProcessingLog.error_message).order_by(
                func.count(ProcessingLog.id).desc()
            ).limit(5).all()
            
            return {
                "total_failures": total_failures,
                "service_failures": service_failures,
                "common_errors": [
                    {"error": error_msg[:100], "count": count} 
                    for error_msg, count in common_errors
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting error metrics: {e}")
            return {"total_failures": 0, "service_failures": {}, "common_errors": []}
    
    def _get_performance_metrics(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get performance metrics for the time period"""
        try:
            # Get average processing times by service
            performance_query = self.db_session.query(
                ProcessingLog.service_name,
                func.avg(ProcessingLog.processing_time_ms).label('avg_time_ms'),
                func.max(ProcessingLog.processing_time_ms).label('max_time_ms'),
                func.min(ProcessingLog.processing_time_ms).label('min_time_ms')
            ).filter(
                and_(
                    ProcessingLog.status.in_(["success", "completed"]),
                    ProcessingLog.processing_time_ms.isnot(None),
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.created_at < end_time
                )
            ).group_by(ProcessingLog.service_name).all()
            
            # Process results
            service_performance = {}
            total_avg_time = 0.0
            
            for service_name, avg_time, max_time, min_time in performance_query:
                avg_time = float(avg_time or 0)
                max_time = float(max_time or 0)
                min_time = float(min_time or 0)
                
                service_performance[service_name] = {
                    "avg_time_ms": avg_time,
                    "max_time_ms": max_time,
                    "min_time_ms": min_time,
                    "avg_time_minutes": avg_time / 60000  # Convert to minutes
                }
                
                total_avg_time += avg_time
            
            # Calculate overall average
            avg_processing_time_minutes = (total_avg_time / len(performance_query) / 60000) if performance_query else 0.0
            
            return {
                "service_performance": service_performance,
                "avg_processing_time_minutes": avg_processing_time_minutes
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {"service_performance": {}, "avg_processing_time_minutes": 0.0}
    
    def _calculate_cost_analysis(self, token_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive cost analysis"""
        try:
            total_cost = token_metrics.get("total_cost_usd", 0.0)
            total_tokens = token_metrics.get("total_tokens", 0)
            
            # Calculate cost per post (if we have posts)
            posts_processed = token_metrics.get("total_api_calls", 0)
            cost_per_post = total_cost / posts_processed if posts_processed > 0 else 0.0
            
            # Estimate monthly cost (30 days)
            estimated_monthly_cost = total_cost * 30
            
            # Calculate cost efficiency
            cost_per_1k_tokens = (total_cost / total_tokens * 1000) if total_tokens > 0 else 0.0
            
            return {
                "total_cost_usd": total_cost,
                "cost_per_post": cost_per_post,
                "estimated_monthly_cost": estimated_monthly_cost,
                "cost_per_1k_tokens": cost_per_1k_tokens,
                "cost_breakdown": token_metrics.get("model_breakdown", {})
            }
            
        except Exception as e:
            logger.error(f"Error calculating cost analysis: {e}")
            return {"total_cost_usd": 0.0, "cost_per_post": 0.0, "estimated_monthly_cost": 0.0, "cost_per_1k_tokens": 0.0, "cost_breakdown": {}}
    
    def _calculate_success_rate(self, collection_metrics: Dict[str, Any], publishing_metrics: Dict[str, Any]) -> float:
        """Calculate overall success rate from collection to publishing"""
        try:
            collected = collection_metrics.get("posts_collected", 0)
            published = publishing_metrics.get("posts_published", 0)
            
            return published / collected if collected > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating success rate: {e}")
            return 0.0
    
    def _determine_overall_status(
        self, 
        collection_metrics: Dict[str, Any], 
        processing_metrics: Dict[str, Any], 
        publishing_metrics: Dict[str, Any], 
        error_metrics: Dict[str, Any]
    ) -> str:
        """Determine overall system status for the day"""
        try:
            # Calculate success rates
            collection_success = collection_metrics.get("collection_success_rate", 0.0)
            processing_success = processing_metrics.get("processing_success_rate", 0.0)
            publishing_success = publishing_metrics.get("publishing_success_rate", 0.0)
            
            total_failures = error_metrics.get("total_failures", 0)
            
            # Determine status based on success rates and failures
            if collection_success >= 0.95 and processing_success >= 0.95 and publishing_success >= 0.95 and total_failures == 0:
                return "excellent"
            elif collection_success >= 0.9 and processing_success >= 0.9 and publishing_success >= 0.9 and total_failures < 5:
                return "good"
            elif collection_success >= 0.8 and processing_success >= 0.8 and publishing_success >= 0.8 and total_failures < 10:
                return "fair"
            else:
                return "poor"
                
        except Exception as e:
            logger.error(f"Error determining overall status: {e}")
            return "unknown"
    
    def _send_slack_report(self, report: Dict[str, Any]) -> bool:
        """Send formatted report to Slack"""
        try:
            summary = report.get("summary", {})
            costs = report.get("costs", {})
            errors = report.get("errors", {})
            
            # Determine report color based on overall status
            status = report.get("overall_status", "unknown")
            color_map = {
                "excellent": "good",
                "good": "good", 
                "fair": "warning",
                "poor": "danger",
                "unknown": "#808080"
            }
            
            emoji_map = {
                "excellent": "🌟",
                "good": "✅",
                "fair": "⚠️", 
                "poor": "❌",
                "unknown": "❓"
            }
            
            # Build Slack payload
            payload = {
                "text": f"📊 {emoji_map.get(status, '📊')} Daily Reddit Publisher Report - {report['report_date']}",
                "attachments": [
                    {
                        "color": color_map.get(status, "warning"),
                        "fields": [
                            {
                                "title": "Overall Status",
                                "value": status.title(),
                                "short": True
                            },
                            {
                                "title": "Success Rate",
                                "value": f"{summary.get('success_rate', 0):.1%}",
                                "short": True
                            },
                            {
                                "title": "Posts Collected",
                                "value": f"{summary.get('total_posts_collected', 0):,}",
                                "short": True
                            },
                            {
                                "title": "Posts Published",
                                "value": f"{summary.get('total_posts_published', 0):,}",
                                "short": True
                            },
                            {
                                "title": "Token Usage",
                                "value": f"{report.get('token_usage', {}).get('total_tokens', 0):,}",
                                "short": True
                            },
                            {
                                "title": "Total Cost",
                                "value": f"${costs.get('total_cost_usd', 0):.2f}",
                                "short": True
                            },
                            {
                                "title": "Failures",
                                "value": f"{errors.get('total_failures', 0):,}",
                                "short": True
                            },
                            {
                                "title": "Avg Processing Time",
                                "value": f"{summary.get('avg_processing_time_minutes', 0):.1f} min",
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            # Add cost breakdown if significant
            if costs.get('total_cost_usd', 0) > 0.01:
                cost_breakdown = costs.get('cost_breakdown', {})
                if cost_breakdown:
                    cost_details = []
                    for model, details in cost_breakdown.items():
                        cost_details.append(f"{model}: ${details.get('cost_usd', 0):.3f}")
                    
                    payload["attachments"][0]["fields"].append({
                        "title": "Cost Breakdown",
                        "value": "\n".join(cost_details),
                        "short": False
                    })
            
            # Add error summary if there are failures
            if errors.get('total_failures', 0) > 0:
                common_errors = errors.get('common_errors', [])
                if common_errors:
                    error_summary = []
                    for error in common_errors[:3]:  # Top 3 errors
                        error_summary.append(f"• {error['error']} ({error['count']}x)")
                    
                    payload["attachments"][0]["fields"].append({
                        "title": "Top Errors",
                        "value": "\n".join(error_summary),
                        "short": False
                    })
            
            # Send to Slack
            import requests
            response = requests.post(
                self.settings.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error sending Slack report: {e}")
            return False
    
    def _get_empty_report(self, date) -> Dict[str, Any]:
        """Get empty report structure for error cases"""
        return {
            "report_date": date.isoformat() if date else datetime.utcnow().date().isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "overall_status": "unknown",
            "collection": {"posts_collected": 0, "collection_failures": 0, "subreddits_collected": 0, "collection_success_rate": 0.0},
            "processing": {"posts_processed": 0, "processing_failures": 0, "avg_processing_time_ms": 0.0, "processing_success_rate": 0.0},
            "publishing": {"posts_published": 0, "publishing_failures": 0, "posts_with_ghost_urls": 0, "publishing_success_rate": 0.0},
            "token_usage": {"total_tokens": 0, "total_cost_usd": 0.0, "total_api_calls": 0, "model_breakdown": {}, "avg_tokens_per_call": 0.0},
            "errors": {"total_failures": 0, "service_failures": {}, "common_errors": []},
            "performance": {"service_performance": {}, "avg_processing_time_minutes": 0.0},
            "costs": {"total_cost_usd": 0.0, "cost_per_post": 0.0, "estimated_monthly_cost": 0.0, "cost_per_1k_tokens": 0.0, "cost_breakdown": {}},
            "summary": {
                "total_posts_collected": 0,
                "total_posts_processed": 0,
                "total_posts_published": 0,
                "total_failures": 0,
                "success_rate": 0.0,
                "total_cost_usd": 0.0,
                "avg_processing_time_minutes": 0.0
            }
        }


# Convenience functions for easy integration
def generate_daily_report(db_session: Session, date: Optional[datetime] = None) -> Dict[str, Any]:
    """Generate daily report"""
    generator = DailyReportGenerator(db_session)
    return generator.generate_daily_report(date)


def send_daily_report(db_session: Session, date: Optional[datetime] = None) -> bool:
    """Generate and send daily report"""
    generator = DailyReportGenerator(db_session)
    return generator.send_daily_report(date)