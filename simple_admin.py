#!/usr/bin/env python3
"""
간단한 Reddit Ghost Publisher 어드민 대시보드
"""
from flask import Flask, render_template_string, request, jsonify
import requests
import psycopg2
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'simple-admin-key'

# 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"

def get_api_headers():
    return {"Content-Type": "application/json", "X-API-Key": API_KEY}

def get_db_stats():
    """데이터베이스 통계 조회"""
    try:
        conn = psycopg2.connect(
            host='localhost', port=5432, database='reddit_publisher',
            user='reddit_publisher', password='reddit_publisher_prod_2024'
        )
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_posts,
                COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published
            FROM posts
        """)
        
        stats = cursor.fetchone()
        conn.close()
        
        return {
            'total_posts': stats[0],
            'ai_processed': stats[1], 
            'published': stats[2]
        }
    except Exception as e:
        return {'error': str(e)}

def get_system_status():
    """시스템 상태 조회"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return {
            'api_accessible': response.status_code == 200,
            'status': response.json() if response.status_code == 200 else None
        }
    except:
        return {'api_accessible': False, 'status': None}

@app.route('/')
def dashboard():
    """메인 대시보드"""
    db_stats = get_db_stats()
    system_status = get_system_status()
    
    html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher Admin</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .card-stat { transition: transform 0.2s; }
        .card-stat:hover { transform: translateY(-2px); }
        .status-healthy { color: #28a745; }
        .status-degraded { color: #ffc107; }
        .status-unhealthy { color: #dc3545; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <span class="navbar-brand">
                <i class="fas fa-robot"></i> Reddit Ghost Publisher Admin
            </span>
            <span class="navbar-text">
                <i class="fas fa-clock"></i> {{ now.strftime('%Y-%m-%d %H:%M:%S') }}
            </span>
        </div>
    </nav>

    <div class="container mt-4">
        <!-- 시스템 상태 -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-heartbeat"></i> 시스템 상태</h5>
                    </div>
                    <div class="card-body">
                        {% if system_status.api_accessible %}
                            <div class="alert alert-success">
                                <i class="fas fa-check-circle"></i> API 서버 정상 작동 중
                                {% if system_status.status %}
                                    <br><small>전체 상태: {{ system_status.status.status.upper() }}</small>
                                {% endif %}
                            </div>
                        {% else %}
                            <div class="alert alert-danger">
                                <i class="fas fa-exclamation-triangle"></i> API 서버 연결 실패
                            </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <!-- 통계 카드 -->
        <div class="row mb-4">
            {% if not db_stats.error %}
            <div class="col-md-4">
                <div class="card card-stat bg-primary text-white">
                    <div class="card-body text-center">
                        <i class="fas fa-database fa-2x mb-2"></i>
                        <h3>{{ db_stats.total_posts }}</h3>
                        <p class="mb-0">총 수집된 포스트</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card card-stat bg-info text-white">
                    <div class="card-body text-center">
                        <i class="fas fa-robot fa-2x mb-2"></i>
                        <h3>{{ db_stats.ai_processed }}</h3>
                        <p class="mb-0">AI 처리 완료</p>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card card-stat bg-success text-white">
                    <div class="card-body text-center">
                        <i class="fas fa-blog fa-2x mb-2"></i>
                        <h3>{{ db_stats.published }}</h3>
                        <p class="mb-0">Ghost 발행 완료</p>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="col-md-12">
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i> 데이터베이스 연결 오류: {{ db_stats.error }}
                </div>
            </div>
            {% endif %}
        </div>

        <!-- 파이프라인 제어 -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-play-circle"></i> 파이프라인 제어</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-4">
                                <div class="card border-primary">
                                    <div class="card-body text-center">
                                        <i class="fas fa-download fa-2x text-primary mb-3"></i>
                                        <h6>Reddit 수집</h6>
                                        <p class="text-muted small">새로운 Reddit 포스트를 수집합니다</p>
                                        <button class="btn btn-primary" onclick="triggerAction('collect')">
                                            <i class="fas fa-play"></i> 수집 시작
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card border-info">
                                    <div class="card-body text-center">
                                        <i class="fas fa-brain fa-2x text-info mb-3"></i>
                                        <h6>AI 처리</h6>
                                        <p class="text-muted small">수집된 포스트를 AI로 요약합니다</p>
                                        <button class="btn btn-info" onclick="processPost()">
                                            <i class="fas fa-robot"></i> 포스트 처리
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card border-success">
                                    <div class="card-body text-center">
                                        <i class="fas fa-rocket fa-2x text-success mb-3"></i>
                                        <h6>전체 파이프라인</h6>
                                        <p class="text-muted small">수집 → AI 처리 → Ghost 발행</p>
                                        <button class="btn btn-success" onclick="triggerAction('pipeline')">
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
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-tools"></i> 빠른 액션</h5>
                    </div>
                    <div class="card-body">
                        <div class="btn-group me-2">
                            <button class="btn btn-outline-primary" onclick="window.location.reload()">
                                <i class="fas fa-sync"></i> 새로고침
                            </button>
                            <button class="btn btn-outline-info" onclick="checkStatus()">
                                <i class="fas fa-heartbeat"></i> 상태 확인
                            </button>
                        </div>
                        <div class="btn-group me-2">
                            <button class="btn btn-outline-success" onclick="viewGhostBlog()">
                                <i class="fas fa-external-link-alt"></i> Ghost 블로그 보기
                            </button>
                            <button class="btn btn-outline-warning" onclick="viewLogs()">
                                <i class="fas fa-file-alt"></i> 로그 보기
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 정보 -->
        <div class="row">
            <div class="col-md-12">
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> 
                    <strong>사용 방법:</strong> 
                    위의 버튼들을 클릭하여 파이프라인을 제어할 수 있습니다. 
                    시스템 상태를 정기적으로 확인하세요.
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        async function triggerAction(action) {
            const button = event.target;
            const originalText = button.innerHTML;
            
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 처리 중...';
            button.disabled = true;
            
            try {
                const response = await fetch(`/api/trigger/${action}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert(`성공: ${result.message || '작업이 완료되었습니다.'}`);
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    alert(`오류: ${result.error || '알 수 없는 오류가 발생했습니다.'}`);
                }
            } catch (error) {
                alert(`네트워크 오류: ${error.message}`);
            } finally {
                button.innerHTML = originalText;
                button.disabled = false;
            }
        }
        
        function processPost() {
            // process_single_post.py 실행
            alert('AI 처리가 시작됩니다. 백그라운드에서 process_single_post.py를 실행하세요.');
        }
        
        function checkStatus() {
            window.location.reload();
        }
        
        function viewGhostBlog() {
            window.open('https://american-trends.ghost.io', '_blank');
        }
        
        function viewLogs() {
            alert('로그는 logs/ 디렉토리에서 확인할 수 있습니다.');
        }
        
        // 자동 새로고침 (60초마다)
        setTimeout(() => {
            window.location.reload();
        }, 60000);
    </script>
</body>
</html>
    """
    
    return render_template_string(html, 
                                db_stats=db_stats, 
                                system_status=system_status,
                                now=datetime.now())

@app.route('/api/trigger/<action>', methods=['POST'])
def trigger_action(action):
    """파이프라인 액션 트리거"""
    try:
        if action == 'collect':
            response = requests.post(
                f"{API_BASE_URL}/api/v1/collect/trigger",
                headers=get_api_headers(),
                json={'batch_size': 10},
                timeout=30
            )
        elif action == 'pipeline':
            response = requests.post(
                f"{API_BASE_URL}/api/v1/pipeline/trigger", 
                headers=get_api_headers(),
                json={'batch_size': 3},
                timeout=30
            )
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': f'API error: {response.status_code}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Reddit Ghost Publisher Admin Dashboard")
    print("📊 대시보드 URL: http://localhost:5002")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5002)