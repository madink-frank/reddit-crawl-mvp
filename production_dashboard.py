#!/usr/bin/env python3
"""
Production Dashboard Server
간단한 Flask 서버로 대시보드를 호스팅
"""

from flask import Flask, render_template_string
import requests
import json

app = Flask(__name__)

# HTML 템플릿 (인라인으로 포함)
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher - Production Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }
        
        .navbar {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 1rem 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        
        .navbar-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .navbar-brand {
            font-size: 1.5rem;
            font-weight: bold;
        }
        
        .production-badge {
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.8rem;
            margin-left: 1rem;
        }
        
        .main-content {
            padding: 2rem 0;
        }
        
        .card {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
            overflow: hidden;
        }
        
        .card-header {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 1rem;
            font-weight: bold;
        }
        
        .card-body {
            padding: 1.5rem;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            cursor: pointer;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-card.primary { border-left: 5px solid #3498db; }
        .stat-card.info { border-left: 5px solid #17a2b8; }
        .stat-card.success { border-left: 5px solid #28a745; }
        .stat-card.warning { border-left: 5px solid #ffc107; }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: bold;
            margin: 0.5rem 0;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.9rem;
        }
        
        .controls-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .control-card {
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border: 2px solid transparent;
            transition: all 0.3s;
        }
        
        .control-card:hover {
            border-color: #3498db;
            transform: scale(1.02);
        }
        
        .btn {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.3s;
            margin: 0.5rem;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(52, 152, 219, 0.4);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn.success {
            background: linear-gradient(135deg, #27ae60, #2ecc71);
        }
        
        .btn.info {
            background: linear-gradient(135deg, #17a2b8, #138496);
        }
        
        .btn.warning {
            background: linear-gradient(135deg, #f39c12, #e67e22);
        }
        
        .status-indicator {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        
        .status-healthy { background: #d4edda; color: #155724; }
        .status-degraded { background: #fff3cd; color: #856404; }
        .status-unhealthy { background: #f8d7da; color: #721c24; }
        
        .log-section {
            display: none;
            margin-top: 2rem;
        }
        
        .log-output {
            background: #1a1a1a;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            padding: 1rem;
            border-radius: 5px;
            max-height: 300px;
            overflow-y: auto;
            font-size: 0.9rem;
        }
        
        .progress-bar {
            background: #e9ecef;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
            margin: 1rem 0;
        }
        
        .progress-fill {
            background: linear-gradient(135deg, #17a2b8, #138496);
            height: 100%;
            transition: width 0.3s;
            border-radius: 10px;
        }
        
        .alert {
            padding: 1rem;
            border-radius: 5px;
            margin: 1rem 0;
        }
        
        .alert.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .alert.warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        
        .alert.danger {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .text-center { text-align: center; }
        .text-muted { color: #666; }
        .mt-2 { margin-top: 1rem; }
        .mb-2 { margin-bottom: 1rem; }
        
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .controls-grid {
                grid-template-columns: 1fr;
            }
            
            .container {
                padding: 0 10px;
            }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <div class="navbar-content">
                <div class="navbar-brand">
                    🤖 Reddit Ghost Publisher
                    <span class="production-badge">PRODUCTION</span>
                </div>
                <div id="currentTime"></div>
            </div>
        </div>
    </nav>

    <div class="container main-content">
        <!-- 시스템 상태 -->
        <div class="card">
            <div class="card-header">
                ❤️ 시스템 상태 - Production Environment
            </div>
            <div class="card-body">
                <div id="systemStatus">
                    <div class="text-center">
                        <div class="spinner"></div>
                        <p class="mt-2">시스템 상태 확인 중...</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 통계 카드 -->
        <div class="stats-grid">
            <div class="stat-card primary">
                <div class="stat-number" id="totalPosts">122</div>
                <div class="stat-label">총 수집된 포스트</div>
            </div>
            <div class="stat-card info">
                <div class="stat-number" id="aiProcessed">4</div>
                <div class="stat-label">AI 처리 완료</div>
            </div>
            <div class="stat-card success">
                <div class="stat-number" id="published">4</div>
                <div class="stat-label">Ghost 발행 완료</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-number" id="successRate">100%</div>
                <div class="stat-label">성공률</div>
            </div>
        </div>

        <!-- 파이프라인 제어 -->
        <div class="card">
            <div class="card-header">
                ▶️ Production 파이프라인 제어
            </div>
            <div class="card-body">
                <div class="controls-grid">
                    <div class="control-card">
                        <h3>📥 Reddit 수집</h3>
                        <p class="text-muted">새로운 Reddit 포스트를 수집합니다</p>
                        <button class="btn" onclick="triggerCollection()">수집 시작</button>
                    </div>
                    <div class="control-card">
                        <h3>🧠 AI 처리</h3>
                        <p class="text-muted">수집된 포스트를 AI로 요약합니다</p>
                        <button class="btn info" onclick="processPost()">AI 처리 시작</button>
                    </div>
                    <div class="control-card">
                        <h3>🚀 전체 파이프라인</h3>
                        <p class="text-muted">수집 → AI 처리 → Ghost 발행</p>
                        <button class="btn success" onclick="runFullPipeline()">전체 실행</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- 빠른 액션 -->
        <div class="card">
            <div class="card-header">
                🛠️ 빠른 액션 & 모니터링
            </div>
            <div class="card-body">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
                    <div>
                        <h4>빠른 액션</h4>
                        <button class="btn" onclick="refreshData()">🔄 데이터 새로고침</button>
                        <button class="btn success" onclick="viewGhostBlog()">👻 Ghost 블로그 보기</button>
                        <button class="btn warning" onclick="showLogs()">📋 시스템 로그</button>
                        <button class="btn info" onclick="checkHealth()">❤️ 헬스체크</button>
                    </div>
                    <div>
                        <h4>실시간 모니터링</h4>
                        <p>API 상태: <span id="apiStatus" class="status-indicator">확인 중</span></p>
                        <p>마지막 업데이트: <span id="lastUpdate" class="text-muted">-</span></p>
                        <div class="progress-bar">
                            <div id="processingProgress" class="progress-fill" style="width: 3%"></div>
                        </div>
                        <small class="text-muted">처리 진행률 (4/122)</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- 로그 섹션 -->
        <div id="logSection" class="log-section">
            <div class="card">
                <div class="card-header">
                    💻 Production 시스템 로그
                    <button class="btn" onclick="clearLogs()" style="float: right; padding: 0.25rem 0.75rem;">지우기</button>
                </div>
                <div class="card-body">
                    <div id="logOutput" class="log-output">
                        Production 시스템 로그가 여기에 표시됩니다...
                    </div>
                </div>
            </div>
        </div>

        <!-- Production 정보 -->
        <div class="alert success">
            <strong>🚀 Production 환경:</strong> 
            Reddit Ghost Publisher가 실제 운영 환경에서 실행되고 있습니다. 
            모든 작업은 실제 데이터에 영향을 미칩니다.
            <br><small class="text-muted">
                API 서버: http://localhost:8000 | 
                Ghost 블로그: https://american-trends.ghost.io |
                환경: Production
            </small>
        </div>
    </div>

    <script>
        // 설정
        const API_BASE_URL = 'http://localhost:8000';
        const API_KEY = 'reddit-publisher-api-key-2024';
        
        // 현재 시간 업데이트
        function updateTime() {
            document.getElementById('currentTime').textContent = new Date().toLocaleString('ko-KR');
        }
        
        // API 헤더
        function getHeaders() {
            return {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            };
        }
        
        // 로그 추가
        function addLog(message, type = 'info') {
            const logOutput = document.getElementById('logOutput');
            const timestamp = new Date().toLocaleTimeString();
            const color = type === 'error' ? '#ff6b6b' : type === 'success' ? '#51cf66' : '#74c0fc';
            
            logOutput.innerHTML += `<div style="color: ${color}">[${timestamp}] ${message}</div>`;
            logOutput.scrollTop = logOutput.scrollHeight;
        }
        
        // 시스템 상태 확인
        async function checkSystemStatus() {
            try {
                const response = await fetch(`${API_BASE_URL}/health`);
                const data = await response.json();
                
                let statusHtml = '';
                if (response.ok) {
                    const status = data.status;
                    const statusClass = status === 'healthy' ? 'success' : status === 'degraded' ? 'warning' : 'danger';
                    
                    // 서비스별 상태 표시
                    let servicesHtml = '';
                    if (data.services) {
                        servicesHtml = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-top: 1rem;">';
                        for (const [serviceName, serviceData] of Object.entries(data.services)) {
                            const serviceStatus = serviceData.status;
                            const serviceClass = serviceStatus === 'healthy' ? 'status-healthy' : serviceStatus === 'degraded' ? 'status-degraded' : 'status-unhealthy';
                            servicesHtml += `
                                <div class="text-center">
                                    <div class="${serviceClass} status-indicator">${serviceName}</div>
                                    <br><small class="text-muted">${serviceData.response_time_ms?.toFixed(1) || 0}ms</small>
                                </div>
                            `;
                        }
                        servicesHtml += '</div>';
                    }
                    
                    statusHtml = `
                        <div class="alert ${statusClass}">
                            <strong>시스템 상태: ${status.toUpperCase()}</strong>
                            <br><small>환경: ${data.environment || 'production'} | 업타임: ${data.uptime_seconds || 0}초</small>
                            ${servicesHtml}
                        </div>
                    `;
                    
                    document.getElementById('apiStatus').className = `status-indicator status-${statusClass}`;
                    document.getElementById('apiStatus').textContent = status;
                } else {
                    statusHtml = '<div class="alert danger">API 서버 연결 실패</div>';
                    document.getElementById('apiStatus').className = 'status-indicator status-unhealthy';
                    document.getElementById('apiStatus').textContent = 'offline';
                }
                
                document.getElementById('systemStatus').innerHTML = statusHtml;
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                
            } catch (error) {
                document.getElementById('systemStatus').innerHTML = 
                    '<div class="alert danger">네트워크 연결 오류</div>';
                document.getElementById('apiStatus').className = 'status-indicator status-unhealthy';
                document.getElementById('apiStatus').textContent = 'error';
                addLog(`상태 확인 실패: ${error.message}`, 'error');
            }
        }
        
        // Reddit 수집 트리거
        async function triggerCollection() {
            const button = event.target;
            const originalText = button.textContent;
            
            button.textContent = '수집 중...';
            button.disabled = true;
            
            addLog('Production 환경에서 Reddit 포스트 수집을 시작합니다...', 'info');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/v1/collect/trigger`, {
                    method: 'POST',
                    headers: getHeaders(),
                    body: JSON.stringify({ batch_size: 10 })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    addLog(`수집 성공: ${result.message}`, 'success');
                    if (result.task_id) {
                        addLog(`작업 ID: ${result.task_id}`, 'info');
                    }
                } else {
                    addLog(`수집 실패: ${result.error || result.detail}`, 'error');
                }
            } catch (error) {
                addLog(`네트워크 오류: ${error.message}`, 'error');
            } finally {
                button.textContent = originalText;
                button.disabled = false;
            }
        }
        
        // AI 포스트 처리
        async function processPost() {
            addLog('Production 환경에서 AI 포스트 처리를 시작합니다...', 'info');
            alert('AI 처리는 백그라운드 워커에서 자동으로 실행됩니다.');
        }
        
        // 전체 파이프라인 실행
        async function runFullPipeline() {
            const button = event.target;
            const originalText = button.textContent;
            
            button.textContent = '실행 중...';
            button.disabled = true;
            
            addLog('Production 환경에서 전체 파이프라인을 시작합니다...', 'info');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/v1/pipeline/trigger`, {
                    method: 'POST',
                    headers: getHeaders(),
                    body: JSON.stringify({ batch_size: 3 })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    addLog(`파이프라인 시작: ${result.message}`, 'success');
                    if (result.task_id) {
                        addLog(`작업 ID: ${result.task_id}`, 'info');
                    }
                } else {
                    addLog(`파이프라인 실패: ${result.error || result.detail}`, 'error');
                }
            } catch (error) {
                addLog(`네트워크 오류: ${error.message}`, 'error');
            } finally {
                button.textContent = originalText;
                button.disabled = false;
            }
        }
        
        // 데이터 새로고침
        function refreshData() {
            addLog('데이터를 새로고침합니다...', 'info');
            checkSystemStatus();
        }
        
        // Ghost 블로그 보기
        function viewGhostBlog() {
            addLog('Ghost 블로그를 새 창에서 엽니다...', 'info');
            window.open('https://american-trends.ghost.io', '_blank');
        }
        
        // 로그 표시/숨기기
        function showLogs() {
            const logSection = document.getElementById('logSection');
            logSection.style.display = logSection.style.display === 'none' ? 'block' : 'none';
            
            if (logSection.style.display === 'block') {
                addLog('Production 시스템 로그를 표시합니다...', 'info');
            }
        }
        
        // 로그 지우기
        function clearLogs() {
            document.getElementById('logOutput').innerHTML = 'Production 로그가 지워졌습니다...<br>';
        }
        
        // 헬스체크
        function checkHealth() {
            addLog('Production 헬스체크를 실행합니다...', 'info');
            checkSystemStatus();
        }
        
        // 초기화
        function init() {
            updateTime();
            checkSystemStatus();
            addLog('Reddit Ghost Publisher Production Dashboard가 시작되었습니다.', 'success');
            
            // 자동 업데이트 (30초마다)
            setInterval(() => {
                updateTime();
                checkSystemStatus();
            }, 30000);
            
            // 시간 업데이트 (1초마다)
            setInterval(updateTime, 1000);
        }
        
        // 페이지 로드 시 초기화
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Production 대시보드"""
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/health')
def health():
    """헬스체크 프록시"""
    try:
        response = requests.get('http://localhost:8000/health', timeout=5)
        return response.json(), response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    print("🚀 Reddit Ghost Publisher Production Dashboard")
    print("📊 대시보드 접속: http://localhost:8083")
    print("🔗 API 서버: http://localhost:8000")
    print("👻 Ghost 블로그: https://american-trends.ghost.io")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=8083, debug=False)