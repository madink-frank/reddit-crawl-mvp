"""
Enhanced Logging and Monitoring for Production Environment
Provides structured logging, performance tracking, and advanced monitoring capabilities
"""

import os
import sys
import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

from app.config import get_settings

# Enhanced log formatter
class StructuredFormatter(logging.Formatter):
    """Structured JSON formatter for production logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add performance metrics if present
        if hasattr(record, 'performance'):
            log_entry["performance"] = record.performance
        
        # Add request context if present
        if hasattr(record, 'request_context'):
            log_entry["request"] = record.request_context
        
        return json.dumps(log_entry, default=str)


class PerformanceLogger:
    """Performance logging and tracking"""
    
    def __init__(self):
        self.logger = logging.getLogger("performance")
        self.metrics = {
            "api_requests": [],
            "database_queries": [],
            "external_api_calls": [],
            "background_tasks": []
        }
        
    @contextmanager
    def track_api_request(self, method: str, path: str, **kwargs):
        """Track API request performance"""
        start_time = time.time()
        request_id = f"req_{int(start_time)}_{hash(path)}"
        
        try:
            yield request_id
        finally:
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            metric = {
                "request_id": request_id,
                "method": method,
                "path": path,
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }
            
            self.metrics["api_requests"].append(metric)
            self._cleanup_old_metrics("api_requests")
            
            # Log slow requests
            if duration > 1000:  # Slower than 1 second
                self.logger.warning(
                    f"Slow API request: {method} {path}",
                    extra={
                        "extra_fields": {
                            "performance": metric,
                            "category": "slow_request"
                        }
                    }
                )
    
    @contextmanager
    def track_database_query(self, query_type: str, **kwargs):
        """Track database query performance"""
        start_time = time.time()
        query_id = f"db_{int(start_time)}_{hash(query_type)}"
        
        try:
            yield query_id
        finally:
            duration = (time.time() - start_time) * 1000
            
            metric = {
                "query_id": query_id,
                "query_type": query_type,
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }
            
            self.metrics["database_queries"].append(metric)
            self._cleanup_old_metrics("database_queries")
            
            # Log slow queries
            if duration > 500:  # Slower than 500ms
                self.logger.warning(
                    f"Slow database query: {query_type}",
                    extra={
                        "extra_fields": {
                            "performance": metric,
                            "category": "slow_query"
                        }
                    }
                )
    
    @contextmanager
    def track_external_api_call(self, service: str, endpoint: str, **kwargs):
        """Track external API call performance"""
        start_time = time.time()
        call_id = f"ext_{int(start_time)}_{hash(service + endpoint)}"
        
        try:
            yield call_id
        finally:
            duration = (time.time() - start_time) * 1000
            
            metric = {
                "call_id": call_id,
                "service": service,
                "endpoint": endpoint,
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }
            
            self.metrics["external_api_calls"].append(metric)
            self._cleanup_old_metrics("external_api_calls")
            
            # Log slow external calls
            if duration > 2000:  # Slower than 2 seconds
                self.logger.warning(
                    f"Slow external API call: {service} {endpoint}",
                    extra={
                        "extra_fields": {
                            "performance": metric,
                            "category": "slow_external_call"
                        }
                    }
                )
    
    @contextmanager
    def track_background_task(self, task_name: str, **kwargs):
        """Track background task performance"""
        start_time = time.time()
        task_id = f"task_{int(start_time)}_{hash(task_name)}"
        
        try:
            yield task_id
        finally:
            duration = (time.time() - start_time) * 1000
            
            metric = {
                "task_id": task_id,
                "task_name": task_name,
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
                **kwargs
            }
            
            self.metrics["background_tasks"].append(metric)
            self._cleanup_old_metrics("background_tasks")
            
            # Log long-running tasks
            if duration > 30000:  # Longer than 30 seconds
                self.logger.info(
                    f"Long-running background task: {task_name}",
                    extra={
                        "extra_fields": {
                            "performance": metric,
                            "category": "long_task"
                        }
                    }
                )
    
    def _cleanup_old_metrics(self, metric_type: str, max_age_hours: int = 1):
        """Clean up old metrics to prevent memory growth"""
        if metric_type not in self.metrics:
            return
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        self.metrics[metric_type] = [
            metric for metric in self.metrics[metric_type]
            if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
        ]
    
    def get_performance_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance summary for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        summary = {}
        
        for metric_type, metrics in self.metrics.items():
            recent_metrics = [
                metric for metric in metrics
                if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
            ]
            
            if recent_metrics:
                durations = [metric["duration_ms"] for metric in recent_metrics]
                
                summary[metric_type] = {
                    "count": len(recent_metrics),
                    "avg_duration_ms": sum(durations) / len(durations),
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations),
                    "p95_duration_ms": self._calculate_percentile(durations, 95),
                    "p99_duration_ms": self._calculate_percentile(durations, 99)
                }
            else:
                summary[metric_type] = {
                    "count": 0,
                    "avg_duration_ms": 0,
                    "min_duration_ms": 0,
                    "max_duration_ms": 0,
                    "p95_duration_ms": 0,
                    "p99_duration_ms": 0
                }
        
        return summary
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        
        if index >= len(sorted_values):
            return sorted_values[-1]
        
        return sorted_values[index]


class SecurityLogger:
    """Security event logging"""
    
    def __init__(self):
        self.logger = logging.getLogger("security")
        self.security_events = []
    
    def log_authentication_attempt(self, success: bool, user_id: Optional[str] = None, ip_address: Optional[str] = None, **kwargs):
        """Log authentication attempt"""
        event = {
            "event_type": "authentication_attempt",
            "success": success,
            "user_id": user_id,
            "ip_address": ip_address,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        self.security_events.append(event)
        self._cleanup_old_events()
        
        level = logging.INFO if success else logging.WARNING
        message = f"Authentication {'successful' if success else 'failed'}"
        
        self.logger.log(
            level,
            message,
            extra={
                "extra_fields": {
                    "security_event": event,
                    "category": "authentication"
                }
            }
        )
    
    def log_authorization_failure(self, user_id: Optional[str], resource: str, action: str, **kwargs):
        """Log authorization failure"""
        event = {
            "event_type": "authorization_failure",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        self.security_events.append(event)
        self._cleanup_old_events()
        
        self.logger.warning(
            f"Authorization failed: {action} on {resource}",
            extra={
                "extra_fields": {
                    "security_event": event,
                    "category": "authorization"
                }
            }
        )
    
    def log_suspicious_activity(self, activity_type: str, details: Dict[str, Any], **kwargs):
        """Log suspicious activity"""
        event = {
            "event_type": "suspicious_activity",
            "activity_type": activity_type,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        self.security_events.append(event)
        self._cleanup_old_events()
        
        self.logger.error(
            f"Suspicious activity detected: {activity_type}",
            extra={
                "extra_fields": {
                    "security_event": event,
                    "category": "suspicious_activity"
                }
            }
        )
    
    def _cleanup_old_events(self, max_age_hours: int = 24):
        """Clean up old security events"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        self.security_events = [
            event for event in self.security_events
            if datetime.fromisoformat(event["timestamp"]) > cutoff_time
        ]
    
    def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get security events summary"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_events = [
            event for event in self.security_events
            if datetime.fromisoformat(event["timestamp"]) > cutoff_time
        ]
        
        summary = {
            "total_events": len(recent_events),
            "events_by_type": {},
            "authentication_attempts": {
                "total": 0,
                "successful": 0,
                "failed": 0
            },
            "authorization_failures": 0,
            "suspicious_activities": 0
        }
        
        for event in recent_events:
            event_type = event["event_type"]
            
            # Count by type
            if event_type not in summary["events_by_type"]:
                summary["events_by_type"][event_type] = 0
            summary["events_by_type"][event_type] += 1
            
            # Specific counters
            if event_type == "authentication_attempt":
                summary["authentication_attempts"]["total"] += 1
                if event.get("success"):
                    summary["authentication_attempts"]["successful"] += 1
                else:
                    summary["authentication_attempts"]["failed"] += 1
            elif event_type == "authorization_failure":
                summary["authorization_failures"] += 1
            elif event_type == "suspicious_activity":
                summary["suspicious_activities"] += 1
        
        return summary


