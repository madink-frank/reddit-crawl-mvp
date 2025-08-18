#!/usr/bin/env python3
"""
간단한 어드민 대시보드 서버
Flask 기반으로 데이터베이스 직접 접근
"""
import os
import psycopg2
from datetime import datetime
from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# 데이터베이스 설정
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
        
        # 최근 활동
        cursor.execute("""
            SELECT reddit_post_id, title, subreddit, score, num_comments, 
                   summary_ko IS NOT NULL as has_summary, ghost_url IS NOT NULL as is_published,
                   created_at, published_at
            FROM posts 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        recent_posts = []
        for row in cursor.fetchall():
            recent_posts.append({
                'reddit_post_id': row[0],
                'title': row[1],
                'subreddit': row[2],
                'score': row[3],
                'num_comments': row[4],
                'has_summary': row[5],
                'is_published': row[6],
                'created_at': row[7].isoformat() if row[7] else None,
                'published_at': row[8].isoformat() if row[8] else None
            })
        
        conn.close()
        
        return {
            'total_posts': total,
            'ai_processed': ai_processed,
            'published': published,
            'active_posts': active,
            'today_collected': today_collected,
            'today_processed': today_processed,
            'today_published': today_published,
            'success_rate': round((published / total * 100) if total > 0 else 0, 1),
            'recent_posts': recent_posts
        }
        
    except Exception as e:
        print(f"통계 조회 오류: {e}")
        return None

@app.route('/')
def dashboard():
    """메인 대시보드"""
    stats = get_system_stats()
    
    html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reddit Ghost Publisher - 어드민 대시보드</title>
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
        .status-badge {
            font-size: 0.8rem;
            padding: 0.25rem 0.5rem;
        }
    </style>
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark shadow">
        <div class="container">
            <span class="navbar-brand">
                <i class="fas fa-robot text-primary"></i> Reddit Ghost Publisher
                <small class="text-muted">Production Dashboard</small>
            </span>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text">
                    <i class="fas fa-clock"></i> {{ current_time }}
                </span>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% if stats %}
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
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card card-stat bg-success text-white shadow">
                    <div class="card-body text-center">
                        <i class="fas fa-blog fa-2x mb-2"></i>
                        <h3>{{ stats.published }}</h3>
                        <p class="mb-0">Ghost 발행 완료</p>
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

        <!-- 오늘 통계 -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card shadow-sm">
                    <div class="card-header bg-secondary text-white">
                        <h5 class="mb-0"><i class="fas fa-calendar-day"></i> 오늘 활동</h5>
                    </div>
                    <div class="card-body">
                        <div class="row text-center">
                            <div class="col-md-4">
                                <h4 class="text-primary">{{ stats.today_collected }}</h4>
                                <p class="text-muted">오늘 수집</p>
                            </div>
                            <div class="col-md-4">
                                <h4 class="text-info">{{ stats.today_processed }}</h4>
                                <p class="text-muted">오늘 AI 처리</p>
                            </div>
                            <div class="col-md-4">
                                <h4 class="text-success">{{ stats.today_published }}</h4>
                                <p class="text-muted">오늘 발행</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 최근 포스트 -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card shadow-sm">
                    <div class="card-header bg-dark text-white">
                        <h5 class="mb-0"><i class="fas fa-list"></i> 최근 포스트 (최신 10개)</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>상태</th>
                                        <th>서브레딧</th>
                                        <th>제목</th>
                                        <th>점수</th>
                                        <th>댓글</th>
                                        <th>생성일</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for post in stats.recent_posts %}
                                    <tr>
                                        <td>
                                            {% if post.is_published %}
                                                <span class="badge bg-success status-badge">발행완료</span>
                                            {% elif post.has_summary %}
                                                <span class="badge bg-info status-badge">처리완료</span>
                                            {% else %}
                                                <span class="badge bg-secondary status-badge">수집완료</span>
                                            {% endif %}
                                        </td>
                                        <td><strong>r/{{ post.subreddit }}</strong></td>
                                        <td>{{ post.title[:60] }}{% if post.title|length > 60 %}...{% endif %}</td>
                                        <td><span class="badge bg-primary">{{ post.score }}</span></td>
                                        <td><span class="badge bg-secondary">{{ post.num_comments }}</span></td>
                                        <td><small class="text-muted">{{ post.created_at[:16] if post.created_at else '-' }}</small></td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 시스템 정보 -->
        <div class="row">
            <div class="col-md-12">
                <div class="alert alert-success shadow-sm">
                    <i class="fas fa-check-circle"></i> 
                    <strong>시스템 상태:</strong> 
                    데이터베이스 연결 정상, 총 {{ stats.total_posts }}개 포스트 관리 중
                    <br><small class="text-muted">
                        마지막 업데이트: {{ current_time }} | 
                        환경: Production
                    </small>
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
        // 자동 새로고침 (30초마다)
        setTimeout(() => {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
    """
    
    return render_template_string(
        html_template, 
        stats=stats, 
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
    print("🚀 Reddit Ghost Publisher 간단 어드민 대시보드")
    print("📊 대시보드 URL: http://localhost:8081")
    print("🔗 API URL: http://localhost:8081/api/stats")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=8081)