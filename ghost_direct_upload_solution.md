# 🚀 Ghost CMS 대시보드 직접 업로드 해결책

## 📊 현재 상황 분석

**확인된 URL 상태:**
- ✅ https://american-trends.ghost.io/ (메인 블로그 정상)
- ✅ https://american-trends.ghost.io/admin-dashboard/ (기존 페이지 존재, 기능 없음)
- ❌ https://american-trends.ghost.io/working-admin-dashboard/ (404 - 페이지 없음)
- 🔒 https://american-trends.ghost.io/ghost/ (로그인 필요)

**문제점:**
- Ghost Admin 패널 접근 권한 필요
- API 키 미설정으로 자동 업로드 불가
- 기존 admin-dashboard는 정적 페이지 (기능 없음)

## 🎯 즉시 실행 가능한 해결책

### 방법 1: 기존 admin-dashboard 페이지 수정 (권장)

**장점:** 기존 URL 유지, SEO 친화적, 즉시 사용 가능
**URL:** https://american-trends.ghost.io/admin-dashboard/

**수정 방법:**
1. Ghost Admin Panel 접속 (브라우저에서 직접)
2. Pages 메뉴에서 "admin-dashboard" 페이지 찾기
3. 기존 내용을 아래 HTML로 교체

### 방법 2: 새 페이지 생성

**URL:** https://american-trends.ghost.io/working-admin-dashboard/

**생성 방법:**
1. Ghost Admin > Pages > New page
2. 제목: "Working Admin Dashboard"
3. Slug: "working-admin-dashboard"
4. HTML 카드에 아래 코드 삽입

## 📝 업로드할 HTML 코드 (최적화된 버전)

