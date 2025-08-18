# Development Environment Setup Guide

## Prerequisites

Before setting up the development environment, ensure you have the following installed:

### Required Software

1. **Python 3.12+**
   ```bash
   # Check Python version
   python --version
   
   # Install Python 3.12 (Ubuntu/Debian)
   sudo apt update
   sudo apt install python3.12 python3.12-venv python3.12-dev
   
   # Install Python 3.12 (macOS with Homebrew)
   brew install python@3.12
   
   # Install Python 3.12 (Windows)
   # Download from https://www.python.org/downloads/
   ```

2. **Docker and Docker Compose**
   ```bash
   # Install Docker (Ubuntu/Debian)
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   
   # Install Docker Desktop (macOS/Windows)
   # Download from https://www.docker.com/products/docker-desktop
   
   # Verify installation
   docker --version
   docker-compose --version
   ```

3. **Git**
   ```bash
   # Install Git (Ubuntu/Debian)
   sudo apt install git
   
   # Install Git (macOS)
   brew install git
   
   # Install Git (Windows)
   # Download from https://git-scm.com/download/win
   
   # Verify installation
   git --version
   ```

4. **Node.js and npm** (for frontend tools)
   ```bash
   # Install Node.js (Ubuntu/Debian)
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install -y nodejs
   
   # Install Node.js (macOS)
   brew install node
   
   # Install Node.js (Windows)
   # Download from https://nodejs.org/
   
   # Verify installation
   node --version
   npm --version
   ```

### Optional Tools

1. **PostgreSQL Client** (for database management)
   ```bash
   # Ubuntu/Debian
   sudo apt install postgresql-client
   
   # macOS
   brew install postgresql
   
   # Windows
   # Download from https://www.postgresql.org/download/windows/
   ```

2. **Redis CLI** (for cache management)
   ```bash
   # Ubuntu/Debian
   sudo apt install redis-tools
   
   # macOS
   brew install redis
   
   # Windows
   # Download from https://github.com/microsoftarchive/redis/releases
   ```

## Project Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/reddit-ghost-publisher.git
cd reddit-ghost-publisher
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate

# Verify activation (should show venv path)
which python
```

### 3. Install Python Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Verify installation
pip list
```

### 4. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit environment file
nano .env  # or use your preferred editor
```

#### Required Environment Variables

Edit `.env` file with the following configuration:

```bash
# Application Configuration
DEBUG=true
ENVIRONMENT=development
TZ=UTC

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Database Configuration (PostgreSQL for development)
DATABASE_URL=postgresql://postgres:dev@localhost:5432/reddit_publisher
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=20

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TIMEZONE=UTC

# Reddit API Configuration with Budget Limits
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=RedditGhostPublisher/1.0
REDDIT_RATE_LIMIT_RPM=60
REDDIT_DAILY_CALLS_LIMIT=5000

# OpenAI Configuration with Budget Limits
OPENAI_API_KEY=your_openai_api_key
OPENAI_PRIMARY_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODEL=gpt-4o
OPENAI_DAILY_TOKENS_LIMIT=100000

# Cost per 1K tokens (fixed internal cost map)
COST_GPT4O_MINI_PER_1K=0.00015
COST_GPT4O_PER_1K=0.005

# Ghost CMS Configuration
GHOST_ADMIN_KEY=your_ghost_admin_key
GHOST_API_URL=https://your-blog.ghost.io
GHOST_JWT_EXPIRY=300
DEFAULT_OG_IMAGE_URL=https://your-blog.ghost.io/content/images/default-og.jpg

# Scheduling Configuration (Cron expressions)
COLLECT_CRON=0 * * * *
BACKUP_CRON=0 4 * * *

# Content Processing Configuration
SUBREDDITS=programming,technology,webdev
BATCH_SIZE=20
CONTENT_MIN_SCORE=10
CONTENT_MIN_COMMENTS=5

# Monitoring and Alerting
LOG_LEVEL=DEBUG
STRUCTURED_LOGGING=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

# Alert Thresholds
QUEUE_ALERT_THRESHOLD=500
FAILURE_RATE_THRESHOLD=0.05

