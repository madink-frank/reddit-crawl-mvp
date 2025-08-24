# Implementation Plan

- [x] 1. MVP 프로젝트 구조 및 기본 설정 구성
  - 단일 노드 Docker Compose 구조 생성 (app/, workers/, tests/ 통합)
  - Python 의존성 관리 (requirements.txt, BERTopic 제거)
  - 환경변수 기반 설정 파일 생성 (config.py, .env.example with budget limits)
  - 단일 Dockerfile 및 docker-compose.yml 구성
  - _Requirements: 4.1, 6.1, 8.1_

- [ ] 2. MVP 데이터베이스 스키마 및 모델 구현
  - [x] 2.1 PostgreSQL 15 스키마 정의 및 마이그레이션 스크립트 작성
    - MVP 스키마 구현 (id uuid, reddit_post_id unique, takedown_status, ghost_post_id, ghost_slug 추가)
    - 인덱스 및 제약조건 포함 (idx_posts_created_ts, idx_posts_subreddit, reddit_post_id UNIQUE, ghost_post_id UNIQUE NULLABLE)
    - updated_at 자동 갱신 트리거 생성
    - 개발/운영 모두 PostgreSQL 사용 (SQLite 제거)
    - _Requirements: 5.1, 5.2_

  - [x] 2.2 동기 SQLAlchemy ORM 모델 구현
    - Post, MediaFile, ProcessingLog, TokenUsage 모델 클래스 작성 (동기 I/O)
    - takedown_status 필드 및 관계 설정
    - 단위 테스트 작성 (커버리지 70% 목표)
    - _Requirements: 5.1, 5.3_

- [x] 3. 기본 인프라 서비스 구현
  - [x] 3.1 Redis 연결 및 Celery 설정 구현 (단순화)
    - Redis 연결 풀 설정
    - Celery task_routes 기반 큐 정의 (AMQP 속성 제거)
    - 시간당 1회 수집 스케줄링 (COLLECT_CRON 환경변수화)
    - _Requirements: 4.1, 4.2_

  - [x] 3.2 환경변수 기반 비밀 관리 구현
    - 환경변수 로딩 및 캐싱 메커니즘
    - PII 마스킹 로직 구현
    - 예산 제한 설정 (REDDIT_DAILY_CALLS_LIMIT, OPENAI_DAILY_TOKENS_LIMIT)
    - 모델 단가 맵 고정 (COST_PER_1K_TOKENS={'gpt-4o-mini':x.xx, 'gpt-4o':y.yy})
    - 일일 토큰 사용량 UTC 00:00 자동 리셋 (Redis 키 롤링: usage:YYYYMMDD)
    - 시간대 통일 (TZ=UTC 환경변수 명시)
    - _Requirements: 6.1_

- [x] 4. FastAPI 게이트웨이 구현 (단순화)
  - [x] 4.1 기본 FastAPI 애플리케이션 및 라우터 구성
    - FastAPI 앱 초기화 (비동기 I/O, 워커는 동기)
    - 헬스체크 엔드포인트 구현 (/health with dependency checks)
    - 기본 로깅 설정 (PII 마스킹 적용)
    - _Requirements: 7.1, 6.2_

  - [x] 4.2 기본 보안 설정 구현
    - 환경변수 기반 인증 (JWT/Vault 제거)
    - CORS 설정 및 기본 보안 헤더
    - 입력 검증 (Pydantic 모델)
    - _Requirements: 6.2, 6.5_

  - [x] 4.3 API 엔드포인트 구현
    - 수동 트리거 엔드포인트 (collect/process/publish) - 멱등 체크 후 enqueue
    - 큐/워커 상태 모니터링 구현 세부:
      * /status/queues: active/reserved/scheduled/queued (celery.inspect + Redis list 길이)
      * /status/workers: 워커명, 하트비트 시각, 소비 큐 반환
    - DB 기반 메트릭 집계 엔드포인트 (/metrics):
      * processing_logs/token_usage에서 최근 5분 슬라이딩 윈도우 집계
      * Prometheus 텍스트 포맷으로 노출 (content-type: text/plain 포함)
    - Takedown 요청 엔드포인트 (/api/v1/takedown/{reddit_post_id})
    - Celery chain(collect→process→publish) 기본 경로 구현
    - _Requirements: 7.1_

