#!/usr/bin/env python3
"""
모의 AI 처리 스크립트
실제 API 키 없이도 테스트할 수 있도록 모의 처리를 수행합니다.
"""
import psycopg2
import time
import random
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'reddit_publisher',
    'user': 'reddit_publisher',
    'password': 'reddit_publisher_prod_2024'
}

def get_unprocessed_post():
    """처리되지 않은 포스트 하나를 가져옵니다"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT reddit_post_id, title, content, subreddit, score, num_comments
            FROM posts 
            WHERE summary_ko IS NULL AND takedown_status = 'active'
            ORDER BY score DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'reddit_post_id': result[0],
                'title': result[1],
                'content': result[2],
                'subreddit': result[3],
                'score': result[4],
                'num_comments': result[5]
            }
        return None
        
    except Exception as e:
        print(f"데이터베이스 오류: {e}")
        return None

def mock_ai_processing(post):
    """모의 AI 처리"""
    print(f"🤖 AI 처리 시뮬레이션 중...")
    time.sleep(2)  # 처리 시간 시뮬레이션
    
    # 모의 한국어 요약 생성
    title = post['title']
    subreddit = post['subreddit']
    
    mock_summaries = [
        f"최근 {subreddit} 커뮤니티에서 화제가 된 '{title[:30]}...' 관련 소식입니다. 이 글은 {post['score']}점의 높은 점수를 받으며 {post['num_comments']}개의 댓글이 달렸습니다.",
        f"Reddit {subreddit}에서 주목받고 있는 '{title[:30]}...' 이슈에 대해 살펴보겠습니다. 많은 사용자들이 관심을 보이며 활발한 토론이 이어지고 있습니다.",
        f"기술 커뮤니티에서 논의되고 있는 '{title[:30]}...' 주제입니다. 이 포스트는 높은 관심을 받으며 다양한 의견이 제시되고 있습니다."
    ]
    
    summary_ko = random.choice(mock_summaries)
    
    # 모의 영어 요약
    summary_en = f"This post about '{title[:50]}...' has gained significant attention in the r/{subreddit} community with {post['score']} upvotes and {post['num_comments']} comments."
    
    return {
        'summary_ko': summary_ko,
        'summary_en': summary_en,
        'tags': ['reddit', subreddit, 'technology', 'trending'],
        'category': 'Technology'
    }

def update_post_with_ai_results(reddit_post_id, ai_results):
    """AI 처리 결과로 포스트 업데이트"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # tags를 JSON 형태로 변환
        import json
        tags_json = json.dumps(ai_results['tags'])
        
        cursor.execute("""
            UPDATE posts 
            SET summary_ko = %s,
                tags = %s,
                updated_at = %s
            WHERE reddit_post_id = %s
        """, (
            ai_results['summary_ko'],
            tags_json,
            datetime.now(),
            reddit_post_id
        ))
        
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"데이터베이스 업데이트 오류: {e}")
        return False

def log_processing_result(service_name, status, processing_time_ms, error_message=None):
    """처리 결과 로깅"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO processing_logs (service_name, status, processing_time_ms, error_message, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (service_name, status, processing_time_ms, error_message, datetime.now()))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"로그 기록 오류: {e}")

def main():
    """메인 처리 함수"""
    print("🚀 모의 AI 처리 스크립트 시작")
    print("=" * 50)
    
    start_time = time.time()
    
    # 처리할 포스트 가져오기
    post = get_unprocessed_post()
    
    if not post:
        print("❌ 처리할 포스트가 없습니다.")
        log_processing_result('mock_nlp_pipeline', 'no_data', 0, 'No posts to process')
        return
    
    print(f"📋 선택된 포스트:")
    print(f"   제목: {post['title']}")
    print(f"   서브레딧: r/{post['subreddit']}")
    print(f"   점수: {post['score']}점, 댓글: {post['num_comments']}개")
    print()
    
    # 모의 AI 처리
    try:
        ai_results = mock_ai_processing(post)
        
        # 결과 저장
        if update_post_with_ai_results(post['reddit_post_id'], ai_results):
            processing_time = int((time.time() - start_time) * 1000)
            
            print("✅ AI 처리 완료!")
            print(f"📝 한국어 요약: {ai_results['summary_ko'][:100]}...")
            print(f"🏷️ 태그: {', '.join(ai_results['tags'])}")
            print(f"⏱️ 처리 시간: {processing_time}ms")
            
            log_processing_result('mock_nlp_pipeline', 'success', processing_time)
            
        else:
            print("❌ 결과 저장 실패")
            log_processing_result('mock_nlp_pipeline', 'failed', 0, 'Database update failed')
            
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        print(f"❌ AI 처리 오류: {e}")
        log_processing_result('mock_nlp_pipeline', 'failed', processing_time, str(e))

if __name__ == "__main__":
    main()