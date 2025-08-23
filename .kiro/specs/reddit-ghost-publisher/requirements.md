# Requirements Document

## Introduction

Reddit Ghost Publisher는 Reddit 인기 글을 수집하고 한국어 요약을 생성한 뒤 Ghost CMS에 자동 발행하는 MVP 시스템입니다. 비용과 운영 복잡도를 최소화하고 하루 단위 배치로 안정 동작을 확보하는 것을 목표로 합니다. FastAPI + Celery + Redis + PostgreSQL을 단일 노드 Docker Compose로 운영합니다.

## Requirements

### Requirement 1: Reddit 수집

**User Story:** 콘텐츠 큐레이터로서 매일 인기 글을 자동으로 모으고 싶다.

#### Acceptance Criteria

1. WHEN 수집기가 실행되면 THEN 시스템은 지정 서브레딧의 Hot과 Rising에서 상위 N개를 시간당 한 번 수집해야 한다 (N은 환경변수로 설정)
2. WHEN Reddit API를 호출할 때 THEN 시스템은 공식 API만 사용하고 60 rpm 이하로 제한해야 한다
3. WHEN API 제한 초과가 예상되면 THEN 시스템은 지수 백오프 후 재시도해야 한다
4. WHEN 남은 요청 수를 확인할 때 THEN 시스템은 헤더로 확인해야 한다
5. WHEN NSFW 플래그가 있는 글을 만나면 THEN 시스템은 저장하지 않아야 한다
6. WHEN 동일 post id가 있으면 THEN 시스템은 저장하지 않아야 한다 (reddit_post_id에 유니크 제약)
7. WHEN 일일 API 호출이 상한의 80%에 도달하면 THEN 시스템은 Slack으로 알려야 한다
8. WHEN 일일 API 호출이 상한을 초과하면 THEN 시스템은 수집을 중단해야 한다

### Requirement 2: AI 요약과 태깅

**User Story:** 퍼블리셔로서 한국어 요약과 핵심 태그를 자동으로 만들고 싶다.

#### Acceptance Criteria

1. WHEN 각 글을 수집할 때 THEN 시스템은 GPT-4o-mini로 한국어 요약을 생성해야 한다
2. WHEN 품질이 실패하면 THEN 시스템은 gpt-4o로 한 번 폴백해야 한다
3. WHEN 태그를 추출할 때 THEN 시스템은 LLM 프롬프트로 3개에서 5개를 추출해야 한다 (토픽 모델 전용 라이브러리 사용 안 함)
4. WHEN pain_points와 product_ideas를 생성할 때 THEN 시스템은 사전 정의한 JSON 스키마로 생성해야 한다
5. WHEN 필드 버전을 저장할 때 THEN 시스템은 meta.version으로 저장해야 한다
6. WHEN 작업이 실패하면 THEN 시스템은 최대 3회 지수 백오프 재시도해야 한다
7. WHEN 일일 토큰 예산의 80%에 도달하면 THEN 시스템은 Slack 알림을 보내야 한다
8. WHEN 일일 토큰 예산의 100%에 도달하면 THEN 시스템은 추가 요청을 차단해야 한다
9. WHEN 토큰 사용량을 계산할 때 THEN 시스템은 내부 코스트 맵으로 계산해 일별 합계를 로그로 남겨야 한다

### Requirement 3: Ghost 자동 발행

**User Story:** 가공된 콘텐츠가 Ghost 블로그에 자동으로 발행되기를 원한다.

#### Acceptance Criteria

1. WHEN 콘텐츠를 변환할 때 THEN 시스템은 Markdown을 HTML로 변환해야 한다
2. WHEN 템플릿을 사용할 때 THEN 시스템은 기본 템플릿 Article 한 종류만 사용해야 한다
3. WHEN Ghost에 인증할 때 THEN 시스템은 Admin Key로 인증해 초안 저장 후 발행해야 한다
4. WHEN Reddit 미디어를 처리할 때 THEN 시스템은 서버에서 먼저 다운로드한 뒤 Ghost Images API로 업로드해야 한다 (원격 링크 사용 안 함)
5. WHEN 태그를 매핑할 때 THEN 시스템은 LLM 태그를 Ghost tags에 매핑해야 한다
6. WHEN 출처를 표기할 때 THEN 시스템은 본문 하단에 "Source: Reddit 링크 포함, Media and usernames belong to their respective owners, Requests for takedown will be honored"를 넣어야 한다
7. WHEN 발행이 실패하면 THEN 시스템은 최대 3회 지수 백오프로 재시도해야 한다
8. WHEN 중복 발행을 방지할 때 THEN 시스템은 동일 reddit_post_id로 중복 발행하지 않아야 한다