- [x] 5. Reddit Collector 서비스 구현 (MVP)
  - [x] 5.1 Reddit API 클라이언트 구현 (레이트리밋 단일화)
    - PRAW 설정 및 OAuth 인증 (환경변수 기반)
    - 레이트리밋 전략: 토큰 버킷(분당 60) + 429/Retry-After 준수 + 작업 큐 백오프(2^n)
    - 헤더 값이 없을 때도 동작하도록 구현 (헤더는 보조 지표로만 사용)
    - 재시도 상한·간격 상수화 (RETRY_MAX=3, BACKOFF_BASE=2, BACKOFF_MIN/MAX)
    - _Requirements: 1.2, 1.3_

  - [x] 5.2 콘텐츠 필터링 및 검증 로직 구현
    - NSFW 콘텐츠 필터링 (Reddit over_18 플래그 기준 고정)
    - reddit_post_id 기반 중복 방지 (UNIQUE 제약)
    - 기본 품질 검증 (제목, 내용 존재)
    - _Requirements: 1.5, 1.6_

  - [x] 5.3 일일 API 호출 예산 관리 구현
    - 일일 호출 수 추적 (Redis 카운터)
    - 80% 도달 시 Slack 알림
    - 100% 도달 시 수집 중단
    - _Requirements: 1.7, 1.8_

  - [x] 5.4 Celery 수집 작업 구현 (동기 I/O)
    - collect_reddit_posts 태스크 구현 (동기)
    - 에러 처리 및 재시도 로직 (최대 3회)
    - 처리 로그 기록 (DB 기반)
    - _Requirements: 1.1, 4.2_

- [x] 6. NLP Pipeline 서비스 구현 (LLM 전용)
  - [x] 6.1 OpenAI GPT-4o-mini/GPT-4o 클라이언트 구현
    - GPT-4o-mini (primary) + GPT-4o (fallback) 구조
    - 한국어 요약 프롬프트 템플릿
    - 내부 코스트 맵 기반 토큰 사용량 추적
    - _Requirements: 2.1, 2.2, 2.9_

  - [x] 6.2 LLM 기반 태그 추출 구현 (BERTopic 제거)
    - LLM 프롬프트로 3-5개 태그 추출
    - 일관된 표기 규칙 적용 (소문자/한글)
    - 검색 최적화된 키워드 생성
    - _Requirements: 2.3_

  - [x] 6.3 JSON 스키마 기반 분석 구현
    - pain_points/product_ideas JSON 스키마 정의
    - meta.version 필드 저장
    - 스키마 검증 및 파싱 로직
    - _Requirements: 2.4, 2.5_

  - [x] 6.4 토큰 예산 관리 및 Celery 작업 구현
    - 일일 토큰 예산 추적 (80%/100% 알림)
    - NLP 단계에서 content_hash=sha256(title+body+media_urls) 생성
    - process_content_with_ai 태스크 구현 (동기)
    - 최대 3회 지수 백오프 재시도 (상수화된 설정 사용)
    - _Requirements: 2.7, 2.8_