class EnhancedLogger:
    """Enhanced logger with structured logging and context"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.performance = PerformanceLogger()
        self.security = SecurityLogger()
        
    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self.logger.info(message, extra={"extra_fields": kwargs})
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self.logger.warning(message, extra={"extra_fields": kwargs})
    
    def error(self, message: str, **kwargs):
        """Log error message with context"""
        self.logger.error(message, extra={"extra_fields": kwargs})
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self.logger.debug(message, extra={"extra_fields": kwargs})
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context"""
        self.logger.critical(message, extra={"extra_fields": kwargs})


def setup_enhanced_logging():
    """Setup enhanced logging configuration"""
    settings = get_settings()
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if settings.environment == "production" else logging.DEBUG)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with structured formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    if settings.environment == "production":
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
    
    root_logger.addHandler(console_handler)
    
    # File handlers for production
    if settings.environment == "production":
        # Application log file
        app_handler = logging.FileHandler(log_dir / "application.log")
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(app_handler)
        
        # Error log file
        error_handler = logging.FileHandler(log_dir / "errors.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
        
        # Performance log file
        perf_logger = logging.getLogger("performance")
        perf_handler = logging.FileHandler(log_dir / "performance.log")
        perf_handler.setFormatter(StructuredFormatter())
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)
        
        # Security log file
        sec_logger = logging.getLogger("security")
        sec_handler = logging.FileHandler(log_dir / "security.log")
        sec_handler.setFormatter(StructuredFormatter())
        sec_logger.addHandler(sec_handler)
        sec_logger.setLevel(logging.INFO)


def get_enhanced_logger(name: str) -> EnhancedLogger:
    """Get enhanced logger instance"""
    return EnhancedLogger(name)


# Global instances
performance_logger = PerformanceLogger()
security_logger = SecurityLogger()


def get_logging_stats() -> Dict[str, Any]:
    """Get logging and monitoring statistics"""
    return {
        "performance": performance_logger.get_performance_summary(),
        "security": security_logger.get_security_summary(),
        "timestamp": datetime.now().isoformat()
    }