### Requirement 4: 아키텍처

**User Story:** 운영과 확장을 고려하되 MVP에서는 단순하고 안정적인 구성을 원한다.

#### Acceptance Criteria

1. WHEN 시스템을 구성할 때 THEN 단일 리포지토리에 FastAPI 웹앱과 Celery 워커, Redis, PostgreSQL을 Docker Compose로 실행해야 한다
2. WHEN 큐를 사용할 때 THEN 시스템은 세 가지 라우팅 키를 사용해야 한다: collect, process, publish
3. WHEN 오토스케일을 할 때 THEN 시스템은 오토스케일이 없어야 한다
4. WHEN 큐 적체가 기준치를 넘으면 THEN 시스템은 Slack으로 알리고 수동으로 워커 수를 늘려야 한다

### Requirement 5: 데이터베이스

**User Story:** 신뢰 가능한 저장과 간단한 조회가 가능해야 한다.

#### Acceptance Criteria

1. WHEN 데이터베이스를 사용할 때 THEN 시스템은 PostgreSQL 15를 사용해야 한다
2. WHEN 스키마를 정의할 때 THEN 시스템은 다음 필드를 포함해야 한다: id uuid, reddit_post_id text unique, title text, subreddit text, score integer, num_comments integer, created_ts timestamptz, summary_ko text, tags jsonb, pain_points jsonb, product_ideas jsonb, ghost_url text, content_hash text
3. WHEN 개발과 운영을 할 때 THEN 시스템은 모두 PostgreSQL을 사용해야 한다 (SQLite 사용 안 함)
4. WHEN 백업을 할 때 THEN 시스템은 매일 새벽 pg_dump로 백업하고 최근 7일을 보존해야 한다
5. WHEN 복구 테스트를 할 때 THEN 시스템은 주 1회 스테이징에서 수행해야 한다

### Requirement 6: 보안과 컴플라이언스

**User Story:** 키와 개인정보를 안전하게 다루고 저작권 요청에 신속히 대응하고 싶다.

#### Acceptance Criteria

1. WHEN 키를 보관할 때 THEN 시스템은 Reddit, Ghost, OpenAI 키를 환경변수 또는 호스팅 비밀 저장소에 보관해야 한다 (Vault는 백로그로 이동)
2. WHEN 로그를 남길 때 THEN 시스템은 액세스 토큰과 사용자 개인정보를 남기지 않아야 한다 (필요한 경우 별표 마스킹 적용)
3. WHEN 권리자 삭제 요청이 접수되면 THEN 시스템은 72시간 이내 비공개 처리 후 삭제해야 한다
4. WHEN 처리 내역을 기록할 때 THEN 시스템은 로그로 남겨야 한다
5. WHEN 크롤링을 할 때 THEN 시스템은 크롤링을 금지하고 Reddit API 정책을 준수해야 한다

### Requirement 7: 관측성과 알림

**User Story:** 장애와 비용 초과를 빠르게 감지하고 싶다.

#### Acceptance Criteria

1. WHEN FastAPI가 실행될 때 THEN 시스템은 헬스체크 경로와 기본 /metrics를 제공해야 한다
2. WHEN 지표를 노출할 때 THEN 시스템은 처리 건수와 실패 건수를 계수형 지표로 노출해야 한다
3. WHEN 실패율이 5%를 넘거나 큐 대기 수가 500을 넘으면 THEN 시스템은 Slack으로 알림을 보내야 한다
4. WHEN 일일 리포트를 할 때 THEN 시스템은 수집 수와 발행 수, 토큰 사용량을 요약해 Slack으로 리포트해야 한다

### Requirement 8: CI와 배포

**User Story:** 변경을 안전하게 릴리스하고 회귀를 막고 싶다.

#### Acceptance Criteria

