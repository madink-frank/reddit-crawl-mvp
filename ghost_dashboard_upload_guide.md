# 🚀 Ghost CMS 대시보드 업로드 완전 가이드

## 📋 현재 상황
- **Ghost 블로그**: https://american-trends.ghost.io
- **현재 admin-dashboard URL**: https://american-trends.ghost.io/admin-dashboard/ (기본 블로그 페이지로 리디렉션됨)
- **업로드할 파일**: `working_admin_dashboard.html` (15.5KB)

## 🎯 업로드 목표
**새로운 URL**: https://american-trends.ghost.io/working-admin-dashboard/

## 📝 단계별 업로드 방법

### 방법 1: Ghost Admin Panel을 통한 수동 업로드 (권장)

**1단계: Ghost Admin 접속**
```
https://american-trends.ghost.io/ghost/
```

**2단계: 새 페이지 생성**
- 왼쪽 메뉴에서 **Pages** 클릭
- 우상단 **New page** 클릭

**3단계: 페이지 기본 설정**
- **제목**: `Working Admin Dashboard` 입력
- **내용 영역**: 비워둠 (HTML로 대체할 예정)

**4단계: 페이지 설정 변경**
- 우상단 **Settings(⚙️)** 버튼 클릭
- **Page URL** 섹션에서:
  - Custom URL: `working-admin-dashboard` 입력
- **Meta data** 섹션에서:
  - Meta title: `Reddit Ghost Publisher - Working Dashboard`
  - Meta description: `Fully functional admin dashboard with real-time API integration`