- [x] 7. Ghost Publisher 서비스 구현 (Article 템플릿 전용)
  - [x] 7.1 Ghost CMS API 클라이언트 구현 (JWT 인증 명확화)
    - Ghost Admin API 클라이언트 설정
    - Admin Key 기반 JWT 토큰 생성 구현 세부:
      * GHOST_ADMIN_KEY="key_id:secret" 파싱
      * HS256 JWT 생성 (iat=now, exp=now+5m)
      * Authorization: Ghost <jwt> 헤더 사용
    - API 호출 재시도 및 에러 처리 (최대 3회 지수 백오프: 2s, 4s, 8s)
    - _Requirements: 3.2_

  - [x] 7.2 Article 템플릿 시스템 구현 (단일 템플릿)
    - Article 템플릿 1종류만 구현
    - Markdown to HTML 변환 로직
    - 고정 출처 고지 자동 삽입 (Source/Media/Takedown 문구)
    - _Requirements: 3.1, 3.6, 10.1, 10.2_

  - [x] 7.3 이미지 처리 및 폴백 구현
    - Reddit 미디어 로컬 다운로드 후 Ghost Images API 업로드
    - 기본 OG 이미지 설정 (DEFAULT_OG_IMAGE_URL env 추가)
    - 미디어 없는 게시글 기본 OG 이미지 자동 삽입 (발행 전 검증)
    - 업로드 실패 시 기본 이미지로 대체
    - _Requirements: 3.4, 10.5_

  - [x] 7.4 태그 매핑 및 발행 멱등성 구현
    - LLM 태그를 Ghost tags로 매핑
    - 발행 멱등성 및 조건부 업데이트:
      * 발행 전 기존 content_hash 비교
      * 동일하면 Skip, 다르면 Update (Ghost patch)
    - reddit_post_id 기반 중복 발행 방지
    - 3-5개 태그 제한 및 표기 규칙 적용
    - _Requirements: 3.5, 3.8, 10.3_

  - [x] 7.5 Celery 발행 작업 구현 (동기 I/O)
    - publish_to_ghost 태스크 구현 (동기)
    - ghost_post_id/ghost_slug 저장 (Takedown 2단계 연동)
    - 발행 상태 추적 및 업데이트
    - 실패 시 재시도 로직 (상수화된 지수 백오프)
    - _Requirements: 3.1, 3.7_

- [x] 8. 기본 모니터링 및 관측성 구현
  - [x] 8.1 DB 기반 메트릭 수집 구현
    - 처리 건수/실패 건수 계수형 지표 (DB 집계)
    - /metrics 엔드포인트에서 Prometheus 포맷 반환 (content-type: text/plain)
    - 멀티프로세스 이슈 해결 (워커→DB→API 집계)
    - 에러 분류 지표화 (외부 API 오류를 429/timeout/5xx/logic_error로 분류 카운트)
    - _Requirements: 7.1, 7.2_

  - [x] 8.2 기본 로깅 시스템 구현 (PII 마스킹)
    - 기본 JSON 로깅 설정
    - PII 마스킹 로직 (API 키, 토큰, 이메일)
    - 서비스별 로그 레벨 설정
    - _Requirements: 6.2, 7.4_

  - [x] 8.3 헬스체크 및 Slack 알림 구현
    - 의존성 상태 확인 (DB, Redis, 외부 API)
    - 알림 임계치 시간 창 명시:
      * 실패율 5% 초과 (최근 5분 이동 구간 기준)
      * 큐 대기 수 500 초과 (즉시 값)
    - 통일된 Slack 알림 템플릿 (Severity, Service, Metrics, 시간 구간 포함)
    - _Requirements: 7.3_

- [x] 9. 에러 처리 및 복원력 구현 (단순화)
  - [x] 9.1 외부 서비스 에러 처리 구현
    - Reddit API 동적 레이트리밋 및 백오프
    - OpenAI GPT-4o-mini → GPT-4o 폴백 로직
    - Ghost CMS 재시도 메커니즘 (최대 3회)
    - _Requirements: 1.3, 2.2, 3.7_

  - [x] 9.2 데이터 일관성 및 트랜잭션 관리 구현
    - 동기 SQLAlchemy 트랜잭션 래퍼
    - 상태 변경 추적 및 롤백 로직
    - 처리 로그 기록 (성공/실패/재시도)
    - _Requirements: 5.3, 9.4_

  - [x] 9.3 Takedown 워크플로 구현 (2단계 DB 필드 연동)
    - 1단계: unpublish(ghost_post_id) 후 takedown_status='pending'
    - 72시간 후 삭제 스케줄링 (2단계)
    - 72h ETA 태스크: 삭제 실행, takedown_status='deleted'
    - 감사 로그 기록 및 SLA 추적
    - _Requirements: 6.3, 6.4_