1. WHEN 코드를 푸시할 때 THEN 시스템은 GitHub Actions로 유닛 테스트를 실행해야 한다 (커버리지 목표 70%)
2. WHEN 테스트가 통과하면 THEN 시스템은 Docker 이미지를 빌드하고 태그해야 한다
3. WHEN 프로덕션 배포를 할 때 THEN 시스템은 수동 승인 후 진행해야 한다
4. WHEN 스모크 테스트를 할 때 THEN 시스템은 Postman 스모크 테스트를 발행 API 중심으로 실행해 100% 통과해야 한다

### Requirement 9: 성능과 처리 지연

**User Story:** 사용자 체감과 운영 안정성을 해치지 않는 성능이 필요하다.

#### Acceptance Criteria

1. WHEN API 지연 시간을 측정할 때 THEN 시스템은 p95 지연 시간 목표 300ms를 달성해야 한다 (경보 기준 400ms)
2. WHEN 단일 배치를 실행할 때 THEN 시스템은 글 하나의 수집부터 발행까지 평균 5분 이내에 완료해야 한다
3. WHEN 처리량을 측정할 때 THEN 시스템은 시간당 100개 글을 안정적으로 처리해야 한다
4. WHEN 실패가 발생하면 THEN 시스템은 재시도로 회복해야 한다

### Requirement 10: 콘텐츠 템플릿과 UX

**User Story:** 읽기 쉬운 포맷으로 일관되게 제공되기를 원한다.

#### Acceptance Criteria

1. WHEN 템플릿을 사용할 때 THEN 시스템은 Article 한 종류만 사용해야 한다
2. WHEN 콘텐츠 순서를 정할 때 THEN 시스템은 제목, 요약, 핵심 인사이트, 원문 링크, 출처 고지 순서로 고정해야 한다
3. WHEN 태그를 적용할 때 THEN 시스템은 3개에서 5개로 제한해야 한다
4. WHEN 태그 표기를 할 때 THEN 시스템은 검색과 탐색을 돕도록 일관된 표기 규칙을 적용해야 한다
5. WHEN 이미지가 없을 때 THEN 시스템은 기본 OG 이미지를 사용해야 한다

### Requirement 11: 시스템 검증 테스트

**User Story:** 개발 완료 후 모든 요구사항이 정상 동작하는지 검증하고 싶다.

#### Acceptance Criteria

**사전 준비**:
1. WHEN 테스트 환경을 구성할 때 THEN 스테이징에 Docker Compose(FastAPI, Celery, Redis, PostgreSQL, Ghost Pro 스테이징 블로그)를 준비해야 한다
2. WHEN 테스트 변수를 설정할 때 THEN SUBREDDITS, BATCH_SIZE(N), RATE_LIMIT_RPM, TOKEN_BUDGET_DAILY, QUEUE_ALERT_THRESHOLD(500), RETRY_MAX(3)를 구성해야 한다
3. WHEN 알림 채널을 설정할 때 THEN Slack 웹훅 테스트 채널을 준비해야 한다
4. WHEN 시드 데이터를 준비할 때 THEN NSFW 포함/미포함 포스트 id 목록, 미디어 포함/미포함 포스트 샘플을 준비해야 한다

**Reddit 수집 테스트 (Req 1)**:
5. WHEN 상위 N 수집을 테스트할 때 THEN 지정 서브레딧 Hot/Rising에서 N=20으로 실행하여 저장 행 개수 ≥ N, subreddit/score/created_ts가 채워져야 한다
6. WHEN API 레이트리밋 준수를 테스트할 때 THEN RATE_LIMIT_RPM=60 설정으로 수집기 연속 실행하여 429 없음, 백오프 로그 존재, 평균 RPM ≤ 60이어야 한다
7. WHEN NSFW 필터를 테스트할 때 THEN NSFW 플래그 포스트 포함 수집하여 DB에 해당 reddit_post_id가 미저장되어야 한다
8. WHEN 중복 방지를 테스트할 때 THEN 동일 범위 두 번 연속 수집하여 reddit_post_id UNIQUE 위반 0건, 신규 삽입 0건이어야 한다
9. WHEN 예산 상한 알림을 테스트할 때 THEN 일일 상한을 낮게(예: 100콜) 설정 후 초과 직전까지 호출하여 80% 도달 시 Slack 알림 발생, 100% 도달 시 수집 중단 로그가 있어야 한다

