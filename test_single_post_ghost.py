#!/usr/bin/env python3
"""
단일 포스트 Ghost 발행 테스트
"""

import sys
import os
sys.path.append('/app')

from workers.publisher.tasks import publish_to_ghost
from app.infrastructure import get_database_session
from app.models.post import Post

def test_single_post_ghost():
    """단일 포스트 Ghost 발행 테스트"""
    
    # 처리된 포스트 가져오기
    db = get_database_session()
    try:
        post = db.query(Post).filter(Post.status == 'processed').order_by(Post.score.desc()).first()
        
        if not post:
            print("❌ No processed posts found")
            return False
        
        print(f"🎯 Testing Ghost publishing for post:")
        print(f"   ID: {post.id}")
        print(f"   Title: {post.title[:100]}...")
        print(f"   Subreddit: r/{post.subreddit}")
        print(f"   Score: {post.score}")
        print(f"   Summary: {post.summary_ko[:100] if post.summary_ko else 'None'}...")
        print(f"   Tags: {post.tags}")
        
        # Ghost 발행 실행
        print(f"\n👻 Starting Ghost publishing...")
        result = publish_to_ghost(str(post.id))
        
        print(f"✅ Ghost publishing completed!")
        print(f"   Action: {result.get('action')}")
        print(f"   Ghost Post ID: {result.get('ghost_post_id')}")
        print(f"   Ghost Slug: {result.get('ghost_slug')}")
        print(f"   Ghost URL: {result.get('ghost_url')}")
        print(f"   Images Processed: {result.get('images_processed', 0)}")
        
        # 결과 확인
        db.refresh(post)
        print(f"\n📊 Publishing Results:")
        print(f"   Status: {post.status}")
        print(f"   Ghost URL: {post.ghost_url}")
        print(f"   Ghost Post ID: {post.ghost_post_id}")
        print(f"   Ghost Slug: {post.ghost_slug}")
        print(f"   Published At: {post.published_at}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ghost publishing failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_single_post_ghost()
    sys.exit(0 if success else 1)