# Design Document

## Overview

Reddit Ghost Publisher는 Reddit 인기 글을 수집하고 한국어 요약을 생성한 뒤 Ghost CMS에 자동 발행하는 MVP 시스템입니다. 비용과 운영 복잡도를 최소화하고 하루 단위 배치로 안정 동작을 확보하는 것을 목표로 합니다. FastAPI + Celery + Redis + PostgreSQL을 단일 노드 Docker Compose로 운영하는 단순한 아키텍처를 사용합니다.

## Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "External Services"
        Reddit[Reddit API]
        OpenAI[OpenAI GPT-4o-mini/GPT-4o]
        Ghost[Ghost Pro]
    end
    
    subgraph "Single Node Docker Compose"
        subgraph "API Layer"
            FastAPI[FastAPI Gateway]
        end
        
        subgraph "Message Queue"
            Redis[(Redis)]
            CeleryBeat[Celery Beat Scheduler]
        end
        
        subgraph "Worker Services"
            Collector[Collector Worker]
            NLPPipe[NLP Pipeline Worker]
            Publisher[Publisher Worker]
        end
        
        subgraph "Data Layer"
            PostgreSQL[(PostgreSQL 15)]
        end
        
        subgraph "Basic Monitoring"
            Metrics[/metrics endpoint]
            Health[/health endpoint]
            Logs[Basic Logging]
        end
    end
    
    subgraph "Notifications"
        Slack[Slack Webhook]
    end
    
    FastAPI --> Redis
    CeleryBeat --> Redis
    Redis --> Collector
    Redis --> NLPPipe
    Redis --> Publisher
    
    Collector --> Reddit
    Collector --> PostgreSQL
    NLPPipe --> OpenAI
    NLPPipe --> PostgreSQL
    Publisher --> Ghost
    Publisher --> PostgreSQL
    
    FastAPI --> Metrics
    FastAPI --> Health
    
    Collector --> Slack
    NLPPipe --> Slack
    Publisher --> Slack
    
    PostgreSQL --> Logs
```

### Simplified Architecture

시스템은 단일 노드에서 실행되는 3개의 Celery 워커로 구성됩니다:

1. **Collector Worker**: Reddit API 호출 및 데이터 수집
2. **NLP Pipeline Worker**: AI 기반 콘텐츠 처리 및 분석  
3. **Publisher Worker**: Ghost CMS 발행 및 이미지 처리

모든 서비스는 동일한 Docker Compose 환경에서 실행되며, 수동 스케일링만 지원합니다.

## Components and Interfaces

### 1. FastAPI Gateway

**책임**: API 엔드포인트 제공, 인증, 요청 라우팅

**주요 엔드포인트**:
```python
# Health check
GET /health

# Manual trigger endpoints
POST /api/v1/collect/trigger
POST /api/v1/process/trigger  
POST /api/v1/publish/trigger

# Status monitoring
GET /api/v1/status/queues
GET /api/v1/status/workers

# Metrics endpoint
GET /metrics

# Takedown endpoint
POST /api/v1/takedown/{reddit_post_id}
```

**큐/워커 상태 API 구현**:
```python
from celery import current_app

@app.get("/api/v1/status/queues")
async def get_queue_status():
    """Redis 기반 큐 상태 조회"""
    inspect = current_app.control.inspect()
    
    # 활성 작업
    active = inspect.active() or {}
    # 예약된 작업  
    scheduled = inspect.scheduled() or {}
    # 대기 중인 작업 (Redis에서 직접 조회)
    
    queue_stats = {}
    for queue in ['collect', 'process', 'publish']:
        queue_stats[queue] = {
            'active': sum(len(tasks) for tasks in active.values()),
            'scheduled': sum(len(tasks) for tasks in scheduled.values()),
            'pending': redis_client.llen(queue)  # Redis 큐 길이
        }
    
    return queue_stats

@app.get("/api/v1/status/workers")
async def get_worker_status():
    """Celery 워커 상태 조회"""
    inspect = current_app.control.inspect()
    
    stats = inspect.stats() or {}
    active = inspect.active() or {}
    
    worker_stats = {}
    for worker_name, worker_info in stats.items():
        worker_stats[worker_name] = {
            'status': 'online',
            'active_tasks': len(active.get(worker_name, [])),
            'processed_tasks': worker_info.get('total', {}).get('tasks.collector.collect_reddit_posts', 0),
            'load_avg': worker_info.get('rusage', {}).get('utime', 0)
        }
    
    return worker_stats
