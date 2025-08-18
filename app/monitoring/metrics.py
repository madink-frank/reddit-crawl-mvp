"""
Enhanced metrics collection with error classification for Reddit Ghost Publisher
Implements DB-based metrics aggregation with Prometheus format output
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from sqlalchemy import func, text, and_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.processing_log import ProcessingLog
from app.models.token_usage import TokenUsage


logger = logging.getLogger(__name__)
settings = get_settings()


class ErrorType(Enum):
    """Error classification types for external API failures"""
    RATE_LIMIT = "429"          # HTTP 429 rate limit errors
    TIMEOUT = "timeout"         # Connection/request timeouts
    SERVER_ERROR = "5xx"        # HTTP 5xx server errors
    LOGIC_ERROR = "logic_error" # Application logic errors
    UNKNOWN = "unknown"         # Unclassified errors


class MetricsCollector:
    """Enhanced metrics collector with error classification"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.settings = get_settings()
    
    def get_processing_metrics(self, time_window_hours: int = 24) -> Dict[str, int]:
        """
        Get processing metrics from database with time window
        
        Args:
            time_window_hours: Time window in hours for metrics collection
            
        Returns:
            Dictionary with processing metrics
        """
        try:
            # Calculate time window
            start_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            
            # Query processing logs within time window
            query = self.db_session.query(
                ProcessingLog.service_name,
                ProcessingLog.status,
                func.count(ProcessingLog.id).label('count')
            ).filter(
                ProcessingLog.created_at >= start_time
            ).group_by(
                ProcessingLog.service_name,
                ProcessingLog.status
            )
            
            results = query.all()
            
            # Initialize metrics
            metrics = {
                "reddit_posts_collected_total": 0,
                "posts_processed_total": 0,
                "posts_published_total": 0,
                "processing_failures_total": 0,
                "collector_failures_total": 0,
                "nlp_failures_total": 0,
                "publisher_failures_total": 0,
                "collector_success_total": 0,
                "nlp_success_total": 0,
                "publisher_success_total": 0
            }
            
            # Process results
            for row in results:
                service_name, status, count = row
                
                # Success metrics
                if status in ("success", "completed", "processed"):
                    if service_name == "collector":
                        metrics["reddit_posts_collected_total"] = count
                        metrics["collector_success_total"] = count
                    elif service_name == "nlp_pipeline":
                        metrics["posts_processed_total"] = count
                        metrics["nlp_success_total"] = count
                    elif service_name == "publisher":
                        metrics["posts_published_total"] = count
                        metrics["publisher_success_total"] = count
                
                # Failure metrics
                elif status in ("failed", "error", "exception"):
                    if service_name == "collector":
                        metrics["collector_failures_total"] = count
                    elif service_name == "nlp_pipeline":
                        metrics["nlp_failures_total"] = count
                    elif service_name == "publisher":
                        metrics["publisher_failures_total"] = count
                    
                    metrics["processing_failures_total"] += count
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get processing metrics: {e}")
            return self._get_empty_processing_metrics()
    
    def get_error_classification_metrics(self, time_window_hours: int = 24) -> Dict[str, int]:
        """
        Get error classification metrics from processing logs
        
        Args:
            time_window_hours: Time window in hours for metrics collection
            
        Returns:
            Dictionary with error classification metrics
        """
        try:
            start_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            
            # Query failed processing logs with error messages
            query = self.db_session.query(
                ProcessingLog.service_name,
                ProcessingLog.error_message
            ).filter(
                and_(
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.status.in_(["failed", "error", "exception"]),
                    ProcessingLog.error_message.isnot(None)
                )
            )
            
            results = query.all()
            
            # Initialize error classification metrics
            error_metrics = {
                "api_errors_429_total": 0,
                "api_errors_timeout_total": 0,
                "api_errors_5xx_total": 0,
                "api_errors_logic_error_total": 0,
                "api_errors_unknown_total": 0,
                "reddit_api_errors_429_total": 0,
                "reddit_api_errors_timeout_total": 0,
                "reddit_api_errors_5xx_total": 0,
                "openai_api_errors_429_total": 0,
                "openai_api_errors_timeout_total": 0,
                "openai_api_errors_5xx_total": 0,
                "ghost_api_errors_429_total": 0,
                "ghost_api_errors_timeout_total": 0,
                "ghost_api_errors_5xx_total": 0
            }
            
            # Classify errors
            for service_name, error_message in results:
                if not error_message:
                    continue
                
                error_type = self._classify_error(error_message)
                
                # Update general error metrics
                if error_type == ErrorType.RATE_LIMIT:
                    error_metrics["api_errors_429_total"] += 1
                elif error_type == ErrorType.TIMEOUT:
                    error_metrics["api_errors_timeout_total"] += 1
                elif error_type == ErrorType.SERVER_ERROR:
                    error_metrics["api_errors_5xx_total"] += 1
                elif error_type == ErrorType.LOGIC_ERROR:
                    error_metrics["api_errors_logic_error_total"] += 1
                else:
                    error_metrics["api_errors_unknown_total"] += 1
                
                # Update service-specific error metrics
                service_prefix = self._get_service_prefix(service_name)
                if service_prefix and error_type != ErrorType.UNKNOWN:
                    metric_key = f"{service_prefix}_api_errors_{error_type.value}_total"
                    if metric_key in error_metrics:
                        error_metrics[metric_key] += 1
            
            return error_metrics
            
        except Exception as e:
            logger.error(f"Failed to get error classification metrics: {e}")
            return self._get_empty_error_metrics()
    
    def get_token_usage_metrics(self, time_window_hours: int = 24) -> Dict[str, float]:
        """
        Get token usage metrics from database
        
        Args:
            time_window_hours: Time window in hours for metrics collection
            
        Returns:
            Dictionary with token usage metrics
        """
        try:
            start_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            
            query = self.db_session.query(
                TokenUsage.model,
                func.sum(TokenUsage.input_tokens).label('total_input_tokens'),
                func.sum(TokenUsage.output_tokens).label('total_output_tokens'),
                func.sum(TokenUsage.cost_usd).label('total_cost')
            ).filter(
                TokenUsage.created_at >= start_time
            ).group_by(TokenUsage.model)
            
            results = query.all()
            
            # Initialize metrics
            metrics = {
                "openai_tokens_used_total": 0,
                "openai_cost_usd_total": 0.0,
                "openai_gpt4o_mini_tokens_total": 0,
                "openai_gpt4o_tokens_total": 0,
                "openai_input_tokens_total": 0,
                "openai_output_tokens_total": 0
            }
            
            # Process results
            for row in results:
                model, input_tokens, output_tokens, cost = row
                input_tokens = input_tokens or 0
                output_tokens = output_tokens or 0
                cost = cost or 0.0
                total_tokens = input_tokens + output_tokens
                
                metrics["openai_tokens_used_total"] += total_tokens
                metrics["openai_input_tokens_total"] += input_tokens
                metrics["openai_output_tokens_total"] += output_tokens
                metrics["openai_cost_usd_total"] += cost
                
                if model == "gpt-4o-mini":
                    metrics["openai_gpt4o_mini_tokens_total"] = total_tokens
                elif model == "gpt-4o":
                    metrics["openai_gpt4o_tokens_total"] = total_tokens
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get token usage metrics: {e}")
            return self._get_empty_token_metrics()
    
    def get_recent_failure_rate(self, time_window_minutes: int = 5) -> float:
        """
        Get failure rate for recent time window (sliding window)
        
        Args:
            time_window_minutes: Time window in minutes for failure rate calculation
            
        Returns:
            Failure rate as float between 0.0 and 1.0
        """
        try:
            start_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
            
            # Get total and failed tasks in time window
            total_query = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                ProcessingLog.created_at >= start_time
            )
            
            failed_query = self.db_session.query(
                func.count(ProcessingLog.id)
            ).filter(
                and_(
                    ProcessingLog.created_at >= start_time,
                    ProcessingLog.status.in_(["failed", "error", "exception"])
                )
            )
            
            total_tasks = total_query.scalar() or 0
            failed_tasks = failed_query.scalar() or 0
            
            if total_tasks == 0:
                return 0.0
            
            return failed_tasks / total_tasks
            
        except Exception as e:
            logger.error(f"Failed to get recent failure rate: {e}")
            return 0.0
    
    def get_queue_metrics(self) -> Dict[str, int]:
        """
        Get queue metrics from Redis (if available)
        
        Returns:
            Dictionary with queue metrics
        """
        try:
            from app.infrastructure import get_redis_client
            
            redis_client = get_redis_client()
            
            # Get queue lengths for each queue
            queue_metrics = {
                "queue_collect_pending": 0,
                "queue_process_pending": 0,
                "queue_publish_pending": 0,
                "queue_total_pending": 0
            }
            
            # Check each queue
            queues = [
                (self.settings.queue_collect_name, "queue_collect_pending"),
                (self.settings.queue_process_name, "queue_process_pending"),
                (self.settings.queue_publish_name, "queue_publish_pending")
            ]
            
            for queue_name, metric_key in queues:
                try:
                    queue_length = redis_client.llen(queue_name)
                    queue_metrics[metric_key] = queue_length
                    queue_metrics["queue_total_pending"] += queue_length
                except Exception as e:
                    logger.warning(f"Failed to get queue length for {queue_name}: {e}")
            
            return queue_metrics
            
        except Exception as e:
            logger.error(f"Failed to get queue metrics: {e}")
            return {
                "queue_collect_pending": 0,
                "queue_process_pending": 0,
                "queue_publish_pending": 0,
                "queue_total_pending": 0
            }
    
    def _classify_error(self, error_message: str) -> ErrorType:
        """
        Classify error message into error types
        
        Args:
            error_message: Error message to classify
            
        Returns:
            ErrorType enum value
        """
        if not error_message:
            return ErrorType.UNKNOWN
        
        error_lower = error_message.lower()
        
        # Rate limit errors (429)
        if any(keyword in error_lower for keyword in [
            "429", "rate limit", "too many requests", "quota exceeded"
        ]):
            return ErrorType.RATE_LIMIT
        
        # Timeout errors
        if any(keyword in error_lower for keyword in [
            "timeout", "timed out", "connection timeout", "read timeout"
        ]):
            return ErrorType.TIMEOUT
        
        # Server errors (5xx)
        if any(keyword in error_lower for keyword in [
            "500", "502", "503", "504", "internal server error", 
            "bad gateway", "service unavailable", "gateway timeout"
        ]):
            return ErrorType.SERVER_ERROR
        
        # Logic errors (application-specific)
        if any(keyword in error_lower for keyword in [
            "validation", "invalid", "missing", "not found", "unauthorized",
            "forbidden", "bad request", "conflict", "unprocessable"
        ]):
            return ErrorType.LOGIC_ERROR
        
        return ErrorType.UNKNOWN
    
    def _get_service_prefix(self, service_name: str) -> Optional[str]:
        """
        Get service prefix for error metrics
        
        Args:
            service_name: Service name from processing log
            
        Returns:
            Service prefix for metrics or None
        """
        service_mapping = {
            "collector": "reddit",
            "nlp_pipeline": "openai",
            "publisher": "ghost"
        }
        return service_mapping.get(service_name)
    
    def _get_empty_processing_metrics(self) -> Dict[str, int]:
        """Get empty processing metrics dictionary"""
        return {
            "reddit_posts_collected_total": 0,
            "posts_processed_total": 0,
            "posts_published_total": 0,
            "processing_failures_total": 0,
            "collector_failures_total": 0,
            "nlp_failures_total": 0,
            "publisher_failures_total": 0,
            "collector_success_total": 0,
            "nlp_success_total": 0,
            "publisher_success_total": 0
        }
    
    def _get_empty_error_metrics(self) -> Dict[str, int]:
        """Get empty error classification metrics dictionary"""
        return {
            "api_errors_429_total": 0,
            "api_errors_timeout_total": 0,
            "api_errors_5xx_total": 0,
            "api_errors_logic_error_total": 0,
            "api_errors_unknown_total": 0,
            "reddit_api_errors_429_total": 0,
            "reddit_api_errors_timeout_total": 0,
            "reddit_api_errors_5xx_total": 0,
            "openai_api_errors_429_total": 0,
            "openai_api_errors_timeout_total": 0,
            "openai_api_errors_5xx_total": 0,
            "ghost_api_errors_429_total": 0,
            "ghost_api_errors_timeout_total": 0,
            "ghost_api_errors_5xx_total": 0
        }
    
    def _get_empty_token_metrics(self) -> Dict[str, float]:
        """Get empty token usage metrics dictionary"""
        return {
            "openai_tokens_used_total": 0,
            "openai_cost_usd_total": 0.0,
            "openai_gpt4o_mini_tokens_total": 0,
            "openai_gpt4o_tokens_total": 0,
            "openai_input_tokens_total": 0,
            "openai_output_tokens_total": 0
        }


