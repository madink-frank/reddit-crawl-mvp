module.exports = (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, X-Requested-With');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  // Serve the production dashboard HTML directly
  const dashboardHtml = `<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher - Production Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --success-color: #27ae60;
            --warning-color: #f39c12;
            --danger-color: #e74c3c;
            --dark-color: #34495e;
        }

        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        .dashboard-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            margin: 20px;
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--dark-color) 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 300;
        }

        .status-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }

        .status-card:hover {
            transform: translateY(-5px);
        }

        .metric-value {
            font-size: 2.5rem;
            font-weight: bold;
            margin: 10px 0;
        }

        .btn-action {
            padding: 12px 30px;
            font-size: 1.1rem;
            border-radius: 25px;
            margin: 10px;
            transition: all 0.3s ease;
        }

        .btn-action:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }

        .log-container {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
        }

        .log-entry {
            padding: 5px 0;
            border-bottom: 1px solid #e9ecef;
        }

        .log-entry:last-child {
            border-bottom: none;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-online {
            background-color: var(--success-color);
        }

        .status-offline {
            background-color: var(--danger-color);
        }

        .status-warning {
            background-color: var(--warning-color);
        }
    </style>
</head>

<body>
    <div class="dashboard-container">
        <!-- Header -->
        <div class="header">
            <h1><i class="fab fa-reddit"></i> Reddit Ghost Publisher</h1>
            <p class="mb-0">Production Dashboard - Vercel Deployment</p>
        </div>

        <!-- Main Content -->
        <div class="container-fluid p-4">
            <!-- System Status Row -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="status-card">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h4><i class="fas fa-server"></i> 시스템 상태</h4>
                                <div id="systemStatus">
                                    <span class="status-indicator status-offline"></span>
                                    <span id="statusText">연결 확인 중...</span>
                                </div>
                            </div>
                            <div>
                                <button class="btn btn-primary btn-action" onclick="checkSystemHealth()">
                                    <i class="fas fa-sync-alt"></i> 상태 확인
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Metrics Row -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="status-card text-center">
                        <i class="fas fa-download fa-2x text-primary mb-2"></i>
                        <h6>수집된 게시글</h6>
                        <div class="metric-value text-primary" id="collectedCount">-</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="status-card text-center">
                        <i class="fas fa-robot fa-2x text-success mb-2"></i>
                        <h6>AI 처리 완료</h6>
                        <div class="metric-value text-success" id="processedCount">-</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="status-card text-center">
                        <i class="fas fa-ghost fa-2x text-info mb-2"></i>
                        <h6>Ghost 발행</h6>
                        <div class="metric-value text-info" id="publishedCount">-</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="status-card text-center">
                        <i class="fas fa-chart-line fa-2x text-warning mb-2"></i>
                        <h6>성공률</h6>
                        <div class="metric-value text-warning" id="successRate">-</div>
                    </div>
                </div>
            </div>

            <!-- Action Buttons Row -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="status-card">
                        <h4><i class="fas fa-play-circle"></i> 빠른 작업</h4>
                        <div class="text-center">
                            <button class="btn btn-success btn-action" onclick="startRedditCollection()" id="collectBtn">
                                <i class="fas fa-reddit"></i> Reddit 수집 시작
                            </button>
                            <button class="btn btn-info btn-action" onclick="runFullPipeline()" id="pipelineBtn">
                                <i class="fas fa-cogs"></i> 전체 파이프라인 실행
                            </button>
                            <button class="btn btn-warning btn-action" onclick="viewGhostBlog()">
                                <i class="fas fa-external-link-alt"></i> Ghost 블로그 보기
                            </button>
                        </div>
                        <div class="mt-3">
                            <div id="actionStatus" class="alert alert-info" style="display: none;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Logs Row -->
            <div class="row">
                <div class="col-12">
                    <div class="status-card">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h4><i class="fas fa-terminal"></i> 시스템 로그</h4>
                            <button class="btn btn-sm btn-outline-secondary" onclick="clearLogs()">
                                <i class="fas fa-trash"></i> 로그 지우기
                            </button>
                        </div>
                        <div id="systemLogs" class="log-container">
                            <div class="log-entry">
                                <span class="text-muted">[INFO]</span> Production 대시보드 초기화 완료
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        // API Base URL - Same domain for Vercel
        const API_BASE = window.location.origin;

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function () {
            checkSystemHealth();
            addLog('Production 대시보드 초기화 완료', 'info');
            
            // Auto-refresh every 30 seconds
            setInterval(updateMetrics, 30000);
        });

        // System health check
        async function checkSystemHealth() {
            try {
                addLog('시스템 상태 확인 중...', 'info');

                const response = await fetch(API_BASE + '/api/health');
                const data = await response.json();

                if (response.ok) {
                    updateSystemStatus('online', '시스템 정상 작동 중');
                    addLog('시스템 상태: 정상', 'success');
                    updateMetrics();
                } else {
                    updateSystemStatus('warning', '시스템 경고 상태');
                    addLog('시스템 상태: 경고', 'warning');
                }
            } catch (error) {
                updateSystemStatus('offline', '시스템 연결 실패');
                addLog('시스템 연결 실패: ' + error.message, 'error');
            }
        }

        // Update system status indicator
        function updateSystemStatus(status, message) {
            const indicator = document.querySelector('.status-indicator');
            const statusText = document.getElementById('statusText');

            indicator.className = 'status-indicator status-' + status;
            statusText.textContent = message;
        }

        // Start Reddit collection
        async function startRedditCollection() {
            const btn = document.getElementById('collectBtn');
            const originalText = btn.innerHTML;

            try {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 수집 중...';

                addLog('Reddit 수집 시작...', 'info');
                showActionStatus('Reddit 게시글 수집을 시작합니다...', 'info');

                const response = await fetch(API_BASE + '/api/reddit-collect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        subreddits: ['programming', 'technology', 'webdev'],
                        limit: 10
                    })
                });

                const data = await response.json();

                if (data.success) {
                    addLog('Reddit 수집 성공: ' + data.data.collected_posts + '개 게시글 수집', 'success');
                    showActionStatus('Reddit 수집 완료: ' + data.data.collected_posts + '개 게시글이 수집되었습니다.', 'success');
                    updateMetrics();
                } else {
                    addLog('Reddit 수집 실패: ' + data.error, 'error');
                    showActionStatus('수집 실패: ' + data.error, 'danger');
                }
            } catch (error) {
                addLog('Reddit 수집 오류: ' + error.message, 'error');
                showActionStatus('수집 오류: ' + error.message, 'danger');
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }

        // Run full pipeline
        async function runFullPipeline() {
            const btn = document.getElementById('pipelineBtn');
            const originalText = btn.innerHTML;

            try {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 실행 중...';

                addLog('전체 파이프라인 실행 시작...', 'info');
                showActionStatus('전체 파이프라인을 실행합니다 (수집 → AI 처리 → Ghost 발행)...', 'info');

                // Step 1: Reddit Collection
                addLog('1단계: Reddit 수집 중...', 'info');
                const collectResponse = await fetch(API_BASE + '/api/reddit-collect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        subreddits: ['programming', 'technology', 'webdev'],
                        limit: 5
                    })
                });

                const collectData = await collectResponse.json();
                if (!collectData.success) {
                    throw new Error('Reddit 수집 실패: ' + collectData.error);
                }

                addLog('✅ Reddit 수집 완료: ' + collectData.data.collected_posts + '개 게시글', 'success');

                // Step 2 & 3: Process and Publish each post
                let processedCount = 0;
                let publishedCount = 0;

                for (let i = 0; i < Math.min(collectData.data.posts.length, 3); i++) {
                    const post = collectData.data.posts[i];
                    try {
                        addLog('AI 처리 중: "' + post.title.substring(0, 50) + '..."', 'info');
                        
                        // AI Processing
                        const aiResponse = await fetch(API_BASE + '/api/ai-process', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                title: post.title,
                                content: post.selftext || post.url,
                                subreddit: post.subreddit
                            })
                        });

                        const aiData = await aiResponse.json();
                        if (aiData.success) {
                            processedCount++;
                            addLog('✅ AI 처리 완료: "' + post.title.substring(0, 50) + '..."', 'success');

                            // Ghost Publishing
                            addLog('Ghost 발행 중: "' + aiData.data.korean_summary.substring(0, 50) + '..."', 'info');
                            
                            const ghostResponse = await fetch(API_BASE + '/api/ghost-publish', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    title: post.title,
                                    content: aiData.data.korean_summary,
                                    tags: aiData.data.tags
                                })
                            });

                            const ghostData = await ghostResponse.json();
                            if (ghostData.success && ghostData.data.published) {
                                publishedCount++;
                                addLog('✅ Ghost 발행 완료: ' + ghostData.data.ghost_url, 'success');
                            } else {
                                addLog('⚠️ Ghost 발행 실패: ' + (ghostData.error || 'Unknown error'), 'warning');
                            }
                        } else {
                            addLog('❌ AI 처리 실패: ' + aiData.error, 'error');
                        }
                    } catch (postError) {
                        addLog('❌ 게시글 처리 오류: ' + postError.message, 'error');
                    }
                }

                addLog('🎉 파이프라인 완료! 수집: ' + collectData.data.collected_posts + ', 처리: ' + processedCount + ', 발행: ' + publishedCount, 'success');
                showActionStatus('파이프라인 완료! ' + publishedCount + '개 게시글이 Ghost에 발행되었습니다.', 'success');

                updateMetrics();

            } catch (error) {
                addLog('파이프라인 오류: ' + error.message, 'error');
                showActionStatus('파이프라인 오류: ' + error.message, 'danger');
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }

        // Update metrics
        async function updateMetrics() {
            try {
                const response = await fetch(API_BASE + '/api/stats');
                const data = await response.json();

                if (response.ok) {
                    document.getElementById('collectedCount').textContent = data.total_posts || 0;
                    document.getElementById('processedCount').textContent = data.processed_posts || 0;
                    document.getElementById('publishedCount').textContent = data.published_posts || 0;

                    const successRate = data.total_posts > 0 ?
                        Math.round((data.published_posts / data.total_posts) * 100) : 0;
                    document.getElementById('successRate').textContent = successRate + '%';

                    if (data.total_posts > 0) {
                        addLog('통계 업데이트: 수집 ' + data.total_posts + ', 처리 ' + data.processed_posts + ', 발행 ' + data.published_posts, 'info');
                    }
                }
            } catch (error) {
                addLog('통계 업데이트 실패: ' + error.message, 'error');
            }
        }

        // Show action status
        function showActionStatus(message, type) {
            const statusDiv = document.getElementById('actionStatus');
            statusDiv.className = 'alert alert-' + type;
            statusDiv.textContent = message;
            statusDiv.style.display = 'block';

            setTimeout(function() {
                statusDiv.style.display = 'none';
            }, 10000);
        }

        // Add log entry
        function addLog(message, type) {
            type = type || 'info';
            const logsContainer = document.getElementById('systemLogs');
            const timestamp = new Date().toLocaleTimeString();

            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';

            let typeClass = 'text-muted';
            let typeLabel = 'INFO';

            switch (type) {
                case 'success':
                    typeClass = 'text-success';
                    typeLabel = 'SUCCESS';
                    break;
                case 'warning':
                    typeClass = 'text-warning';
                    typeLabel = 'WARNING';
                    break;
                case 'error':
                    typeClass = 'text-danger';
                    typeLabel = 'ERROR';
                    break;
            }

            logEntry.innerHTML = '<span class="text-muted">[' + timestamp + ']</span> <span class="' + typeClass + '">[' + typeLabel + ']</span> ' + message;

            logsContainer.appendChild(logEntry);
            logsContainer.scrollTop = logsContainer.scrollHeight;

            while (logsContainer.children.length > 100) {
                logsContainer.removeChild(logsContainer.firstChild);
            }
        }

        // Clear logs
        function clearLogs() {
            document.getElementById('systemLogs').innerHTML = '';
            addLog('로그가 지워졌습니다', 'info');
        }

        // View Ghost blog
        function viewGhostBlog() {
            window.open('https://american-trends.ghost.io', '_blank');
            addLog('Ghost 블로그 열기', 'info');
        }
    </script>
</body>
</html>`;
  
  res.setHeader('Content-Type', 'text/html');
  return res.status(200).send(dashboardHtml);
};