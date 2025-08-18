"""
Input validation and security filters
Pydantic models and validation logic for API endpoints
"""
import re
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
# EmailStr is available in pydantic v2 as pydantic_extra_types
# from pydantic_extra_types import EmailStr
import structlog


logger = structlog.get_logger(__name__)


class SortType(str, Enum):
    """Reddit sort types"""
    HOT = "hot"
    NEW = "new"
    RISING = "rising"
    TOP = "top"


class TimeFilter(str, Enum):
    """Time filter for Reddit posts"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL = "all"


class ContentType(str, Enum):
    """Content types for processing"""
    ARTICLE = "article"
    LIST = "list"
    QA = "qa"


class BaseValidationModel(BaseModel):
    """Base model with common validation"""
    
    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
        "populate_by_name": True,
        "extra": "forbid"
    }
    
    @field_validator('*', mode='before')
    @classmethod
    def sanitize_strings(cls, v):
        """Sanitize string inputs to prevent XSS"""
        if isinstance(v, str):
            # Remove potentially dangerous characters
            v = re.sub(r'[<>"\']', '', v)
            # Limit string length to prevent DoS
            if len(v) > 10000:
                raise ValueError("String too long")
            # Strip whitespace
            v = v.strip()
        return v


class SubredditCollectionRequest(BaseValidationModel):
    """Request model for Reddit collection"""
    subreddits: List[str] = Field(
        ..., 
        min_items=1, 
        max_items=10,
        description="List of subreddit names to collect from"
    )
    sort_type: SortType = Field(
        default=SortType.HOT,
        description="Sort type for posts"
    )
    time_filter: Optional[TimeFilter] = Field(
        default=None,
        description="Time filter for top posts"
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Number of posts to collect per subreddit"
    )
    min_score: int = Field(
        default=10,
        ge=0,
        description="Minimum score for posts"
    )
    min_comments: int = Field(
        default=5,
        ge=0,
        description="Minimum number of comments"
    )
    
    @field_validator('subreddits')
    @classmethod
    def validate_subreddit_names(cls, v):
        """Validate subreddit names"""
        if not isinstance(v, list):
            raise ValueError("Subreddits must be a list")
        
        validated_subreddits = []
        for subreddit in v:
            if not isinstance(subreddit, str):
                raise ValueError("Subreddit name must be a string")
            
            # Remove r/ prefix if present
            if subreddit.startswith('r/'):
                subreddit = subreddit[2:]
            
            # Validate subreddit name format
            if not re.match(r'^[A-Za-z0-9_]{1,21}$', subreddit):
                raise ValueError(
                    "Invalid subreddit name. Must be 1-21 characters, "
                    "alphanumeric and underscores only"
                )
            
            validated_subreddits.append(subreddit)
        
        return validated_subreddits
    
    @model_validator(mode='after')
    def validate_time_filter_with_sort(self):
        """Validate time filter is only used with top sort"""
        if self.time_filter and self.sort_type != SortType.TOP:
            raise ValueError("Time filter can only be used with 'top' sort type")
        
        return self


class ContentProcessingRequest(BaseValidationModel):
    """Request model for content processing"""
    post_ids: List[str] = Field(
        ...,
        min_items=1,
        max_items=50,
        description="List of post IDs to process"
    )
    force_reprocess: bool = Field(
        default=False,
        description="Force reprocessing of already processed posts"
    )
    content_type: ContentType = Field(
        default=ContentType.ARTICLE,
        description="Type of content to generate"
    )
    
    @field_validator('post_ids')
    @classmethod
    def validate_post_ids(cls, v):
        """Validate Reddit post ID format"""
        if not isinstance(v, list):
            raise ValueError("Post IDs must be a list")
        
        validated_ids = []
        for post_id in v:
            if not isinstance(post_id, str):
                raise ValueError("Post ID must be a string")
            
            # Reddit post IDs are alphanumeric, 6-7 characters
            if not re.match(r'^[a-z0-9]{6,7}$', post_id):
                raise ValueError("Invalid Reddit post ID format")
            
            validated_ids.append(post_id)
        
        return validated_ids


class PublishingRequest(BaseValidationModel):
    """Request model for publishing to Ghost"""
    post_ids: List[str] = Field(
        ...,
        min_items=1,
        max_items=20,
        description="List of processed post IDs to publish"
    )
    publish_immediately: bool = Field(
        default=True,
        description="Publish immediately or save as draft"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        max_items=10,
        description="Additional tags to add to posts"
    )
    
    @field_validator('post_ids')
    @classmethod
    def validate_post_ids(cls, v):
        """Validate post ID format"""
        if not isinstance(v, list):
            raise ValueError("Post IDs must be a list")
        
        validated_ids = []
        for post_id in v:
            if not isinstance(post_id, str):
                raise ValueError("Post ID must be a string")
            
            if not re.match(r'^[a-z0-9]{6,7}$', post_id):
                raise ValueError("Invalid post ID format")
            
            validated_ids.append(post_id)
        
        return validated_ids
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate Ghost tags"""
        if v is None:
            return v
        
        if not isinstance(v, list):
            raise ValueError("Tags must be a list")
        
        validated_tags = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("Tag must be a string")
            
            # Ghost tag validation
            if len(tag) > 191:
                raise ValueError("Tag too long (max 191 characters)")
            
            # Remove special characters that could cause issues
            if re.search(r'[<>"\']', tag):
                raise ValueError("Tag contains invalid characters")
            
            validated_tags.append(tag.strip())
        
        return validated_tags


