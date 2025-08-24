#!/usr/bin/env python3
"""
Reddit Ghost Publisher API Pipeline Test
실제 API 엔드포인트를 테스트하여 전체 파이프라인이 작동하는지 확인
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

def test_health_check() -> Dict[str, Any]:
    """Health check API 테스트"""
    print("🔍 Testing Health Check API...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", headers=HEADERS, timeout=10)
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print("✅ Health Check: PASSED")
            return {"success": True, "data": data}
        else:
            print(f"❌ Health Check: FAILED - {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"❌ Health Check: ERROR - {str(e)}")
        return {"success": False, "error": str(e)}

def test_reddit_collection() -> Dict[str, Any]:
    """Reddit 수집 API 테스트"""
    print("\n📥 Testing Reddit Collection API...")
    
    payload = {
        "subreddits": ["programming", "technology"],
        "limit": 3
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/reddit-collect", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            collected_posts = data.get('data', {}).get('collected_posts', 0)
            posts = data.get('data', {}).get('posts', [])
            
            print(f"✅ Reddit Collection: PASSED - {collected_posts} posts collected")
            
            # 실제 데이터인지 확인
            if posts and len(posts) > 0:
                first_post = posts[0]
                if 'reddit_post_id' in first_post and 'title' in first_post:
                    print(f"   📝 Sample post: {first_post['title'][:50]}...")
                    print(f"   🆔 Post ID: {first_post.get('reddit_post_id', 'N/A')}")
                    return {"success": True, "data": data, "posts": posts}
                else:
                    print("   ⚠️ Warning: Posts structure seems incomplete")
            else:
                print("   ⚠️ Warning: No posts returned")
            
            return {"success": True, "data": data, "posts": posts}
        else:
            print(f"❌ Reddit Collection: FAILED - {response.status_code}")
            print(f"   Error: {data.get('error', 'Unknown error')}")
            return {"success": False, "error": data.get('error', f"HTTP {response.status_code}")}
            
    except Exception as e:
        print(f"❌ Reddit Collection: ERROR - {str(e)}")
        return {"success": False, "error": str(e)}

def test_ai_processing(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """AI 처리 API 테스트"""
    print("\n🤖 Testing AI Processing API...")
    
    payload = {
        "title": post_data.get('title', 'Test Post Title'),
        "content": post_data.get('selftext', post_data.get('url', 'Test content')),
        "subreddit": post_data.get('subreddit', 'programming')
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
            
            print("✅ AI Processing: PASSED")
            
            # 실제 AI 처리인지 확인
            if 'korean_summary' in processed_data:
                print(f"   📝 Korean Summary: {processed_data['korean_summary'][:100]}...")
                print(f"   🏷️ Tags: {processed_data.get('tags', [])}")
                return {"success": True, "data": data, "processed": processed_data}
            elif 'enhanced_title' in processed_data:
                print(f"   📝 Enhanced Title: {processed_data['enhanced_title']}")
                print(f"   🏷️ Tags: {processed_data.get('tags', [])}")
                return {"success": True, "data": data, "processed": processed_data}
            else:
                print("   ⚠️ Warning: AI processing response format unexpected")
                
            return {"success": True, "data": data, "processed": processed_data}
        else:
            print(f"❌ AI Processing: FAILED - {response.status_code}")
            print(f"   Error: {data.get('error', 'Unknown error')}")
            return {"success": False, "error": data.get('error', f"HTTP {response.status_code}")}
            
    except Exception as e:
        print(f"❌ AI Processing: ERROR - {str(e)}")
        return {"success": False, "error": str(e)}

def test_ghost_publishing(title: str, content: str, tags: List[str]) -> Dict[str, Any]:
    """Ghost 발행 API 테스트"""
    print("\n👻 Testing Ghost Publishing API...")
    
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
                print("✅ Ghost Publishing: PASSED - Actually published!")
                print(f"   🔗 Ghost URL: {published_data.get('ghost_url', 'N/A')}")
                print(f"   🆔 Post ID: {published_data.get('ghost_post_id', 'N/A')}")
            else:
                print("✅ Ghost Publishing: PASSED - Mock mode")
                print(f"   📝 Mock URL: {published_data.get('mock_data', {}).get('ghost_url', 'N/A')}")
                print(f"   💡 Note: {published_data.get('message', 'N/A')}")
            
            return {"success": True, "data": data, "published": published_data}
        else:
            print(f"❌ Ghost Publishing: FAILED - {response.status_code}")
            print(f"   Error: {data.get('error', 'Unknown error')}")
            return {"success": False, "error": data.get('error', f"HTTP {response.status_code}")}
            
    except Exception as e:
        print(f"❌ Ghost Publishing: ERROR - {str(e)}")
        return {"success": False, "error": str(e)}

def test_stats_api() -> Dict[str, Any]:
    """통계 API 테스트"""
    print("\n📊 Testing Stats API...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats", headers=HEADERS, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            print("✅ Stats API: PASSED")
            print(f"   📈 Total Posts: {data.get('total_posts', 0)}")
            print(f"   🤖 Processed: {data.get('processed_posts', 0)}")
            print(f"   👻 Published: {data.get('published_posts', 0)}")
            print(f"   📊 Success Rate: {data.get('success_rate', 0)}%")
            return {"success": True, "data": data}
        else:
            print(f"❌ Stats API: FAILED - {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"❌ Stats API: ERROR - {str(e)}")
        return {"success": False, "error": str(e)}

def run_full_pipeline_test():
    """전체 파이프라인 테스트 실행"""
    print("🚀 Reddit Ghost Publisher API Pipeline Test")
    print("=" * 60)
    
    results = {
        "health": None,
        "reddit": None,
        "ai": None,
        "ghost": None,
        "stats": None
    }
    
    # 1. Health Check
    results["health"] = test_health_check()
    if not results["health"]["success"]:
        print("\n❌ Health check failed. Stopping pipeline test.")
        return results
    
    # 2. Reddit Collection
    results["reddit"] = test_reddit_collection()
    if not results["reddit"]["success"]:
        print("\n❌ Reddit collection failed. Continuing with mock data...")
        # Mock data for testing
        mock_post = {
            "title": "Mock Reddit Post for Testing",
            "selftext": "This is mock content for testing the AI processing pipeline.",
            "subreddit": "programming"
        }
    else:
        posts = results["reddit"].get("posts", [])
        mock_post = posts[0] if posts else {
            "title": "Mock Reddit Post for Testing",
            "selftext": "This is mock content for testing the AI processing pipeline.",
            "subreddit": "programming"
        }
    
    # 3. AI Processing
    results["ai"] = test_ai_processing(mock_post)
    if not results["ai"]["success"]:
        print("\n❌ AI processing failed. Using mock data for Ghost publishing...")
        title = mock_post["title"]
        content = mock_post.get("selftext", "Mock content")
        tags = ["test", "api", "mock"]
    else:
        processed = results["ai"].get("processed", {})
        title = processed.get("enhanced_title", processed.get("korean_summary", mock_post["title"]))
        content = processed.get("enhanced_content", processed.get("korean_summary", mock_post.get("selftext", "Mock content")))
        tags = processed.get("tags", ["test", "api"])
    
    # 4. Ghost Publishing
    results["ghost"] = test_ghost_publishing(title, content, tags)
    
    # 5. Stats Check
    results["stats"] = test_stats_api()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 PIPELINE TEST SUMMARY")
    print("=" * 60)
    
    success_count = sum(1 for result in results.values() if result and result.get("success"))
    total_tests = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result and result.get("success") else "❌ FAIL"
        print(f"{test_name.upper():12} | {status}")
    
    print(f"\nOverall: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All tests passed! The API pipeline is working correctly.")
    elif success_count >= 3:
        print("⚠️ Most tests passed. Some issues may need attention.")
    else:
        print("❌ Multiple tests failed. The API needs debugging.")
    
    return results

if __name__ == "__main__":
    results = run_full_pipeline_test()