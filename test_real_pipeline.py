#!/usr/bin/env python3
"""
실제 Reddit 데이터로 전체 파이프라인 테스트
로컬에서 Reddit 데이터를 수집하고 Vercel API로 처리
"""

import requests
import json
import time
from typing import Dict, Any, List

# API 설정
API_BASE_URL = "https://reddit-crawl-mvp.vercel.app"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Reddit-Ghost-Publisher-Test/1.0"
}

def get_real_reddit_data(subreddit: str = "programming", limit: int = 3) -> List[Dict[str, Any]]:
    """실제 Reddit 데이터 수집 (로컬에서)"""
    print(f"🔍 Fetching real Reddit data from r/{subreddit}...")
    
    try:
        reddit_url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        response = requests.get(reddit_url, headers={
            "User-Agent": "reddit-ghost-publisher/1.0.0 (by /u/reddit-publisher)"
        }, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            posts = []
            
            if data.get('data') and data['data'].get('children'):
                for child in data['data']['children']:
                    post = child['data']
                    
                    # 필터링: NSFW, 스티키, 삭제된 게시글 제외
                    if post.get('over_18') or post.get('stickied') or not post.get('title'):
                        continue
                    
                    post_data = {
                        'reddit_post_id': post.get('id'),
                        'title': post.get('title'),
                        'subreddit': post.get('subreddit'),
                        'author': post.get('author'),
                        'score': post.get('score', 0),
                        'num_comments': post.get('num_comments', 0),
                        'created_utc': post.get('created_utc'),
                        'url': post.get('url'),
                        'selftext': post.get('selftext', ''),
                        'permalink': f"https://reddit.com{post.get('permalink', '')}",
                        'over_18': post.get('over_18', False),
                        'thumbnail': post.get('thumbnail') if post.get('thumbnail') not in ['self', 'default'] else None,
                        'domain': post.get('domain'),
                        'is_video': post.get('is_video', False)
                    }
                    posts.append(post_data)
                    
                    if len(posts) >= limit:
                        break
            
            print(f"✅ Successfully fetched {len(posts)} real Reddit posts")
            for i, post in enumerate(posts[:3]):
                print(f"   {i+1}. {post['title'][:60]}... (Score: {post['score']})")
            
            return posts
        else:
            print(f"❌ Failed to fetch Reddit data: HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error fetching Reddit data: {str(e)}")
        return []

def test_ai_with_real_data(post: Dict[str, Any]) -> Dict[str, Any]:
    """실제 Reddit 데이터로 AI 처리 테스트"""
    print(f"\n🤖 Testing AI processing with real Reddit post...")
    print(f"   📝 Title: {post['title'][:60]}...")
    
    payload = {
        "title": post['title'],
        "content": post['selftext'] if post['selftext'] else post['url'],
        "subreddit": post['subreddit']
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/ai-process", 
            headers=HEADERS, 
            json=payload,
            timeout=60
        )
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            processed_data = data.get('data', {})
            
            print("✅ AI Processing: SUCCESS")
            
            # 실제 AI 처리 결과 확인
            if 'korean_summary' in processed_data:
                print("   🎉 Real AI processing detected!")
                print(f"   📝 Korean Summary: {processed_data['korean_summary'][:100]}...")
                print(f"   🏷️ Tags: {processed_data.get('tags', [])}")
                print(f"   💰 Cost: ${processed_data.get('token_usage', {}).get('estimated_cost_usd', 0):.6f}")
                return {"success": True, "real_ai": True, "data": processed_data}
            else:
                print("   ⚠️ Mock AI processing (API key not configured)")
                print(f"   📝 Enhanced Title: {processed_data.get('enhanced_title', 'N/A')}")
                return {"success": True, "real_ai": False, "data": processed_data}
        else:
            print(f"❌ AI Processing failed: {data.get('error', 'Unknown error')}")
            return {"success": False, "error": data.get('error')}
            
    except Exception as e:
        print(f"❌ AI Processing error: {str(e)}")
        return {"success": False, "error": str(e)}

def test_ghost_with_processed_data(title: str, content: str, tags: List[str]) -> Dict[str, Any]:
    """처리된 데이터로 Ghost 발행 테스트"""
    print(f"\n👻 Testing Ghost publishing...")
    print(f"   📝 Title: {title[:60]}...")
    
    payload = {
        "title": title,
        "content": content,
        "tags": tags
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/ghost-publish", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            published_data = data.get('data', {})
            
            if published_data.get('published'):
                print("✅ Ghost Publishing: REAL PUBLISH SUCCESS!")
                print(f"   🔗 Published URL: {published_data.get('ghost_url')}")
                print(f"   🆔 Ghost Post ID: {published_data.get('ghost_post_id')}")
                return {"success": True, "real_publish": True, "data": published_data}
            else:
                print("✅ Ghost Publishing: Mock mode (API key not configured)")
                print(f"   📝 Mock URL: {published_data.get('mock_data', {}).get('ghost_url', 'N/A')}")
                return {"success": True, "real_publish": False, "data": published_data}
        else:
            print(f"❌ Ghost Publishing failed: {data.get('error', 'Unknown error')}")
            return {"success": False, "error": data.get('error')}
            
    except Exception as e:
        print(f"❌ Ghost Publishing error: {str(e)}")
        return {"success": False, "error": str(e)}

def run_real_pipeline_test():
    """실제 데이터로 전체 파이프라인 테스트"""
    print("🚀 Real Data Pipeline Test")
    print("=" * 60)
    
    # 1. 실제 Reddit 데이터 수집
    reddit_posts = get_real_reddit_data("programming", 3)
    
    if not reddit_posts:
        print("❌ No Reddit posts fetched. Cannot continue test.")
        return
    
    # 2. 첫 번째 포스트로 AI 처리 테스트
    test_post = reddit_posts[0]
    ai_result = test_ai_with_real_data(test_post)
    
    if not ai_result["success"]:
        print("❌ AI processing failed. Using original post for Ghost test.")
        title = test_post["title"]
        content = test_post["selftext"] if test_post["selftext"] else f"Original post: {test_post['url']}"
        tags = ["reddit", test_post["subreddit"], "test"]
    else:
        processed = ai_result["data"]
        if ai_result.get("real_ai"):
            title = test_post["title"]  # 원본 제목 사용
            content = processed.get("korean_summary", processed.get("enhanced_content", ""))
            tags = processed.get("tags", ["reddit", test_post["subreddit"]])
        else:
            title = processed.get("enhanced_title", test_post["title"])
            content = processed.get("enhanced_content", test_post["selftext"] or test_post["url"])
            tags = processed.get("tags", ["reddit", test_post["subreddit"]])
    
    # 3. Ghost 발행 테스트
    ghost_result = test_ghost_with_processed_data(title, content, tags)
    
    # 4. 결과 요약
    print("\n" + "=" * 60)
    print("📋 REAL PIPELINE TEST SUMMARY")
    print("=" * 60)
    
    print(f"Reddit Data Collection: ✅ SUCCESS ({len(reddit_posts)} posts)")
    print(f"AI Processing: {'✅ REAL AI' if ai_result.get('success') and ai_result.get('real_ai') else '⚠️ MOCK MODE'}")
    print(f"Ghost Publishing: {'✅ REAL PUBLISH' if ghost_result.get('success') and ghost_result.get('real_publish') else '⚠️ MOCK MODE'}")
    
    if ai_result.get("real_ai") and ghost_result.get("real_publish"):
        print("\n🎉 FULL REAL PIPELINE SUCCESS!")
        print("   All APIs are working with real data and credentials!")
    elif ai_result.get("success") and ghost_result.get("success"):
        print("\n⚠️ PIPELINE WORKING IN MOCK MODE")
        print("   APIs are functional but need environment variables configured.")
        print("   Required: OPENAI_API_KEY, GHOST_ADMIN_KEY")
    else:
        print("\n❌ PIPELINE HAS ISSUES")
        print("   Some APIs are not responding correctly.")
    
    return {
        "reddit_posts": len(reddit_posts),
        "ai_success": ai_result.get("success", False),
        "ai_real": ai_result.get("real_ai", False),
        "ghost_success": ghost_result.get("success", False),
        "ghost_real": ghost_result.get("real_publish", False)
    }

if __name__ == "__main__":
    results = run_real_pipeline_test()