class PrometheusFormatter:
    """Formats metrics in Prometheus text format"""
    
    @staticmethod
    def format_metrics(
        processing_metrics: Dict[str, int],
        error_metrics: Dict[str, int],
        token_metrics: Dict[str, float],
        queue_metrics: Dict[str, int],
        failure_rate: float
    ) -> str:
        """
        Format all metrics in Prometheus text format
        
        Args:
            processing_metrics: Processing metrics dictionary
            error_metrics: Error classification metrics dictionary
            token_metrics: Token usage metrics dictionary
            queue_metrics: Queue metrics dictionary
            failure_rate: Recent failure rate
            
        Returns:
            Prometheus formatted metrics string
        """
        prometheus_output = []
        
        # Processing metrics (counters)
        prometheus_output.extend([
            "# HELP reddit_posts_collected_total Total Reddit posts collected",
            "# TYPE reddit_posts_collected_total counter",
            f"reddit_posts_collected_total {processing_metrics['reddit_posts_collected_total']}",
            "",
            "# HELP posts_processed_total Total posts processed with AI",
            "# TYPE posts_processed_total counter", 
            f"posts_processed_total {processing_metrics['posts_processed_total']}",
            "",
            "# HELP posts_published_total Total posts published to Ghost",
            "# TYPE posts_published_total counter",
            f"posts_published_total {processing_metrics['posts_published_total']}",
            "",
            "# HELP processing_failures_total Total processing failures",
            "# TYPE processing_failures_total counter",
            f"processing_failures_total {processing_metrics['processing_failures_total']}",
            ""
        ])
        
        # Service-specific metrics
        prometheus_output.extend([
            "# HELP collector_success_total Total collector successes",
            "# TYPE collector_success_total counter",
            f"collector_success_total {processing_metrics['collector_success_total']}",
            "",
            "# HELP collector_failures_total Total collector failures",
            "# TYPE collector_failures_total counter",
            f"collector_failures_total {processing_metrics['collector_failures_total']}",
            "",
            "# HELP nlp_success_total Total NLP pipeline successes",
            "# TYPE nlp_success_total counter",
            f"nlp_success_total {processing_metrics['nlp_success_total']}",
            "",
            "# HELP nlp_failures_total Total NLP pipeline failures", 
            "# TYPE nlp_failures_total counter",
            f"nlp_failures_total {processing_metrics['nlp_failures_total']}",
            "",
            "# HELP publisher_success_total Total publisher successes",
            "# TYPE publisher_success_total counter",
            f"publisher_success_total {processing_metrics['publisher_success_total']}",
            "",
            "# HELP publisher_failures_total Total publisher failures",
            "# TYPE publisher_failures_total counter",
            f"publisher_failures_total {processing_metrics['publisher_failures_total']}",
            ""
        ])
        
        # Error classification metrics
        prometheus_output.extend([
            "# HELP api_errors_429_total Total API rate limit errors (429)",
            "# TYPE api_errors_429_total counter",
            f"api_errors_429_total {error_metrics['api_errors_429_total']}",
            "",
            "# HELP api_errors_timeout_total Total API timeout errors",
            "# TYPE api_errors_timeout_total counter",
            f"api_errors_timeout_total {error_metrics['api_errors_timeout_total']}",
            "",
            "# HELP api_errors_5xx_total Total API server errors (5xx)",
            "# TYPE api_errors_5xx_total counter",
            f"api_errors_5xx_total {error_metrics['api_errors_5xx_total']}",
            "",
            "# HELP api_errors_logic_error_total Total API logic errors",
            "# TYPE api_errors_logic_error_total counter",
            f"api_errors_logic_error_total {error_metrics['api_errors_logic_error_total']}",
            "",
            "# HELP api_errors_unknown_total Total unclassified API errors",
            "# TYPE api_errors_unknown_total counter",
            f"api_errors_unknown_total {error_metrics['api_errors_unknown_total']}",
            ""
        ])
        
        # Service-specific error metrics
        for service in ["reddit", "openai", "ghost"]:
            for error_type in ["429", "timeout", "5xx"]:
                metric_name = f"{service}_api_errors_{error_type}_total"
                prometheus_output.extend([
                    f"# HELP {metric_name} Total {service} API {error_type} errors",
                    f"# TYPE {metric_name} counter",
                    f"{metric_name} {error_metrics[metric_name]}",
                    ""
                ])
        
        # Token usage metrics
        prometheus_output.extend([
            "# HELP openai_tokens_used_total Total OpenAI tokens used",
            "# TYPE openai_tokens_used_total counter",
            f"openai_tokens_used_total {token_metrics['openai_tokens_used_total']}",
            "",
            "# HELP openai_input_tokens_total Total OpenAI input tokens",
            "# TYPE openai_input_tokens_total counter",
            f"openai_input_tokens_total {token_metrics['openai_input_tokens_total']}",
            "",
            "# HELP openai_output_tokens_total Total OpenAI output tokens",
            "# TYPE openai_output_tokens_total counter",
            f"openai_output_tokens_total {token_metrics['openai_output_tokens_total']}",
            "",
            "# HELP openai_cost_usd_total Total OpenAI cost in USD",
            "# TYPE openai_cost_usd_total counter",
            f"openai_cost_usd_total {token_metrics['openai_cost_usd_total']:.6f}",
            "",
            "# HELP openai_gpt4o_mini_tokens_total GPT-4o-mini tokens used",
            "# TYPE openai_gpt4o_mini_tokens_total counter",
            f"openai_gpt4o_mini_tokens_total {token_metrics['openai_gpt4o_mini_tokens_total']}",
            "",
            "# HELP openai_gpt4o_tokens_total GPT-4o tokens used",
            "# TYPE openai_gpt4o_tokens_total counter",
            f"openai_gpt4o_tokens_total {token_metrics['openai_gpt4o_tokens_total']}",
            ""
        ])
        
        # Queue metrics
        prometheus_output.extend([
            "# HELP queue_collect_pending Pending tasks in collect queue",
            "# TYPE queue_collect_pending gauge",
            f"queue_collect_pending {queue_metrics['queue_collect_pending']}",
            "",
            "# HELP queue_process_pending Pending tasks in process queue",
            "# TYPE queue_process_pending gauge",
            f"queue_process_pending {queue_metrics['queue_process_pending']}",
            "",
            "# HELP queue_publish_pending Pending tasks in publish queue",
            "# TYPE queue_publish_pending gauge",
            f"queue_publish_pending {queue_metrics['queue_publish_pending']}",
            "",
            "# HELP queue_total_pending Total pending tasks across all queues",
            "# TYPE queue_total_pending gauge",
            f"queue_total_pending {queue_metrics['queue_total_pending']}",
            ""
        ])
        
        # Failure rate gauge (last 5 minutes sliding window)
        prometheus_output.extend([
            "# HELP processing_failure_rate_5m Processing failure rate over last 5 minutes",
            "# TYPE processing_failure_rate_5m gauge",
            f"processing_failure_rate_5m {failure_rate:.4f}",
            ""
        ])
        
        return "\n".join(prometheus_output)


def get_all_metrics(db_session: Session) -> str:
    """
    Get all metrics in Prometheus format
    
    Args:
        db_session: Database session
        
    Returns:
        Prometheus formatted metrics string
    """
    collector = MetricsCollector(db_session)
    
    # Collect all metrics
    processing_metrics = collector.get_processing_metrics()
    error_metrics = collector.get_error_classification_metrics()
    token_metrics = collector.get_token_usage_metrics()
    queue_metrics = collector.get_queue_metrics()
    failure_rate = collector.get_recent_failure_rate()
    
    # Format as Prometheus metrics
    return PrometheusFormatter.format_metrics(
        processing_metrics,
        error_metrics,
        token_metrics,
        queue_metrics,
        failure_rate
    )