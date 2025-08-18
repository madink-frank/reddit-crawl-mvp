#!/usr/bin/env python3
"""
Reddit Ghost Publisher 어드민 대시보드
Flask 기반 간단한 웹 대시보드로 파이프라인 제어 및 모니터링
"""
import os
import json
import psycopg2
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from dotenv import load_dotenv
import subprocess
import threading
import time

# 환경 변수 로드
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.getenv('JWT_SECRET_KEY', 'dev-secret-key')

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
        
        # 최근 활동
        cursor.execute("""
            SELECT reddit_post_id, title, subreddit, score, num_comments, 
                   summary_ko, ghost_url, created_at, published_at
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
                'summary_ko': row[5],
                'ghost_url': row[6],
                'created_at': row[7],
                'published_at': row[8]
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
            'recent_posts': recent_posts
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
        # 백그라운드에서 process_single_post.py 실행
        def run_script():
            subprocess.run(["python", "process_single_post.py"], 
                         capture_output=True, text=True)
        
        thread = threading.Thread(target=run_script)
        thread.start()
        
        return {"success": True, "message": "AI 처리 스크립트가 백그라운드에서 실행 중입니다."}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def dashboard():
    """메인 대시보드"""
    stats = get_system_stats()
    api_status = get_api_status()
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         api_status=api_status,
                         current_time=datetime.now())

@app.route('/api/stats')
def api_stats():
    """통계 API"""
    stats = get_system_stats()
    return jsonify(stats)

@app.route('/api/status')
def api_status_endpoint():
    """상태 API"""
    status = get_api_status()
    return jsonify(status)

@app.route('/api/trigger/<action>', methods=['POST'])
def api_trigger(action):
    """파이프라인 트리거 API"""
    params = request.get_json() or {}
    result = trigger_pipeline_action(action, params)
    return jsonify(result)

@app.route('/control')
def control_panel():
    """제어 패널"""
    return render_template('control.html')

@app.route('/logs')
def logs_view():
    """로그 뷰"""
    try:
        # 최근 처리 로그 조회
        conn = get_db_connection()
        if not conn:
            return render_template('logs.html', logs=[])
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT service_name, status, error_message, processing_time_ms, created_at
            FROM processing_logs 
            ORDER BY created_at DESC 
            LIMIT 100
        """)
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'service': row[0],
                'status': row[1],
                'error': row[2],
                'time_ms': row[3],
                'created_at': row[4]
            })
        
        conn.close()
        return render_template('logs.html', logs=logs)
        
    except Exception as e:
        return render_template('logs.html', logs=[], error=str(e))

@app.route('/posts')
def posts_view():
    """포스트 관리"""
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('posts.html', posts=[])
            
        cursor = conn.cursor()
        
        # 페이지네이션
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # 필터
        status_filter = request.args.get('status', 'all')
        subreddit_filter = request.args.get('subreddit', '')
        
        where_clause = "WHERE 1=1"
        params = []
        
        if status_filter == 'unprocessed':
            where_clause += " AND summary_ko IS NULL"
        elif status_filter == 'processed':
            where_clause += " AND summary_ko IS NOT NULL AND ghost_url IS NULL"
        elif status_filter == 'published':
            where_clause += " AND ghost_url IS NOT NULL"
        
        if subreddit_filter:
            where_clause += " AND subreddit = %s"
            params.append(subreddit_filter)
        
        query = f"""
            SELECT reddit_post_id, title, subreddit, score, num_comments,
                   summary_ko, ghost_url, takedown_status, created_at, published_at
            FROM posts 
            {where_clause}
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cursor.execute(query, params)
        
        posts = []
        for row in cursor.fetchall():
            posts.append({
                'reddit_post_id': row[0],
                'title': row[1],
                'subreddit': row[2],
                'score': row[3],
                'num_comments': row[4],
                'summary_ko': row[5],
                'ghost_url': row[6],
                'takedown_status': row[7],
                'created_at': row[8],
                'published_at': row[9]
            })
        
        # 서브레딧 목록
        cursor.execute("SELECT DISTINCT subreddit FROM posts ORDER BY subreddit")
        subreddits = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return render_template('posts.html', 
                             posts=posts, 
                             subreddits=subreddits,
                             current_page=page,
                             status_filter=status_filter,
                             subreddit_filter=subreddit_filter)
        
    except Exception as e:
        return render_template('posts.html', posts=[], error=str(e))

@app.route('/settings')
def settings_view():
    """설정 페이지"""
    env_vars = {
        'REDDIT_CLIENT_ID': os.getenv('REDDIT_CLIENT_ID', ''),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', '')[:20] + '...' if os.getenv('OPENAI_API_KEY') else '',
        'GHOST_API_URL': os.getenv('GHOST_API_URL', ''),
        'SLACK_WEBHOOK_URL': os.getenv('SLACK_WEBHOOK_URL', '')[:50] + '...' if os.getenv('SLACK_WEBHOOK_URL') else '',
        'SUBREDDITS': os.getenv('SUBREDDITS', ''),
        'BATCH_SIZE': os.getenv('BATCH_SIZE', '20'),
        'COLLECT_CRON': os.getenv('COLLECT_CRON', '0 * * * *')
    }
    
    return render_template('settings.html', env_vars=env_vars)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)