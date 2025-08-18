"""
Security utilities for Reddit Ghost Publisher MVP
Environment variable-based secret management and PII masking
"""
import os
import re
import logging
from typing import Any, Dict, Optional, Union
from functools import lru_cache
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SecretManager:
    """Environment variable-based secret management with caching"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._loaded = False
    
    @lru_cache(maxsize=128)
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from environment variables with caching"""
        try:
            value = os.getenv(key, default)
            if value:
                # Cache non-sensitive metadata only
                self._cache[f"{key}_loaded"] = True
                return value
            return default
        except Exception as e:
            logger.error(f"Failed to load secret {key}: {e}")
            return default
    
    def load_all_secrets(self) -> Dict[str, bool]:
        """Load and validate all required secrets"""
        required_secrets = [
            "REDDIT_CLIENT_ID",
            "REDDIT_CLIENT_SECRET", 
            "OPENAI_API_KEY",
            "GHOST_ADMIN_KEY",
            "DATABASE_URL",
            "REDIS_URL"
        ]
        
        optional_secrets = [
            "SLACK_WEBHOOK_URL",
            "JWT_SECRET_KEY"
        ]
        
        status = {}
        
        # Check required secrets
        for secret in required_secrets:
            value = self.get_secret(secret)
            status[secret] = bool(value and len(value.strip()) > 0)
            if not status[secret]:
                logger.warning(f"Required secret {secret} is missing or empty")
        
        # Check optional secrets
        for secret in optional_secrets:
            value = self.get_secret(secret)
            status[secret] = bool(value and len(value.strip()) > 0)
            if not status[secret]:
                logger.info(f"Optional secret {secret} is not configured")
        
        self._loaded = True
        return status
    
    def is_loaded(self) -> bool:
        """Check if secrets have been loaded"""
        return self._loaded
    
    def clear_cache(self) -> None:
        """Clear secret cache (for testing)"""
        self._cache.clear()
        self._loaded = False