- [x] 10. 보안 구현 (단순화)
  - [x] 10.1 환경변수 기반 인증 구현
    - 환경변수 기반 비밀 관리 (Vault 제거)
    - Ghost Admin Key JWT 생성 로직
    - API 키 로딩 및 캐싱
    - _Requirements: 6.1, 6.2_

  - [x] 10.2 입력 검증 및 로그 마스킹 구현
    - Pydantic 모델 기반 입력 검증
    - PII 마스킹 로직 (API 키, 토큰, 이메일)
    - Reddit API 정책 준수 (크롤링 금지)
    - _Requirements: 6.2, 6.5_

- [x] 11. 테스트 구현 (MVP 목표)
  - [x] 11.1 단위 테스트 작성
    - 각 서비스별 핵심 로직 테스트
    - Mock 객체를 사용한 외부 의존성 테스트
    - 70% 이상 코드 커버리지 달성 (MVP 목표)
    - _Requirements: 8.1_

  - [x] 11.2 Postman 스모크 테스트 작성
    - 수집→요약→발행 주요 엔드포인트 테스트
    - 중복 발행 방지 테스트 (동일 reddit_post_id 재시도)
    - 스모크 컬렉션 파일 경로와 환경파일 키 목록 명시
    - 100% 스모크 테스트 통과 목표
    - _Requirements: 8.4_

  - [x] 11.3 k6 성능 테스트 구현
    - k6를 사용한 성능 테스트 시나리오
    - p95 < 300ms, E2E < 5분, 시간당 100개 글 처리
    - 성능 메트릭 수집 및 분석
    - _Requirements: 9.1, 9.2, 9.3_

- [x] 12. 배포 및 인프라 구현 (단순화)
  - [x] 12.1 단일 Dockerfile 컨테이너화 구현
    - 단일 Dockerfile 작성 (멀티스테이지 최적화)
    - 환경변수 기반 설정
    - 보안 스캔 구체화 (Docker 이미지를 Trivy로 스캔, High↑ 발견 시 CI 실패)
    - _Requirements: 8.2_

  - [x] 12.2 단일 노드 Docker Compose 구현
    - 단일 노드용 docker-compose.yml 작성
    - 백업 실행 주체 고정: backup 전용 컨테이너+크론만 사용
    - 환경변수 및 볼륨 설정 (TZ=UTC 명시)
    - _Requirements: 4.1, 5.4_

  - [x] 12.3 수동 배포 스크립트 구현 (Terraform 제거)
    - 수동 배포 스크립트 작성
    - 백업 및 복구 스크립트
    - 헬스체크 및 롤백 메커니즘
    - _Requirements: 8.2, 5.5_

- [x] 13. CI/CD 파이프라인 구현 (단순화)
  - [x] 13.1 GitHub Actions 워크플로우 구현
    - 테스트 자동화 파이프라인 (커버리지 70%)
    - Docker 이미지 빌드 및 태그
    - 주간 백업 복구 테스트 자동화
    - _Requirements: 8.1, 8.2, 5.5_

  - [x] 13.2 수동 승인 배포 시스템 구현
    - 수동 승인 후 배포 진행
    - 배포 후 헬스체크
    - 배포 후 스모크 자동 실행과 롤백 조건 (스모크 실패 시) 명시
    - _Requirements: 8.2, 8.4_

- [x] 14. 기본 알림 시스템 구현 (Grafana/Alertmanager 제거)
  - [x] 14.1 Slack 알림 시스템 구현
    - 통일된 Slack 알림 템플릿 (Severity, Service, Metrics)
    - 실패율 5% 초과 알림
    - 큐 대기 수 500 초과 알림
    - API/토큰 예산 80% 도달 알림
    - _Requirements: 7.3, 7.4_

  - [x] 14.2 일일 리포트 시스템 구현
    - 수집/발행/토큰 사용량 일일 집계
    - 비용 추정 계산
    - Slack 일일 리포트 전송
    - _Requirements: 7.4_

- [x] 15. 백업 및 재해 복구 구현 (단순화)
  - [x] 15.1 PostgreSQL 백업 시스템 구현
    - pg_dump 기반 백업 스크립트
    - 매일 새벽 4시 자동 백업 (BACKUP_CRON)
    - 최근 7일 백업 보존
    - _Requirements: 5.4, 5.5_

  - [x] 15.2 백업 복구 테스트 구현
    - 복구 테스트 스크립트 작성
    - 주간 복구 테스트: 복구 후 최소 레코드 수/인덱스 존재 검사를 스크립트에 포함
    - GitHub Actions 주간 자동화 (Actions는 주간 복구 테스트만)
    - _Requirements: 5.5_

