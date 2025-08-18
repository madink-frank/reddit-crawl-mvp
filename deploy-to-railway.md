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

## 3. 환경 변수 설정
```bash
# Railway 대시보드에서 설정
railway variables set REDDIT_CLIENT_ID=your_client_id
railway variables set REDDIT_CLIENT_SECRET=your_client_secret
railway variables set OPENAI_API_KEY=your_openai_key
railway variables set GHOST_ADMIN_KEY=your_ghost_key
railway variables set GHOST_API_URL=https://american-trends.ghost.io
```

## 4. 배포
```bash
railway up
```

## 장점
- 자동 HTTPS
- 자동 도메인 (예: reddit-publisher-production.up.railway.app)
- PostgreSQL, Redis 자동 프로비저닝
- 무료 티어 제공