class QueueStatusRequest(BaseValidationModel):
    """Request model for queue status"""
    queue_names: Optional[List[str]] = Field(
        default=None,
        description="Specific queue names to check"
    )
    include_failed: bool = Field(
        default=False,
        description="Include failed tasks in response"
    )
    
    @field_validator('queue_names')
    @classmethod
    def validate_queue_names(cls, v):
        """Validate queue names"""
        if v is None:
            return v
        
        if not isinstance(v, list):
            raise ValueError("Queue names must be a list")
        
        valid_queues = ['collect', 'process', 'publish']
        validated_queues = []
        for queue_name in v:
            if queue_name not in valid_queues:
                raise ValueError(f"Invalid queue name. Must be one of: {valid_queues}")
            validated_queues.append(queue_name)
        
        return validated_queues


class SearchRequest(BaseValidationModel):
    """Request model for searching posts"""
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query"
    )
    subreddits: Optional[List[str]] = Field(
        default=None,
        max_items=10,
        description="Limit search to specific subreddits"
    )
    date_from: Optional[datetime] = Field(
        default=None,
        description="Search from this date"
    )
    date_to: Optional[datetime] = Field(
        default=None,
        description="Search until this date"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of results"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset for pagination"
    )
    
    @field_validator('query')
    @classmethod
    def validate_search_query(cls, v):
        """Validate and sanitize search query"""
        # Remove potentially dangerous SQL characters
        dangerous_chars = [';', '--', '/*', '*/', 'xp_', 'sp_']
        for char in dangerous_chars:
            if char in v.lower():
                raise ValueError("Search query contains invalid characters")
        
        # Basic XSS prevention
        if re.search(r'<script|javascript:|data:|vbscript:', v.lower()):
            raise ValueError("Search query contains invalid content")
        
        return v
    
    @model_validator(mode='after')
    def validate_date_range(self):
        """Validate date range"""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        
        return self


class ConfigUpdateRequest(BaseValidationModel):
    """Request model for configuration updates"""
    reddit_rate_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Reddit API rate limit per minute"
    )
    openai_max_tokens: Optional[int] = Field(
        default=None,
        ge=1000,
        le=10000000,
        description="OpenAI daily token limit"
    )
    content_min_score: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum score for content collection"
    )
    content_min_comments: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum comments for content collection"
    )
    worker_concurrency: Optional[Dict[str, int]] = Field(
        default=None,
        description="Worker concurrency settings"
    )
    
    @field_validator('worker_concurrency')
    @classmethod
    def validate_worker_concurrency(cls, v):
        """Validate worker concurrency settings"""
        if not v:
            return v
        
        valid_workers = ['collector', 'nlp', 'publisher']
        for worker, concurrency in v.items():
            if worker not in valid_workers:
                raise ValueError(f"Invalid worker type: {worker}")
            if not isinstance(concurrency, int) or concurrency < 1 or concurrency > 10:
                raise ValueError(f"Invalid concurrency for {worker}: must be 1-10")
        
        return v


# Response models
class ValidationErrorResponse(BaseModel):
    """Response model for validation errors"""
    error: str = "Validation failed"
    details: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Security validation functions
def validate_sql_injection(value: str) -> str:
    """Check for SQL injection patterns"""
    if not isinstance(value, str):
        return value
    
    # Common SQL injection patterns
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
        r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
        r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
        r"(--|#|/\*|\*/)",
        r"(\bxp_|\bsp_)",
        r"(\bCAST\s*\(|\bCONVERT\s*\()",
    ]
    
    for pattern in sql_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning("Potential SQL injection detected", value=value[:100])
            raise ValueError("Input contains potentially dangerous content")
    
    return value


def validate_xss_injection(value: str) -> str:
    """Check for XSS injection patterns"""
    if not isinstance(value, str):
        return value
    
    # Common XSS patterns
    xss_patterns = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"data:text/html",
        r"vbscript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"onclick\s*=",
        r"onmouseover\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
    ]
    
    for pattern in xss_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning("Potential XSS injection detected", value=value[:100])
            raise ValueError("Input contains potentially dangerous content")
    
    return value


