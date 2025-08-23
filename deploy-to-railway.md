# Railway 배포 가이드

## 1. Railway 설정
```bash
# Railway CLI 설치
npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 생성
railway init
```

## 2. railway.json 설정
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health"
  }
}
```

## 3. PostgreSQL 데이터베이스 추가
```bash
# Railway 대시보드에서 PostgreSQL 서비스 추가
# 또는 CLI로 추가
railway add postgresql
```

## 4. 환경 변수 설정
```bash
# Reddit API 설정
railway variables set REDDIT_CLIENT_ID=your_client_id
railway variables set REDDIT_CLIENT_SECRET=your_client_secret
railway variables set REDDIT_USER_AGENT="RedditGhostPublisher/1.0"

# OpenAI API 설정
railway variables set OPENAI_API_KEY=your_openai_key

# Ghost CMS 설정
railway variables set GHOST_ADMIN_KEY=your_ghost_key
railway variables set GHOST_API_URL=https://american-trends.ghost.io

# Slack 알림 설정 (선택사항)
railway variables set SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# 기타 설정
railway variables set ENVIRONMENT=production
railway variables set DEBUG=false
railway variables set TZ=UTC
```

## 5. 데이터베이스 초기화
```bash
# 배포 후 데이터베이스 스키마 생성
railway run python scripts/init_railway_db.py

# 스키마 검증
railway run python scripts/init_railway_db.py --verify
```

## 6. 배포
```bash
# 첫 배포
railway up

# 이후 배포
git push origin main  # Railway가 자동으로 배포
```

## 7. 배포 후 확인
```bash
# 헬스체크
curl https://your-app.up.railway.app/health

# 통계 확인
curl https://your-app.up.railway.app/api/stats

# 로그 확인
railway logs
```

## Railway 장점
- 자동 HTTPS
- 자동 도메인 (예: reddit-publisher-production.up.railway.app)
- PostgreSQL, Redis 자동 프로비저닝
- 무료 티어 제공 ($5/월 크레딧)
- 자동 배포 (Git 연동)
- 환경 변수 관리
- 로그 모니터링

## 비용 예상
- 무료 티어: $5/월 크레딧
- PostgreSQL: ~$1-2/월
- 앱 인스턴스: ~$2-3/월
- 총 예상 비용: $3-5/월 (무료 크레딧 내)

## 트러블슈팅

### 데이터베이스 연결 오류
```bash
# 환경 변수 확인
railway variables

# 데이터베이스 상태 확인
railway status

# 로그 확인
railway logs --tail
```

### 메모리 부족
```bash
# 메모리 사용량 확인
railway metrics

# 필요시 플랜 업그레이드
```

### 배포 실패
```bash
# 빌드 로그 확인
railway logs --deployment

# 환경 변수 재설정
railway variables set KEY=value
```