#!/usr/bin/env python3
"""
전체 파이프라인 실행 스크립트
수집된 Reddit 콘텐츠를 AI로 처리하고 Ghost CMS에 발행합니다.
"""
import requests
import json
import time
import psycopg2
from datetime import datetime
from typing import List, Dict, Any

# API 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"

# PostgreSQL 연결 설정
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'reddit_publisher',
    'user': 'reddit_publisher',
    'password': 'reddit_publisher_prod_2024'
}

def get_unprocessed_posts(limit=5) -> List[Dict]:
    """처리되지 않은 포스트들을 가져옵니다"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
        SELECT id, reddit_post_id, title, subreddit, score, num_comments, content, url
        FROM posts 
        WHERE summary_ko IS NULL 
        AND score >= 10 
        ORDER BY score DESC, num_comments DESC 
        LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        
        posts = []
        for row in rows:
            posts.append({
                'id': row[0],
                'reddit_post_id': row[1],
                'title': row[2],
                'subreddit': row[3],
                'score': row[4],
                'num_comments': row[5],
                'content': row[6],
                'url': row[7]
            })
        
        conn.close()
        return posts
        
    except Exception as e:
        print(f"❌ 데이터베이스 조회 오류: {e}")
        return []

def process_post_with_ai(post_id: str) -> bool:
    """특정 포스트를 AI로 처리합니다"""
    try:
        url = f"{API_BASE_URL}/api/v1/process/trigger"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        data = {
            "post_id": post_id,
            "force": True
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ AI 처리 트리거 성공: {result.get('message')}")
            return True
        else:
            print(f"❌ AI 처리 트리거 실패: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ AI 처리 오류: {e}")
        return False

def publish_post_to_ghost(post_id: str) -> bool:
    """특정 포스트를 Ghost CMS에 발행합니다"""
    try:
        url = f"{API_BASE_URL}/api/v1/publish/trigger"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        data = {
            "post_id": post_id,
            "force": True
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Ghost 발행 트리거 성공: {result.get('message')}")
            return True
        else:
            print(f"❌ Ghost 발행 트리거 실패: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ghost 발행 오류: {e}")
        return False

def run_ai_processing_pipeline(posts: List[Dict]) -> None:
    """AI 처리 파이프라인 실행"""
    print(f"\n🤖 AI 처리 파이프라인 시작 ({len(posts)}개 포스트)")
    print("=" * 60)
    
    for i, post in enumerate(posts, 1):
        print(f"\n[{i}/{len(posts)}] 처리 중: {post['title'][:50]}...")
        print(f"   서브레딧: r/{post['subreddit']} | 점수: {post['score']} | 댓글: {post['num_comments']}")
        
        # AI 처리 실행 (실제로는 Celery 작업을 통해 비동기 처리)
        success = process_post_with_ai(post['id'])
        
        if success:
            print(f"   ✅ AI 처리 요청 완료")
            # 처리 시간 대기 (실제 환경에서는 Celery 작업 상태를 모니터링)
            time.sleep(2)
        else:
            print(f"   ❌ AI 처리 실패")
            continue

def run_ghost_publishing_pipeline(posts: List[Dict]) -> None:
    """Ghost 발행 파이프라인 실행"""
    print(f"\n👻 Ghost 발행 파이프라인 시작 ({len(posts)}개 포스트)")
    print("=" * 60)
    
    for i, post in enumerate(posts, 1):
        print(f"\n[{i}/{len(posts)}] 발행 중: {post['title'][:50]}...")
        
        # Ghost 발행 실행
        success = publish_post_to_ghost(post['id'])
        
        if success:
            print(f"   ✅ Ghost 발행 요청 완료")
            time.sleep(3)  # Ghost API 레이트 리밋 고려
        else:
            print(f"   ❌ Ghost 발행 실패")
            continue

def run_direct_celery_tasks(posts: List[Dict]) -> None:
    """Celery 작업을 직접 실행"""
    print(f"\n⚡ Celery 작업 직접 실행 ({len(posts)}개 포스트)")
    print("=" * 60)
    
    try:
        from workers.nlp_pipeline.tasks import process_content_with_ai
        from workers.publisher.tasks import publish_to_ghost
        
        for i, post in enumerate(posts, 1):
            print(f"\n[{i}/{len(posts)}] 처리 중: {post['title'][:50]}...")
            
            try:
                # 1. AI 처리
                print("   🤖 AI 처리 시작...")
                ai_task = process_content_with_ai.delay(post['id'])
                print(f"   AI 작업 ID: {ai_task.id}")
                
                # AI 처리 완료 대기 (최대 60초)
                try:
                    ai_result = ai_task.get(timeout=60)
                    print(f"   ✅ AI 처리 완료: {ai_result.get('status', 'unknown')}")
                    
                    # 2. Ghost 발행
                    print("   👻 Ghost 발행 시작...")
                    ghost_task = publish_to_ghost.delay(post['id'])
                    print(f"   Ghost 작업 ID: {ghost_task.id}")
                    
                    # Ghost 발행 완료 대기 (최대 30초)
                    try:
                        ghost_result = ghost_task.get(timeout=30)
                        print(f"   ✅ Ghost 발행 완료: {ghost_result.get('status', 'unknown')}")
                    except Exception as e:
                        print(f"   ⚠️ Ghost 발행 시간 초과 또는 오류: {e}")
                        
                except Exception as e:
                    print(f"   ⚠️ AI 처리 시간 초과 또는 오류: {e}")
                    continue
                    
            except Exception as e:
                print(f"   ❌ 작업 실행 오류: {e}")
                continue
                
            # 다음 포스트 처리 전 잠시 대기
            if i < len(posts):
                print("   ⏳ 다음 포스트 처리 대기 중...")
                time.sleep(5)
                
    except ImportError as e:
        print(f"❌ Celery 작업 임포트 오류: {e}")
        print("   API 엔드포인트를 통한 처리로 전환합니다...")
        run_ai_processing_pipeline(posts)
        time.sleep(10)  # AI 처리 완료 대기
        run_ghost_publishing_pipeline(posts)

def check_processing_results() -> None:
    """처리 결과 확인"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 처리 통계
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as ai_processed,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published
            FROM posts
        """)
        
        total, ai_processed, published = cursor.fetchone()
        
        print(f"\n📊 처리 결과 통계:")
        print(f"   총 포스트: {total}개")
        print(f"   AI 처리 완료: {ai_processed}개")
        print(f"   Ghost 발행 완료: {published}개")
        
        # 최근 처리된 포스트들
        cursor.execute("""
            SELECT title, subreddit, summary_ko, ghost_url
            FROM posts 
            WHERE summary_ko IS NOT NULL 
            ORDER BY updated_at DESC 
            LIMIT 5
        """)
        
        recent_posts = cursor.fetchall()
        
        if recent_posts:
            print(f"\n📝 최근 처리된 포스트들:")
            for title, subreddit, summary, ghost_url in recent_posts:
                title_short = title[:40] + "..." if len(title) > 40 else title
                status = "발행됨" if ghost_url else "처리됨"
                print(f"   • [{status}] r/{subreddit} - {title_short}")
                if summary:
                    summary_short = summary[:60] + "..." if len(summary) > 60 else summary
                    print(f"     요약: {summary_short}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 결과 확인 오류: {e}")

def main():
    """메인 실행 함수"""
    print("🚀 Reddit → AI → Ghost 전체 파이프라인 시작")
    print("=" * 60)
    
    # 1. 처리할 포스트 선택
    print("📋 처리할 포스트 선택 중...")
    posts = get_unprocessed_posts(limit=3)  # 테스트용으로 3개만
    
    if not posts:
        print("❌ 처리할 포스트가 없습니다.")
        return
    
    print(f"✅ {len(posts)}개 포스트 선택됨")
    for i, post in enumerate(posts, 1):
        print(f"   {i}. r/{post['subreddit']} - {post['title'][:50]}... ({post['score']}점)")
    
    # 2. 사용자 확인
    try:
        confirm = input(f"\n이 {len(posts)}개 포스트를 AI 처리하고 Ghost에 발행하시겠습니까? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("작업이 취소되었습니다.")
            return
    except KeyboardInterrupt:
        print("\n작업이 취소되었습니다.")
        return
    
    # 3. 전체 파이프라인 실행
    start_time = time.time()
    
    try:
        # Celery 작업 직접 실행 시도
        run_direct_celery_tasks(posts)
        
    except Exception as e:
        print(f"❌ 파이프라인 실행 오류: {e}")
    
    # 4. 결과 확인
    print("\n" + "=" * 60)
    print("📊 최종 결과 확인")
    check_processing_results()
    
    # 5. 실행 시간 계산
    duration = time.time() - start_time
    print(f"\n⏱️ 총 실행 시간: {duration:.1f}초")
    print("✨ 전체 파이프라인 완료!")

if __name__ == "__main__":
    main()