class PIIMasker:
    """PII masking utility for logs and responses with enhanced patterns"""
    
    # Regex patterns for sensitive data (enhanced for MVP requirements)
    PATTERNS = {
        'api_key': re.compile(r'(api[_-]?key["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{6,})', re.IGNORECASE),
        'token': re.compile(r'(token["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{6,})', re.IGNORECASE),
        'secret': re.compile(r'(secret["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{6,})', re.IGNORECASE),
        'password': re.compile(r'(password["\s]*[:=]["\s]*)([^\s"\']{6,})', re.IGNORECASE),
        'email': re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'),
        'reddit_id': re.compile(r'(reddit[_-]?(?:client[_-]?)?id["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{6,})', re.IGNORECASE),
        'reddit_secret': re.compile(r'(reddit[_-]?(?:client[_-]?)?secret["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{6,})', re.IGNORECASE),
        'ghost_key': re.compile(r'(ghost[_-]?(?:admin[_-]?)?key["\s]*[:=]["\s]*)([a-zA-Z0-9\-_:]{10,})', re.IGNORECASE),
        'openai_key': re.compile(r'(openai[_-]?(?:api[_-]?)?key["\s]*[:=]["\s]*)([a-zA-Z0-9\-_]{20,})', re.IGNORECASE),
        'jwt': re.compile(r'(bearer\s+|authorization["\s]*[:=]["\s]*(?:bearer\s+)?)(eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+)', re.IGNORECASE),
        'url_credentials': re.compile(r'(://[^:]+:)([^@]+)(@)'),  # URLs with credentials
        'slack_webhook': re.compile(r'(hooks\.slack\.com/services/)([A-Z0-9/]+)', re.IGNORECASE),
        'database_url': re.compile(r'(://[^:]+:)([^@]+)(@[^/]+/)', re.IGNORECASE),  # Database URLs with credentials
        'reddit_username': re.compile(r'(/u/|u/)([a-zA-Z0-9_-]+)', re.IGNORECASE),  # Reddit usernames
        'reddit_post_id': re.compile(r'(reddit\.com/r/[^/]+/comments/)([a-zA-Z0-9]+)', re.IGNORECASE),  # Reddit post IDs in URLs
    }
    
    @classmethod
    def mask_sensitive_data(cls, text: str) -> str:
        """Mask sensitive information in text with enhanced patterns"""
        if not isinstance(text, str):
            text = str(text)
        
        masked_text = text
        
        # Apply all masking patterns
        for pattern_name, pattern in cls.PATTERNS.items():
            if pattern_name == 'email':
                # Special handling for email - mask username part
                masked_text = pattern.sub(r'****@\2', masked_text)
            elif pattern_name == 'url_credentials':
                # Special handling for URL credentials
                masked_text = pattern.sub(r'\1****\3', masked_text)
            elif pattern_name == 'database_url':
                # Special handling for database URLs
                masked_text = pattern.sub(r'\1****\3', masked_text)
            elif pattern_name == 'jwt':
                # Special handling for JWT tokens
                masked_text = pattern.sub(r'\1****', masked_text)
            elif pattern_name == 'slack_webhook':
                # Special handling for Slack webhooks
                masked_text = pattern.sub(r'\1****', masked_text)
            elif pattern_name == 'reddit_username':
                # Special handling for Reddit usernames (partial masking for privacy)
                def mask_username(match):
                    prefix = match.group(1)
                    username = match.group(2)
                    if len(username) <= 4:
                        return f"{prefix}****"
                    else:
                        return f"{prefix}{username[:2]}****{username[-2:]}"
                masked_text = pattern.sub(mask_username, masked_text)
            elif pattern_name == 'reddit_post_id':
                # Special handling for Reddit post IDs (partial masking)
                def mask_post_id(match):
                    prefix = match.group(1)
                    post_id = match.group(2)
                    if len(post_id) <= 6:
                        return f"{prefix}****"
                    else:
                        return f"{prefix}{post_id[:3]}****{post_id[-3:]}"
                masked_text = pattern.sub(mask_post_id, masked_text)
            else:
                # Standard masking for keys, tokens, secrets
                masked_text = pattern.sub(r'\1****', masked_text)
        
        return masked_text
    
    @classmethod
    def mask_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively mask sensitive data in dictionary"""
        if not isinstance(data, dict):
            return data
        
        masked_data = {}
        for key, value in data.items():
            # Check if key name suggests sensitive data
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in ['key', 'secret', 'token', 'password']):
                masked_data[key] = '****'
            elif isinstance(value, dict):
                masked_data[key] = cls.mask_dict(value)
            elif isinstance(value, list):
                masked_data[key] = [cls.mask_dict(item) if isinstance(item, dict) else cls.mask_sensitive_data(str(item)) for item in value]
            elif isinstance(value, str):
                masked_data[key] = cls.mask_sensitive_data(value)
            else:
                masked_data[key] = value
        
        return masked_data
    
    @classmethod
    def safe_log(cls, message: str, **kwargs) -> None:
        """Log message with PII masking"""
        masked_message = cls.mask_sensitive_data(message)
        masked_kwargs = cls.mask_dict(kwargs)
        logger.info(masked_message, extra=masked_kwargs)


class BudgetManager:
    """Budget management for API calls and token usage"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        
        # Budget limits from environment
        self.reddit_daily_limit = int(os.getenv('REDDIT_DAILY_CALLS_LIMIT', '5000'))
        self.openai_daily_limit = int(os.getenv('OPENAI_DAILY_TOKENS_LIMIT', '100000'))
        
        # Cost per 1K tokens (fixed internal cost map)
        self.cost_per_1k_tokens = {
            'gpt-4o-mini': float(os.getenv('COST_GPT4O_MINI_PER_1K', '0.00015')),  # $0.15 per 1M input tokens
            'gpt-4o': float(os.getenv('COST_GPT4O_PER_1K', '0.005'))  # $5.00 per 1M input tokens
        }
    
    def get_daily_key(self, service: str) -> str:
        """Get Redis key for daily usage tracking (UTC date)"""
        utc_date = datetime.now(timezone.utc).strftime('%Y%m%d')
        return f"usage:{service}:{utc_date}"
    
    async def get_daily_usage(self, service: str) -> int:
        """Get current daily usage for a service"""
        if not self.redis_client:
            return 0
        
        key = self.get_daily_key(service)
        usage = await self.redis_client.get(key)
        return int(usage) if usage else 0
    
    async def increment_usage(self, service: str, amount: int = 1) -> int:
        """Increment daily usage counter"""
        if not self.redis_client:
            return amount
        
        key = self.get_daily_key(service)
        
        # Increment counter
        new_usage = await self.redis_client.incr(key, amount)
        
        # Set expiration to end of day (UTC)
        now_utc = datetime.now(timezone.utc)
        end_of_day = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        seconds_until_reset = int((end_of_day - now_utc).total_seconds()) + 1
        
        await self.redis_client.expire(key, seconds_until_reset)
        
        return new_usage
    
    async def check_reddit_budget(self) -> Dict[str, Any]:
        """Check Reddit API call budget"""
        current_usage = await self.get_daily_usage('reddit')
        limit = self.reddit_daily_limit
        
        usage_percent = (current_usage / limit) * 100 if limit > 0 else 0
        
        return {
            'service': 'reddit',
            'current_usage': current_usage,
            'daily_limit': limit,
            'usage_percent': usage_percent,
            'remaining': max(0, limit - current_usage),
            'budget_exceeded': current_usage >= limit,
            'warning_threshold_80': usage_percent >= 80.0,
            'warning_threshold_100': usage_percent >= 100.0
        }
    
    async def check_openai_budget(self) -> Dict[str, Any]:
        """Check OpenAI token budget"""
        current_usage = await self.get_daily_usage('openai')
        limit = self.openai_daily_limit
        
        usage_percent = (current_usage / limit) * 100 if limit > 0 else 0
        
        return {
            'service': 'openai',
            'current_usage': current_usage,
            'daily_limit': limit,
            'usage_percent': usage_percent,
            'remaining': max(0, limit - current_usage),
            'budget_exceeded': current_usage >= limit,
            'warning_threshold_80': usage_percent >= 80.0,
            'warning_threshold_100': usage_percent >= 100.0
        }
    
    def calculate_token_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage"""
        cost_per_1k = self.cost_per_1k_tokens.get(model, 0.0)
        total_tokens = input_tokens + output_tokens
        return (total_tokens / 1000.0) * cost_per_1k
    
    async def track_token_usage(self, model: str, input_tokens: int, output_tokens: int) -> Dict[str, Any]:
        """Track token usage and calculate cost"""
        total_tokens = input_tokens + output_tokens
        cost = self.calculate_token_cost(model, input_tokens, output_tokens)
        
        # Increment usage counter
        new_usage = await self.increment_usage('openai', total_tokens)
        
        # Log usage (with PII masking)
        PIIMasker.safe_log(
            f"Token usage tracked for model {model}",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            daily_usage=new_usage
        )
        
        return {
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens,
            'cost_usd': cost,
            'daily_usage': new_usage
        }
    
    async def should_block_request(self, service: str) -> bool:
        """Check if request should be blocked due to budget limits"""
        if service == 'reddit':
            budget = await self.check_reddit_budget()
            return budget['budget_exceeded']
        elif service == 'openai':
            budget = await self.check_openai_budget()
            return budget['budget_exceeded']
        return False
    
    async def get_budget_status(self) -> Dict[str, Any]:
        """Get comprehensive budget status"""
        reddit_budget = await self.check_reddit_budget()
        openai_budget = await self.check_openai_budget()
        
        return {
            'reddit': reddit_budget,
            'openai': openai_budget,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'timezone': 'UTC'
        }


# Global instances
secret_manager = SecretManager()
pii_masker = PIIMasker()


def get_secret_manager() -> SecretManager:
    """Get global secret manager instance"""
    return secret_manager


def get_pii_masker() -> PIIMasker:
    """Get global PII masker instance"""
    return pii_masker


def create_budget_manager(redis_client=None) -> BudgetManager:
    """Create budget manager with Redis client"""
    return BudgetManager(redis_client)


def mask_sensitive_data(text: str) -> str:
    """Convenience function for PII masking"""
    return pii_masker.mask_sensitive_data(text)


def safe_log(message: str, **kwargs) -> None:
    """Convenience function for safe logging"""
    pii_masker.safe_log(message, **kwargs)


class RedditAPIComplianceChecker:
    """Reddit API policy compliance checker"""
    
    # Prohibited patterns that indicate non-API access
    PROHIBITED_PATTERNS = [
        # Direct web scraping patterns
        re.compile(r'requests\.get\(["\']https?://(?:www\.)?reddit\.com/r/', re.IGNORECASE),
        re.compile(r'urllib\.request\.urlopen\(["\']https?://(?:www\.)?reddit\.com/r/', re.IGNORECASE),
        re.compile(r'selenium.*reddit\.com', re.IGNORECASE),
        re.compile(r'beautifulsoup.*reddit\.com', re.IGNORECASE),
        re.compile(r'scrapy.*reddit\.com', re.IGNORECASE),
        
        # Direct HTML parsing
        re.compile(r'html\.parser.*reddit', re.IGNORECASE),
        re.compile(r'lxml.*reddit', re.IGNORECASE),
        
        # Non-API endpoints
        re.compile(r'reddit\.com/r/[^/]+/(?!api/)', re.IGNORECASE),
        re.compile(r'old\.reddit\.com', re.IGNORECASE),
        re.compile(r'www\.reddit\.com/(?!api/)', re.IGNORECASE),
    ]
    
    # Allowed patterns (official API usage)
    ALLOWED_PATTERNS = [
        re.compile(r'praw\.Reddit', re.IGNORECASE),
        re.compile(r'reddit\.com/api/', re.IGNORECASE),
        re.compile(r'oauth\.reddit\.com', re.IGNORECASE),
        re.compile(r'reddit\.com/dev/api', re.IGNORECASE),
    ]
    
    @classmethod
    def check_code_compliance(cls, code: str) -> Dict[str, Any]:
        """Check code for Reddit API policy compliance
        
        Args:
            code: Code string to check
            
        Returns:
            Dictionary with compliance status and violations
        """
        violations = []
        allowed_usage = []
        
        # Check for prohibited patterns
        for pattern in cls.PROHIBITED_PATTERNS:
            matches = pattern.findall(code)
            if matches:
                violations.extend([
                    {
                        'type': 'prohibited_pattern',
                        'pattern': pattern.pattern,
                        'matches': matches,
                        'severity': 'high'
                    }
                ])
        
        # Check for allowed patterns
        for pattern in cls.ALLOWED_PATTERNS:
            matches = pattern.findall(code)
            if matches:
                allowed_usage.extend([
                    {
                        'type': 'allowed_pattern',
                        'pattern': pattern.pattern,
                        'matches': matches
                    }
                ])
        
        is_compliant = len(violations) == 0
        
        return {
            'compliant': is_compliant,
            'violations': violations,
            'allowed_usage': allowed_usage,
            'violation_count': len(violations),
            'summary': 'Compliant with Reddit API policy' if is_compliant else f'{len(violations)} policy violations found'
        }
    
    @classmethod
    def check_url_compliance(cls, url: str) -> bool:
        """Check if URL uses official Reddit API
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is compliant, False otherwise
        """
        if not url:
            return True
        
        # Check if URL uses official API endpoints
        api_endpoints = [
            'oauth.reddit.com',
            'reddit.com/api/',
            'reddit.com/dev/api'
        ]
        
        url_lower = url.lower()
        
        # Allow official API endpoints
        if any(endpoint in url_lower for endpoint in api_endpoints):
            return True
        
        # Prohibit direct web scraping URLs
        prohibited_patterns = [
            'reddit.com/r/',
            'old.reddit.com',
            'www.reddit.com/r/'
        ]
        
        if any(pattern in url_lower for pattern in prohibited_patterns):
            return False
        
        return True
    
    @classmethod
    def log_api_usage(cls, endpoint: str, method: str = 'GET', user_agent: str = None) -> None:
        """Log Reddit API usage for compliance tracking
        
        Args:
            endpoint: API endpoint being accessed
            method: HTTP method
            user_agent: User agent string
        """
        compliance_log = {
            'event': 'reddit_api_usage',
            'endpoint': endpoint,
            'method': method,
            'user_agent': user_agent,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'compliant': cls.check_url_compliance(endpoint)
        }
        
        # Use safe logging to mask any sensitive data
        safe_log("Reddit API usage logged", **compliance_log)
    
    @classmethod
    def validate_user_agent(cls, user_agent: str) -> bool:
        """Validate user agent string for Reddit API compliance
        
        Args:
            user_agent: User agent string
            
        Returns:
            True if user agent is compliant, False otherwise
        """
        if not user_agent:
            return False
        
        # User agent should identify the application and version
        # Format: AppName/Version (by /u/username)
        required_elements = ['/', 'by']  # Should contain version and attribution
        
        return all(element in user_agent.lower() for element in required_elements)


# Global compliance checker instance
reddit_compliance_checker = RedditAPIComplianceChecker()


def check_reddit_api_compliance(code: str) -> Dict[str, Any]:
    """Convenience function for Reddit API compliance checking"""
    return reddit_compliance_checker.check_code_compliance(code)


def validate_reddit_url(url: str) -> bool:
    """Convenience function for Reddit URL validation"""
    return reddit_compliance_checker.check_url_compliance(url)


def log_reddit_api_usage(endpoint: str, method: str = 'GET', user_agent: str = None) -> None:
    """Convenience function for Reddit API usage logging"""
    reddit_compliance_checker.log_api_usage(endpoint, method, user_agent)