**AI 요약/태깅 테스트 (Req 2)**:
10. WHEN 요약 생성과 폴백을 테스트할 때 THEN gpt-4o-mini 키 정상 실행 후 mini 키를 의도적으로 차단하고 재실행하여 1차 실패 후 gpt-4o로 재시도 성공, summary_ko가 채워져야 한다
11. WHEN 태그 3-5개 제한을 테스트할 때 THEN LLM 태그 추출 프롬프트로 처리하여 tags 배열 길이 3-5, 전부 소문자/한글 표기 규칙 일치해야 한다
12. WHEN JSON 스키마 준수를 테스트할 때 THEN pain_points/product_ideas 생성하여 사전 정의 스키마 키 모두 존재, meta.version 기록되어야 한다
13. WHEN 재시도/백오프를 테스트할 때 THEN OpenAI API를 500/timeout으로 모킹하여 최대 3회 재시도 후 실패 플래그, 간격이 지수 백오프 로그로 확인되어야 한다
14. WHEN 토큰 예산 게이트를 테스트할 때 THEN 일일 TOKEN_BUDGET_DAILY를 낮게 설정하여 80% Slack 알림, 100% 이후 신규 요청 차단되어야 한다

**Ghost 발행 테스트 (Req 3)**:
15. WHEN Markdown→HTML 변환을 테스트할 때 THEN 샘플 포스트 3건 발행하여 고정 섹션(제목/요약/인사이트/원문링크/출처) 순서가 유지되어야 한다
16. WHEN Admin API 인증/초안→발행을 테스트할 때 THEN 초안 저장 후 발행 플로우로 Ghost에 초안 생성→발행 상태 변환, ghost_url 저장되어야 한다
17. WHEN 이미지 업로드를 테스트할 때 THEN Reddit 미디어 포함 포스트 발행하여 본문 내 이미지 URL이 Ghost 도메인/Images API 경로, 외부 핫링크 없어야 한다
18. WHEN 태그 매핑을 테스트할 때 THEN LLM 태그를 Ghost tags로 전달하여 Ghost 관리자에서 동일 태그가 확인되어야 한다
19. WHEN 출처 고지/삭제요청 문구를 테스트할 때 THEN 본문 하단 문구 포함 검증하여 링크/문구가 정확히 노출되어야 한다
20. WHEN 발행 리트라이와 멱등성을 테스트할 때 THEN Ghost API 503을 모킹하여 최대 3회 백오프, 중복 발행 없음(ghost_url 불변, 한 건만 존재)이어야 한다

**아키텍처/큐 테스트 (Req 4)**:
21. WHEN 큐 라우팅을 테스트할 때 THEN collect→process→publish 순서로 체인 태스크 실행하여 각 라우팅 키별 소비량/실패 수가 노출되어야 한다
22. WHEN 수동 스케일 운영 알림을 테스트할 때 THEN 큐 적체 500 초과 상황을 만들어 Slack 알림 트리거, 오토스케일 없음이어야 한다

**데이터베이스 테스트 (Req 5)**:
23. WHEN 스키마/제약을 테스트할 때 THEN 마이그레이션 적용 후 삽입/조회하여 reddit_post_id UNIQUE, 필수 컬럼 NULL 아님, content_hash 생성되어야 한다
24. WHEN 백업/복구 리허설을 테스트할 때 THEN pg_dump 생성→새 DB에 복구하여 복구된 DB에서 최근 데이터 존재, 인덱스/제약 동일해야 한다

**보안/컴플라이언스 테스트 (Req 6)**:
25. WHEN 비밀 관리/로그 마스킹을 테스트할 때 THEN 환경변수 주입, 요청/응답 로깅 확인하여 키/토큰 미노출(**** 마스킹), PII 없어야 한다
26. WHEN Takedown 워크플로를 테스트할 때 THEN API로 특정 ghost_url 비공개 처리 호출하여 72시간 SLA 내 상태 전환 기록, 감사 로그가 남아야 한다
27. WHEN Reddit API 정책 준수를 테스트할 때 THEN 비API 크롤링 호출 경로가 아예 없음을 코드/로그로 확인하여 비API 접근 로그가 0이어야 한다

**관측성/알림 테스트 (Req 7)**:
28. WHEN /health, /metrics를 테스트할 때 THEN 헬스 체크 200, /metrics에 처리 건수/실패 건수 노출하여 Prometheus 포맷으로 카운터가 확인되어야 한다
29. WHEN 실패율/큐 대기 알림을 테스트할 때 THEN 실패율 5%를 의도적으로 초과 + 큐 500 초과하여 두 조건 각각 Slack 메시지가 전송되어야 한다
30. WHEN 일일 리포트를 테스트할 때 THEN 수집/발행/토큰 사용량 집계 작업 트리거하여 Slack 리포트에 3 지표 모두가 포함되어야 한다

