#!/usr/bin/env python3
"""
크롤링 결과 확인 스크립트
데이터베이스에서 수집된 Reddit 포스트들을 확인합니다.
"""
import sqlite3
from datetime import datetime
import json

def check_database_results():
    """데이터베이스에서 크롤링 결과 확인"""
    try:
        # SQLite 데이터베이스 연결
        conn = sqlite3.connect('reddit_publisher.db')
        cursor = conn.cursor()
        
        print("🔍 크롤링 결과 확인")
        print("=" * 60)
        
        # 1. 전체 포스트 수 확인
        cursor.execute("SELECT COUNT(*) FROM posts")
        total_posts = cursor.fetchone()[0]
        print(f"📊 총 수집된 포스트 수: {total_posts}개")
        
        if total_posts == 0:
            print("❌ 아직 수집된 포스트가 없습니다.")
            return
        
        # 2. 서브레딧별 통계
        cursor.execute("""
            SELECT subreddit, COUNT(*) as count, AVG(score) as avg_score
            FROM posts 
            GROUP BY subreddit 
            ORDER BY count DESC
        """)
        
        print("\n📈 서브레딧별 통계:")
        for row in cursor.fetchall():
            subreddit, count, avg_score = row
            print(f"   r/{subreddit}: {count}개 포스트, 평균 점수: {avg_score:.1f}")
        
        # 3. 최근 수집된 포스트들
        cursor.execute("""
            SELECT reddit_post_id, title, subreddit, score, num_comments, created_at
            FROM posts 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        
        print("\n📝 최근 수집된 포스트 (최대 10개):")
        for row in cursor.fetchall():
            reddit_id, title, subreddit, score, comments, created_at = row
            title_short = title[:50] + "..." if len(title) > 50 else title
            print(f"   • r/{subreddit} | {score}점 | {comments}댓글 | {title_short}")
            print(f"     ID: {reddit_id} | 수집: {created_at}")
        
        # 4. 처리 로그 확인
        cursor.execute("SELECT COUNT(*) FROM processing_logs")
        total_logs = cursor.fetchone()[0]
        print(f"\n📋 처리 로그 수: {total_logs}개")
        
        if total_logs > 0:
            cursor.execute("""
                SELECT service_name, status, COUNT(*) as count
                FROM processing_logs 
                GROUP BY service_name, status
                ORDER BY service_name, status
            """)
            
            print("   서비스별 처리 상태:")
            for row in cursor.fetchall():
                service, status, count = row
                print(f"     {service} - {status}: {count}개")
        
        # 5. 최근 활동 시간
        cursor.execute("SELECT MAX(created_at) FROM posts")
        last_collection = cursor.fetchone()[0]
        if last_collection:
            print(f"\n⏰ 마지막 수집 시간: {last_collection}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ 크롤링 결과 확인 완료!")
        
        if total_posts > 0:
            print("🎉 Reddit 크롤링이 성공적으로 작동하고 있습니다!")
        
    except Exception as e:
        print(f"❌ 데이터베이스 확인 오류: {e}")

def check_recent_activity():
    """최근 활동 상세 확인"""
    try:
        conn = sqlite3.connect('reddit_publisher.db')
        cursor = conn.cursor()
        
        print("\n🔍 최근 활동 상세 분석")
        print("-" * 40)
        
        # 시간대별 수집 통계
        cursor.execute("""
            SELECT 
                DATE(created_at) as collection_date,
                COUNT(*) as posts_count,
                AVG(score) as avg_score
            FROM posts 
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY collection_date DESC
        """)
        
        print("📅 최근 7일간 일별 수집 통계:")
        for row in cursor.fetchall():
            date, count, avg_score = row
            print(f"   {date}: {count}개 포스트, 평균 점수: {avg_score:.1f}")
        
        # 인기 포스트 TOP 5
        cursor.execute("""
            SELECT title, subreddit, score, num_comments, reddit_post_id
            FROM posts 
            ORDER BY score DESC 
            LIMIT 5
        """)
        
        print("\n🏆 인기 포스트 TOP 5:")
        for i, row in enumerate(cursor.fetchall(), 1):
            title, subreddit, score, comments, reddit_id = row
            title_short = title[:60] + "..." if len(title) > 60 else title
            print(f"   {i}. [{score}점] r/{subreddit} - {title_short}")
            print(f"      댓글: {comments}개 | ID: {reddit_id}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 최근 활동 확인 오류: {e}")

if __name__ == "__main__":
    check_database_results()
    check_recent_activity()