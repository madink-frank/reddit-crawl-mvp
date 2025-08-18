#!/usr/bin/env python3
"""
최소한의 어드민 대시보드
"""
import psycopg2
from datetime import datetime
from flask import Flask, jsonify

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'reddit_publisher',
    'user': 'reddit_publisher',
    'password': 'reddit_publisher_prod_2024'
}

@app.route('/')
def dashboard():
    """메인 대시보드"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 기본 통계
        cursor.execute("""
            SELECT 
                COUNT(*) as total_posts,
                COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published
            FROM posts
        """)
        
        total, ai_processed, published = cursor.fetchone()
        success_rate = round((published / total * 100) if total > 0 else 0, 1)
        
        conn.close()
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Reddit Ghost Publisher - 어드민</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); flex: 1; text-align: center; }}
        .stat-number {{ font-size: 2em; font-weight: bold; margin-bottom: 10px; }}
        .stat-label {{ color: #666; }}
        .primary {{ color: #3498db; }}
        .success {{ color: #27ae60; }}
        .info {{ color: #f39c12; }}
        .warning {{ color: #e74c3c; }}
        .status {{ background: #27ae60; color: white; padding: 10px; border-radius: 4px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Reddit Ghost Publisher - 어드민 대시보드</h1>
            <p>Production 환경 | 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number primary">{total}</div>
                <div class="stat-label">총 수집된 포스트</div>
            </div>
            <div class="stat-card">
                <div class="stat-number info">{ai_processed}</div>
                <div class="stat-label">AI 처리 완료</div>
            </div>
            <div class="stat-card">
                <div class="stat-number success">{published}</div>
                <div class="stat-label">Ghost 발행 완료</div>
            </div>
            <div class="stat-card">
                <div class="stat-number warning">{success_rate}%</div>
                <div class="stat-label">성공률</div>
            </div>
        </div>
        
        <div class="status">
            ✅ 시스템 정상 작동 중 | 데이터베이스 연결 성공 | 총 {total}개 포스트 관리
        </div>
        
        <script>
            // 30초마다 자동 새로고침
            setTimeout(() => location.reload(), 30000);
        </script>
    </div>
</body>
</html>
        """
        
        return html
        
    except Exception as e:
        return f"""
<!DOCTYPE html>
<html>
<head><title>어드민 대시보드 - 오류</title></head>
<body style="font-family: Arial; margin: 40px;">
    <h1>❌ 데이터베이스 연결 오류</h1>
    <p>오류: {e}</p>
    <p><a href="/">다시 시도</a></p>
</body>
</html>
        """

@app.route('/api/stats')
def api_stats():
    """통계 API"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_posts,
                COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published
            FROM posts
        """)
        
        total, ai_processed, published = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_posts': total,
                'ai_processed': ai_processed,
                'published': published,
                'success_rate': round((published / total * 100) if total > 0 else 0, 1)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health():
    """헬스체크"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 최소한의 어드민 대시보드 시작")
    print("📊 URL: http://localhost:8082")
    app.run(debug=False, host='0.0.0.0', port=8082)