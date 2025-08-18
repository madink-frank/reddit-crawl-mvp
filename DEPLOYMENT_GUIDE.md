# Reddit Ghost Publisher 배포 가이드

## 🚀 배포 준비 완료!

모든 개발 작업이 완료되었으며, 프로덕션 배포를 위한 모든 구성 요소가 준비되었습니다.

## 📋 배포 전 체크리스트

### ✅ 완료된 작업
- [x] MVP 시스템 개발 완료 (Task 1-17)
- [x] 시스템 검증 테스트 완료 (Task 18.1-18.4)
- [x] Docker 컨테이너화 구성 완료
- [x] 프로덕션 환경 설정 파일 생성
- [x] 배포 스크립트 준비
- [x] 백업 및 복구 시스템 구현
- [x] 모니터링 및 알림 시스템 구현

### 🔧 배포 전 필요한 작업

1. **Docker 설치**
   ```bash
   # macOS (Homebrew)
   brew install --cask docker
   
   # 또는 Docker Desktop 다운로드
   # https://www.docker.com/products/docker-desktop/
   ```

2. **환경 변수 설정**
   - `.env.production` 파일의 실제 API 키 입력 필요:
     - `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`
     - `OPENAI_API_KEY`
     - `GHOST_ADMIN_KEY`, `GHOST_API_URL`
     - `SLACK_WEBHOOK_URL`

## 🚀 배포 실행 방법

### 1단계: Docker 이미지 빌드
```bash
# 프로젝트 루트에서 실행
docker build -t reddit-publisher:latest .
```

### 2단계: 환경 변수 설정
```bash
# .env.production 파일 편집
nano .env.production

# 필수 변경 항목:
# - REDDIT_CLIENT_ID=실제_클라이언트_ID
# - REDDIT_CLIENT_SECRET=실제_클라이언트_시크릿
# - OPENAI_API_KEY=실제_OpenAI_키
# - GHOST_ADMIN_KEY=실제_Ghost_관리자_키
# - GHOST_API_URL=실제_Ghost_사이트_URL
# - SLACK_WEBHOOK_URL=실제_Slack_웹훅_URL
```

### 3단계: 배포 실행
```bash
# 자동 배포 스크립트 실행
./scripts/deploy.sh reddit-publisher:latest production

# 또는 수동 배포
docker-compose -f docker-compose.prod.yml up -d
```

### 4단계: 배포 확인
```bash
# 서비스 상태 확인
docker-compose -f docker-compose.prod.yml ps

# 헬스체크
curl http://localhost:8000/health

# 메트릭 확인
curl http://localhost:8000/metrics

# 로그 확인
docker-compose -f docker-compose.prod.yml logs -f
```

## 📊 시스템 구성

### 서비스 구성
- **API 서버**: FastAPI 웹 애플리케이션 (포트 8000)
- **Collector Worker**: Reddit 수집 전용 워커
- **NLP Worker**: AI 요약/태깅 전용 워커  
- **Publisher Worker**: Ghost 발행 전용 워커
- **Scheduler**: Celery Beat 스케줄러
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Backup**: 자동 백업 시스템

### 데이터 플로우
```
Reddit API → Collector → NLP Processing → Ghost Publishing
     ↓           ↓            ↓              ↓
   Queue      Database    AI Analysis    Published Post
```

## 🔍 모니터링 및 관리

### 헬스체크 엔드포인트
- `GET /health` - 시스템 전체 상태
- `GET /metrics` - Prometheus 메트릭
- `GET /api/v1/status/queues` - 큐 상태
- `GET /api/v1/status/workers` - 워커 상태

### 수동 트리거 엔드포인트
- `POST /api/v1/collect/trigger` - 수집 트리거
- `POST /api/v1/process/trigger` - 처리 트리거
- `POST /api/v1/publish/trigger` - 발행 트리거

### Slack 알림
- API/토큰 예산 80% 도달 시
- 실패율 5% 초과 시
- 큐 대기 수 500 초과 시
- 일일 처리 현황 리포트

## 🛠 운영 관리

### 로그 확인
```bash
# 전체 로그
docker-compose -f docker-compose.prod.yml logs -f

# 특정 서비스 로그
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f worker-collector
```

### 스케일링
```bash
# 워커 수 증가
docker-compose -f docker-compose.prod.yml up -d --scale worker-collector=2
docker-compose -f docker-compose.prod.yml up -d --scale worker-nlp=2
```

### 백업 관리
```bash
# 수동 백업 실행
./scripts/backup-database.sh

# 백업 복구
./scripts/restore-database.sh /backups/backup_20240811_040000.sql
```

## 🔧 트러블슈팅

### 일반적인 문제

1. **서비스가 시작되지 않는 경우**
   ```bash
   # 환경 변수 확인
   docker-compose -f docker-compose.prod.yml config
   
   # 개별 서비스 로그 확인
   docker-compose -f docker-compose.prod.yml logs api
   ```

2. **데이터베이스 연결 오류**
   ```bash
   # PostgreSQL 상태 확인
   docker-compose -f docker-compose.prod.yml exec postgres pg_isready
   
   # 데이터베이스 접속 테스트
   docker-compose -f docker-compose.prod.yml exec postgres psql -U reddit_publisher -d reddit_publisher
   ```

3. **Redis 연결 오류**
   ```bash
   # Redis 상태 확인
   docker-compose -f docker-compose.prod.yml exec redis redis-cli ping
   ```

4. **외부 API 연결 오류**
   - Reddit API 키 및 권한 확인
   - OpenAI API 키 및 크레딧 확인
   - Ghost CMS Admin Key 및 URL 확인

### 성능 최적화

1. **큐 적체 해결**
   - 워커 수 증가
   - 배치 크기 조정
   - 처리 간격 조정

2. **메모리 사용량 최적화**
   - Docker 메모리 제한 설정
   - Redis 메모리 정책 조정

## 📈 성능 지표

### 목표 성능
- **API 응답 시간**: p95 ≤ 300ms
- **E2E 처리 시간**: ≤ 5분/포스트
- **처리량**: 100 포스트/시간
- **가용성**: 99.9%
- **실패율**: < 5%

### 모니터링 대시보드
- Prometheus 메트릭 수집
- Grafana 대시보드 (선택사항)
- Slack 알림 시스템

## 🔒 보안 고려사항

### 환경 변수 보안
- API 키는 환경 변수로만 관리
- 프로덕션 환경에서 `.env` 파일 권한 제한
- 로그에서 민감 정보 마스킹

### 네트워크 보안
- 데이터베이스/Redis는 localhost만 바인딩
- 필요시 방화벽 규칙 설정
- HTTPS 사용 권장

## 📞 지원 및 문의

### 문서 참조
- [시스템 요구사항](requirements.md)
- [시스템 설계](design.md)
- [API 문서](docs/api.md)
- [운영 매뉴얼](docs/operations.md)

### 로그 및 디버깅
- 모든 로그는 JSON 형식으로 출력
- PII 정보는 자동 마스킹
- 에러 추적 및 재시도 로직 내장

---

## 🎉 배포 완료 후 확인사항

1. ✅ 모든 서비스가 정상 실행 중
2. ✅ 헬스체크 통과
3. ✅ 첫 번째 수집 작업 성공
4. ✅ AI 처리 및 Ghost 발행 성공
5. ✅ Slack 알림 정상 작동
6. ✅ 백업 시스템 정상 작동

**축하합니다! Reddit Ghost Publisher MVP가 성공적으로 배포되었습니다! 🚀**