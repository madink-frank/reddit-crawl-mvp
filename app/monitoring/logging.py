"""
Enhanced logging system with PII masking for Reddit Ghost Publisher
Implements structured JSON logging with comprehensive PII protection
"""
import json
import logging
import re
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Union
from enum import Enum

from app.config import get_settings


class LogLevel(Enum):
    """Log levels for service-specific configuration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PIIMasker:
    """Comprehensive PII masking utility"""
    
    # Compiled regex patterns for performance
    API_KEY_PATTERN = re.compile(
        r'(api[_-]?key["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{10,})',
        re.IGNORECASE
    )
    
    TOKEN_PATTERN = re.compile(
        r'(token["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{10,})',
        re.IGNORECASE
    )
    
    SECRET_PATTERN = re.compile(
        r'(secret["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{10,})',
        re.IGNORECASE
    )
    
    PASSWORD_PATTERN = re.compile(
        r'(password["\s]*[:=]["\s]*)([^\s"\']{4,})',
        re.IGNORECASE
    )
    
    EMAIL_PATTERN = re.compile(
        r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    )
    
    AUTHORIZATION_PATTERN = re.compile(
        r'(authorization["\s]*[:=]["\s]*)([a-zA-Z0-9\-_=+/]{10,})',
        re.IGNORECASE
    )
    
    BEARER_TOKEN_PATTERN = re.compile(
        r'(bearer\s+)([a-zA-Z0-9\-_=+/]{10,})',
        re.IGNORECASE
    )
    
    JWT_PATTERN = re.compile(
        r'(eyJ[a-zA-Z0-9\-_=+/]{10,}\.eyJ[a-zA-Z0-9\-_=+/]{10,}\.[a-zA-Z0-9\-_=+/]{10,})'
    )
    
    REDDIT_CLIENT_SECRET_PATTERN = re.compile(
        r'(reddit[_-]?client[_-]?secret["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{10,})',
        re.IGNORECASE
    )
    
    OPENAI_KEY_PATTERN = re.compile(
        r'(sk-[a-zA-Z0-9]{20,})'
    )
    
    GHOST_ADMIN_KEY_PATTERN = re.compile(
        r'([a-f0-9]{24}:[a-f0-9]{64})'
    )
    
    # Credit card pattern (basic)
    CREDIT_CARD_PATTERN = re.compile(
        r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    )
    
    # Phone number pattern (basic)
    PHONE_PATTERN = re.compile(
        r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
    )
    
    @classmethod
    def mask_sensitive_data(cls, text: str) -> str:
        """
        Comprehensive PII masking for log messages
        
        Args:
            text: Text to mask
            
        Returns:
            Masked text with sensitive information replaced
        """
        if not isinstance(text, str):
            text = str(text)
        
        # API keys and tokens
        text = cls.API_KEY_PATTERN.sub(r'\1****', text)
        text = cls.TOKEN_PATTERN.sub(r'\1****', text)
        text = cls.SECRET_PATTERN.sub(r'\1****', text)
        text = cls.PASSWORD_PATTERN.sub(r'\1****', text)
        
        # Authorization headers
        text = cls.AUTHORIZATION_PATTERN.sub(r'\1****', text)
        text = cls.BEARER_TOKEN_PATTERN.sub(r'\1****', text)
        
        # JWT tokens
        text = cls.JWT_PATTERN.sub('eyJ****.eyJ****.****.', text)
        
        # Service-specific keys
        text = cls.REDDIT_CLIENT_SECRET_PATTERN.sub(r'\1****', text)
        text = cls.OPENAI_KEY_PATTERN.sub('sk-****', text)
        text = cls.GHOST_ADMIN_KEY_PATTERN.sub('****:****', text)
        
        # Email addresses (preserve domain for debugging)
        text = cls.EMAIL_PATTERN.sub(r'****@\2', text)
        
        # Credit cards
        text = cls.CREDIT_CARD_PATTERN.sub('****-****-****-****', text)
        
        # Phone numbers
        text = cls.PHONE_PATTERN.sub(r'\1(***) ***-\4', text)
        
        return text
    
    @classmethod
    def mask_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively mask sensitive data in dictionaries
        
        Args:
            data: Dictionary to mask
            
        Returns:
            Dictionary with masked sensitive values
        """
        if not isinstance(data, dict):
            return data
        
        masked_data = {}
        sensitive_keys = {
            'password', 'secret', 'token', 'key', 'authorization',
            'api_key', 'client_secret', 'admin_key', 'webhook_url',
            'database_url', 'redis_url'
        }
        
        for key, value in data.items():
            key_lower = key.lower()
            
            if any(sensitive_key in key_lower for sensitive_key in sensitive_keys):
                masked_data[key] = "****"
            elif isinstance(value, dict):
                masked_data[key] = cls.mask_dict(value)
            elif isinstance(value, list):
                masked_data[key] = [
                    cls.mask_dict(item) if isinstance(item, dict) 
                    else cls.mask_sensitive_data(str(item)) if isinstance(item, str)
                    else item
                    for item in value
                ]
            elif isinstance(value, str):
                masked_data[key] = cls.mask_sensitive_data(value)
            else:
                masked_data[key] = value
        
        return masked_data


