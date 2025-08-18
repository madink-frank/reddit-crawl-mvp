"""
Logging configuration with PII masking for Reddit Ghost Publisher MVP
Structured logging with security-aware formatters
"""
import os
import sys
import json
import logging
import logging.config
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.security import PIIMasker, mask_sensitive_data


class PIIMaskingFormatter(logging.Formatter):
    """Custom formatter that masks PII in log messages"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pii_masker = PIIMasker()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with PII masking"""
        # Mask the main message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self.pii_masker.mask_sensitive_data(record.msg)
        
        # Mask arguments
        if hasattr(record, 'args') and record.args:
            masked_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    masked_args.append(self.pii_masker.mask_sensitive_data(arg))
                elif isinstance(arg, dict):
                    masked_args.append(self.pii_masker.mask_dict(arg))
                else:
                    masked_args.append(arg)
            record.args = tuple(masked_args)
        
        # Mask extra fields
        for key, value in record.__dict__.items():
            if key.startswith('_') or key in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                continue
            
            if isinstance(value, str):
                setattr(record, key, self.pii_masker.mask_sensitive_data(value))
            elif isinstance(value, dict):
                setattr(record, key, self.pii_masker.mask_dict(value))
        
        return super().format(record)


class StructuredJSONFormatter(PIIMaskingFormatter):
    """JSON formatter with PII masking for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with PII masking"""
        # Apply PII masking first
        super().format(record)
        
        # Create structured log entry
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                if not key.startswith('_'):
                    log_entry[key] = value
        
        return json.dumps(log_entry, default=str, ensure_ascii=False)


class SecurityAuditFormatter(PIIMaskingFormatter):
    """Special formatter for security audit logs"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format security audit log with enhanced masking"""
        # Apply PII masking
        super().format(record)
        
        # Create audit log entry
        audit_entry = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'event_type': 'security_audit',
            'level': record.levelname,
            'service': getattr(record, 'service', 'unknown'),
            'action': getattr(record, 'action', 'unknown'),
            'user': getattr(record, 'user', 'system'),
            'ip_address': getattr(record, 'ip_address', 'unknown'),
            'user_agent': mask_sensitive_data(getattr(record, 'user_agent', 'unknown')),
            'message': record.getMessage(),
            'details': getattr(record, 'details', {})
        }
        
        # Mask the details dictionary
        if isinstance(audit_entry['details'], dict):
            audit_entry['details'] = self.pii_masker.mask_dict(audit_entry['details'])
        
        return json.dumps(audit_entry, default=str, ensure_ascii=False)


