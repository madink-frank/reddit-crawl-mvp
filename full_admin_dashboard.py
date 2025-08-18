#!/usr/bin/env python3
"""
완전한 어드민 대시보드 - 파이프라인 제어 기능 포함
"""
import os
import psycopg2
import requests
import subprocess
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'reddit_publisher',
    'user': 'reddit_publisher',
    'password': 'reddit_publisher_prod_2024'
}

def get_db_connection():
    """데이터베이스 연결"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"DB 연결 오류: {e}")
        return None

def get_system_stats():
    """시스템 통계 조회"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        # 기본 통계
        cursor.execute("""
            SELECT 
                COUNT(*) as total_posts,
                COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published,
                COUNT(CASE WHEN takedown_status = 'active' THEN 1 END) as active_posts
            FROM posts
        """)
        
        total, ai_processed, published, active = cursor.fetchone()
        
        # 오늘 통계
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE THEN 1 END) as today_collected,
                COUNT(CASE WHEN DATE(updated_at) = CURRENT_DATE AND summary_ko IS NOT NULL THEN 1 END) as today_processed,
                COUNT(CASE WHEN DATE(published_at) = CURRENT_DATE THEN 1 END) as today_published
            FROM posts
        """)
        
        today_collected, today_processed, today_published = cursor.fetchone()
        
        # 처리 대기 중인 포스트
        cursor.execute("""
            SELECT COUNT(*) FROM posts 
            WHERE summary_ko IS NULL AND takedown_status = 'active'
        """)
        pending_processing = cursor.fetchone()[0]
        
        # 발행 대기 중인 포스트
        cursor.execute("""
            SELECT COUNT(*) FROM posts 
            WHERE summary_ko IS NOT NULL AND ghost_url IS NULL AND takedown_status = 'active'
        """)
        pending_publishing = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_posts': total,
            'ai_processed': ai_processed,
            'published': published,
            'active_posts': active,
            'today_collected': today_collected,
            'today_processed': today_processed,
            'today_published': today_published,
            'pending_processing': pending_processing,
            'pending_publishing': pending_publishing,
            'success_rate': round((published / total * 100) if total > 0 else 0, 1)
        }
        
    except Exception as e:
        print(f"통계 조회 오류: {e}")
        return None

def get_api_status():
    """API 서버 상태 확인"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}

