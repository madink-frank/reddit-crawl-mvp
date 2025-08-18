# Heroku 배포 가이드

## 1. Heroku 설정
```bash
# Heroku CLI 설치 후
heroku login
heroku create reddit-ghost-publisher

# PostgreSQL 애드온
heroku addons:create heroku-postgresql:mini

# Redis 애드온
heroku addons:create heroku-redis:mini
```

## 2. Procfile 생성
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: celery -A app.celery_app worker --loglevel=info
beat: celery -A app.celery_app beat --loglevel=info
```

## 3. 환경 변수 설정
```bash
heroku config:set REDDIT_CLIENT_ID=your_client_id
heroku config:set REDDIT_CLIENT_SECRET=your_client_secret
heroku config:set OPENAI_API_KEY=your_openai_key
heroku config:set GHOST_ADMIN_KEY=your_ghost_key
heroku config:set GHOST_API_URL=https://american-trends.ghost.io
```

## 4. 배포
```bash
git push heroku main
heroku ps:scale web=1 worker=1 beat=1
```