```

**기술 스택**:
- FastAPI with async/await
- Pydantic models for validation
- 환경변수 기반 인증
- 기본 메트릭 노출 (/metrics)

### 2. Celery Queue System

**큐 구성**:
```python
# Redis 브로커용 단순 큐 설정
CELERY_TASK_ROUTES = {
    'workers.collector.tasks.collect_reddit_posts': {'queue': 'collect'},
    'workers.nlp_pipeline.tasks.process_content_with_ai': {'queue': 'process'},
    'workers.publisher.tasks.publish_to_ghost': {'queue': 'publish'},
}

# 워커 실행 명령
# celery -A app.celery worker -Q collect -c 1
# celery -A app.celery worker -Q process -c 1  
# celery -A app.celery worker -Q publish -c 1
```

**스케줄링**:
- Celery Beat을 사용한 주기적 작업 스케줄링
- Reddit 수집: 시간당 1회 (COLLECT_CRON="0 * * * *")
- 시스템 헬스체크: 매 5분
- 백업 작업: 매일 새벽 4시 (BACKUP_CRON="0 4 * * *")

### 3. Collector Service

**책임**: Reddit API 호출, 콘텐츠 필터링, 속도 계산

**핵심 기능**:
```python
@celery_app.task(bind=True, max_retries=3)
def collect_reddit_posts(self, subreddits: List[str], sort_type: str = "hot"):
    """
    Reddit에서 게시글 수집
    - API 제한 준수 (100 req/min)
    - NSFW 필터링
    - 속도 계산 (score/time)
    - 중복 제거
    """
    pass

@celery_app.task(bind=True)
def calculate_velocity(self, post_data: dict):
    """
    게시글 속도 계산
    - 시간당 점수 증가율
    - 댓글 증가율
    - 트렌드 점수 산출
    """
    pass
```

**Reddit API 통합**:
- PRAW (Python Reddit API Wrapper) 사용
- OAuth 2.0 인증 (환경변수에서 토큰 관리)
- Rate limiting: 60 requests/minute
- Exponential backoff 재시도 로직
- 일일 API 호출 상한 모니터링

### 4. NLP Pipeline Service

**책임**: AI 기반 콘텐츠 분석, 요약, 태깅

**핵심 기능**:
```python
@celery_app.task(bind=True, max_retries=3)
def process_content_with_ai(self, post_id: str):
    """
    AI 기반 콘텐츠 처리
    - GPT-4o 한국어 요약
    - BERTopic 태그 추출
    - 페인 포인트 분석
    - 제품 아이디어 추출
    """
    pass

@celery_app.task(bind=True)
def extract_topics_llm(self, content: str):
    """
    LLM 프롬프트를 사용한 태그 추출
    - 3-5개 태그 추출
    - 일관된 표기 규칙 적용
    - 검색 최적화된 키워드 생성
    """
    pass
```

**AI 통합**:
- OpenAI GPT-4o-mini (primary) + GPT-4o (fallback)
- 내부 코스트 맵을 통한 토큰 사용량 추적
- LLM 프롬프트만으로 태그 추출 (3-5개 제한)
- 일일 토큰 예산 모니터링 및 차단

### 5. Publisher Service

**책임**: Ghost CMS 발행, 이미지 처리, 템플릿 적용

**핵심 기능**:
```python
@celery_app.task(bind=True, max_retries=5)
def publish_to_ghost(self, processed_content_id: str):
    """
    Ghost CMS에 콘텐츠 발행
    - Markdown to HTML 변환
    - 이미지 업로드 및 CDN 처리
    - 태그 매핑
    - 저작권 표시 추가
    """
    pass

@celery_app.task(bind=True)
def process_media_content(self, media_urls: List[str]):
    """
    미디어 콘텐츠 처리
    - Reddit 이미지 다운로드
    - Ghost Images API 업로드
    - CDN URL 생성
    """
    pass