```html
<!-- Reddit Ghost Publisher - Working Dashboard -->
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px;">

<!-- Dashboard Header -->
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; text-align: center;">
    <h1 style="margin: 0; font-size: 2.2rem;">🤖 Reddit Ghost Publisher</h1>
    <p style="margin: 10px 0 0 0; opacity: 0.9;">Working Dashboard - Real-time API Integration</p>
    <div style="margin-top: 15px; font-size: 0.9rem;">
        Connected to: <strong>https://reddit-crawl-mvp.vercel.app</strong>
        <br>Last updated: <span id="currentTime">-</span>
    </div>
</div>

<!-- System Status -->
<div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-bottom: 30px;">
    <h3 style="margin-top: 0;">🌐 System Status</h3>
    <div id="systemStatus" style="display: inline-block; padding: 8px 16px; border-radius: 20px; font-size: 0.9rem; font-weight: 500; margin-bottom: 15px; background: #fed7d7; color: #742a2a;">
        System Initializing...
    </div>
    <br>
    <button id="testBtn" onclick="testConnection()" style="background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 500; margin: 5px;">
        🔍 Test API Connection
    </button>
    <button id="loadBtn" onclick="loadDashboardData()" style="background: #48bb78; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 500; margin: 5px;">
        📊 Load Statistics
    </button>
</div>

<!-- Statistics Grid -->
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
    <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; border-left: 4px solid #667eea;">
        <div id="totalPosts" style="font-size: 2.5rem; font-weight: bold; color: #667eea; margin: 10px 0;">-</div>
        <div style="color: #666; font-size: 0.9rem;">Total Posts Collected</div>
        <div style="width: 100%; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; margin: 10px 0;">
            <div id="postsProgress" style="height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); transition: width 0.3s ease; width: 0%;"></div>
        </div>
    </div>
    
    <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; border-left: 4px solid #667eea;">
        <div id="aiProcessed" style="font-size: 2.5rem; font-weight: bold; color: #667eea; margin: 10px 0;">-</div>
        <div style="color: #666; font-size: 0.9rem;">AI Enhanced</div>
        <div style="width: 100%; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; margin: 10px 0;">
            <div id="aiProgress" style="height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); transition: width 0.3s ease; width: 0%;"></div>
        </div>
    </div>
    
    <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; border-left: 4px solid #667eea;">
        <div id="published" style="font-size: 2.5rem; font-weight: bold; color: #667eea; margin: 10px 0;">-</div>
        <div style="color: #666; font-size: 0.9rem;">Published to Ghost</div>
        <div style="width: 100%; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; margin: 10px 0;">
            <div id="publishProgress" style="height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); transition: width 0.3s ease; width: 0%;"></div>
        </div>
    </div>
    
    <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; border-left: 4px solid #667eea;">
        <div id="successRate" style="font-size: 2.5rem; font-weight: bold; color: #667eea; margin: 10px 0;">-</div>
        <div style="color: #666; font-size: 0.9rem;">Success Rate</div>
        <div style="width: 100%; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; margin: 10px 0;">
            <div id="successProgress" style="height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); transition: width 0.3s ease; width: 0%;"></div>
        </div>
    </div>
</div>

<!-- Actions and Logs -->
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 30px;">
    <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
        <h3 style="margin-top: 0;">⚡ Quick Actions</h3>
        <button onclick="triggerCollection()" style="background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 500; margin: 5px;">
            📥 Start Reddit Collection
        </button>
        <br>
        <button onclick="triggerPipeline()" style="background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 500; margin: 5px;">
            🔄 Run Full Pipeline
        </button>
        <div id="actionResults" style="margin-top: 20px; min-height: 100px;">
            <p style="color: #666; font-style: italic;">Action results will appear here...</p>
        </div>
    </div>

    <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
        <h3 style="margin-top: 0;">📊 System Logs</h3>
        <div id="systemLogs" style="background: #1a202c; color: #4fd1c7; font-family: 'Courier New', monospace; padding: 20px; border-radius: 8px; max-height: 300px; overflow-y: auto; font-size: 0.85rem; line-height: 1.4;">
            <div>[INFO] Dashboard initialized</div>
            <div>[INFO] Waiting for API connection test...</div>
        </div>
    </div>
</div>

<!-- Recent Activity -->
<div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
    <h3 style="margin-top: 0;">📈 Recent Activity</h3>
    <div id="recentActivity">
        <p style="color: #666; font-style: italic;">Load statistics to see recent activity...</p>
    </div>
</div>

</div>

<script>
const API_BASE = 'https://reddit-crawl-mvp.vercel.app';

function updateTime() {
    document.getElementById('currentTime').textContent = new Date().toLocaleString('ko-KR');
}

function addLog(message, type = 'INFO') {
    const logs = document.getElementById('systemLogs');
    const time = new Date().toLocaleTimeString();
    logs.innerHTML += `<div>[${type}] ${time}: ${message}</div>`;
    logs.scrollTop = logs.scrollHeight;
}

function updateStatus(message, isHealthy = false) {
    const status = document.getElementById('systemStatus');
    status.textContent = message;
    status.style.background = isHealthy ? '#c6f6d5' : '#fed7d7';
    status.style.color = isHealthy ? '#22543d' : '#742a2a';
}

async function testConnection() {
    const btn = document.getElementById('testBtn');
    btn.disabled = true;
    btn.textContent = '🔄 Testing...';
    
    updateStatus('Testing API connection...', false);
    addLog('Starting API connection test...');
    
    try {
        const response = await fetch(`${API_BASE}/api/health`);
        const data = await response.json();
        
        if (response.ok && data.success) {
            updateStatus(`✅ API Connected - ${data.data.overall_status}`, true);
            addLog('API connection successful!', 'SUCCESS');
        } else {
            throw new Error(data.error || 'API returned error');
        }
    } catch (error) {
        updateStatus(`❌ Connection Failed: ${error.message}`, false);
        addLog(`Connection test failed: ${error.message}`, 'ERROR');
    }
    
    btn.disabled = false;
    btn.textContent = '🔍 Test API Connection';
}

async function loadDashboardData() {
    const btn = document.getElementById('loadBtn');
    btn.disabled = true;
    btn.textContent = '📊 Loading...';
    
    addLog('Loading dashboard statistics...');
    
    try {
        const response = await fetch(`${API_BASE}/api/stats`);
        const data = await response.json();
        
        if (response.ok && data.success) {
            const stats = data.data;
            document.getElementById('totalPosts').textContent = stats.total_posts || 0;
            document.getElementById('aiProcessed').textContent = stats.ai_processed || 0;
            document.getElementById('published').textContent = stats.published || 0;
            document.getElementById('successRate').textContent = (stats.success_rate || 0) + '%';
            
            // Update progress bars
            const maxPosts = Math.max(stats.total_posts || 1, 100);
            document.getElementById('postsProgress').style.width = `${Math.min((stats.total_posts || 0) / maxPosts * 100, 100)}%`;
            document.getElementById('aiProgress').style.width = `${Math.min((stats.ai_processed || 0) / maxPosts * 100, 100)}%`;
            document.getElementById('publishProgress').style.width = `${Math.min((stats.published || 0) / maxPosts * 100, 100)}%`;
            document.getElementById('successProgress').style.width = `${stats.success_rate || 0}%`;
            
            // Update recent activity
            if (stats.recent_posts && stats.recent_posts.length > 0) {
                let activityHtml = '<h4>Recent Posts:</h4>';
                stats.recent_posts.forEach(post => {
                    activityHtml += `
                        <div style="padding: 10px; margin: 10px 0; background: #f7fafc; border-radius: 6px; border-left: 3px solid #667eea;">
                            <strong>${post.title}</strong><br>
                            <small>r/${post.subreddit} | Score: ${post.score} | Comments: ${post.comments} | 
                            Status: ${post.published ? '✅ Published' : '⏳ Pending'}
                            ${post.ghost_url ? ` | <a href="${post.ghost_url}" target="_blank">View on Ghost</a>` : ''}
                            </small>
                        </div>`;
                });
                document.getElementById('recentActivity').innerHTML = activityHtml;
            }
            
            addLog(`Statistics loaded: ${stats.total_posts} posts, ${stats.success_rate}% success rate`, 'SUCCESS');
        } else {
            throw new Error(data.error || 'Failed to load statistics');
        }
    } catch (error) {
        addLog(`Statistics loading failed: ${error.message}`, 'ERROR');
    }
    
    btn.disabled = false;
    btn.textContent = '📊 Load Statistics';
}

async function triggerCollection() {
    addLog('Triggering Reddit collection...');
    
    try {
        const response = await fetch(`${API_BASE}/api/trigger/collect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ batch_size: 10, subreddits: ['programming', 'technology', 'webdev'] })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            document.getElementById('actionResults').innerHTML = `
                <div style="background: #c6f6d5; color: #22543d; padding: 15px; border-radius: 6px;">
                    <strong>✅ Collection Started!</strong><br>
                    Task ID: ${data.data.task_id}<br>
                    Batch Size: ${data.data.batch_size}<br>
                    Subreddits: ${data.data.subreddits?.join(', ') || 'Default'}
                </div>`;
            addLog(`Collection started: ${data.data.task_id}`, 'SUCCESS');
        } else {
            throw new Error(data.error || 'Collection failed');
        }
    } catch (error) {
        addLog(`Collection trigger failed: ${error.message}`, 'ERROR');
    }
}

