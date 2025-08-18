#!/usr/bin/env python3
"""
Ghost 발행 디버깅 스크립트
"""

import sys
import traceback
sys.path.append('/app')

from workers.publisher.tasks import publish_to_ghost
from app.infrastructure import get_database_session
from app.models.post import Post

def debug_ghost_publishing():
    """Ghost 발행 디버깅"""
    
    # 처리된 포스트 가져오기
    db = get_database_session()
    try:
        post = db.query(Post).filter(Post.status == 'processed').first()
        
        if not post:
            print("❌ No processed posts found")
            return False
        
        print(f"👻 Debugging Ghost publishing for post:")
        print(f"   ID: {post.id}")
        print(f"   Title: {post.title[:100]}...")
        print(f"   Summary: {post.summary_ko[:100] if post.summary_ko else 'None'}...")
        print(f"   Tags: {post.tags}")
        
        # Ghost 발행 실행 (디버깅 모드)
        print(f"\n👻 Starting Ghost publishing with detailed logging...")
        
        try:
            result = publish_to_ghost(str(post.id))
            print(f"✅ Ghost publishing completed!")
            print(f"   Result: {result}")
            return True
        except Exception as e:
            print(f"❌ Ghost publishing failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            print(f"   Traceback:")
            traceback.print_exc()
            return False
        
    finally:
        db.close()

if __name__ == "__main__":
    success = debug_ghost_publishing()
    sys.exit(0 if success else 1)