def sanitize_html_input(value: str) -> str:
    """Sanitize HTML input by removing dangerous tags and attributes"""
    if not isinstance(value, str):
        return value
    
    # Remove script tags and their content
    value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove dangerous attributes
    dangerous_attrs = ['onload', 'onerror', 'onclick', 'onmouseover', 'onfocus', 'onblur']
    for attr in dangerous_attrs:
        value = re.sub(f'{attr}\\s*=\\s*["\'][^"\']*["\']', '', value, flags=re.IGNORECASE)
    
    # Remove dangerous protocols
    value = re.sub(r'(javascript|data|vbscript):', '', value, flags=re.IGNORECASE)
    
    return value


def validate_file_path(path: str) -> str:
    """Validate file path to prevent directory traversal"""
    if not isinstance(path, str):
        return path
    
    # Check for directory traversal patterns
    if '..' in path or path.startswith('/') or '\\' in path:
        logger.warning("Potential directory traversal detected", path=path)
        raise ValueError("Invalid file path")
    
    # Only allow alphanumeric, dots, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9._-]+$', path):
        raise ValueError("File path contains invalid characters")
    
    return path


class TakedownRequest(BaseValidationModel):
    """Request model for takedown requests"""
    reddit_post_id: str = Field(
        ...,
        min_length=6,
        max_length=7,
        description="Reddit post ID to takedown"
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Reason for takedown request"
    )
    contact_email: Optional[str] = Field(
        default=None,
        description="Contact email for follow-up"
    )
    
    @field_validator('reddit_post_id')
    @classmethod
    def validate_reddit_post_id(cls, v):
        """Validate Reddit post ID format"""
        if not re.match(r'^[a-z0-9]{6,7}$', v):
            raise ValueError("Invalid Reddit post ID format")
        return v
    
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        """Validate and sanitize takedown reason"""
        # Apply security validations
        v = validate_sql_injection(v)
        v = validate_xss_injection(v)
        v = sanitize_html_input(v)
        
        # Check for minimum meaningful content
        if len(v.strip()) < 10:
            raise ValueError("Reason must be at least 10 characters")
        
        return v.strip()
    
    @field_validator('contact_email')
    @classmethod
    def validate_contact_email(cls, v):
        """Validate contact email format"""
        if v is None:
            return v
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        
        return v.lower().strip()


class BudgetStatusRequest(BaseValidationModel):
    """Request model for budget status"""
    services: Optional[List[str]] = Field(
        default=None,
        description="Specific services to check (reddit, openai)"
    )
    include_history: bool = Field(
        default=False,
        description="Include usage history"
    )
    
    @field_validator('services')
    @classmethod
    def validate_services(cls, v):
        """Validate service names"""
        if v is None:
            return v
        
        valid_services = ['reddit', 'openai']
        for service in v:
            if service not in valid_services:
                raise ValueError(f"Invalid service: {service}. Must be one of: {valid_services}")
        
        return v


class HealthCheckRequest(BaseValidationModel):
    """Request model for health check"""
    include_external: bool = Field(
        default=True,
        description="Include external service checks"
    )
    timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Timeout for external service checks"
    )


class LogSearchRequest(BaseValidationModel):
    """Request model for log searching"""
    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Log search query"
    )
    level: Optional[str] = Field(
        default=None,
        description="Log level filter"
    )
    service: Optional[str] = Field(
        default=None,
        description="Service name filter"
    )
    start_time: Optional[datetime] = Field(
        default=None,
        description="Start time for log search"
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="End time for log search"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of log entries"
    )
    
    @field_validator('query')
    @classmethod
    def validate_log_query(cls, v):
        """Validate log search query"""
        # Apply security validations
        v = validate_sql_injection(v)
        v = validate_xss_injection(v)
        
        # Remove potentially dangerous regex patterns
        dangerous_patterns = ['.*', '.+', '\\', '(?', '(?=', '(?!']
        for pattern in dangerous_patterns:
            if pattern in v:
                raise ValueError("Log query contains potentially dangerous patterns")
        
        return v
    
    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level"""
        if v is None:
            return v
        
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        
        return v.upper()
    
    @field_validator('service')
    @classmethod
    def validate_service_name(cls, v):
        """Validate service name"""
        if v is None:
            return v
        
        valid_services = ['collector', 'nlp_pipeline', 'publisher', 'api', 'scheduler']
        if v not in valid_services:
            raise ValueError(f"Invalid service name. Must be one of: {valid_services}")
        
        return v


# Enhanced security validation functions
def validate_reddit_compliance(url: str) -> str:
    """Validate URL for Reddit API compliance"""
    from app.security import validate_reddit_url
    
    if not validate_reddit_url(url):
        logger.warning("Non-compliant Reddit URL detected", url=url)
        raise ValueError("URL does not comply with Reddit API policy")
    
    return url


def validate_content_safety(content: str) -> str:
    """Validate content for safety and compliance"""
    if not isinstance(content, str):
        return content
    
    # Check for NSFW indicators
    nsfw_patterns = [
        r'\b(nsfw|not safe for work)\b',
        r'\b(adult|explicit|mature)\b',
        r'\b(porn|sex|nude)\b'
    ]
    
    for pattern in nsfw_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            logger.info("NSFW content detected", content_preview=content[:50])
            raise ValueError("Content may contain NSFW material")
    
    return content


def validate_rate_limit_compliance(requests_per_minute: int, service: str) -> bool:
    """Validate rate limit compliance for external services"""
    limits = {
        'reddit': 60,  # Reddit API limit
        'openai': 3500,  # OpenAI API limit (approximate)
        'ghost': 100   # Conservative Ghost API limit
    }
    
    service_limit = limits.get(service, 60)
    
    if requests_per_minute > service_limit:
        logger.warning(
            "Rate limit exceeded",
            service=service,
            requested=requests_per_minute,
            limit=service_limit
        )
        return False
    
    return True


def mask_sensitive_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in data for logging"""
    from app.security import PIIMasker
    
    masker = PIIMasker()
    return masker.mask_dict(data)


