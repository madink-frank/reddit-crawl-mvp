#!/usr/bin/env python3
"""
단일 포스트 AI 처리 테스트
"""

import sys
import os
sys.path.append('/app')

from workers.nlp_pipeline.tasks import process_content_with_ai
from app.infrastructure import get_database_session
from app.models.post import Post

def test_single_post_ai():
    """단일 포스트 AI 처리 테스트"""
    
    # 가장 높은 점수의 포스트 가져오기
    db = get_database_session()
    try:
        post = db.query(Post).filter(Post.status == 'collected').order_by(Post.score.desc()).first()
        
        if not post:
            print("❌ No collected posts found")
            return False
        
        print(f"🎯 Testing AI processing for post:")
        print(f"   ID: {post.id}")
        print(f"   Title: {post.title[:100]}...")
        print(f"   Subreddit: r/{post.subreddit}")
        print(f"   Score: {post.score}")
        
        # AI 처리 실행
        print(f"\n🤖 Starting AI processing...")
        result = process_content_with_ai(str(post.id))
        
        print(f"✅ AI processing completed!")
        print(f"   Status: {result.get('status')}")
        print(f"   Processing time: {result.get('processing_time_ms')}ms")
        print(f"   Total tokens: {result.get('total_tokens')}")
        print(f"   Total cost: ${result.get('total_cost'):.6f}")
        
        # 결과 확인
        db.refresh(post)
        print(f"\n📊 Processing Results:")
        print(f"   Status: {post.status}")
        print(f"   Summary: {post.summary_ko[:200] if post.summary_ko else 'None'}...")
        print(f"   Tags: {post.tags}")
        print(f"   Pain Points: {len(post.pain_points) if post.pain_points else 0} items")
        print(f"   Product Ideas: {len(post.product_ideas) if post.product_ideas else 0} items")
        
        return True
        
    except Exception as e:
        print(f"❌ AI processing failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_single_post_ai()
    sys.exit(0 if success else 1)