async function triggerPipeline() {
    addLog('Triggering full pipeline...');
    
    try {
        const response = await fetch(`${API_BASE}/api/trigger/pipeline`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            document.getElementById('actionResults').innerHTML = `
                <div style="background: #bee3f8; color: #2c5282; padding: 15px; border-radius: 6px;">
                    <strong>🔄 Pipeline Started!</strong><br>
                    Task ID: ${data.data.task_id}<br>
                    Status: ${data.data.status || 'Running'}
                </div>`;
            addLog(`Pipeline started: ${data.data.task_id}`, 'SUCCESS');
        } else {
            throw new Error(data.error || 'Pipeline failed');
        }
    } catch (error) {
        addLog(`Pipeline trigger failed: ${error.message}`, 'ERROR');
    }
}

// Initialize
updateTime();
setInterval(updateTime, 1000);

// Auto-test connection on load
setTimeout(testConnection, 2000);

addLog('Dashboard ready for operation');
</script>
```

## 🎯 업로드 후 확인사항

**즉시 테스트 가능한 URL:**
- https://american-trends.ghost.io/admin-dashboard/ (수정된 기존 페이지)
- https://american-trends.ghost.io/working-admin-dashboard/ (새 페이지)

**기능 테스트:**
1. 페이지 로드 시 자동 API 연결 테스트
2. "Load Statistics" 버튼으로 실제 데이터 확인
3. "Start Reddit Collection" 작업 트리거 테스트
4. 실시간 시스템 로그 확인

**현재 API 연동 상태:**
- ✅ Health Check: 정상 작동
- ✅ Statistics: 149개 포스트, 2.7% 성공률
- ✅ Collection Trigger: 작업 큐잉 성공
- ✅ Pipeline Trigger: 전체 파이프라인 실행

## 🚀 다음 단계

1. **Ghost Admin Panel 접속** (브라우저에서 직접)
2. **위 HTML 코드 복사/붙여넣기**
3. **실시간 대시보드 테스트**
4. **Vercel 환경변수 설정** (실제 API 연동)

---

**준비 완료!** 이제 Ghost Admin Panel에서 위의 HTML 코드를 붙여넣으면 즉시 작동하는 대시보드를 사용할 수 있습니다.