- [x] 16. 성능 최적화 구현 (자동 스케일링 제거)
  - [x] 16.1 수동 스케일링 알림 구현
    - 큐 적체 500 초과 시 Slack 알림
    - 수동 워커 수 증설 가이드
    - 리소스 사용률 모니터링
    - _Requirements: 4.4, 9.1_

  - [x] 16.2 기본 캐싱 및 성능 최적화 구현
    - Redis 캐싱 범위 제한 (조회용 상태 페이지에만 한정, 수집은 캐시 미사용)
    - 데이터베이스 인덱스 최적화
    - API 응답 시간 모니터링
    - _Requirements: 9.1, 9.2_

- [x] 17. 문서화 및 운영 가이드 작성
  - [x] 17.1 API 문서 및 개발자 가이드 작성
    - 기본 API 문서 생성 (헬스체크, 트리거, 상태)
    - 환경변수 설정 가이드 (.env.example)
    - 개발 환경 설정 가이드
    - _Requirements: 8.1_

  - [x] 17.2 운영 매뉴얼 및 트러블슈팅 가이드 작성
    - 수동 배포 및 운영 절차 문서
    - 백업/복구 절차 가이드
    - Slack 알림 대응 절차
    - _Requirements: 5.5, 7.4_

- [x] 18. MVP 시스템 검증 테스트 실행
  - [x] 18.1 사전 준비 및 환경 구성
    - 스테이징 환경 구성 (Docker Compose)
    - 테스트 변수 설정 (SUBREDDITS, BATCH_SIZE, 예산 제한)
    - Slack 테스트 채널 및 시드 데이터 준비
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 18.2 기능별 검증 테스트 실행
    - Reddit 수집 테스트 (상위 N 수집, API 제한, NSFW 필터, 중복 방지, 예산 알림)
    - AI 요약/태깅 테스트 (폴백, 태그 제한, JSON 스키마, 재시도, 예산 게이트)
    - Ghost 발행 테스트 (템플릿, 인증, 이미지 업로드, 태그 매핑, 출처 고지, 멱등성)
    - 아키텍처/큐 테스트 (라우팅, 수동 스케일 알림)
    - _Requirements: 11.5-11.22_

  - [x] 18.3 시스템 품질 검증 테스트 실행
    - 데이터베이스 테스트 (스키마/제약, 백업/복구)
    - 보안/컴플라이언스 테스트 (비밀 관리, Takedown 워크플로, API 정책)
    - 관측성/알림 테스트 (/health, /metrics, 실패율/큐 알림, 일일 리포트)
    - CI/배포 테스트 (커버리지 70%, 이미지 빌드, Postman 스모크)
    - _Requirements: 11.23-11.33_

  - [x] 18.4 성능 및 UX 검증 테스트 실행
    - 성능/지연 테스트 (API p95 목표, E2E 처리 시간, 처리량 안정성)
    - 템플릿/UX 테스트 (Article 템플릿 일관성, 태그 제한/표기 규칙, 이미지 폴백)
    - 최종 합격 기준 검증 (기능, 품질, 성능, 운영 모든 조건)
    - _Requirements: 11.34-11.40_