def setup_logging() -> None:
    """Setup logging configuration with PII masking"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                '()': PIIMaskingFormatter,
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                '()': PIIMaskingFormatter,
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(funcName)s(): %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'json': {
                '()': StructuredJSONFormatter,
            },
            'security_audit': {
                '()': SecurityAuditFormatter,
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'json' if settings.structured_logging else 'standard',
                'stream': sys.stdout
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': 'json' if settings.structured_logging else 'detailed',
                'filename': log_dir / 'reddit_publisher.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'encoding': 'utf-8'
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': logging.ERROR,
                'formatter': 'json' if settings.structured_logging else 'detailed',
                'filename': log_dir / 'reddit_publisher_errors.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 10,
                'encoding': 'utf-8'
            },
            'security_audit': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': logging.INFO,
                'formatter': 'security_audit',
                'filename': log_dir / 'security_audit.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 20,  # Keep more security logs
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            # Root logger
            '': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            },
            # Application loggers
            'app': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            },
            'workers': {
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            },
            # Security audit logger
            'security': {
                'level': logging.INFO,
                'handlers': ['security_audit', 'console'],
                'propagate': False
            },
            # External library loggers (reduce noise)
            'urllib3': {
                'level': logging.WARNING,
                'handlers': ['file'],
                'propagate': False
            },
            'requests': {
                'level': logging.WARNING,
                'handlers': ['file'],
                'propagate': False
            },
            'praw': {
                'level': logging.INFO,
                'handlers': ['file'],
                'propagate': False
            },
            'openai': {
                'level': logging.INFO,
                'handlers': ['file'],
                'propagate': False
            },
            'celery': {
                'level': logging.INFO,
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'sqlalchemy': {
                'level': logging.WARNING,
                'handlers': ['file'],
                'propagate': False
            }
        }
    }
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Log startup message
    logger = logging.getLogger('app.logging')
    logger.info(
        "Logging system initialized",
        extra={
            'log_level': settings.log_level,
            'structured_logging': settings.structured_logging,
            'environment': settings.environment
        }
    )


def get_security_logger() -> logging.Logger:
    """Get security audit logger"""
    return logging.getLogger('security')


def log_security_event(
    action: str,
    service: str,
    user: str = 'system',
    ip_address: str = 'unknown',
    user_agent: str = 'unknown',
    details: Optional[Dict[str, Any]] = None,
    level: int = logging.INFO
) -> None:
    """Log security event with proper formatting
    
    Args:
        action: Action being performed
        service: Service name
        user: User performing action
        ip_address: IP address of user
        user_agent: User agent string
        details: Additional details
        level: Log level
    """
    logger = get_security_logger()
    
    logger.log(
        level,
        f"Security event: {action}",
        extra={
            'action': action,
            'service': service,
            'user': user,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'details': details or {}
        }
    )


def log_api_access(
    endpoint: str,
    method: str,
    status_code: int,
    user: str = 'anonymous',
    ip_address: str = 'unknown',
    user_agent: str = 'unknown',
    response_time_ms: Optional[float] = None,
    request_size: Optional[int] = None,
    response_size: Optional[int] = None
) -> None:
    """Log API access with security context
    
    Args:
        endpoint: API endpoint accessed
        method: HTTP method
        status_code: HTTP status code
        user: User making request
        ip_address: IP address
        user_agent: User agent string
        response_time_ms: Response time in milliseconds
        request_size: Request size in bytes
        response_size: Response size in bytes
    """
    logger = get_security_logger()
    
    details = {
        'endpoint': endpoint,
        'method': method,
        'status_code': status_code,
        'response_time_ms': response_time_ms,
        'request_size': request_size,
        'response_size': response_size
    }
    
    # Remove None values
    details = {k: v for k, v in details.items() if v is not None}
    
    log_security_event(
        action='api_access',
        service='api',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        level=logging.INFO if status_code < 400 else logging.WARNING
    )


def log_authentication_event(
    event_type: str,
    user: str,
    success: bool,
    ip_address: str = 'unknown',
    user_agent: str = 'unknown',
    details: Optional[Dict[str, Any]] = None
) -> None:
    """Log authentication event
    
    Args:
        event_type: Type of auth event (login, logout, token_refresh, etc.)
        user: Username or user ID
        success: Whether authentication was successful
        ip_address: IP address
        user_agent: User agent string
        details: Additional details
    """
    logger = get_security_logger()
    
    event_details = {
        'event_type': event_type,
        'success': success,
        **(details or {})
    }
    
    log_security_event(
        action=f'auth_{event_type}',
        service='auth',
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        details=event_details,
        level=logging.INFO if success else logging.WARNING
    )


def log_data_access(
    resource: str,
    action: str,
    user: str,
    success: bool,
    record_count: Optional[int] = None,
    filters: Optional[Dict[str, Any]] = None,
    ip_address: str = 'unknown'
) -> None:
    """Log data access event
    
    Args:
        resource: Resource being accessed (posts, users, etc.)
        action: Action performed (read, create, update, delete)
        user: User performing action
        success: Whether action was successful
        record_count: Number of records affected
        filters: Filters applied to query
        ip_address: IP address
    """
    logger = get_security_logger()
    
    details = {
        'resource': resource,
        'action': action,
        'success': success,
        'record_count': record_count,
        'filters': filters
    }
    
    # Remove None values
    details = {k: v for k, v in details.items() if v is not None}
    
    log_security_event(
        action=f'data_{action}',
        service='database',
        user=user,
        ip_address=ip_address,
        details=details,
        level=logging.INFO if success else logging.ERROR
    )


def log_external_api_call(
    service: str,
    endpoint: str,
    method: str,
    status_code: Optional[int] = None,
    response_time_ms: Optional[float] = None,
    error: Optional[str] = None,
    rate_limit_remaining: Optional[int] = None
) -> None:
    """Log external API call
    
    Args:
        service: External service name (reddit, openai, ghost)
        endpoint: API endpoint
        method: HTTP method
        status_code: HTTP status code
        response_time_ms: Response time in milliseconds
        error: Error message if any
        rate_limit_remaining: Remaining rate limit
    """
    logger = logging.getLogger(f'app.external.{service}')
    
    details = {
        'endpoint': endpoint,
        'method': method,
        'status_code': status_code,
        'response_time_ms': response_time_ms,
        'error': error,
        'rate_limit_remaining': rate_limit_remaining
    }
    
    # Remove None values
    details = {k: v for k, v in details.items() if v is not None}
    
    level = logging.INFO
    if error or (status_code and status_code >= 400):
        level = logging.ERROR
    elif status_code and status_code >= 300:
        level = logging.WARNING
    
    logger.log(
        level,
        f"External API call to {service}: {method} {endpoint}",
        extra=details
    )


# Context managers for structured logging
class LogContext:
    """Context manager for adding structured logging context"""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_context = {}
    
    def __enter__(self):
        # Store old context and add new context
        for key, value in self.context.items():
            if hasattr(self.logger, key):
                self.old_context[key] = getattr(self.logger, key)
            setattr(self.logger, key, value)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old context
        for key in self.context.keys():
            if key in self.old_context:
                setattr(self.logger, key, self.old_context[key])
            else:
                delattr(self.logger, key)


def with_log_context(logger: logging.Logger, **context):
    """Create log context manager"""
    return LogContext(logger, **context)


# Initialize logging on module import
if not logging.getLogger().handlers:
    setup_logging()