class StructuredLogger:
    """Enhanced structured logger with PII masking"""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        self.settings = get_settings()
        
        # Configure handler if not already configured
        if not self.logger.handlers:
            self._configure_handler()
    
    def _configure_handler(self):
        """Configure logging handler with JSON formatting"""
        handler = logging.StreamHandler(sys.stdout)
        
        if self.settings.structured_logging:
            formatter = StructuredFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def _log_structured(
        self, 
        level: str, 
        message: str, 
        **kwargs
    ):
        """Log structured message with PII masking"""
        # Mask the message
        masked_message = PIIMasker.mask_sensitive_data(message)
        
        # Mask additional fields
        masked_kwargs = PIIMasker.mask_dict(kwargs)
        
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "message": masked_message,
            "service": "reddit-ghost-publisher",
            **masked_kwargs
        }
        
        # Log the structured entry
        getattr(self.logger, level.lower())(json.dumps(log_entry))
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log_structured("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log_structured("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log_structured("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log_structured("ERROR", message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log_structured("CRITICAL", message, **kwargs)
    
    def log_api_call(
        self,
        service: str,
        endpoint: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        duration_ms: Optional[float] = None,
        **kwargs
    ):
        """Log API call with standardized format"""
        self.info(
            f"API call to {service}",
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_processing_start(
        self,
        service: str,
        post_id: str,
        operation: str,
        **kwargs
    ):
        """Log processing start"""
        self.info(
            f"Starting {operation} in {service}",
            service=service,
            post_id=post_id,
            operation=operation,
            status="started",
            **kwargs
        )
    
    def log_processing_success(
        self,
        service: str,
        post_id: str,
        operation: str,
        duration_ms: Optional[float] = None,
        **kwargs
    ):
        """Log processing success"""
        self.info(
            f"Completed {operation} in {service}",
            service=service,
            post_id=post_id,
            operation=operation,
            status="success",
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_processing_failure(
        self,
        service: str,
        post_id: str,
        operation: str,
        error: str,
        duration_ms: Optional[float] = None,
        **kwargs
    ):
        """Log processing failure"""
        self.error(
            f"Failed {operation} in {service}",
            service=service,
            post_id=post_id,
            operation=operation,
            status="failed",
            error=error,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_rate_limit(
        self,
        service: str,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """Log rate limit hit"""
        self.warning(
            f"Rate limit hit for {service}",
            service=service,
            error_type="rate_limit",
            retry_after=retry_after,
            **kwargs
        )
    
    def log_budget_alert(
        self,
        budget_type: str,
        current_usage: Union[int, float],
        limit: Union[int, float],
        percentage: float,
        **kwargs
    ):
        """Log budget alert"""
        self.warning(
            f"Budget alert: {budget_type} at {percentage:.1f}%",
            budget_type=budget_type,
            current_usage=current_usage,
            limit=limit,
            percentage=percentage,
            **kwargs
        )


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        # If the message is already JSON, return as-is
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": PIIMasker.mask_sensitive_data(record.getMessage()),
            "service": "reddit-ghost-publisher"
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                          'pathname', 'filename', 'module', 'lineno', 
                          'funcName', 'created', 'msecs', 'relativeCreated', 
                          'thread', 'threadName', 'processName', 'process',
                          'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                if isinstance(value, str):
                    log_entry[key] = PIIMasker.mask_sensitive_data(value)
                else:
                    log_entry[key] = value
        
        return json.dumps(log_entry)


class ServiceLoggerConfig:
    """Service-specific logger configuration"""
    
    DEFAULT_LEVELS = {
        "collector": LogLevel.INFO,
        "nlp_pipeline": LogLevel.INFO,
        "publisher": LogLevel.INFO,
        "api": LogLevel.INFO,
        "metrics": LogLevel.WARNING,
        "health": LogLevel.WARNING,
        "celery": LogLevel.WARNING,
        "sqlalchemy": LogLevel.WARNING,
        "redis": LogLevel.WARNING
    }
    
    @classmethod
    def configure_service_loggers(cls):
        """Configure all service loggers with appropriate levels"""
        settings = get_settings()
        
        for service, default_level in cls.DEFAULT_LEVELS.items():
            # Get level from environment or use default
            env_key = f"{service.upper()}_LOG_LEVEL"
            level = getattr(settings, env_key.lower(), default_level.value)
            
            # Configure logger
            logger = StructuredLogger(f"app.{service}", level)
            
            # Set specific configurations
            if service == "sqlalchemy" and not settings.debug:
                # Reduce SQL query logging in production
                logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
            
            if service == "celery":
                # Configure Celery logging
                logging.getLogger("celery").setLevel(getattr(logging, level))
                logging.getLogger("celery.task").setLevel(getattr(logging, level))


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        StructuredLogger instance
    """
    settings = get_settings()
    return StructuredLogger(name, settings.log_level)


def configure_logging():
    """Configure application-wide logging"""
    settings = get_settings()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure service loggers
    ServiceLoggerConfig.configure_service_loggers()
    
    # Configure third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Log configuration completion
    logger = get_logger(__name__)
    logger.info(
        "Logging configuration completed",
        log_level=settings.log_level,
        structured_logging=settings.structured_logging,
        environment=settings.environment
    )