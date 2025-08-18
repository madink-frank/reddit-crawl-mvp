# Contributing Guidelines

## Welcome Contributors!

Thank you for your interest in contributing to Reddit Ghost Publisher! This document provides guidelines and information for contributors to help maintain code quality and ensure smooth collaboration.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)
- [Security](#security)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of background, experience level, or identity.

### Expected Behavior

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing private information without permission
- Any conduct that would be inappropriate in a professional setting

## Getting Started

### Prerequisites

Before contributing, ensure you have:

1. **Development Environment**: Follow the [Development Setup Guide](development-setup.md)
2. **GitHub Account**: Required for submitting pull requests
3. **Git Knowledge**: Basic understanding of Git workflows
4. **Python Experience**: Familiarity with Python 3.12+ and async programming

### First-Time Contributors

If you're new to the project:

1. **Start Small**: Look for issues labeled `good-first-issue` or `help-wanted`
2. **Read Documentation**: Familiarize yourself with the codebase and architecture
3. **Join Discussions**: Participate in issue discussions before starting work
4. **Ask Questions**: Don't hesitate to ask for clarification or help

### Finding Work

- **Bug Reports**: Check the [Issues](https://github.com/your-org/reddit-ghost-publisher/issues) page
- **Feature Requests**: Look for enhancement issues
- **Documentation**: Help improve or expand documentation
- **Testing**: Add test coverage for existing code

## Development Workflow

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/reddit-ghost-publisher.git
cd reddit-ghost-publisher

# Add upstream remote
git remote add upstream https://github.com/your-org/reddit-ghost-publisher.git
```

### 2. Create Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### 3. Make Changes

Follow the [Code Standards](#code-standards) and ensure your changes:
- Address the specific issue or feature
- Include appropriate tests
- Update documentation if needed
- Follow existing code patterns

### 4. Test Your Changes

```bash
# Run the full test suite
pytest

# Run with coverage
pytest --cov=app --cov-report=html --cov-fail-under=90

# Run specific test categories
pytest tests/unit/
pytest tests/integration/

# Run linting
black .
isort .
flake8 .
mypy app/
```

### 5. Commit Changes

```bash
# Stage your changes
git add .

# Commit with descriptive message
git commit -m "feat: add Reddit API rate limiting

- Implement exponential backoff for Reddit API calls
- Add rate limit monitoring and alerting
- Update tests for new rate limiting logic

Fixes #123"
```

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
# Use the pull request template and provide detailed description
```

## Code Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

#### Formatting

```python
# Use Black for automatic formatting
black .

# Line length: 88 characters (Black default)
# Use double quotes for strings
# Use trailing commas in multi-line structures

# Good
def process_posts(
    posts: List[Post],
    batch_size: int = 10,
    priority: int = 5,
) -> ProcessingResult:
    """Process a batch of posts with AI analysis."""
    pass

# Bad
def process_posts(posts: List[Post], batch_size: int=10, priority: int=5) -> ProcessingResult:
    pass
```

#### Import Organization

```python
# Use isort for automatic import sorting
isort .

# Import order:
# 1. Standard library
# 2. Third-party packages
# 3. Local application imports

import asyncio
import time
from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.models.post import Post
```

#### Type Hints

```python
# Always use type hints for function signatures
from typing import Dict, List, Optional, Union

def collect_posts(
    subreddits: List[str],
    limit: int = 25,
    sort_type: str = "hot"
) -> Dict[str, List[Post]]:
    """Collect posts from specified subreddits."""
    pass

# Use Optional for nullable values
def get_post_by_id(post_id: str) -> Optional[Post]:
    """Get post by ID, return None if not found."""
    pass

# Use Union for multiple types
def process_content(content: Union[str, Dict[str, str]]) -> str:
    """Process content from various formats."""
    pass
```

#### Documentation

```python
# Use Google-style docstrings
def calculate_velocity(post: Post, current_time: float) -> float:
    """Calculate post velocity score.
    
    Args:
        post: The Reddit post to analyze
        current_time: Current timestamp for calculation
        
    Returns:
        Velocity score as float (higher = more trending)
        
    Raises:
        ValueError: If post data is invalid
        
    Example:
        >>> post = Post(score=100, created_ts=1642248600)
        >>> velocity = calculate_velocity(post, 1642252200)
        >>> print(f"Velocity: {velocity:.2f}")
    """
    if post.score < 0:
        raise ValueError("Post score cannot be negative")
    
    time_diff = current_time - post.created_ts
    return post.score / max(time_diff / 3600, 1)  # Score per hour
```

#### Error Handling

```python
# Use specific exception types
from fastapi import HTTPException
import structlog

logger = structlog.get_logger(__name__)

async def fetch_reddit_posts(subreddit: str) -> List[Post]:
    """Fetch posts from Reddit API."""
    try:
        # API call logic
        posts = await reddit_client.get_posts(subreddit)
        return posts
        
    except RateLimitError as e:
        logger.warning(
            "Reddit API rate limit exceeded",
            subreddit=subreddit,
            retry_after=e.retry_after
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited, retry after {e.retry_after} seconds"
        )
        
    except RedditAPIError as e:
        logger.error(
            "Reddit API error",
            subreddit=subreddit,
            error=str(e),
            error_code=e.code
        )
        raise HTTPException(
            status_code=502,
            detail="External API error"
        )
        
    except Exception as e:
        logger.error(
            "Unexpected error fetching posts",
            subreddit=subreddit,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

#### Logging

```python
# Use structured logging with contextual information
import structlog

logger = structlog.get_logger(__name__)

async def process_post(post_id: str) -> ProcessingResult:
    """Process a single post with AI analysis."""
    logger.info(
        "Starting post processing",
        post_id=post_id,
        service="nlp_pipeline"
    )
    
    try:
        # Processing logic
        result = await ai_processor.analyze(post_id)
        
        logger.info(
            "Post processing completed",
            post_id=post_id,
            processing_time_ms=result.processing_time,
            tokens_used=result.tokens_used,
            success=True
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "Post processing failed",
            post_id=post_id,
            error=str(e),
            error_type=type(e).__name__,
            success=False,
            exc_info=True
        )
        raise
```

### FastAPI Patterns

#### Route Organization

```python
# Group related endpoints in router modules
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/posts", tags=["posts"])

class PostResponse(BaseModel):
    """Response model for post data."""
    id: str
    title: str
    score: int
    created_at: datetime

@router.get("/", response_model=List[PostResponse])
async def list_posts(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
) -> List[PostResponse]:
    """List posts with pagination."""
    pass
```

#### Dependency Injection

```python
# Use FastAPI dependencies for common functionality
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current authenticated user."""
    # Token validation logic
    pass

@router.post("/posts/")
async def create_post(
    post_data: PostCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new post."""
    pass
```

### Database Patterns

#### SQLAlchemy Models

```python
# Use declarative base and proper relationships
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base

class Post(Base):
    """Reddit post model."""
    __tablename__ = "posts"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    score = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    media_files = relationship("MediaFile", back_populates="post")
    processing_logs = relationship("ProcessingLog", back_populates="post")
    
    def __repr__(self) -> str:
        return f"<Post(id='{self.id}', title='{self.title[:50]}...')>"
```

#### Database Queries

```python
# Use async database operations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def get_posts_by_subreddit(
    db: AsyncSession,
    subreddit: str,
    limit: int = 25
) -> List[Post]:
    """Get posts from specific subreddit."""
    query = (
        select(Post)
        .where(Post.subreddit == subreddit)
        .order_by(Post.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()
```

### Celery Patterns

#### Task Definition

```python
# Use proper task decorators and error handling
from celery import Task
from app.celery_app import celery_app
import structlog

logger = structlog.get_logger(__name__)

@celery_app.task(
    bind=True,
    autoretry_for=(RedditAPIError, OpenAIError),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True
)
def collect_reddit_posts(
    self: Task,
    subreddits: List[str],
    sort_type: str = "hot",
    limit: int = 25
) -> Dict[str, Any]:
    """Collect posts from Reddit API."""
    logger.info(
        "Starting Reddit collection",
        task_id=self.request.id,
        subreddits=subreddits,
        sort_type=sort_type,
        limit=limit
    )
    
    try:
        # Collection logic
        results = perform_collection(subreddits, sort_type, limit)
        
        logger.info(
            "Reddit collection completed",
            task_id=self.request.id,
            posts_collected=len(results),
            success=True
        )
        
        return results
        
    except Exception as e:
        logger.error(
            "Reddit collection failed",
            task_id=self.request.id,
            error=str(e),
            retry_count=self.request.retries,
            exc_info=True
        )
        raise
```

## Testing Requirements

### Test Coverage

- **Minimum Coverage**: 90% for new code
- **Critical Paths**: 100% coverage for core business logic
- **Integration Points**: Full coverage for external API interactions

### Test Categories

#### Unit Tests

```python
# Test individual functions and methods
import pytest
from unittest.mock import Mock, patch
from app.workers.collector.reddit_client import RedditClient

class TestRedditClient:
    """Test Reddit API client functionality."""
    
    @pytest.fixture
    def reddit_client(self):
        """Create Reddit client for testing."""
        return RedditClient(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="test_agent"
        )
    
    @patch('praw.Reddit')
    def test_fetch_posts_success(self, mock_reddit, reddit_client):
        """Test successful post fetching."""
        # Setup mock
        mock_submission = Mock()
        mock_submission.id = "test123"
        mock_submission.title = "Test Post"
        mock_submission.score = 100
        
        mock_reddit.return_value.subreddit.return_value.hot.return_value = [
            mock_submission
        ]
        
        # Execute
        posts = reddit_client.fetch_posts("python", limit=1)
        
        # Assert
        assert len(posts) == 1
        assert posts[0]["id"] == "test123"
        assert posts[0]["title"] == "Test Post"
        assert posts[0]["score"] == 100
    
    def test_calculate_velocity(self, reddit_client):
        """Test velocity calculation."""
        post_data = {
            "score": 100,
            "created_utc": 1642248600
        }
        current_time = 1642252200  # 1 hour later
        
        velocity = reddit_client.calculate_velocity(post_data, current_time)
        
        assert velocity == 100.0  # 100 score / 1 hour
```

#### Integration Tests

```python
# Test component interactions
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
class TestAPIIntegration:
    """Test API endpoint integration."""
    
    async def test_health_check_endpoint(self):
        """Test health check returns proper status."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
            
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data
    
    async def test_trigger_collection_authenticated(self):
        """Test collection trigger with authentication."""
        headers = {"X-API-Key": "test-api-key"}
        payload = {
            "subreddits": ["python"],
            "sort_type": "hot",
            "limit": 5
        }
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/collect/trigger",
                json=payload,
                headers=headers
            )
            
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "queued"
```

#### End-to-End Tests

```python
# Test complete workflows
import pytest
from app.test_utils import create_test_post, wait_for_task_completion

@pytest.mark.e2e
class TestCompleteWorkflow:
    """Test complete content processing workflow."""
    
    async def test_full_pipeline(self):
        """Test complete pipeline from collection to publishing."""
        # 1. Trigger collection
        collection_task = await trigger_collection(["python"], limit=1)
        await wait_for_task_completion(collection_task["task_id"])
        
        # 2. Verify post was collected
        posts = await get_collected_posts()
        assert len(posts) >= 1
        
        # 3. Trigger processing
        processing_task = await trigger_processing(post_ids=[posts[0]["id"]])
        await wait_for_task_completion(processing_task["task_id"])
        
        # 4. Verify processing results
        processed_post = await get_post_by_id(posts[0]["id"])
        assert processed_post["summary_ko"] is not None
        assert processed_post["topic_tag"] is not None
        
        # 5. Trigger publishing
        publishing_task = await trigger_publishing(post_ids=[posts[0]["id"]])
        await wait_for_task_completion(publishing_task["task_id"])
        
        # 6. Verify publication
        published_post = await get_post_by_id(posts[0]["id"])
        assert published_post["ghost_url"] is not None
        assert published_post["status"] == "published"
```

### Test Fixtures

```python
# Create reusable test fixtures
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

@pytest.fixture(scope="session")
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()

@pytest.fixture
def sample_post():
    """Create sample post for testing."""
    return {
        "id": "test123",
        "title": "Test Post Title",
        "subreddit": "python",
        "score": 100,
        "comments": 25,
        "created_utc": 1642248600,
        "url": "https://reddit.com/r/python/test123",
        "content": "This is test content for the post."
    }
```

## Documentation

### Code Documentation

- **Docstrings**: All public functions and classes must have docstrings
- **Type Hints**: Use comprehensive type annotations
- **Comments**: Explain complex logic and business rules
- **Examples**: Include usage examples in docstrings

### API Documentation

- **OpenAPI**: Ensure all endpoints have proper OpenAPI documentation
- **Response Models**: Define Pydantic models for all responses
- **Error Codes**: Document all possible error responses
- **Examples**: Provide request/response examples

### Architecture Documentation

- **Design Decisions**: Document significant architectural choices
- **Data Flow**: Explain how data flows through the system
- **External Dependencies**: Document all external service integrations
- **Configuration**: Explain all configuration options

## Pull Request Process

### Before Submitting

1. **Rebase on Latest Main**
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-feature-branch
   git rebase main
   ```

2. **Run Full Test Suite**
   ```bash
   pytest --cov=app --cov-fail-under=90
   black .
   isort .
   flake8 .
   mypy app/
   ```

3. **Update Documentation**
   - Update relevant documentation files
   - Add docstrings to new functions
   - Update API documentation if needed

### Pull Request Template

Use this template for your pull request description:

```markdown
## Description
Brief description of the changes and their purpose.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Related Issues
Fixes #(issue number)

## Changes Made
- List of specific changes made
- Include any new dependencies added
- Mention any configuration changes required

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally
- [ ] Test coverage maintained/improved

## Documentation
- [ ] Code comments added/updated
- [ ] API documentation updated
- [ ] README updated (if needed)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] No sensitive information exposed
- [ ] Performance impact considered
- [ ] Security implications reviewed
```

### Review Process

1. **Automated Checks**: All CI checks must pass
2. **Code Review**: At least one maintainer review required
3. **Testing**: Reviewer will test functionality
4. **Documentation**: Ensure documentation is complete and accurate

### Merge Requirements

- All CI checks passing
- At least one approved review from maintainer
- No merge conflicts
- Up-to-date with main branch
- Test coverage requirements met

## Issue Reporting

### Bug Reports

Use this template for bug reports:

```markdown
## Bug Description
Clear and concise description of the bug.

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Environment
- OS: [e.g., Ubuntu 20.04]
- Python Version: [e.g., 3.12.0]
- Docker Version: [e.g., 20.10.8]
- Browser: [e.g., Chrome 96.0] (if applicable)

## Additional Context
- Error messages
- Log output
- Screenshots (if applicable)
- Configuration details
```

### Feature Requests

Use this template for feature requests:

```markdown
## Feature Description
Clear and concise description of the feature.

## Problem Statement
What problem does this feature solve?

## Proposed Solution
Detailed description of the proposed solution.

## Alternatives Considered
Other solutions you've considered.

## Additional Context
- Use cases
- Examples from other projects
- Mockups or diagrams (if applicable)
```

## Security

### Reporting Security Issues

**DO NOT** create public issues for security vulnerabilities.

Instead:
1. Email security@your-domain.com
2. Include detailed description of the vulnerability
3. Provide steps to reproduce (if safe to do so)
4. Allow reasonable time for response before public disclosure

### Security Guidelines

- **Never commit secrets**: Use environment variables or Vault
- **Validate all inputs**: Sanitize and validate user inputs
- **Use HTTPS**: All external communications must use TLS
- **Follow OWASP guidelines**: Implement security best practices
- **Regular updates**: Keep dependencies updated

### Security Checklist

- [ ] No hardcoded secrets or credentials
- [ ] Input validation implemented
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] CSRF protection
- [ ] Rate limiting implemented
- [ ] Authentication and authorization proper
- [ ] Secure headers configured
- [ ] Dependencies scanned for vulnerabilities

## Recognition

Contributors will be recognized in:
- **CONTRIBUTORS.md**: List of all contributors
- **Release Notes**: Major contributions mentioned
- **GitHub**: Contributor statistics and graphs

## Questions?

If you have questions about contributing:

1. **Check Documentation**: Review existing docs first
2. **Search Issues**: Look for similar questions
3. **Create Discussion**: Use GitHub Discussions for questions
4. **Join Community**: Connect with other contributors

Thank you for contributing to Reddit Ghost Publisher! 🚀