# Queue Configuration
QUEUE_COLLECT_NAME=collect
QUEUE_PROCESS_NAME=process
QUEUE_PUBLISH_NAME=publish

# Worker Configuration (Single node)
WORKER_COLLECTOR_CONCURRENCY=1
WORKER_NLP_CONCURRENCY=1
WORKER_PUBLISHER_CONCURRENCY=1

# Retry Configuration (Constants)
RETRY_MAX=3
BACKOFF_BASE=2
BACKOFF_MIN=2
BACKOFF_MAX=8

# Template Configuration (Article only for MVP)
TEMPLATE_ARTICLE_PATH=templates/article.hbs

# Security Configuration (Environment variables only, no Vault)
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Database Credentials (for Docker Compose)
POSTGRES_DB=reddit_publisher
POSTGRES_USER=postgres
POSTGRES_PASSWORD=dev
POSTGRES_PORT=5432

# Redis Configuration (for Docker Compose)
REDIS_PORT=6379
```

### 5. Start Development Services

#### Option A: Docker Compose (Recommended)

```bash
# Start all services in development mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Option B: Manual Service Startup

1. **Start Redis**
   ```bash
   # Using Docker
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   
   # Or install locally
   redis-server
   ```

2. **Start PostgreSQL** (Required - PostgreSQL used for all environments)
   ```bash
   # Using Docker
   docker run -d --name postgres \
     -e POSTGRES_DB=reddit_publisher \
     -e POSTGRES_USER=postgres \
     -e POSTGRES_PASSWORD=dev \
     -p 5432:5432 \
     postgres:15
   ```

3. **Initialize Database**
   ```bash
   # Run database migrations
   alembic upgrade head
   
   # Verify database setup
   python -c "from app.infrastructure import get_database; print('Database connection successful')"
   ```

### 6. Start the Application

#### Development Server

```bash
# Start FastAPI development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the convenience script
python -m app.main
```

#### Celery Workers (MVP Single Node)

Open separate terminal windows/tabs for each worker:

```bash
# Terminal 1: Collector worker (single concurrency)
celery -A app.celery_app worker -Q collect -c 1 --loglevel=info

# Terminal 2: NLP processing worker (single concurrency)
celery -A app.celery_app worker -Q process -c 1 --loglevel=info

# Terminal 3: Publisher worker (single concurrency)
celery -A app.celery_app worker -Q publish -c 1 --loglevel=info

# Terminal 4: Celery Beat scheduler
celery -A app.celery_app beat --loglevel=info
```

#### Basic Monitoring (MVP)

The MVP includes basic monitoring via API endpoints:

```bash
# Check health
curl http://localhost:8000/health

# Check queue status
curl http://localhost:8000/api/v1/status/queues

# Check worker status
curl http://localhost:8000/api/v1/status/workers

# Check metrics
curl http://localhost:8000/metrics
```

## Development Workflow

### 1. Code Structure

```
reddit-ghost-publisher/
├── app/                    # Main application code
│   ├── api/               # FastAPI routes and middleware
│   ├── models/            # SQLAlchemy models
│   ├── services/          # Business logic services
│   ├── monitoring/        # Health checks and metrics
│   ├── caching/           # Redis caching utilities
│   └── scaling/           # Auto-scaling logic
├── workers/               # Celery worker implementations
│   ├── collector/         # Reddit collection workers
│   ├── nlp_pipeline/      # AI processing workers
│   └── publisher/         # Ghost publishing workers
├── tests/                 # Test suites
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   ├── e2e/              # End-to-end tests
│   └── load/             # Load testing
├── docs/                  # Documentation
├── docker/                # Docker configurations
├── terraform/             # Infrastructure as code
└── scripts/               # Utility scripts
```

### 2. Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest tests/e2e/          # End-to-end tests only

# Run tests with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "test_reddit" -v

# Run tests and stop on first failure
pytest -x
```

### 3. Code Quality Tools

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Lint code with flake8
flake8 .

# Type checking with mypy
mypy app/

# Security scanning with bandit
bandit -r app/

# Dependency vulnerability scanning
safety check

# Run all quality checks
make lint  # If Makefile is configured
```

