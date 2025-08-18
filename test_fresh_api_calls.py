#!/usr/bin/env python3
"""
새로운 환경 변수로 실제 외부 API 호출 테스트
캐시를 우회하고 직접 환경 변수에서 로드합니다.
"""
import os
import sys
import requests
import json
import jwt
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env 파일을 강제로 다시 로드
load_dotenv(override=True)

def test_openai_with_new_key():
    """새로운 OpenAI API 키로 실제 호출 테스트"""
    print("🤖 새로운 OpenAI API 키로 실제 호출 테스트...")
    
    # 환경 변수에서 직접 로드
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        return False
    
    print(f"   사용 중인 API 키: {api_key[:20]}...")
    
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # 간단한 테스트 요청
        data = {
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'user', 'content': 'Hello, this is a test. Please respond with "API connection successful".'}
            ],
            'max_tokens': 20
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            print(f"✅ OpenAI API 호출 성공: {message.strip()}")
            return True
        else:
            print(f"❌ OpenAI API 호출 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI API 연결 실패: {e}")
        return False

def test_reddit_with_env():
    """환경 변수에서 직접 Reddit API 테스트"""
    print("🔍 환경 변수에서 직접 Reddit API 테스트...")
    
    client_id = os.getenv('REDDIT_CLIENT_ID')
    client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    user_agent = os.getenv('REDDIT_USER_AGENT', 'RedditGhostPublisher/1.0')
    
    print(f"   Reddit Client ID: {client_id}")
    
    try:
        # Reddit OAuth 토큰 요청
        auth_url = "https://www.reddit.com/api/v1/access_token"
        auth_data = {
            'grant_type': 'client_credentials'
        }
        auth_headers = {
            'User-Agent': user_agent
        }
        
        response = requests.post(
            auth_url,
            data=auth_data,
            headers=auth_headers,
            auth=(client_id, client_secret),
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            print(f"✅ Reddit OAuth 토큰 획득 성공: {access_token[:20]}...")
            return True
        else:
            print(f"❌ Reddit OAuth 토큰 획득 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Reddit API 연결 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 새로운 환경 변수로 API 호출 테스트 시작")
    print("=" * 60)
    
    # 현재 환경 변수 확인
    print("📋 현재 환경 변수 상태:")
    print(f"   OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'NOT_SET')[:30]}...")
    print(f"   REDDIT_CLIENT_ID: {os.getenv('REDDIT_CLIENT_ID', 'NOT_SET')}")
    print(f"   REDDIT_CLIENT_SECRET: {'설정됨' if os.getenv('REDDIT_CLIENT_SECRET') else '미설정'}")
    print()
    
    results = {
        'openai': test_openai_with_new_key(),
        'reddit': test_reddit_with_env()
    }
    
    print("\n" + "=" * 60)
    print("📊 테스트 결과:")
    
    for service, result in results.items():
        status = "✅ 성공" if result else "❌ 실패"
        print(f"   {service.upper()}: {status}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n총 {success_count}/{total_count} API 호출 성공")
    
    if success_count == total_count:
        print("🎉 모든 API 연결이 성공했습니다!")
        return 0
    else:
        print("⚠️  일부 API 호출에 문제가 있습니다.")
        return 1

if __name__ == "__main__":
    sys.exit(main())