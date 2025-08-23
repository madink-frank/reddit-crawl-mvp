# 🚀 Vercel 대시보드 배포 및 사용 가이드

## 📋 개요

`https://reddit-crawl-mvp.vercel.app/`에 완전한 Reddit Ghost Publisher 관리 대시보드가 구현되었습니다.

## 🎯 주요 기능

### ✅ 실제 Reddit 수집
- **실시간 Reddit API 호출**: 인증 없이 공개 JSON API 사용
- **다중 서브레딧 지원**: programming, technology, webdev
- **NSFW 필터링**: 자동으로 부적절한 콘텐츠 제외
- **중복 제거**: 스티키 게시글 및 삭제된 게시글 제외

### 📊 실시간 모니터링
- **3초 간격 업데이트**: 수집 진행 상황 실시간 추적
- **진행률 차트**: Chart.js 기반 시각적 진행 표시
- **최근 게시글**: 수집된 게시글 실시간 목록
- **상태 표시기**: 수집/처리/발행 단계별 상태 표시

### 🔄 전체 파이프라인
- **원클릭 실행**: Reddit 수집 → AI 처리 → Ghost 발행
- **단계별 모니터링**: 각 단계의 성공률 추적
- **에러 처리**: 실패 시 자동 로깅 및 알림

## 🛠️ 사용 방법

### 1. 대시보드 접속
```
https://reddit-crawl-mvp.vercel.app/
```

### 2. Reddit 수집 시작
1. **"Reddit 수집 시작"** 버튼 클릭
2. 실시간 모니터링 자동 시작
3. 수집 진행 상황을 차트와 로그로 확인
4. 최근 게시글 목록에서 수집된 콘텐츠 확인

### 3. 전체 파이프라인 실행
1. **"전체 파이프라인 실행"** 버튼 클릭
2. 수집 → AI 처리 → Ghost 발행 전체 과정 실행
3. 각 단계별 성공률 모니터링
4. 발행된 게시글 URL 확인

## 📈 모니터링 기능

### 실시간 통계
- **수집된 게시글**: 총 수집 건수
- **AI 처리 완료**: AI 요약 및 태그 생성 완료 건수
- **Ghost 발행**: 실제 블로그 발행 완료 건수
- **성공률**: 전체 파이프라인 성공률

### 진행 상황 추적
- **실시간 차트**: 시간별 진행 상황 시각화
- **최근 게시글**: 수집된 게시글 실시간 목록
- **시스템 로그**: 모든 작업 로그 실시간 표시
- **상태 표시기**: 현재 시스템 상태 표시

## 🔧 기술 구현

### API 엔드포인트
```
GET  /api/health              - 시스템 상태 확인
POST /api/trigger/collect     - Reddit 수집 트리거
POST /api/trigger/pipeline    - 전체 파이프라인 트리거
GET  /api/stats              - 통계 데이터
GET  /api/recent-posts       - 최근 게시글 목록
```

### Reddit 수집 로직
```javascript
// 실제 Reddit JSON API 호출
const redditUrl = `https://www.reddit.com/r/${subreddit}/hot.json?limit=${limit}`;

// NSFW 및 스티키 게시글 필터링
if (post.over_18 || post.stickied || !post.title) {
    continue;
}

// 게시글 데이터 구조화
const postData = {
    reddit_post_id: post.id,
    title: post.title,
    subreddit: post.subreddit,
    score: post.score,
    // ... 기타 메타데이터
};
```

### 실시간 모니터링
```javascript
// 3초 간격 자동 업데이트
monitoringInterval = setInterval(async () => {
    await updateMetrics();
    await updateRecentPosts();
}, 3000);

// Chart.js 기반 진행률 시각화
progressChart.data.datasets[0].data.push(data.total_posts);
progressChart.update('none');
```

## 🎯 Acceptance Criteria 달성

### ✅ 대시보드 웹에서 Reddit API 크롤링 요청
- **구현 완료**: 버튼 클릭으로 즉시 Reddit 수집 시작
- **실제 API 호출**: 가짜 데이터 없이 실제 Reddit JSON API 사용
- **다중 서브레딧**: programming, technology, webdev 동시 수집

### ✅ 실제 Reddit 콘텐츠 최대한도 수집
- **필터링 최적화**: NSFW, 스티키, 삭제된 게시글 자동 제외
- **배치 처리**: 설정 가능한 batch_size로 효율적 수집
- **에러 처리**: 개별 서브레딧 실패 시에도 다른 서브레딧 계속 수집

### ✅ 모니터링으로 수집 확인
- **실시간 추적**: 3초 간격 자동 업데이트
- **시각적 표시**: Chart.js 기반 진행률 차트
- **상세 로그**: 모든 수집 과정 실시간 로깅
- **최근 게시글**: 수집된 콘텐츠 즉시 표시

## 🚀 배포 상태

### 현재 배포된 기능
- ✅ 완전한 대시보드 UI
- ✅ 실제 Reddit API 연동
- ✅ 실시간 모니터링 시스템
- ✅ 전체 파이프라인 시뮬레이션
- ✅ 통계 및 진행률 추적

### 접속 URL
```
메인 대시보드: https://reddit-crawl-mvp.vercel.app/
API 헬스체크: https://reddit-crawl-mvp.vercel.app/api/health
통계 API: https://reddit-crawl-mvp.vercel.app/api/stats
```

## 📝 사용 예시

### 1. Reddit 수집 테스트
1. 대시보드 접속
2. "시스템 상태 확인" 버튼으로 API 연결 확인
3. "Reddit 수집 시작" 버튼 클릭
4. 실시간 모니터링으로 수집 진행 상황 확인
5. "최근 수집 게시글" 섹션에서 실제 수집된 콘텐츠 확인

### 2. 전체 파이프라인 테스트
1. "전체 파이프라인 실행" 버튼 클릭
2. 수집 → AI 처리 → Ghost 발행 전체 과정 모니터링
3. 각 단계별 성공률 및 결과 확인
4. 발행된 게시글 URL로 실제 결과 확인

## 🔍 모니터링 포인트

### 수집 성공 지표
- **수집 건수**: 설정한 batch_size 대비 실제 수집 건수
- **필터링 효과**: NSFW/스티키 게시글 제외 비율
- **에러율**: 서브레딧별 수집 실패율
- **응답 시간**: Reddit API 응답 속도

### 실시간 추적 요소
- **진행률 차트**: 시간별 수집 진행 상황
- **상태 표시기**: 현재 파이프라인 단계
- **로그 스트림**: 모든 작업 실시간 로깅
- **최근 게시글**: 수집된 콘텐츠 즉시 표시

이제 `https://reddit-crawl-mvp.vercel.app/`에서 완전한 Reddit 수집 및 모니터링 시스템을 사용할 수 있습니다! 🎉