```

**Ghost CMS 통합**:
- Ghost Admin API v5
- JWT 인증 (Admin Key로 서명)
- Article 템플릿 1종류만 사용 (고정 출처 고지 포함)

**고정 출처 고지 문구**:
```html
<!-- 본문 하단에 자동 삽입 -->
<hr>
<p><strong>Source:</strong> <a href="{reddit_url}" target="_blank">Reddit</a></p>
<p><em>Media and usernames belong to their respective owners.</em></p>
<p><em>Takedown requests will be honored.</em></p>
```
- 이미지 로컬 다운로드 후 Ghost Images API 업로드
- 미디어 없을 시 기본 OG 이미지 사용

## Data Models

### PostgreSQL Schema

```sql
-- 메인 게시글 테이블 (MVP 스키마)
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reddit_post_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    subreddit TEXT NOT NULL,
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    created_ts TIMESTAMPTZ NOT NULL,
    
    -- AI 처리 결과
    summary_ko TEXT,
    tags JSONB, -- 3-5개 태그 배열
    pain_points JSONB, -- JSON 스키마 준수
    product_ideas JSONB, -- JSON 스키마 준수
    
    -- Ghost 발행 정보
    ghost_url TEXT,
    
    -- 메타데이터
    content_hash TEXT,
    takedown_status TEXT DEFAULT 'active' CHECK (takedown_status IN ('active', 'takedown_pending', 'removed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 미디어 파일 테이블
CREATE TABLE media_files (
    id SERIAL PRIMARY KEY,
    post_id UUID REFERENCES posts(id),
    original_url TEXT NOT NULL,
    ghost_url TEXT,
    file_type TEXT,
    file_size INTEGER,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 처리 로그 테이블
CREATE TABLE processing_logs (
    id SERIAL PRIMARY KEY,
    post_id UUID REFERENCES posts(id),
    service_name TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 토큰 사용량 추적
CREATE TABLE token_usage (
    id SERIAL PRIMARY KEY,
    post_id UUID REFERENCES posts(id),
    service TEXT NOT NULL, -- 'openai'
    model TEXT NOT NULL, -- 'gpt-4o-mini', 'gpt-4o'
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE UNIQUE INDEX idx_posts_reddit_post_id ON posts(reddit_post_id);
CREATE INDEX idx_posts_created_ts ON posts(created_ts);
CREATE INDEX idx_posts_subreddit ON posts(subreddit);
CREATE INDEX idx_processing_logs_post_id ON processing_logs(post_id);
CREATE INDEX idx_token_usage_created_at ON token_usage(created_at);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_posts_updated_at BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Redis Data Structures

```python
# 큐 상태 모니터링
QUEUE_STATS = {
    'collect:pending': 'list',      # 대기 중인 수집 작업
    'process:pending': 'list',      # 대기 중인 처리 작업  
    'publish:pending': 'list',      # 대기 중인 발행 작업
}

# API 제한 추적 (단순화)
RATE_LIMITS = {
    'reddit:daily_calls': 'counter',     # 일일 API 호출 수
    'openai:daily_tokens': 'counter',    # 일일 토큰 사용량
}

# 기본 캐시
CACHE_KEYS = {
    'subreddit:hot:{name}': 'hash',      # 서브레딧 핫 게시글 캐시 (15분)
    'config:system': 'hash'              # 시스템 설정 캐시
}
```

## Error Handling

### 1. 계층별 에러 처리

**API Layer (FastAPI)**:
```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path
        }
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "details": exc.errors(),
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

**Worker Layer (Celery)**:
```python
@celery_app.task(bind=True, autoretry_for=(RequestException, OpenAIError), 
                 retry_kwargs={'max_retries': 3, 'countdown': 60})
def resilient_task(self, *args, **kwargs):
    try:
        # 작업 실행
        result = perform_task(*args, **kwargs)
        return result
    except RateLimitError as e:
        # Rate limit 에러 시 더 긴 대기
        raise self.retry(countdown=300, exc=e)
    except CriticalError as e:
        # 재시도하지 않을 에러
        logger.error(f"Critical error in task: {e}")
        raise
```

### 2. 외부 서비스 에러 처리

**Reddit API**:
- Rate limit: 헤더 기반 동적 제어 (남은 쿼터 추적)
- 초과 예상 시: 큐로 지연 처리 및 지수 백오프
- 인증 실패: 환경변수에서 토큰 재로드
- 일일 상한 도달: 수집 중단 및 Slack 알림

**OpenAI API**:
- GPT-4o-mini 실패: GPT-4o로 폴백
- 토큰 예산 초과: 일일 예산 알림 및 작업 차단
- 모델 오버로드: 30초 대기 후 재시도

**Ghost CMS**:
- 발행 실패: 3회까지 재시도 (지수적 백오프)
- 이미지 업로드 실패: 기본 OG 이미지로 대체
- 미디어 없는 게시글: 기본 OG 이미지 자동 삽입
- 중복 발행 방지: reddit_post_id 기반 체크 (멱등성 보장)

### 3. 데이터 일관성 보장

**트랜잭션 관리**:
```python
async def process_post_with_transaction(post_id: str):
    async with database.transaction():
        try:
            # 상태 업데이트
            await update_post_status(post_id, 'processing')
            
            # AI 처리
            result = await process_with_ai(post_id)
            
            # 결과 저장
            await save_processing_result(post_id, result)
            
            # 상태 완료로 변경
            await update_post_status(post_id, 'processed')
            
        except Exception as e:
            # 실패 상태로 변경
            await update_post_status(post_id, 'failed')
            raise
```

## Testing Strategy

### 1. 단위 테스트 (pytest)

**커버리지 목표**: 70% 이상

```python
# 테스트 구조 (단순화)
tests/
├── unit/
│   ├── test_collector.py      # Reddit API 호출 테스트
│   ├── test_nlp_pipeline.py   # AI 처리 로직 테스트
│   ├── test_publisher.py      # Ghost 발행 테스트
│   └── test_models.py         # 데이터 모델 테스트
├── integration/
│   ├── test_api_endpoints.py  # FastAPI 엔드포인트 테스트
│   └── test_celery_tasks.py   # Celery 작업 테스트
└── e2e/
    └── test_smoke_tests.py    # 스모크 테스트
```

**Mock 전략**:
```python
# 외부 서비스 Mock
@pytest.fixture
def mock_reddit_api():
    with patch('praw.Reddit') as mock:
        mock.return_value.subreddit.return_value.hot.return_value = [
            MockSubmission(id='test1', title='Test Post', score=100)
        ]
        yield mock

@pytest.fixture  
def mock_openai_api():
    with patch('openai.ChatCompletion.create') as mock:
        mock.return_value = {
            'choices': [{'message': {'content': 'Test summary'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }
        yield mock
```

### 2. 통합 테스트 (Postman/Newman)

**API 테스트 시나리오**:
- 헬스체크 엔드포인트
- 메트릭 엔드포인트
- 수동 트리거 엔드포인트 (수집→요약→발행)
- 중복 발행 방지 테스트 (동일 reddit_post_id 재시도 시 409/멱등 처리)

**목표**: 100% 스모크 테스트 통과

### 3. 성능 테스트 (k6)

**테스트 시나리오**:
```javascript
import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 50,
  duration: '5m',
  thresholds: {
    http_req_duration: ['p(95)<300'],
    http_req_failed: ['rate<0.05'],
  },
};

export default function () {
  const res = http.get(__ENV.API_BASE + '/health');
  check(res, { 'status 200': (r) => r.status === 200 });
}
```

**성능 목표**:
- p95 응답시간 < 300ms
- E2E 처리 시간 < 5분
- 시간당 100개 글 처리

## Monitoring and Observability

### 1. Basic Metrics

**기본 메트릭 (DB 기반 집계)**:
```python
# 워커는 DB에 카운터 저장, FastAPI가 /metrics에서 집계
def get_metrics_from_db():
    """DB에서 메트릭 집계하여 Prometheus 포맷으로 반환"""
    with get_db_session() as session:
        # 일일 수집/처리/발행 건수
        today = datetime.utcnow().date()
        
        collected = session.query(ProcessingLog).filter(
            ProcessingLog.service_name == 'collector',
            ProcessingLog.status == 'success',
            func.date(ProcessingLog.created_at) == today
        ).count()
        
        processed = session.query(ProcessingLog).filter(
            ProcessingLog.service_name == 'nlp_pipeline',
            ProcessingLog.status == 'success',
            func.date(ProcessingLog.created_at) == today
        ).count()
        
        published = session.query(ProcessingLog).filter(
            ProcessingLog.service_name == 'publisher',
            ProcessingLog.status == 'success',
            func.date(ProcessingLog.created_at) == today
        ).count()
        
        failures = session.query(ProcessingLog).filter(
            ProcessingLog.status == 'failed',
            func.date(ProcessingLog.created_at) == today
        ).count()
        
        return f"""# HELP reddit_posts_collected_total Total Reddit posts collected
# TYPE reddit_posts_collected_total counter
reddit_posts_collected_total {collected}

# HELP posts_processed_total Total posts processed
# TYPE posts_processed_total counter
posts_processed_total {processed}

# HELP posts_published_total Total posts published
# TYPE posts_published_total counter
posts_published_total {published}

# HELP processing_failures_total Total processing failures
# TYPE processing_failures_total counter
processing_failures_total {failures}
"""
```

### 2. Health Check

**헬스체크 엔드포인트**:
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": await check_database(),
            "redis": await check_redis(),
            "external_apis": await check_external_apis()
        }
    }
```

### 3. Slack Notifications

**알림 조건**:
- 실패율 > 5%
- 큐 대기 수 > 500
- 일일 API 호출 80% 도달
- 일일 토큰 예산 80% 도달

**Slack 알림 템플릿 통일**:
```python
def send_slack_alert(severity: str, service: str, message: str, metrics: dict = None):
    """통일된 Slack 알림 템플릿"""
    payload = {
        "text": f"🚨 [{severity}] {service} Alert",
        "attachments": [
            {
                "color": "danger" if severity == "HIGH" else "warning",
                "fields": [
                    {"title": "Service", "value": service, "short": True},
                    {"title": "Message", "value": message, "short": False}
                ]
            }
        ]
    }
    
    if metrics:
        metric_fields = [
            {"title": k, "value": str(v), "short": True} 
            for k, v in metrics.items()
        ]
        payload["attachments"][0]["fields"].extend(metric_fields)
    
    requests.post(SLACK_WEBHOOK_URL, json=payload)

def send_daily_report():
    """일일 리포트"""
    report = {
        "collected_posts": get_daily_collected_count(),
        "published_posts": get_daily_published_count(), 
        "token_usage": get_daily_token_usage(),
        "cost_estimate": calculate_daily_cost()
    }
    
    payload = {
        "text": "📊 Daily Reddit Publisher Report",
        "attachments": [
            {
                "color": "good",
                "fields": [
                    {"title": "Posts Collected", "value": str(report["collected_posts"]), "short": True},
                    {"title": "Posts Published", "value": str(report["published_posts"]), "short": True},
                    {"title": "Token Usage", "value": f"{report['token_usage']:,}", "short": True},
                    {"title": "Est. Cost", "value": f"${report['cost_estimate']:.2f}", "short": True}
                ]
            }
        ]
    }
    
    requests.post(SLACK_WEBHOOK_URL, json=payload)
```

### 4. Basic Logging

**로그 구조화**:
```python
import logging
import json

logger = logging.getLogger(__name__)

# 기본 로깅 (PII 마스킹)
def log_reddit_collection(post_id, subreddit, score):
    logger.info(json.dumps({
        "event": "reddit_post_collected",
        "post_id": post_id,
        "subreddit": subreddit,
        "score": score,
        "timestamp": datetime.utcnow().isoformat()
    }))

def log_api_error(service, error_message, retry_count):
    logger.error(json.dumps({
        "event": "api_error",
        "service": service,
        "error": mask_sensitive_data(error_message),
        "retry_count": retry_count,
        "timestamp": datetime.utcnow().isoformat()
    }))
```

## Security Architecture

### 1. 환경변수 기반 비밀 관리

**환경변수 구조**:
```bash
# Reddit API
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent
REDDIT_DAILY_CALLS_LIMIT=5000

# OpenAI API
OPENAI_API_KEY=your_openai_key
OPENAI_DAILY_TOKENS_LIMIT=100000

# Ghost CMS
GHOST_ADMIN_KEY=your_ghost_admin_key
GHOST_API_URL=https://your-blog.ghost.io

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/reddit_publisher
REDIS_URL=redis://localhost:6379

# Slack (통일된 알림 템플릿)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# 스케줄링
COLLECT_CRON=0 * * * *  # 시간당 1회 (운영 기본)
BACKUP_CRON=0 4 * * *   # 매일 새벽 4시

# 알림 임계치
QUEUE_ALERT_THRESHOLD=500
FAILURE_RATE_THRESHOLD=0.05
```

**비밀 정보 로딩**:
```python
import os
from functools import lru_cache

@lru_cache()
def get_settings():
    return {
        'reddit_client_id': os.getenv('REDDIT_CLIENT_ID'),
        'reddit_client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
        'openai_api_key': os.getenv('OPENAI_API_KEY'),
        'ghost_admin_key': os.getenv('GHOST_ADMIN_KEY'),
        'slack_webhook_url': os.getenv('SLACK_WEBHOOK_URL')
    }
```

### 2. 로그 마스킹 및 PII 보호

**민감 정보 마스킹**:
```python
import re

def mask_sensitive_data(text: str) -> str:
    """로그에서 민감 정보 마스킹"""
    # API 키 마스킹
    text = re.sub(r'(api[_-]?key["\s]*[:=]["\s]*)([a-zA-Z0-9-_]{10,})', r'\1****', text, flags=re.IGNORECASE)
    # 토큰 마스킹
    text = re.sub(r'(token["\s]*[:=]["\s]*)([a-zA-Z0-9-_]{10,})', r'\1****', text, flags=re.IGNORECASE)
    # 이메일 마스킹
    text = re.sub(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'****@\2', text)
    return text

def log_with_masking(message: str, **kwargs):
    """마스킹된 로그 출력"""
    masked_message = mask_sensitive_data(message)
    masked_kwargs = {k: mask_sensitive_data(str(v)) if isinstance(v, str) else v 
                    for k, v in kwargs.items()}
    logger.info(masked_message, **masked_kwargs)
```

**Ghost Admin API JWT 인증**:
```python
import jwt
import time

def generate_ghost_jwt(admin_key: str) -> str:
    """Ghost Admin Key로 JWT 생성"""
    # Admin Key 형식: key_id:secret
    key_id, secret = admin_key.split(':')
    
    iat = int(time.time())
    exp = iat + 300  # 5분 만료
    
    payload = {
        'iat': iat,
        'exp': exp,
        'aud': '/admin/'
    }
    
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
    return token

def get_ghost_headers(admin_key: str) -> dict:
    """Ghost API 요청 헤더 생성"""
    jwt_token = generate_ghost_jwt(admin_key)
    return {
        'Authorization': f'Ghost {jwt_token}',
        'Content-Type': 'application/json'
    }
```

### 3. Takedown 워크플로 (2단계)

**권리자 삭제 요청 처리**:
```python
def handle_takedown_request(reddit_post_id: str, reason: str):
    """즉시 비공개 → 72시간 내 삭제 (2단계)"""
    try:
        # 1단계: 즉시 비공개 처리
        post = get_post_by_reddit_id(reddit_post_id)
        if post and post.ghost_url:
            ghost_client.unpublish_post(post.ghost_id)
        
        # 상태를 takedown_pending으로 변경
        update_post_status(reddit_post_id, 'takedown_pending')
        
        # 감사 로그 기록 (1단계)
        audit_log = {
            "event": "takedown_request_received",
            "reddit_post_id": reddit_post_id,
            "reason": reason,
            "action": "unpublished_immediately",
            "processed_at": datetime.utcnow().isoformat(),
            "deletion_scheduled": (datetime.utcnow() + timedelta(hours=72)).isoformat()
        }
        logger.info(json.dumps(audit_log))
        
        # 2단계: 72시간 후 삭제 스케줄링
        schedule_deletion.apply_async(
            args=[reddit_post_id, reason],
            countdown=72 * 3600  # 72시간 후
        )
        
        return {"status": "unpublished", "message": "Content unpublished, deletion scheduled in 72h"}
    
    except Exception as e:
        logger.error(f"Takedown request failed: {mask_sensitive_data(str(e))}")
        raise

@celery_app.task
def schedule_deletion(reddit_post_id: str, reason: str):
    """72시간 후 실제 삭제"""
    try:
        delete_post(reddit_post_id)
        
        # 감사 로그 기록 (2단계)
        audit_log = {
            "event": "takedown_deletion_completed",
            "reddit_post_id": reddit_post_id,
            "reason": reason,
            "deleted_at": datetime.utcnow().isoformat(),
            "sla_met": True
        }
        logger.info(json.dumps(audit_log))
        
    except Exception as e:
        logger.error(f"Scheduled deletion failed: {mask_sensitive_data(str(e))}")
```

## Deployment Architecture

### 1. 단일 노드 Docker Compose 구성

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - REDDIT_CLIENT_ID=${REDDIT_CLIENT_ID}
      - REDDIT_CLIENT_SECRET=${REDDIT_CLIENT_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GHOST_ADMIN_KEY=${GHOST_ADMIN_KEY}
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
  
  worker-collector:
    build: .
    command: celery -A app.celery worker -Q collect -c 1
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - REDDIT_CLIENT_ID=${REDDIT_CLIENT_ID}
      - REDDIT_CLIENT_SECRET=${REDDIT_CLIENT_SECRET}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
  
  worker-nlp:
    build: .
    command: celery -A app.celery worker -Q process -c 1
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
  
  worker-publisher:
    build: .
    command: celery -A app.celery worker -Q publish -c 1
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - GHOST_ADMIN_KEY=${GHOST_ADMIN_KEY}
      - GHOST_API_URL=${GHOST_API_URL}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
  
  scheduler:
    build: .
    command: celery -A app.celery beat
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - COLLECT_CRON=${COLLECT_CRON:-0 * * * *}
      - BACKUP_CRON=${BACKUP_CRON:-0 4 * * *}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
  
  backup:
    image: postgres:15-alpine
    command: >
      sh -c "
        echo '${BACKUP_CRON:-0 4 * * *} /usr/local/bin/backup-database.sh' | crontab - &&
        crond -f
      "
    environment:
      - PGHOST=postgres
      - PGUSER=${DB_USER}
      - PGPASSWORD=${DB_PASSWORD}
      - PGDATABASE=reddit_publisher
    volumes:
      - ./scripts/backup-database.sh:/usr/local/bin/backup-database.sh:ro
      - postgres_backups:/backups
    depends_on:
      - postgres
    restart: unless-stopped
  
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=reddit_publisher
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "5432:5432"
    restart: unless-stopped
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  postgres_backups:
```

### 2. 백업 및 복구

**PostgreSQL 백업 스크립트**:
```bash
#!/bin/bash
# backup-database.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="reddit_publisher"

# pg_dump 백업 생성
pg_dump -h postgres -U ${DB_USER} -d ${DB_NAME} > ${BACKUP_DIR}/backup_${DATE}.sql

# 7일 이상 된 백업 삭제
find ${BACKUP_DIR} -name "backup_*.sql" -mtime +7 -delete

echo "Backup completed: backup_${DATE}.sql"
```

**복구 테스트 스크립트**:
```bash
#!/bin/bash
# restore-test.sh

BACKUP_FILE=$1
TEST_DB="reddit_publisher_test"

# 테스트 DB 생성
createdb -h postgres -U ${DB_USER} ${TEST_DB}

# 백업 복구
psql -h postgres -U ${DB_USER} -d ${TEST_DB} < ${BACKUP_FILE}

# 데이터 검증
psql -h postgres -U ${DB_USER} -d ${TEST_DB} -c "SELECT COUNT(*) FROM posts;"

# 테스트 DB 삭제
dropdb -h postgres -U ${DB_USER} ${TEST_DB}

echo "Restore test completed successfully"
```

### 3. CI/CD 파이프라인 (GitHub Actions)

```yaml
name: Reddit Publisher CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest --cov=app --cov-report=xml --cov-fail-under=70
    
    - name: Weekly backup restore test
      if: github.event.schedule == '0 2 * * 1'  # 매주 월요일 02:00
      run: |
        # 최신 백업으로 복구 테스트
        ./scripts/restore-test.sh /backups/$(ls -t /backups/backup_*.sql | head -1)
    
    - name: Build Docker image
      run: |
        docker build -t reddit-publisher:${{ github.sha }} .
    
    - name: Run Postman smoke tests
      run: |
        docker-compose -f docker-compose.test.yml up -d
        sleep 30
        newman run tests/postman/smoke-tests.json --environment tests/postman/test-env.json
        docker-compose -f docker-compose.test.yml down
  
  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Manual approval required
      uses: trstringer/manual-approval@v1
      with:
        secret: ${{ github.TOKEN }}
        approvers: maintainer1,maintainer2
        minimum-approvals: 1
        issue-title: "Deploy Reddit Publisher to Production"
    
    - name: Deploy to production
      run: |
        # 수동 배포 스크립트 실행
        ./scripts/deploy.sh ${{ github.sha }}
    
    - name: Health check
      run: |
        sleep 30
        curl -f ${{ secrets.API_BASE_URL }}/health || exit 1
```

이 설계는 MVP 요구사항에 맞춰 단순화되었으며, 비용과 운영 복잡도를 최소화하면서도 안정적인 운영이 가능한 아키텍처를 제공합니다.