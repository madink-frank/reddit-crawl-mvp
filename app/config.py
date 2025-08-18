"""
Configuration management for Reddit Ghost Publisher MVP
"""
import os
from typing import Optional, Dict
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support for MVP"""
    
    # Application
    app_name: str = "Reddit Ghost Publisher MVP"
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    timezone: str = Field(default="UTC", env="TZ")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_workers: int = Field(default=1, env="API_WORKERS")
    
    # Database (PostgreSQL only for MVP)
    database_url: str = Field(env="DATABASE_URL")
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis
    redis_url: str = Field(env="REDIS_URL")
    redis_max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    
    # Celery Configuration (Simplified)
    celery_broker_url: str = Field(env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(env="CELERY_RESULT_BACKEND")
    celery_task_serializer: str = Field(default="json", env="CELERY_TASK_SERIALIZER")
    celery_result_serializer: str = Field(default="json", env="CELERY_RESULT_SERIALIZER")
    celery_accept_content: list = Field(default=["json"], env="CELERY_ACCEPT_CONTENT")
    celery_timezone: str = Field(default="UTC", env="CELERY_TIMEZONE")
    
    # Reddit API with Budget Limits
    reddit_client_id: Optional[str] = Field(default=None, env="REDDIT_CLIENT_ID")
    reddit_client_secret: Optional[str] = Field(default=None, env="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="RedditGhostPublisher/1.0", env="REDDIT_USER_AGENT")
    reddit_rate_limit_rpm: int = Field(default=60, env="REDDIT_RATE_LIMIT_RPM")  # requests per minute
    reddit_daily_calls_limit: int = Field(default=5000, env="REDDIT_DAILY_CALLS_LIMIT")  # daily API call budget
    
    # OpenAI with Budget Limits and Cost Map
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_primary_model: str = Field(default="gpt-4o-mini", env="OPENAI_PRIMARY_MODEL")
    openai_fallback_model: str = Field(default="gpt-4o", env="OPENAI_FALLBACK_MODEL")
    openai_daily_tokens_limit: int = Field(default=100000, env="OPENAI_DAILY_TOKENS_LIMIT")  # daily token budget
    
    # Cost per 1K tokens (fixed internal cost map)
    cost_per_1k_tokens: Dict[str, float] = Field(default={
        "gpt-4o-mini": 0.00015,  # $0.15 per 1M input tokens
        "gpt-4o": 0.005          # $5.00 per 1M input tokens
    })
    
    # Individual cost settings for environment override
    cost_gpt4o_mini_per_1k: float = Field(default=0.00015, env="COST_GPT4O_MINI_PER_1K")
    cost_gpt4o_per_1k: float = Field(default=0.005, env="COST_GPT4O_PER_1K")
    
    # Ghost CMS
    ghost_admin_key: Optional[str] = Field(default=None, env="GHOST_ADMIN_KEY")
    ghost_api_url: str = Field(env="GHOST_API_URL")
    ghost_jwt_expiry: int = Field(default=300, env="GHOST_JWT_EXPIRY")  # 5 minutes
    default_og_image_url: str = Field(default="", env="DEFAULT_OG_IMAGE_URL")  # fallback OG image
    
    # Scheduling (Cron expressions)
    collect_cron: str = Field(default="0 * * * *", env="COLLECT_CRON")  # hourly collection
    backup_cron: str = Field(default="0 4 * * *", env="BACKUP_CRON")    # daily backup at 4 AM
    
    # Monitoring and Alerting
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    structured_logging: bool = Field(default=True, env="STRUCTURED_LOGGING")
    
    # Slack Notifications
    slack_webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    
    # API Security
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    
    # Alert Thresholds
    queue_alert_threshold: int = Field(default=500, env="QUEUE_ALERT_THRESHOLD")
    failure_rate_threshold: float = Field(default=0.05, env="FAILURE_RATE_THRESHOLD")  # 5%
    
    # Queue Configuration (Simplified)
    queue_collect_name: str = Field(default="collect", env="QUEUE_COLLECT_NAME")
    queue_process_name: str = Field(default="process", env="QUEUE_PROCESS_NAME")
    queue_publish_name: str = Field(default="publish", env="QUEUE_PUBLISH_NAME")
    
    # Worker Configuration (Single node)
    worker_collector_concurrency: int = Field(default=1, env="WORKER_COLLECTOR_CONCURRENCY")
    worker_nlp_concurrency: int = Field(default=1, env="WORKER_NLP_CONCURRENCY")
    worker_publisher_concurrency: int = Field(default=1, env="WORKER_PUBLISHER_CONCURRENCY")
    
    # Retry Configuration (Constants)
    retry_max: int = Field(default=3, env="RETRY_MAX")
    backoff_base: int = Field(default=2, env="BACKOFF_BASE")
    backoff_min: int = Field(default=2, env="BACKOFF_MIN")  # seconds
    backoff_max: int = Field(default=8, env="BACKOFF_MAX")  # seconds
    
    # Content Processing
    subreddits: str = Field(default="programming,technology", env="SUBREDDITS")  # comma-separated
    batch_size: int = Field(default=20, env="BATCH_SIZE")  # N posts to collect
    content_min_score: int = Field(default=10, env="CONTENT_MIN_SCORE")
    content_min_comments: int = Field(default=5, env="CONTENT_MIN_COMMENTS")
    
    # Template Configuration (Article only for MVP)
    template_article_path: str = Field(default="templates/article.hbs", env="TEMPLATE_ARTICLE_PATH")
    
    # Security (Environment variables only, no Vault)
    jwt_secret_key: str = Field(default="dev-secret-key", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields for MVP


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings


def get_database_url() -> str:
    """Get PostgreSQL database URL (no SQLite fallback for MVP)"""
    return settings.database_url


def get_redis_url() -> str:
    """Get Redis URL with fallback for development"""
    if settings.environment == "development" and not settings.redis_url:
        return "redis://localhost:6379/0"
    return settings.redis_url


def get_subreddits_list() -> list:
    """Get list of subreddits from comma-separated string"""
    return [s.strip() for s in settings.subreddits.split(",") if s.strip()]


def get_cost_per_token(model: str) -> float:
    """Get cost per token for a specific model"""
    return settings.cost_per_1k_tokens.get(model, 0.0) / 1000  # convert to per-token cost


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return settings.environment.lower() == "development"