- [x] 19. 실제 데이터 파이프라인 구현 (가짜 데이터 제거)
  - [x] 19.1 CORS 설정 및 Ghost 대시보드 연동 수정
    - Vercel API에 CORS 헤더 추가 (american-trends.ghost.io 도메인 허용)
    - Ghost 호스팅 대시보드에서 API 호출 성공하도록 수정
    - 네트워크 에러 처리 및 재시도 로직 강화
    - _Requirements: 새로운 요구사항 - Ghost 대시보드 연동_

  - [x] 19.2 실제 Reddit API 연동 구현
    - 가짜 Reddit 데이터 제거하고 실제 PRAW 라이브러리 연동
    - Reddit OAuth 인증 설정 (환경변수 기반)
    - 실제 서브레딧에서 인기 게시글 수집 (programming, technology, webdev)
    - Railway PostgreSQL에 실제 데이터 저장
    - _Requirements: 1.1, 1.2, 1.3 - 실제 Reddit 수집_

  - [x] 19.3 실제 OpenAI API 연동 구현
    - 가짜 AI 처리 제거하고 실제 OpenAI GPT-4o-mini 연동
    - Reddit 게시글을 한국어로 요약하는 프롬프트 구현
    - 태그 추출 및 메타데이터 생성
    - 토큰 사용량 추적 및 비용 관리
    - _Requirements: 2.1, 2.2, 2.3 - 실제 AI 처리_

  - [x] 19.4 실제 Ghost CMS 발행 구현
    - 가짜 발행 로직 제거하고 실제 Ghost Admin API 연동
    - JWT 토큰 생성 및 인증 구현
    - AI 처리된 콘텐츠를 Ghost 블로그 글로 발행
    - 이미지 업로드 및 메타데이터 설정
    - _Requirements: 3.1, 3.2, 3.4 - 실제 Ghost 발행_

  - [x] 19.5 실제 데이터베이스 연동 및 상태 관리
    - Railway PostgreSQL에 실제 스키마 생성
    - 게시글 상태 추적 (수집됨 → AI처리됨 → 발행됨)
    - 실제 통계 데이터 계산 및 대시보드 표시
    - 에러 로깅 및 재시도 메커니즘
    - _Requirements: 5.1, 5.2, 5.3 - 실제 데이터 관리_

- [x] 20. 전체 파이프라인 통합 테스트
  - [x] 20.1 End-to-End 파이프라인 테스트
    - Reddit 수집 → AI 처리 → Ghost 발행 전체 플로우 테스트
    - Ghost 대시보드에서 실시간 진행 상황 모니터링
    - 실제 블로그 글이 american-trends.ghost.io에 발행되는지 확인
    - 에러 처리 및 복구 메커니즘 테스트
    - _Requirements: 전체 시스템 통합, 12.7_

  - [x] 20.2 프로덕션 환경 최적화
    - API 응답 속도 최적화
    - 대시보드 실시간 업데이트 개선
    - 에러 메시지 및 사용자 경험 개선
    - 로깅 및 모니터링 강화
    - _Requirements: 사용자 경험 최적화, 12.8_

- [ ] 21. Vercel 대시보드 완전 구현 (Ghost 대시보드와 동일 기능)
  - [ ] 21.1 Vercel 라우팅 수정 및 대시보드 페이지 구현
    - index.html을 API 문서에서 기능적 대시보드로 완전 교체
    - Ghost 대시보드와 동일한 UI/UX 구현 (버튼, 상태 표시, 로그 등)
    - API 엔드포인트 연결 및 실시간 데이터 업데이트
    - CORS 설정 확인 및 API 호출 성공 보장
    - _Requirements: 새로운 요구사항 - Vercel 대시보드 완전 구현_

  - [ ] 21.2 실시간 파이프라인 실행 기능 구현
    - "Start Reddit Collection" 버튼으로 실제 Reddit 수집 트리거
    - "Run Full Pipeline" 버튼으로 전체 파이프라인 실행
    - 실시간 진행 상황 모니터링 및 상태 업데이트
    - 에러 처리 및 사용자 피드백 개선
    - _Requirements: 새로운 요구사항 - 실시간 파이프라인 제어_

  - [ ] 21.3 통계 및 모니터링 대시보드 구현
    - 실시간 통계 표시 (수집/처리/발행 건수)
    - 성공률 계산 및 표시
    - 최근 게시글 목록 실시간 업데이트
    - 시스템 로그 실시간 표시
    - _Requirements: 새로운 요구사항 - 실시간 모니터링 대시보드_

  - [ ] 21.4 E2E 테스트 및 검증
    - Vercel 대시보드에서 전체 파이프라인 테스트
    - Ghost 블로그에 10개 게시글 발행 목표 달성
    - 실시간 모니터링 기능 검증
    - 사용자 경험 최적화 및 버그 수정
    - _Requirements: 새로운 요구사항 - 완전한 E2E 테스트_