### 4. Database Management

```bash
# Create new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history

# Reset database (development only)
dropdb -h localhost -U postgres reddit_publisher
createdb -h localhost -U postgres reddit_publisher
alembic upgrade head
```

### 5. Debugging

#### Using Python Debugger

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use built-in breakpoint() (Python 3.7+)
breakpoint()
```

#### Using VS Code Debugger

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/app/main.py",
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        },
        {
            "name": "Celery Worker",
            "type": "python",
            "request": "launch",
            "module": "celery",
            "args": ["-A", "app.celery_app", "worker", "-Q", "collect", "--loglevel=debug"],
            "console": "integratedTerminal",
            "env": {
                "PYTHONPATH": "${workspaceFolder}"
            }
        }
    ]
}
```

#### Logging Configuration

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or use structured logging
import structlog
logger = structlog.get_logger(__name__)
logger.debug("Debug message", key="value")
```

## API Development

### 1. Interactive API Documentation

Once the server is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 2. Testing API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Get queue status (no authentication in MVP)
curl http://localhost:8000/api/v1/status/queues

# Get worker status
curl http://localhost:8000/api/v1/status/workers

# Trigger collection
curl -X POST http://localhost:8000/api/v1/collect/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "subreddits": ["python"],
    "sort_type": "hot",
    "limit": 5
  }'

# Trigger processing
curl -X POST http://localhost:8000/api/v1/process/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "post_ids": ["post1", "post2"]
  }'

# Trigger publishing
curl -X POST http://localhost:8000/api/v1/publish/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "post_ids": ["post1", "post2"]
  }'

# Request takedown
curl -X POST http://localhost:8000/api/v1/takedown/abc123 \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Copyright infringement",
    "contact_email": "test@example.com"
  }'
```

### 3. Testing Slack Notifications

```python
# Run this script to test Slack notifications
import requests
import os

def test_slack_notification():
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        print("SLACK_WEBHOOK_URL not configured")
        return
    
    payload = {
        "text": "🧪 Test notification from Reddit Ghost Publisher",
        "attachments": [
            {
                "color": "good",
                "fields": [
                    {"title": "Environment", "value": "development", "short": True},
                    {"title": "Status", "value": "Testing", "short": True}
                ]
            }
        ]
    }
    
    response = requests.post(webhook_url, json=payload)
    if response.status_code == 200:
        print("✅ Slack notification sent successfully")
    else:
        print(f"❌ Failed to send Slack notification: {response.status_code}")

if __name__ == "__main__":
    test_slack_notification()
```

## Frontend Development (Optional)

If you're developing a frontend interface:

### 1. Install Frontend Dependencies

```bash
# Navigate to frontend directory (if exists)
cd frontend/

# Install dependencies
npm install

# Start development server
npm run dev
```

### 2. API Client Generation

```bash
# Generate TypeScript client from OpenAPI spec
npx @openapitools/openapi-generator-cli generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-axios \
  -o src/api/generated
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   
   # Kill process
   kill -9 <PID>
   
   # Or use different port
   uvicorn app.main:app --port 8001
   ```

2. **Database Connection Issues**
   ```bash
   # Check if PostgreSQL is running
   docker ps | grep postgres
   
   # Check SQLite file permissions
   ls -la reddit_publisher.db
   
   # Reset database
   rm reddit_publisher.db
   alembic upgrade head
   ```

3. **Redis Connection Issues**
   ```bash
   # Check if Redis is running
   docker ps | grep redis
   
   # Test Redis connection
   redis-cli ping
   
   # Check Redis logs
   docker logs redis
   ```

4. **Import Errors**
   ```bash
   # Ensure PYTHONPATH is set
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   
   # Or add to .bashrc/.zshrc
   echo 'export PYTHONPATH="${PYTHONPATH}:$(pwd)"' >> ~/.bashrc
   ```

5. **Celery Worker Issues**
   ```bash
   # Check Celery broker connection
   celery -A app.celery_app inspect ping
   
   # List active workers
   celery -A app.celery_app inspect active
   
   # Check queue lengths
   redis-cli llen collect
   redis-cli llen process
   redis-cli llen publish
   
   # Purge all queues (development only)
   celery -A app.celery_app purge
   ```

