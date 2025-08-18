#!/usr/bin/env python3
"""
어드민 대시보드용 간단한 API 서버
CORS 문제 해결 및 데이터베이스 직접 접근
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # CORS 허용

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

@app.route('/api/stats')
def get_stats():
    """통계 데이터 반환"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': False,
                'error': 'Database connection failed'
            }), 500
        cursor = conn.cursor()
        
        # 기본 통계
        cursor.execute("""
            SELECT 
                COUNT(*) as total_posts,
                COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as collected_today
            FROM posts
        """)
        
        stats = cursor.fetchone()
        
        # 최근 포스트
        cursor.execute("""
            SELECT reddit_post_id, title, subreddit, score, num_comments, 
                   summary_ko, ghost_url, created_at
            FROM posts 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        recent_posts = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_posts': stats[0],
                'ai_processed': stats[1],
                'published': stats[2],
                'collected_today': stats[3],
                'success_rate': round((stats[2] / stats[0] * 100) if stats[0] > 0 else 0, 1),
                'recent_posts': [
                    {
                        'id': post[0],
                        'title': post[1][:60] + '...' if len(post[1]) > 60 else post[1],
                        'subreddit': post[2],
                        'score': post[3],
                        'comments': post[4],
                        'processed': bool(post[5]),
                        'published': bool(post[6]),
                        'ghost_url': post[6],
                        'created_at': post[7].isoformat() if post[7] else None
                    }
                    for post in recent_posts
                ]
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health')
def get_health():
    """시스템 헬스체크"""
    try:
        # API 서버 상태 확인
        api_response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        api_healthy = api_response.status_code == 200
        api_data = api_response.json() if api_healthy else None
        
        # 데이터베이스 상태 확인
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            db_healthy = True
        except:
            db_healthy = False
        
        return jsonify({
            'success': True,
            'data': {
                'api_server': {
                    'healthy': api_healthy,
                    'status': api_data.get('status') if api_data else 'unknown',
                    'services': api_data.get('services') if api_data else {}
                },
                'database': {
                    'healthy': db_healthy
                },
                'overall_status': 'healthy' if (api_healthy and db_healthy) else 'degraded'
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/trigger/<action>', methods=['POST'])
def trigger_action(action):
    """파이프라인 액션 트리거"""
    try:
        data = request.get_json() or {}
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        if action == 'collect':
            response = requests.post(
                f"{API_BASE_URL}/api/v1/collect/trigger",
                headers=headers,
                json={
                    'batch_size': data.get('batch_size', 10),
                    'subreddits': data.get('subreddits', ['programming', 'technology', 'webdev'])
                },
                timeout=30
            )
        elif action == 'pipeline':
            response = requests.post(
                f"{API_BASE_URL}/api/v1/pipeline/trigger",
                headers=headers,
                json={
                    'batch_size': data.get('batch_size', 3)
                },
                timeout=30
            )
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid action'
            }), 400
        
        if response.status_code == 200:
            result = response.json()
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': f'API error: {response.status_code}',
                'details': response.text
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/logs')
def get_logs():
    """시스템 로그 반환 (모의 데이터)"""
    try:
        # 실제 환경에서는 로그 파일을 읽거나 데이터베이스에서 로그를 가져옴
        logs = [
            {
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': 'Admin API server is running',
                'service': 'admin'
            },
            {
                'timestamp': (datetime.now()).isoformat(),
                'level': 'SUCCESS',
                'message': 'Database connection established',
                'service': 'database'
            }
        ]
        
        return jsonify({
            'success': True,
            'data': logs
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("🚀 Reddit Ghost Publisher Admin API Server")
    print("📊 API URL: http://localhost:5003")
    print("🌐 CORS 활성화됨 - Ghost 페이지에서 접근 가능")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5003)