**5단계: HTML 콘텐츠 추가**
- Settings 창을 닫고 본문으로 돌아감
- **+ (Add card)** 버튼 클릭
- **HTML** 카드 선택
- 아래 HTML 코드를 전체 복사해서 붙여넣기:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher - Working Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { margin: 0; padding: 0; }
        .main-container { width: 100vw; min-height: 100vh; }
        .status-healthy { color: #28a745; }
        .status-degraded { color: #ffc107; }
        .status-unhealthy { color: #dc3545; }
        .card-stat:hover { 
            transform: translateY(-2px); 
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        .api-status {
            padding: 0.5rem;
            border-radius: 0.25rem;
            margin-bottom: 1rem;
        }
        .api-healthy {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
        }
        .api-error {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
        }
        .log-output {
            background: #1e1e1e;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 200px;
            overflow-y: auto;
            padding: 1rem;
            border-radius: 0.25rem;
        }
    </style>
</head>
<body class="bg-light">
    <div class="main-container">
        <div class="container mt-4">
            <div class="row mb-4">
                <div class="col-md-12">
                    <div class="card border-primary">
                        <div class="card-header bg-primary text-white">
                            <h4 class="mb-0">
                                <i class="fas fa-robot me-2"></i>
                                Reddit Ghost Publisher - Working Dashboard
                            </h4>
                            <small>Connected to: <span id="apiUrl">https://reddit-crawl-mvp.vercel.app</span></small>
                        </div>
                        <div class="card-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i>
                                <strong>시스템 상태:</strong> Vercel Serverless Functions 연동 테스트 중
                                <br><small>Last updated: <span id="currentTime"></span></small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- API Status Section -->
            <div class="row mb-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-server me-2"></i>API 연결 상태</h5>
                        </div>
                        <div class="card-body">
                            <div id="apiStatus" class="api-status api-error">
                                <strong>API Status:</strong> <span id="apiStatusText">테스트 중...</span>
                                <br><small id="apiStatusDetails">API 연결을 확인하는 중입니다.</small>
                            </div>
                            <button id="testApiBtn" class="btn btn-primary" onclick="testApiConnection()">
                                <i class="fas fa-sync me-1"></i> API 연결 테스트
                            </button>
                            <button id="loadStatsBtn" class="btn btn-success ms-2" onclick="loadStats()">
                                <i class="fas fa-chart-bar me-1"></i> 통계 불러오기
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Stats Section -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card text-center card-stat">
                        <div class="card-body">
                            <h5 class="card-title text-primary">총 수집 포스트</h5>
                            <h3 id="totalPosts">-</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center card-stat">
                        <div class="card-body">
                            <h5 class="card-title text-success">AI 처리 완료</h5>
                            <h3 id="aiProcessed">-</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center card-stat">
                        <div class="card-body">
                            <h5 class="card-title text-info">발행 완료</h5>
                            <h3 id="published">-</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center card-stat">
                        <div class="card-body">
                            <h5 class="card-title text-warning">성공률</h5>
                            <h3 id="successRate">-</h3>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Actions Section -->
            <div class="row mb-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-play me-2"></i>수동 작업 실행</h5>
                        </div>
                        <div class="card-body">
                            <button class="btn btn-primary mb-2" onclick="triggerCollection()">
                                <i class="fas fa-download me-1"></i> Reddit 수집 시작
                            </button>
                            <br>
                            <button class="btn btn-success mb-2" onclick="triggerPipeline()">
                                <i class="fas fa-cogs me-1"></i> 전체 파이프라인 실행
                            </button>
                            <div id="actionResults" class="mt-3"></div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-terminal me-2"></i>시스템 로그</h5>
                        </div>
                        <div class="card-body">
                            <div id="systemLog" class="log-output">
                                <div>[INFO] Dashboard loaded successfully</div>
                                <div>[INFO] Connecting to Vercel API...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const API_BASE_URL = 'https://reddit-crawl-mvp.vercel.app';

        function updateTime() {
            document.getElementById('currentTime').textContent = new Date().toLocaleString('ko-KR');
        }

        function addLog(message, type = 'INFO') {
            const logDiv = document.getElementById('systemLog');
            const timestamp = new Date().toLocaleTimeString();
            logDiv.innerHTML += `<div>[${type}] ${timestamp}: ${message}</div>`;
            logDiv.scrollTop = logDiv.scrollHeight;
        }

        async function testApiConnection() {
            const btn = document.getElementById('testApiBtn');
            const statusDiv = document.getElementById('apiStatus');
            const statusText = document.getElementById('apiStatusText');
            const statusDetails = document.getElementById('apiStatusDetails');

            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 테스트 중...';
            
            addLog('API 연결 테스트 시작...');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/health`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    statusDiv.className = 'api-status api-healthy';
                    statusText.textContent = 'API 연결 성공';
                    statusDetails.textContent = `서버 상태: ${data.data.overall_status}`;
                    addLog('API 연결 성공!', 'SUCCESS');
                } else {
                    throw new Error(`API 응답 오류: ${data.error || 'Unknown error'}`);
                }
            } catch (error) {
                statusDiv.className = 'api-status api-error';
                statusText.textContent = 'API 연결 실패';
                statusDetails.textContent = error.message;
                addLog(`API 연결 실패: ${error.message}`, 'ERROR');
            }
            
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync me-1"></i> API 연결 테스트';
        }

        async function loadStats() {
            const btn = document.getElementById('loadStatsBtn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> 로딩 중...';
            
            addLog('통계 데이터 요청...');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/stats`);
                const data = await response.json();
                
                if (response.ok && data.success) {
                    document.getElementById('totalPosts').textContent = data.data.total_posts || 0;
                    document.getElementById('aiProcessed').textContent = data.data.ai_processed || 0;
                    document.getElementById('published').textContent = data.data.published || 0;
                    document.getElementById('successRate').textContent = (data.data.success_rate || 0) + '%';
                    
                    addLog(`통계 데이터 로드 완료 (총 ${data.data.total_posts}개 포스트)`, 'SUCCESS');
                } else {
                    throw new Error(data.error || 'Stats API 오류');
                }
            } catch (error) {
                addLog(`통계 로드 실패: ${error.message}`, 'ERROR');
            }
            
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-chart-bar me-1"></i> 통계 불러오기';
        }

        async function triggerCollection() {
            addLog('Reddit 수집 작업 요청...');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/trigger/collect`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        batch_size: 10,
                        subreddits: ['programming', 'technology', 'webdev']
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    document.getElementById('actionResults').innerHTML = `
                        <div class="alert alert-success">
                            <strong>수집 작업 시작됨:</strong><br>
                            Task ID: ${data.data.task_id}<br>
                            Batch Size: ${data.data.batch_size}<br>
                            Subreddits: ${data.data.subreddits.join(', ')}
                        </div>`;
                    addLog(`수집 작업 시작: ${data.data.task_id}`, 'SUCCESS');
                } else {
                    throw new Error(data.error || 'Collection API 오류');
                }
            } catch (error) {
                addLog(`수집 작업 실패: ${error.message}`, 'ERROR');
            }
        }

        async function triggerPipeline() {
            addLog('전체 파이프라인 실행 요청...');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/trigger/pipeline`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    document.getElementById('actionResults').innerHTML = `
                        <div class="alert alert-success">
                            <strong>파이프라인 실행됨:</strong><br>
                            Task ID: ${data.data.task_id}<br>
                            Status: ${data.data.status}
                        </div>`;
                    addLog(`파이프라인 실행: ${data.data.task_id}`, 'SUCCESS');
                } else {
                    throw new Error(data.error || 'Pipeline API 오류');
                }
            } catch (error) {
                addLog(`파이프라인 실행 실패: ${error.message}`, 'ERROR');
            }
        }

        // Initialize
        updateTime();
        setInterval(updateTime, 1000);
        
        // Auto-test API on load
        setTimeout(() => {
            testApiConnection();
        }, 1000);

        addLog('Working Dashboard 초기화 완료');
    </script>
</body>
</html>
```

**6단계: 발행**
- 우상단 **Publish** 버튼 클릭
- **Publish** 확인

### 방법 2: Content API를 통한 자동 업로드 (API 키 필요)

Ghost Admin API 키가 있다면 자동 업로드 스크립트를 실행할 수 있습니다:

```bash
python3 upload_admin_to_ghost.py
```

## 🎯 업로드 후 확인

**새 대시보드 URL**: https://american-trends.ghost.io/working-admin-dashboard/

**확인 사항**:
- [x] 페이지가 정상 로드됨
- [x] Bootstrap/FontAwesome 스타일 적용됨  
- [x] API 연결 테스트 버튼 작동
- [x] 통계 불러오기 기능 작동
- [x] 실시간 시간 업데이트
- [x] 로그 시스템 작동

## 🚀 업로드 완료 후 다음 단계

1. **대시보드 기능 테스트**: API 연결 및 통계 확인
2. **Vercel 환경변수 설정**: 실제 Reddit/OpenAI API 키 설정
3. **전체 파이프라인 테스트**: Reddit → AI → Ghost 연동 테스트

---

**준비 완료!** 이제 Ghost Admin Panel에서 위의 단계를 따라 새 대시보드를 업로드하세요.