def validate_json_schema(data: dict, schema_type: str) -> dict:
    """Validate JSON data against predefined schemas"""
    schemas = {
        'pain_points': {
            'type': 'object',
            'required': ['points', 'meta'],
            'properties': {
                'points': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'required': ['description', 'severity'],
                        'properties': {
                            'description': {'type': 'string', 'maxLength': 500},
                            'severity': {'type': 'string', 'enum': ['low', 'medium', 'high']},
                            'category': {'type': 'string', 'maxLength': 100}
                        }
                    }
                },
                'meta': {
                    'type': 'object',
                    'required': ['version'],
                    'properties': {
                        'version': {'type': 'string'},
                        'generated_at': {'type': 'string'}
                    }
                }
            }
        },
        'product_ideas': {
            'type': 'object',
            'required': ['ideas', 'meta'],
            'properties': {
                'ideas': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'required': ['title', 'description'],
                        'properties': {
                            'title': {'type': 'string', 'maxLength': 200},
                            'description': {'type': 'string', 'maxLength': 1000},
                            'feasibility': {'type': 'string', 'enum': ['low', 'medium', 'high']},
                            'market_size': {'type': 'string', 'enum': ['small', 'medium', 'large']}
                        }
                    }
                },
                'meta': {
                    'type': 'object',
                    'required': ['version'],
                    'properties': {
                        'version': {'type': 'string'},
                        'generated_at': {'type': 'string'}
                    }
                }
            }
        }
    }
    
    schema = schemas.get(schema_type)
    if not schema:
        raise ValueError(f"Unknown schema type: {schema_type}")
    
    # Basic schema validation (simplified for MVP)
    def validate_object(obj, schema_def):
        if schema_def['type'] == 'object':
            if not isinstance(obj, dict):
                raise ValueError("Expected object")
            
            # Check required fields
            for field in schema_def.get('required', []):
                if field not in obj:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate properties
            for field, value in obj.items():
                if field in schema_def.get('properties', {}):
                    prop_schema = schema_def['properties'][field]
                    validate_object(value, prop_schema)
        
        elif schema_def['type'] == 'array':
            if not isinstance(obj, list):
                raise ValueError("Expected array")
            
            if 'items' in schema_def:
                for item in obj:
                    validate_object(item, schema_def['items'])
        
        elif schema_def['type'] == 'string':
            if not isinstance(obj, str):
                raise ValueError("Expected string")
            
            if 'maxLength' in schema_def and len(obj) > schema_def['maxLength']:
                raise ValueError(f"String too long (max {schema_def['maxLength']})")
            
            if 'enum' in schema_def and obj not in schema_def['enum']:
                raise ValueError(f"Invalid enum value: {obj}")
    
    validate_object(data, schema)
    return data
    
    return path


def validate_json_input(data: Union[str, dict]) -> dict:
    """Validate and sanitize JSON input"""
    import json
    
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format")
    
    if not isinstance(data, dict):
        raise ValueError("JSON input must be an object")
    
    # Recursively sanitize string values
    def sanitize_dict(obj):
        if isinstance(obj, dict):
            return {k: sanitize_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_dict(item) for item in obj]
        elif isinstance(obj, str):
            return sanitize_html_input(validate_xss_injection(validate_sql_injection(obj)))
        else:
            return obj
    
    return sanitize_dict(data)