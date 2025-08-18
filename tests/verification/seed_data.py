"""
Seed data for MVP system verification tests
Contains test data for Reddit posts, NSFW content, and media samples
"""

# Sample Reddit post IDs for testing (these should be real post IDs for actual testing)
SAMPLE_REDDIT_POSTS = {
    "with_media": [
        "1abc123",  # Post with image
        "2def456",  # Post with video
        "3ghi789",  # Post with multiple images
    ],
    "without_media": [
        "4jkl012",  # Text-only post
        "5mno345",  # Link post without media
        "6pqr678",  # Discussion post
    ],
    "nsfw_posts": [
        "7stu901",  # NSFW post that should be filtered
        "8vwx234",  # Another NSFW post
    ],
    "high_score_posts": [
        "9yza567",  # High score post (>1000)
        "0bcd890",  # Another high score post
    ],
    "low_score_posts": [
        "1efg123",  # Low score post (<10)
        "2hij456",  # Another low score post
    ]
}

# Test subreddits for verification
TEST_SUBREDDITS = [
    "programming",
    "technology",
    "webdev",
    "MachineLearning",
    "artificial"
]

# Sample content for AI processing tests
SAMPLE_CONTENT = {
    "programming_post": {
        "title": "New Python 3.12 Features You Should Know",
        "body": "Python 3.12 introduces several new features including improved error messages, better performance optimizations, and new syntax for pattern matching. Here's what developers need to know about the latest release.",
        "subreddit": "programming",
        "score": 1250,
        "num_comments": 89,
        "expected_tags": ["python", "programming", "features", "update"],
        "expected_pain_points": ["learning curve", "migration effort"],
        "expected_product_ideas": ["migration tool", "tutorial platform"]
    },
    "technology_post": {
        "title": "The Future of AI in Software Development",
        "body": "Artificial Intelligence is transforming how we write, test, and deploy software. From code generation to automated testing, AI tools are becoming essential for modern developers.",
        "subreddit": "technology", 
        "score": 2100,
        "num_comments": 156,
        "expected_tags": ["ai", "software", "development", "automation"],
        "expected_pain_points": ["job displacement", "tool complexity"],
        "expected_product_ideas": ["ai coding assistant", "automated testing platform"]
    }
}

# Expected JSON schema for AI analysis
EXPECTED_JSON_SCHEMA = {
    "pain_points": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "point": {"type": "string"},
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                "category": {"type": "string"}
            },
            "required": ["point", "severity", "category"]
        }
    },
    "product_ideas": {
        "type": "array", 
        "items": {
            "type": "object",
            "properties": {
                "idea": {"type": "string"},
                "feasibility": {"type": "string", "enum": ["low", "medium", "high"]},
                "market_size": {"type": "string", "enum": ["small", "medium", "large"]}
            },
            "required": ["idea", "feasibility", "market_size"]
        }
    },
    "meta": {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "processed_at": {"type": "string"},
            "model_used": {"type": "string"}
        },
        "required": ["version"]
    }
}

# Test configuration for different verification scenarios
TEST_CONFIGS = {
    "reddit_collection": {
        "subreddits": ["programming", "technology"],
        "batch_size": 5,
        "rate_limit_rpm": 60,
        "daily_calls_limit": 100,
        "expected_min_posts": 5,
        "nsfw_filter_enabled": True
    },
    "ai_processing": {
        "primary_model": "gpt-4o-mini",
        "fallback_model": "gpt-4o", 
        "daily_tokens_limit": 1000,
        "expected_tag_count": {"min": 3, "max": 5},
        "retry_max": 3,
        "backoff_base": 2
    },
    "ghost_publishing": {
        "template_type": "article",
        "max_retries": 3,
        "jwt_expiry": 300,
        "expected_sections": [
            "title",
            "summary", 
            "insights",
            "original_link",
            "source_attribution"
        ]
    },
    "monitoring": {
        "queue_alert_threshold": 10,
        "failure_rate_threshold": 0.05,
        "health_check_timeout": 30,
        "metrics_update_interval": 60
    }
}

# Slack test webhook configuration
SLACK_TEST_CONFIG = {
    "test_channel": "#reddit-publisher-test",
    "webhook_url": "https://hooks.slack.com/services/TEST/WEBHOOK/URL",
    "alert_types": [
        "budget_80_percent",
        "budget_100_percent", 
        "queue_threshold_exceeded",
        "failure_rate_exceeded",
        "daily_report"
    ],
    "expected_message_format": {
        "severity": ["LOW", "MEDIUM", "HIGH"],
        "service": ["collector", "nlp_pipeline", "publisher"],
        "required_fields": ["timestamp", "message", "metrics"]
    }
}

# Performance test expectations
PERFORMANCE_TARGETS = {
    "api_response_time": {
        "p95_target_ms": 300,
        "p95_alert_threshold_ms": 400,
        "timeout_ms": 5000
    },
    "e2e_processing": {
        "target_minutes": 5,
        "alert_threshold_minutes": 7,
        "timeout_minutes": 10
    },
    "throughput": {
        "posts_per_hour": 100,
        "min_success_rate": 0.95,
        "max_failure_rate": 0.05
    }
}

# Database test data
DATABASE_TEST_DATA = {
    "required_tables": [
        "posts",
        "media_files", 
        "processing_logs",
        "token_usage"
    ],
    "required_indexes": [
        "idx_posts_reddit_post_id",
        "idx_posts_created_ts",
        "idx_posts_subreddit",
        "idx_processing_logs_post_id",
        "idx_token_usage_created_at"
    ],
    "required_constraints": [
        "posts_reddit_post_id_unique",
        "posts_takedown_status_check"
    ],
    "sample_post_data": {
        "reddit_post_id": "test_post_123",
        "title": "Test Post Title",
        "subreddit": "programming",
        "score": 100,
        "num_comments": 25,
        "summary_ko": "테스트 요약",
        "tags": ["test", "programming", "verification"],
        "content_hash": "abc123def456"
    }
}

# Security test data
SECURITY_TEST_DATA = {
    "sensitive_patterns": [
        "api_key=sk-1234567890abcdef",
        "token=ghp_1234567890abcdef", 
        "password=secret123",
        "email=user@example.com"
    ],
    "expected_masked_patterns": [
        "api_key=****",
        "token=****",
        "password=****", 
        "email=****@example.com"
    ],
    "takedown_test_data": {
        "reddit_post_id": "takedown_test_123",
        "reason": "Copyright infringement",
        "expected_sla_hours": 72,
        "expected_statuses": ["active", "takedown_pending", "removed"]
    }
}