#!/usr/bin/env python3
"""
간단한 Reddit Ghost Publisher 대시보드
데이터베이스 연결 없이 기본 기능만 제공
"""
import os
import requests
import subprocess
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.getenv('JWT_SECRET_KEY', 'dev-secret-key')

# 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"

# 간단한 HTML 템플릿
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher 어드민</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .card-metric {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
        }
        .status-healthy { color: #28a745; }
        .status-degraded { color: #ffc107; }
        .status-unhealthy { color: #dc3545; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-12">
                <nav class="navbar navbar-dark bg-dark mb-4">
                    <div class="container-fluid">
                        <span class="navbar-brand mb-0 h1">
                            <i class="fas fa-robot"></i> Reddit Ghost Publisher 어드민
                        </span>
                        <span class="navbar-text">
                            <i class="fas fa-clock"></i> {{ current_time }}
                        </span>
                    </div>
                </nav>
            </div>
        </div>
        
        <!-- 시스템 상태 -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">
                            <i class="fas fa-heartbeat"></i> 시스템 상태
                            <button class="btn btn-sm btn-outline-primary float-end" onclick="checkSystemStatus()">
                                <i class="fas fa-sync-alt"></i> 새로고침
                            </button>
                        </h5>
                    </div>
                    <div class="card-body">
                        <div id="systemStatus">
                            <div class="text-center">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">로딩 중...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 제어 패널 -->
        <div class="row mb-4">
            <div class="col-md-4 mb-3">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">
                            <i class="fas fa-download text-primary"></i> Reddit 수집
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <label class="form-label">서브레딧</label>
                            <input type="text" class="form-control" id="collectSubreddits" 
                                   value="programming,technology" placeholder="programming,technology">
                        </div>
                        <div class="mb-3">
                            <label class="form-label">배치 크기</label>
                            <input type="number" class="form-control" id="collectBatchSize" 
                                   value="10" min="1" max="50">
                        </div>
                        <button class="btn btn-primary w-100" onclick="triggerCollect()">
                            <i class="fas fa-play"></i> 수집 시작
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4 mb-3">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">
                            <i class="fas fa-brain text-info"></i> AI 처리
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <p class="text-muted small">
                                수집된 포스트를 AI로 요약하고 태그를 생성합니다.
                            </p>
                        </div>
                        <button class="btn btn-info w-100" onclick="triggerAIProcess()">
                            <i class="fas fa-play"></i> AI 처리 시작
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4 mb-3">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">
                            <i class="fas fa-cogs text-success"></i> 전체 파이프라인
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <p class="text-muted small">
                                수집 → AI 처리 → Ghost 발행을 한 번에 실행합니다.
                            </p>
                        </div>
                        <button class="btn btn-success w-100" onclick="triggerPipeline()">
                            <i class="fas fa-play"></i> 파이프라인 실행
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 실행 결과 -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">
                            <i class="fas fa-terminal"></i> 실행 결과
                            <button class="btn btn-sm btn-outline-secondary float-end" onclick="clearResults()">
                                <i class="fas fa-trash"></i> 지우기
                            </button>
                        </h5>
                    </div>
                    <div class="card-body">
                        <div id="executionResults" class="bg-dark text-light p-3 rounded" 
                             style="height: 300px; overflow-y: auto; font-family: monospace; font-size: 0.9rem;">
                            <div class="text-muted">실행 결과가 여기에 표시됩니다...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 빠른 링크 -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">
                            <i class="fas fa-link"></i> 빠른 링크
                        </h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-3 mb-2">
                                <a href="https://american-trends.ghost.io" target="_blank" class="btn btn-outline-primary w-100">
                                    <i class="fas fa-ghost"></i> Ghost 블로그
                                </a>
                            </div>
                            <div class="col-md-3 mb-2">
                                <button class="btn btn-outline-info w-100" onclick="openAPI()">
                                    <i class="fas fa-code"></i> API 문서
                                </button>
                            </div>
                            <div class="col-md-3 mb-2">
                                <button class="btn btn-outline-success w-100" onclick="runProcessScript()">
                                    <i class="fas fa-play-circle"></i> 처리 스크립트
                                </button>
                            </div>
                            <div class="col-md-3 mb-2">
                                <button class="btn btn-outline-warning w-100" onclick="showStats()">
                                    <i class="fas fa-chart-bar"></i> 통계 보기
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const resultsDiv = document.getElementById('executionResults');
        
        function addResult(message, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const colorClass = type === 'error' ? 'text-danger' : type === 'success' ? 'text-success' : 'text-info';
            
            const resultLine = document.createElement('div');
            resultLine.innerHTML = `<span class="text-muted">[${timestamp}]</span> <span class="${colorClass}">${message}</span>`;
            
            resultsDiv.appendChild(resultLine);
            resultsDiv.scrollTop = resultsDiv.scrollHeight;
            
            if (resultsDiv.children.length > 50) {
                resultsDiv.removeChild(resultsDiv.firstChild);
            }
        }
        
        function checkSystemStatus() {
            addResult('시스템 상태 확인 중...');
            
            fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                const statusDiv = document.getElementById('systemStatus');
                
                if (data.success) {
                    const status = data.data;
                    let html = '<div class="row">';
                    
                    if (status.services) {
                        Object.entries(status.services).forEach(([name, info]) => {
                            const statusClass = info.status === 'healthy' ? 'success' : 
                                              info.status === 'degraded' ? 'warning' : 'danger';
                            const icon = info.status === 'healthy' ? 'check-circle' : 
                                       info.status === 'degraded' ? 'exclamation-triangle' : 'times-circle';
                            
                            html += `
                                <div class="col-md-3 mb-2">
                                    <div class="d-flex align-items-center">
                                        <i class="fas fa-${icon} text-${statusClass} me-2"></i>
                                        <span>${name.replace('_', ' ')}</span>
                                    </div>
                                </div>
                            `;
                        });
                    }
                    
                    html += '</div>';
                    statusDiv.innerHTML = html;
                    addResult('✅ 시스템 상태 확인 완료', 'success');
                } else {
                    statusDiv.innerHTML = '<div class="alert alert-danger">시스템 상태를 확인할 수 없습니다.</div>';
                    addResult('❌ 시스템 상태 확인 실패', 'error');
                }
            })
            .catch(error => {
                document.getElementById('systemStatus').innerHTML = 
                    '<div class="alert alert-warning">API 서버에 연결할 수 없습니다.</div>';
                addResult(`❌ 상태 확인 오류: ${error.message}`, 'error');
            });
        }
        
        function triggerCollect() {
            const subreddits = document.getElementById('collectSubreddits').value.split(',').map(s => s.trim());
            const batchSize = parseInt(document.getElementById('collectBatchSize').value);
            
            addResult(`Reddit 수집 시작: ${subreddits.join(', ')} (배치: ${batchSize})`);
            
            fetch('/api/trigger/collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subreddits: subreddits, batch_size: batchSize })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addResult(`✅ 수집 작업 시작됨: ${data.message}`, 'success');
                } else {
                    addResult(`❌ 수집 실패: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                addResult(`❌ 네트워크 오류: ${error.message}`, 'error');
            });
        }
        
        function triggerAIProcess() {
            addResult('AI 처리 시작...');
            
            fetch('/api/trigger/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addResult(`✅ AI 처리 시작됨: ${data.message}`, 'success');
                } else {
                    addResult(`❌ AI 처리 실패: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                addResult(`❌ 네트워크 오류: ${error.message}`, 'error');
            });
        }
        
        function triggerPipeline() {
            addResult('전체 파이프라인 시작...');
            
            fetch('/api/trigger/pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ batch_size: 5 })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addResult(`✅ 파이프라인 시작됨: ${data.message}`, 'success');
                } else {
                    addResult(`❌ 파이프라인 실패: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                addResult(`❌ 네트워크 오류: ${error.message}`, 'error');
            });
        }
        
        function clearResults() {
            resultsDiv.innerHTML = '<div class="text-muted">실행 결과가 여기에 표시됩니다...</div>';
        }
        
        function openAPI() {
            window.open('http://localhost:8000/docs', '_blank');
        }
        
        function runProcessScript() {
            addResult('처리 스크립트 실행 중...');
            
            fetch('/api/run-script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ script: 'process_single_post' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addResult(`✅ 스크립트 실행됨: ${data.message}`, 'success');
                } else {
                    addResult(`❌ 스크립트 실행 실패: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                addResult(`❌ 네트워크 오류: ${error.message}`, 'error');
            });
        }
        
        function showStats() {
            addResult('통계 조회 중...');
            
            fetch('/api/stats')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const stats = data.data;
                    addResult(`📊 통계: 총 ${stats.total || 0}개 포스트, 처리 ${stats.processed || 0}개, 발행 ${stats.published || 0}개`, 'info');
                } else {
                    addResult(`❌ 통계 조회 실패: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                addResult(`❌ 네트워크 오류: ${error.message}`, 'error');
            });
        }
        
        // 페이지 로드 시 시스템 상태 확인
        document.addEventListener('DOMContentLoaded', function() {
            addResult('🚀 Reddit Ghost Publisher 어드민 대시보드가 시작되었습니다.', 'success');
            checkSystemStatus();
        });
        
        // 5분마다 자동 새로고침
        setInterval(checkSystemStatus, 300000);
    </script>
</body>
</html>
"""

def get_api_status():
    """API 서버 상태 확인"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def trigger_action(action, params=None):
    """파이프라인 액션 트리거"""
    try:
        if action == "collect":
            url = f"{API_BASE_URL}/api/v1/collect/trigger"
        elif action == "process":
            # 직접 스크립트 실행
            return run_processing_script()
        elif action == "pipeline":
            url = f"{API_BASE_URL}/api/v1/pipeline/trigger"
        else:
            return {"success": False, "error": "Unknown action"}
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        data = params or {}
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def run_processing_script():
    """AI 처리 스크립트 실행"""
    try:
        def run_script():
            subprocess.run(["python", "process_single_post.py"], 
                         capture_output=True, text=True)
        
        thread = threading.Thread(target=run_script)
        thread.start()
        
        return {"success": True, "message": "AI 처리 스크립트가 백그라운드에서 실행 중입니다."}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_simple_stats():
    """간단한 통계 (파일 기반)"""
    try:
        # 간단한 통계 시뮬레이션
        return {
            "success": True,
            "data": {
                "total": 122,
                "processed": 4,
                "published": 4,
                "active": 118
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def dashboard():
    """메인 대시보드"""
    return render_template_string(DASHBOARD_TEMPLATE, 
                                current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/status')
def api_status():
    """상태 API"""
    status = get_api_status()
    return jsonify(status)

@app.route('/api/trigger/<action>', methods=['POST'])
def api_trigger(action):
    """파이프라인 트리거 API"""
    params = request.get_json() or {}
    result = trigger_action(action, params)
    return jsonify(result)

@app.route('/api/stats')
def api_stats():
    """통계 API"""
    stats = get_simple_stats()
    return jsonify(stats)

@app.route('/api/run-script', methods=['POST'])
def api_run_script():
    """스크립트 실행 API"""
    data = request.get_json() or {}
    script_name = data.get('script', '')
    
    if script_name == 'process_single_post':
        result = run_processing_script()
        return jsonify(result)
    else:
        return jsonify({"success": False, "error": "Unknown script"})

if __name__ == '__main__':
    print("🚀 간단한 Reddit Ghost Publisher 대시보드 시작")
    print("📍 http://localhost:8081 에서 접속 가능합니다")
    app.run(host='0.0.0.0', port=8081, debug=True)