**CI/배포 테스트 (Req 8)**:
31. WHEN 유닛 커버리지 70%를 테스트할 때 THEN GitHub Actions에서 테스트 실행하여 커버리지 리포트 ≥ 70%, 실패 테스트 0이어야 한다
32. WHEN 이미지 빌드/수동 승인 배포를 테스트할 때 THEN main→build, release 브랜치→수동 승인 후 배포하여 빌드 성공, 태그/해시 일치, 승인이 없으면 배포 보류되어야 한다
33. WHEN Postman 스모크를 테스트할 때 THEN 수집→요약→발행 주요 엔드포인트 스모크 셋으로 100% 패스해야 한다

**성능/지연 테스트 (Req 9)**:
34. WHEN API p95 목표를 테스트할 때 THEN k6로 100 rps, 5분 테스트하여 http_req_duration p(95) ≤ 300ms, 경보 기준 400ms 미만을 유지해야 한다
35. WHEN E2E 처리 시간을 테스트할 때 THEN 글 10건 배치 처리하여 각 글 단위 수집→발행 평균 5분 이내여야 한다
36. WHEN 처리량 안정성을 테스트할 때 THEN 1시간에 100건 처리 시뮬레이션하여 실패율 <5%, 실패 건은 재시도로 완료되어야 한다

**템플릿/UX 테스트 (Req 10)**:
37. WHEN Article 템플릿 일관성을 테스트할 때 THEN 포스트 5건 랜덤 검수하여 섹션 순서 고정, 헤더/본문 스타일이 동일해야 한다
38. WHEN 태그 제한/표기 규칙을 테스트할 때 THEN 최근 20건 점검하여 태그 3-5개, 표기 규칙 준수(예: 소문자/한글)해야 한다
39. WHEN 이미지 폴백을 테스트할 때 THEN 미디어 없는 포스트 발행하여 기본 OG 이미지가 노출되어야 한다

**최종 합격 기준**:
40. WHEN 릴리스 게이트를 통과할 때 THEN 기능(Req 1-10의 각 섹션 최소 1개 이상 핵심 케이스 Pass), 품질(유닛 커버리지 ≥ 70%, Postman 스모크 100% 통과), 성능(p95 ≤ 300ms, E2E 평균 ≤ 5분, 실패율 < 5%), 운영(Slack 알림 정상, 백업/복구 리허설 성공) 모든 조건을 만족해야 한다

### Requirement 12: 실제 데이터 파이프라인 구현

**User Story:** Ghost 대시보드에서 실제 Reddit 데이터를 수집하고 AI로 처리하여 Ghost 블로그에 발행하고 싶다.

#### Acceptance Criteria

1. WHEN Ghost 대시보드에서 API를 호출할 때 THEN 시스템은 CORS 헤더를 설정하여 american-trends.ghost.io에서 접근을 허용해야 한다
2. WHEN Reddit API를 연동할 때 THEN 시스템은 가짜 데이터를 제거하고 실제 PRAW 라이브러리로 Reddit에서 데이터를 수집해야 한다
3. WHEN AI 처리를 할 때 THEN 시스템은 가짜 AI 응답을 제거하고 실제 OpenAI API로 한국어 요약과 태그를 생성해야 한다
4. WHEN Ghost에 발행할 때 THEN 시스템은 가짜 발행 로직을 제거하고 실제 Ghost Admin API로 블로그 글을 발행해야 한다
5. WHEN 데이터베이스를 사용할 때 THEN 시스템은 Railway PostgreSQL에 실제 스키마를 생성하고 실제 데이터를 저장해야 한다
6. WHEN 대시보드에서 통계를 표시할 때 THEN 시스템은 가짜 통계를 제거하고 실제 데이터베이스에서 계산된 통계를 표시해야 한다
7. WHEN 전체 파이프라인을 실행할 때 THEN 시스템은 Reddit 수집 → AI 처리 → Ghost 발행이 실제로 작동하여 american-trends.ghost.io에 새 글이 발행되어야 한다
8. WHEN 에러가 발생할 때 THEN 시스템은 실제 에러 처리와 재시도 메커니즘이 작동해야 한다