def trigger_pipeline_action(action, params=None):
    """파이프라인 액션 트리거"""
    try:
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        data = params or {}
        
        if action == "collect":
            url = f"{API_BASE_URL}/api/v1/collect/trigger"
            data.setdefault('batch_size', 10)
            data.setdefault('subreddits', ['programming', 'technology', 'webdev'])
        elif action == "process":
            # AI 처리를 위한 직접 스크립트 실행 (params 무시)
            return run_ai_processing()
        elif action == "pipeline":
            url = f"{API_BASE_URL}/api/v1/pipeline/trigger"
            data.setdefault('batch_size', 3)
        else:
            return {"success": False, "error": "Unknown action"}
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def run_ai_processing():
    """AI 처리 스크립트 실행 (모의 처리 사용)"""
    try:
        # 백그라운드에서 모의 AI 처리 스크립트 실행
        def run_script():
            try:
                result = subprocess.run(
                    ["python", "mock_ai_processor.py"], 
                    capture_output=True, 
                    text=True,
                    timeout=30
                )
                print(f"모의 AI 처리 결과: {result.returncode}")
                if result.stdout:
                    print(f"출력: {result.stdout}")
                if result.stderr:
                    print(f"오류: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("모의 AI 처리 타임아웃")
            except Exception as e:
                print(f"모의 AI 처리 스크립트 오류: {e}")
        
        thread = threading.Thread(target=run_script)
        thread.start()
        
        return {"success": True, "message": "모의 AI 처리 스크립트가 백그라운드에서 실행 중입니다."}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def dashboard():
    """메인 대시보드"""
    stats = get_system_stats()
    api_status = get_api_status()
    
    html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher - 완전한 어드민 대시보드</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .card-stat { 
            transition: transform 0.2s; 
            cursor: pointer;
        }
        .card-stat:hover { 
            transform: translateY(-2px); 
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .action-card {
            border: 2px solid transparent;
            transition: all 0.3s;
        }
        .action-card:hover {
            border-color: var(--bs-primary);
            transform: scale(1.02);
        }
        .log-output {
            background: #1e1e1e;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
        }
        .status-healthy { color: #28a745; }
        .status-degraded { color: #ffc107; }
        .status-unhealthy { color: #dc3545; }
    </style>
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark shadow">
        <div class="container">
            <span class="navbar-brand">
                <i class="fas fa-robot text-primary"></i> Reddit Ghost Publisher
                <small class="text-muted">완전한 어드민 대시보드</small>
            </span>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text">
                    <i class="fas fa-clock"></i> <span id="currentTime">{{ current_time }}</span>
                </span>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% if stats %}
        <!-- 시스템 상태 -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card shadow-sm">
                    <div class="card-header bg-primary text-white">
                        <h5 class="mb-0"><i class="fas fa-heartbeat"></i> 시스템 상태</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <h6>API 서버 상태</h6>
                                {% if api_status.status == 'healthy' %}
                                    <span class="badge bg-success">정상</span>
                                {% elif api_status.status == 'degraded' %}
                                    <span class="badge bg-warning">제한적</span>
                                {% else %}
                                    <span class="badge bg-danger">오류</span>
                                {% endif %}
                            </div>
                            <div class="col-md-6">
                                <h6>데이터베이스</h6>
                                <span class="badge bg-success">연결됨</span>
                            </div>
                        </div>
                        {% if api_status.services %}
                        <hr>
                        <h6>서비스 상태</h6>
                        <div class="row">
                            {% for service, info in api_status.services.items() %}
                            <div class="col-md-2">
                                <small>{{ service }}</small><br>
                                {% if info.status == 'healthy' %}
                                    <span class="badge bg-success">정상</span>
                                {% elif info.status == 'degraded' %}
                                    <span class="badge bg-warning">제한적</span>
                                {% else %}
                                    <span class="badge bg-danger">오류</span>
                                {% endif %}
                            </div>
                            {% endfor %}
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <!-- 통계 카드 -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card card-stat bg-primary text-white shadow">
                    <div class="card-body text-center">
                        <i class="fas fa-database fa-2x mb-2"></i>
                        <h3>{{ stats.total_posts }}</h3>
                        <p class="mb-0">총 수집된 포스트</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card card-stat bg-info text-white shadow">
                    <div class="card-body text-center">
                        <i class="fas fa-robot fa-2x mb-2"></i>
                        <h3>{{ stats.ai_processed }}</h3>
                        <p class="mb-0">AI 처리 완료</p>
                        <small>대기: {{ stats.pending_processing }}개</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card card-stat bg-success text-white shadow">
                    <div class="card-body text-center">
                        <i class="fas fa-blog fa-2x mb-2"></i>
                        <h3>{{ stats.published }}</h3>
                        <p class="mb-0">Ghost 발행 완료</p>
                        <small>대기: {{ stats.pending_publishing }}개</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card card-stat bg-warning text-white shadow">
                    <div class="card-body text-center">
                        <i class="fas fa-percentage fa-2x mb-2"></i>
                        <h3>{{ stats.success_rate }}%</h3>
                        <p class="mb-0">성공률</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 파이프라인 제어 -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card shadow-sm">
                    <div class="card-header bg-success text-white">
                        <h5 class="mb-0"><i class="fas fa-play-circle"></i> 파이프라인 제어</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-4">
                                <div class="card action-card border-primary h-100">
                                    <div class="card-body text-center">
                                        <i class="fas fa-download fa-3x text-primary mb-3"></i>
                                        <h6>Reddit 수집</h6>
                                        <p class="text-muted small">새로운 Reddit 포스트를 수집합니다</p>
                                        <button class="btn btn-primary" onclick="triggerCollection()">
                                            <i class="fas fa-play"></i> 수집 시작
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card action-card border-info h-100">
                                    <div class="card-body text-center">
                                        <i class="fas fa-brain fa-3x text-info mb-3"></i>
                                        <h6>AI 처리</h6>
                                        <p class="text-muted small">수집된 포스트를 AI로 요약합니다</p>
                                        <button class="btn btn-info" onclick="processPost()">
                                            <i class="fas fa-robot"></i> AI 처리 시작
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card action-card border-success h-100">
                                    <div class="card-body text-center">
                                        <i class="fas fa-rocket fa-3x text-success mb-3"></i>
                                        <h6>전체 파이프라인</h6>
                                        <p class="text-muted small">수집 → AI 처리 → Ghost 발행</p>
                                        <button class="btn btn-success" onclick="runFullPipeline()">
                                            <i class="fas fa-play"></i> 전체 실행
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 빠른 액션 -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card shadow-sm">
                    <div class="card-header bg-info text-white">
                        <h5 class="mb-0"><i class="fas fa-tools"></i> 빠른 액션</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-grid gap-2">
                            <button class="btn btn-outline-primary" onclick="refreshData()">
                                <i class="fas fa-sync"></i> 데이터 새로고침
                            </button>
                            <button class="btn btn-outline-success" onclick="viewGhostBlog()">
                                <i class="fas fa-external-link-alt"></i> Ghost 블로그 보기
                            </button>
                            <button class="btn btn-outline-warning" onclick="showLogs()">
                                <i class="fas fa-file-alt"></i> 시스템 로그
                            </button>
                            <button class="btn btn-outline-info" onclick="checkHealth()">
                                <i class="fas fa-heartbeat"></i> 헬스체크
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card shadow-sm">
                    <div class="card-header bg-warning text-dark">
                        <h5 class="mb-0"><i class="fas fa-chart-line"></i> 오늘 활동</h5>
                    </div>
                    <div class="card-body">
                        <div class="row text-center">
                            <div class="col-4">
                                <h4 class="text-primary">{{ stats.today_collected }}</h4>
                                <p class="text-muted small">수집</p>
                            </div>
                            <div class="col-4">
                                <h4 class="text-info">{{ stats.today_processed }}</h4>
                                <p class="text-muted small">AI 처리</p>
                            </div>
                            <div class="col-4">
                                <h4 class="text-success">{{ stats.today_published }}</h4>
                                <p class="text-muted small">발행</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 로그 출력 -->
        <div class="row mb-4" id="logSection" style="display: none;">
            <div class="col-md-12">
                <div class="card shadow-sm">
                    <div class="card-header bg-dark text-white">
                        <h5 class="mb-0">
                            <i class="fas fa-terminal"></i> 시스템 로그
                            <button class="btn btn-sm btn-outline-light float-end" onclick="clearLogs()">
                                <i class="fas fa-trash"></i> 지우기
                            </button>
                        </h5>
                    </div>
                    <div class="card-body p-0">
                        <div id="logOutput" class="log-output p-3">
                            완전한 어드민 대시보드가 시작되었습니다...<br>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        {% else %}
        <!-- 오류 상태 -->
        <div class="row">
            <div class="col-md-12">
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i> 
                    <strong>데이터베이스 연결 오류</strong>
                    <br>시스템 관리자에게 문의하세요.
                </div>
            </div>
        </div>
        {% endif %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 설정
        const API_BASE_URL = 'http://localhost:8082';
        
        // 현재 시간 업데이트
        function updateTime() {
            document.getElementById('currentTime').textContent = new Date().toLocaleString('ko-KR');
        }
        
        // 로그 추가
        function addLog(message, type = 'info') {
            const logOutput = document.getElementById('logOutput');
            const timestamp = new Date().toLocaleTimeString();
            const color = type === 'error' ? '#ff6b6b' : type === 'success' ? '#51cf66' : '#74c0fc';
            
            logOutput.innerHTML += `<div style="color: ${color}">[${timestamp}] ${message}</div>`;
            logOutput.scrollTop = logOutput.scrollHeight;
        }
        
        // Reddit 수집 트리거
        async function triggerCollection() {
            const button = event.target;
            const originalText = button.innerHTML;
            
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 수집 중...';
            button.disabled = true;
            
            addLog('Reddit 포스트 수집을 시작합니다...', 'info');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/trigger/collect`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ batch_size: 10 })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    addLog(`수집 성공: ${result.message || '수집이 시작되었습니다.'}`, 'success');
                    setTimeout(refreshData, 3000);
                } else {
                    addLog(`수집 실패: ${result.error}`, 'error');
                }
            } catch (error) {
                addLog(`네트워크 오류: ${error.message}`, 'error');
            } finally {
                button.innerHTML = originalText;
                button.disabled = false;
            }
        }
        
        // AI 포스트 처리
        async function processPost() {
            const button = event.target;
            const originalText = button.innerHTML;
            
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 처리 중...';
            button.disabled = true;
            
            addLog('AI 포스트 처리를 시작합니다...', 'info');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/trigger/process`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const result = await response.json();
                
                if (result.success) {
                    addLog(`AI 처리 시작: ${result.message}`, 'success');
                    setTimeout(refreshData, 5000);
                } else {
                    addLog(`AI 처리 실패: ${result.error}`, 'error');
                }
            } catch (error) {
                addLog(`AI 처리 오류: ${error.message}`, 'error');
            } finally {
                button.innerHTML = originalText;
                button.disabled = false;
            }
        }
        
        // 전체 파이프라인 실행
        async function runFullPipeline() {
            const button = event.target;
            const originalText = button.innerHTML;
            
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 실행 중...';
            button.disabled = true;
            
            addLog('전체 파이프라인을 시작합니다...', 'info');
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/trigger/pipeline`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ batch_size: 3 })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    addLog(`파이프라인 시작: ${result.message || '파이프라인이 시작되었습니다.'}`, 'success');
                    setTimeout(refreshData, 5000);
                } else {
                    addLog(`파이프라인 실패: ${result.error}`, 'error');
                }
            } catch (error) {
                addLog(`네트워크 오류: ${error.message}`, 'error');
            } finally {
                button.innerHTML = originalText;
                button.disabled = false;
            }
        }
        
        // 데이터 새로고침
        function refreshData() {
            addLog('데이터를 새로고침합니다...', 'info');
            location.reload();
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
                addLog('시스템 로그를 표시합니다...', 'info');
            }
        }
        
        // 로그 지우기
        function clearLogs() {
            document.getElementById('logOutput').innerHTML = '로그가 지워졌습니다...<br>';
        }
        
        // 헬스체크
        async function checkHealth() {
            addLog('헬스체크를 실행합니다...', 'info');
            try {
                const response = await fetch(`${API_BASE_URL}/health`);
                const data = await response.json();
                if (data.status === 'healthy') {
                    addLog('시스템 상태: 정상', 'success');
                } else {
                    addLog('시스템 상태: 문제 있음', 'error');
                }
            } catch (error) {
                addLog(`헬스체크 오류: ${error.message}`, 'error');
            }
        }
        
        // 초기화
        function init() {
            updateTime();
            addLog('완전한 어드민 대시보드가 시작되었습니다.', 'success');
            
            // 시간 업데이트 (1초마다)
            setInterval(updateTime, 1000);
        }
        
        // 페이지 로드 시 초기화
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
    """
    
    return render_template_string(
        html_template, 
        stats=stats,
        api_status=api_status,
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/api/stats')
def api_stats():
    """통계 API"""
    stats = get_system_stats()
    if stats:
        return jsonify({
            'success': True,
            'data': stats,
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Database connection failed'
        }), 500

@app.route('/api/trigger/<action>', methods=['POST'])
def api_trigger(action):
    """파이프라인 트리거 API"""
    params = request.get_json() or {}
    result = trigger_pipeline_action(action, params)
    return jsonify(result)

@app.route('/health')
def health():
    """헬스체크"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected'
        })
    else:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'disconnected'
        }), 500

if __name__ == '__main__':
    print("🚀 Reddit Ghost Publisher 완전한 어드민 대시보드")
    print("📊 대시보드 URL: http://localhost:8082")
    print("🔗 API URL: http://localhost:8082/api/stats")
    print("🎮 파이프라인 제어 기능 포함")
    print("=" * 50)
    
    app.run(debug=False, host='0.0.0.0', port=8082)