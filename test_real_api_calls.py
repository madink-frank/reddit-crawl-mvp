#!/usr/bin/env python3
"""
실제 외부 API 호출 테스트
각 API에 실제 요청을 보내서 연결 상태를 확인합니다.
"""
import os
import sys
import requests
import json
import jwt
import time
from datetime import datetime, timedelta
from app.config import get_settings

def test_reddit_real_api():
    """실제 Reddit API 호출 테스트"""
    print("🔍 Reddit API 실제 호출 테스트...")
    settings = get_settings()
    
    try:
        # Reddit OAuth 토큰 요청
        auth_url = "https://www.reddit.com/api/v1/access_token"
        auth_data = {
            'grant_type': 'client_credentials'
        }
        auth_headers = {
            'User-Agent': settings.reddit_user_agent
        }
        
        response = requests.post(
            auth_url,
            data=auth_data,
            headers=auth_headers,
            auth=(settings.reddit_client_id, settings.reddit_client_secret),
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            print(f"✅ Reddit OAuth 토큰 획득 성공: {access_token[:20]}...")
            
            # 간단한 API 호출 테스트
            api_headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': settings.reddit_user_agent
            }
            
            test_response = requests.get(
                'https://oauth.reddit.com/r/programming/hot',
                headers=api_headers,
                params={'limit': 1},
                timeout=10
            )
            
            if test_response.status_code == 200:
                print("✅ Reddit API 데이터 조회 성공")
                return True
            else:
                print(f"❌ Reddit API 데이터 조회 실패: {test_response.status_code}")
                return False
        else:
            print(f"❌ Reddit OAuth 토큰 획득 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Reddit API 연결 실패: {e}")
        return False

def test_openai_real_api():
    """실제 OpenAI API 호출 테스트"""
    print("\n🤖 OpenAI API 실제 호출 테스트...")
    settings = get_settings()
    
    try:
        headers = {
            'Authorization': f'Bearer {settings.openai_api_key}',
            'Content-Type': 'application/json'
        }
        
        # 간단한 테스트 요청
        data = {
            'model': settings.openai_primary_model,
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

def test_ghost_real_api():
    """실제 Ghost CMS API 호출 테스트"""
    print("\n👻 Ghost CMS API 실제 호출 테스트...")
    settings = get_settings()
    
    try:
        # Ghost Admin Key 파싱
        if ':' not in settings.ghost_admin_key:
            print("❌ Ghost Admin Key 형식이 잘못되었습니다. (key_id:secret 형태여야 함)")
            return False
            
        key_id, secret = settings.ghost_admin_key.split(':', 1)
        
        # JWT 토큰 생성
        iat = int(time.time())
        exp = iat + settings.ghost_jwt_expiry
        
        payload = {
            'iat': iat,
            'exp': exp,
            'aud': '/admin/'
        }
        
        token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
        
        # Ghost API 호출
        headers = {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{settings.ghost_api_url}/ghost/api/admin/site/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            site_data = response.json()
            site_title = site_data.get('site', {}).get('title', 'Unknown')
            print(f"✅ Ghost API 호출 성공: 사이트 제목 = {site_title}")
            return True
        else:
            print(f"❌ Ghost API 호출 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ghost API 연결 실패: {e}")
        return False

def test_slack_real_webhook():
    """실제 Slack Webhook 호출 테스트"""
    print("\n💬 Slack Webhook 실제 호출 테스트...")
    settings = get_settings()
    
    try:
        # 테스트 메시지 전송
        message = {
            'text': f'🧪 API 연결 테스트 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'username': 'Reddit Ghost Publisher',
            'icon_emoji': ':robot_face:'
        }
        
        response = requests.post(
            settings.slack_webhook_url,
            json=message,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Slack Webhook 호출 성공")
            return True
        else:
            print(f"❌ Slack Webhook 호출 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Slack Webhook 연결 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 실제 외부 API 호출 테스트 시작")
    print("=" * 50)
    
    results = {
        'reddit': test_reddit_real_api(),
        'openai': test_openai_real_api(),
        'ghost': test_ghost_real_api(),
        'slack': test_slack_real_webhook()
    }
    
    print("\n" + "=" * 50)
    print("📊 실제 API 호출 테스트 결과:")
    
    for service, result in results.items():
        status = "✅ 성공" if result else "❌ 실패"
        print(f"   {service.upper()}: {status}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n총 {success_count}/{total_count} API 실제 호출 성공")
    
    if success_count == total_count:
        print("🎉 모든 외부 API 실제 연결이 성공했습니다!")
        return 0
    else:
        print("⚠️  일부 API 실제 호출에 문제가 있습니다.")
        return 1

if __name__ == "__main__":
    sys.exit(main())