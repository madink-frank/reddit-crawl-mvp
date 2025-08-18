"""
Unit tests for configuration management
"""
import pytest
import os
from unittest.mock import patch, Mock
from pydantic import ValidationError

from app.config import Settings, get_settings, get_database_url, get_redis_url, is_production, is_development


class TestSettings:
    """Test Settings configuration class"""
    
    def test_settings_default_values(self):
        """Test default configuration values"""
        # Test with minimal required environment variables
        env_vars = {
            "DATABASE_URL": "sqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "GHOST_API_URL": "https://test.ghost.io",
            "JWT_SECRET_KEY": "test_secret_key_123456789"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.app_name == "Reddit Ghost Publisher"
            assert settings.debug is False
            assert settings.environment == "development"
    
    def test_settings_from_environment(self):
        """Test loading settings from environment variables"""
        env_vars = {
            "DEBUG": "true",
            "ENVIRONMENT": "testing",
            "JWT_SECRET_KEY": "test_secret_key_123456789",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
            "REDIS_URL": "redis://localhost:6379/1",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "CELERY_BROKER_URL": "redis://localhost:6379/1",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/1",
            "GHOST_API_URL": "https://test.ghost.io"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.debug is True
            assert settings.environment == "testing"
            assert settings.jwt_secret_key == "test_secret_key_123456789"
            assert settings.database_url == "postgresql://test:test@localhost/test"
            assert settings.redis_url == "redis://localhost:6379/1"
            assert settings.vault_url == "http://localhost:8200"
            assert settings.vault_token == "test_token"
    
    def test_database_settings(self):
        """Test database-specific settings"""
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/dbname",
            "DATABASE_POOL_SIZE": "20",
            "DATABASE_MAX_OVERFLOW": "30",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "GHOST_API_URL": "https://test.ghost.io",
            "JWT_SECRET_KEY": "test_secret_key_123456789"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.database_url == "postgresql://user:pass@localhost:5432/dbname"
            assert settings.database_pool_size == 20
            assert settings.database_max_overflow == 30
    
    def test_redis_settings(self):
        """Test Redis-specific settings"""
        env_vars = {
            "REDIS_URL": "redis://localhost:6379/2",
            "REDIS_MAX_CONNECTIONS": "50",
            "DATABASE_URL": "sqlite:///test.db",
            "CELERY_BROKER_URL": "redis://localhost:6379/2",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "GHOST_API_URL": "https://test.ghost.io",
            "JWT_SECRET_KEY": "test_secret_key_123456789"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.redis_url == "redis://localhost:6379/2"
            assert settings.redis_max_connections == 50
    
    def test_vault_settings(self):
        """Test Vault-specific settings"""
        env_vars = {
            "VAULT_URL": "https://vault.example.com",
            "VAULT_TOKEN": "hvs.test_token",
            "VAULT_MOUNT_POINT": "secret",
            "DATABASE_URL": "sqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
            "GHOST_API_URL": "https://test.ghost.io",
            "JWT_SECRET_KEY": "test_secret_key_123456789"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.vault_url == "https://vault.example.com"
            assert settings.vault_token == "hvs.test_token"
            assert settings.vault_mount_point == "secret"
    
    def test_api_rate_limits(self):
        """Test API rate limit settings"""
        env_vars = {
            "REDDIT_RATE_LIMIT": "120",
            "DATABASE_URL": "sqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "GHOST_API_URL": "https://test.ghost.io",
            "JWT_SECRET_KEY": "test_secret_key_123456789"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.reddit_rate_limit == 120
    
    def test_celery_settings(self):
        """Test Celery-specific settings"""
        env_vars = {
            "CELERY_BROKER_URL": "redis://localhost:6379/3",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/4",
            "CELERY_TASK_SERIALIZER": "pickle",
            "CELERY_RESULT_SERIALIZER": "pickle",
            "DATABASE_URL": "sqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/0",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "GHOST_API_URL": "https://test.ghost.io",
            "JWT_SECRET_KEY": "test_secret_key_123456789"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.celery_broker_url == "redis://localhost:6379/3"
            assert settings.celery_result_backend == "redis://localhost:6379/4"
            assert settings.celery_task_serializer == "pickle"
            assert settings.celery_result_serializer == "pickle"
    
    def test_monitoring_settings(self):
        """Test monitoring-specific settings"""
        env_vars = {
            "PROMETHEUS_PORT": "9090",
            "LOG_LEVEL": "DEBUG",
            "DATABASE_URL": "sqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "GHOST_API_URL": "https://test.ghost.io",
            "JWT_SECRET_KEY": "test_secret_key_123456789"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.prometheus_port == 9090
            assert settings.log_level == "DEBUG"
    
    def test_security_settings(self):
        """Test security-specific settings"""
        env_vars = {
            "JWT_SECRET_KEY": "very_long_secret_key_for_testing_purposes_123456789",
            "JWT_ALGORITHM": "HS512",
            "JWT_EXPIRY_HOURS": "48",
            "DATABASE_URL": "sqlite:///test.db",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/0",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/0",
            "VAULT_URL": "http://localhost:8200",
            "VAULT_TOKEN": "test_token",
            "GHOST_API_URL": "https://test.ghost.io"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.jwt_secret_key == "very_long_secret_key_for_testing_purposes_123456789"
            assert settings.jwt_algorithm == "HS512"
            assert settings.jwt_expiry_hours == 48


class TestUtilityFunctions:
    """Test configuration utility functions"""
    
    def test_get_database_url_with_env(self):
        """Test get_database_url with environment variable"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.environment = "production"
            mock_settings.database_url = "postgresql://user:pass@localhost/db"
            
            url = get_database_url()
            
            assert url == "postgresql://user:pass@localhost/db"
    
    def test_get_database_url_development_fallback(self):
        """Test get_database_url fallback in development"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.environment = "development"
            mock_settings.database_url = None
            
            url = get_database_url()
            
            assert url == "sqlite:///./reddit_publisher.db"
    
    def test_get_redis_url_with_env(self):
        """Test get_redis_url with environment variable"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.environment = "production"
            mock_settings.redis_url = "redis://localhost:6379/1"
            
            url = get_redis_url()
            
            assert url == "redis://localhost:6379/1"
    
    def test_get_redis_url_development_fallback(self):
        """Test get_redis_url fallback in development"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.environment = "development"
            mock_settings.redis_url = None
            
            url = get_redis_url()
            
            assert url == "redis://localhost:6379/0"
    
    def test_is_production(self):
        """Test is_production function"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.environment = "production"
            
            assert is_production() is True
    
    def test_is_development(self):
        """Test is_development function"""
        with patch('app.config.settings') as mock_settings:
            mock_settings.environment = "development"
            
            assert is_development() is True


class TestGetSettings:
    """Test get_settings function"""
    
    def test_get_settings_returns_settings(self):
        """Test that get_settings returns settings instance"""
        settings = get_settings()
        
        assert isinstance(settings, Settings)
        assert settings.app_name == "Reddit Ghost Publisher"


if __name__ == "__main__":
    pytest.main([__file__])