# 🚀 Vercel 배포 가이드

## 1. Vercel 계정 설정

1. **Vercel 가입**: https://vercel.com
2. **GitHub 연결**: 프로젝트를 GitHub에 푸시
3. **Vercel CLI 설치** (선택사항):
   ```bash
   npm i -g vercel
   ```

## 2. 프로젝트 배포

### 방법 1: GitHub 연동 (권장)
1. GitHub에 프로젝트 푸시
2. Vercel 대시보드에서 "New Project" 클릭
3. GitHub 저장소 선택
4. 자동 배포 완료

### 방법 2: CLI 배포
```bash
# 프로젝트 루트에서
vercel

# 프로덕션 배포
vercel --prod
```

## 3. 환경 변수 설정

Vercel 대시보드 → Settings → Environment Variables에서 설정:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
OPENAI_API_KEY=your-openai-api-key
GHOST_ADMIN_KEY=your-ghost-admin-key
GHOST_API_URL=https://american-trends.ghost.io
```

## 4. 배포 후 설정

1. **API URL 업데이트**: 
   - `ghost_vercel_dashboard.html`에서 `API_BASE_URL` 수정
   - 예: `https://reddit-publisher.vercel.app`

2. **Ghost 대시보드 업데이트**:
   ```bash
   python upload_admin_to_ghost.py ghost_vercel_dashboard.html
   ```

## 5. 테스트

배포 완료 후 다음 엔드포인트 테스트:

- `https://your-app.vercel.app/api/health` - 헬스체크
- `https://your-app.vercel.app/api/stats` - 통계 조회

## 6. 자동 배포 설정

GitHub에 푸시할 때마다 자동 배포됩니다:
- `main` 브랜치 → Production
- 다른 브랜치 → Preview

## 7. 도메인 설정 (선택사항)

Vercel 대시보드 → Settings → Domains에서 커스텀 도메인 추가 가능

## 8. 모니터링

- **Vercel Analytics**: 자동 제공
- **Function Logs**: Vercel 대시보드에서 확인
- **Performance**: 자동 모니터링

## 장점

✅ **무료 티어**: 월 100GB 대역폭, 100 Function 실행  
✅ **자동 HTTPS**: SSL 인증서 자동 관리  
✅ **Global CDN**: 전 세계 빠른 접근  
✅ **자동 스케일링**: 트래픽에 따른 자동 확장  
✅ **Zero Config**: 설정 없이 바로 배포  

## 주의사항

⚠️ **Serverless 제한**: 각 Function은 10초 실행 제한  
⚠️ **Cold Start**: 첫 요청 시 약간의 지연  
⚠️ **Background Jobs**: 별도 워커 필요 (Supabase Edge Functions 또는 다른 서비스)  

## 다음 단계

1. **Background Workers**: Supabase Edge Functions로 실제 Reddit 수집/AI 처리 구현
2. **Cron Jobs**: Vercel Cron으로 정기 실행 설정
3. **Database**: Supabase PostgreSQL 연동 완료
4. **Monitoring**: 실시간 알림 시스템 구축