6. **External API Issues**
   ```bash
   # Test Reddit API connection
   python -c "
   import praw
   import os
   reddit = praw.Reddit(
       client_id=os.getenv('REDDIT_CLIENT_ID'),
       client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
       user_agent=os.getenv('REDDIT_USER_AGENT')
   )
   print('Reddit API:', reddit.user.me() or 'Connected')
   "
   
   # Test OpenAI API connection
   python -c "
   import openai
   import os
   openai.api_key = os.getenv('OPENAI_API_KEY')
   try:
       response = openai.ChatCompletion.create(
           model='gpt-4o-mini',
           messages=[{'role': 'user', 'content': 'test'}],
           max_tokens=5
       )
       print('OpenAI API: Connected')
   except Exception as e:
       print(f'OpenAI API Error: {e}')
   "
   
   # Test Ghost API connection
   python -c "
   import requests
   import os
   import jwt
   import time
   
   admin_key = os.getenv('GHOST_ADMIN_KEY')
   api_url = os.getenv('GHOST_API_URL')
   
   if admin_key and api_url:
       key_id, secret = admin_key.split(':')
       iat = int(time.time())
       payload = {'iat': iat, 'exp': iat + 300, 'aud': '/admin/'}
       token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
       
       headers = {'Authorization': f'Ghost {token}'}
       response = requests.get(f'{api_url}/ghost/api/admin/site/', headers=headers)
       print(f'Ghost API: {response.status_code}')
   else:
       print('Ghost API: Not configured')
   "
   ```

### Getting Help

1. **Check Application Logs**
   ```bash
   # FastAPI logs
   tail -f logs/app.log
   
   # Celery logs
   tail -f logs/celery.log
   
   # Docker logs
   docker-compose logs -f
   ```

2. **Health Check Endpoints**
   ```bash
   # Basic health
   curl http://localhost:8000/health
   
   # Detailed health
   curl http://localhost:8000/health?detailed=true
   
   # Dependencies check
   curl http://localhost:8000/health/dependencies
   ```

3. **Database Inspection**
   ```bash
   # PostgreSQL
   psql -h localhost -U postgres -d reddit_publisher -c "\dt"
   psql -h localhost -U postgres -d reddit_publisher -c "SELECT * FROM posts LIMIT 5;"
   psql -h localhost -U postgres -d reddit_publisher -c "SELECT COUNT(*) FROM posts;"
   ```

4. **Redis Inspection**
   ```bash
   # Connect to Redis
   redis-cli
   
   # List all keys
   KEYS *
   
   # Check queue lengths
   LLEN celery:collect
   LLEN celery:process
   LLEN celery:publish
   ```

## Performance Optimization

### 1. Development Performance

```bash
# Use faster Python interpreter
export PYTHONOPTIMIZE=1

# Enable SQLite WAL mode for better concurrency
sqlite3 reddit_publisher.db "PRAGMA journal_mode=WAL;"

# Use Redis for session storage
export SESSION_BACKEND="redis"
```

### 2. Profiling

```python
# Profile API endpoints
from fastapi import Request
import time

@app.middleware("http")
async def profile_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

### 3. Memory Usage

```bash
# Monitor memory usage
pip install memory-profiler
python -m memory_profiler your_script.py

# Or use built-in profiling
python -m cProfile -o profile.stats your_script.py
```

## Next Steps

After setting up your development environment:

1. **Read the API Documentation**: Review `docs/api-documentation.md`
2. **Understand the Architecture**: Study `docs/architecture.md`
3. **Run the Test Suite**: Execute `pytest` to ensure everything works
4. **Make Your First Change**: Try modifying a simple endpoint
5. **Submit a Pull Request**: Follow the contributing guidelines

## Additional Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Celery Documentation**: https://docs.celeryproject.org/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **Redis Documentation**: https://redis.io/documentation
- **Docker Documentation**: https://docs.docker.com/
- **Pytest Documentation**: https://docs.pytest.org/