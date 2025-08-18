#!/usr/bin/env python3
"""
최종 외부 API 연결 테스트
모든 API 키를 환경 변수에서 직접 로드하여 테스트합니다.
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

def test_all_apis():
    """모든 외부 API 연결 테스트"""
    print("🚀 최종 외부 API 연결 테스트")
    print("=" * 60)
    
    results = {}
    
    # 1. Reddit API 테스트
    print("🔍 Reddit API 테스트...")
    try:
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        user_agent = os.getenv('REDDIT_USER_AGENT', 'RedditGhostPublisher/1.0')
        
        auth_url = "https://www.reddit.com/api/v1/access_token"
        auth_data = {'grant_type': 'client_credentials'}
        auth_headers = {'User-Agent': user_agent}
        
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
            
            # 실제 데이터 조회 테스트
            api_headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': user_agent
            }
            
            test_response = requests.get(
                'https://oauth.reddit.com/r/programming/hot',
                headers=api_headers,
                params={'limit': 1},
                timeout=10
            )
            
            if test_response.status_code == 200:
                print("✅ Reddit API: OAuth + 데이터 조회 성공")
                results['reddit'] = True
            else:
                print(f"❌ Reddit API: 데이터 조회 실패 ({test_response.status_code})")
                results['reddit'] = False
        else:
            print(f"❌ Reddit API: OAuth 실패 ({response.status_code})")
            results['reddit'] = False
            
    except Exception as e:
        print(f"❌ Reddit API: 연결 실패 - {e}")
        results['reddit'] = False
    
    # 2. OpenAI API 테스트
    print("\n🤖 OpenAI API 테스트...")
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'user', 'content': 'Test message. Reply with "OK".'}
            ],
            'max_tokens': 10
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
            print(f"✅ OpenAI API: 호출 성공 - {message.strip()}")
            results['openai'] = True
        else:
            print(f"❌ OpenAI API: 호출 실패 ({response.status_code})")
            print(f"   응답: {response.text[:200]}...")
            results['openai'] = False
            
    except Exception as e:
        print(f"❌ OpenAI API: 연결 실패 - {e}")
        results['openai'] = False
    
    # 3. Ghost CMS API 테스트
    print("\n👻 Ghost CMS API 테스트...")
    try:
        admin_key = os.getenv('GHOST_ADMIN_KEY')
        api_url = os.getenv('GHOST_API_URL')
        
        if ':' not in admin_key:
            print("❌ Ghost API: Admin Key 형식 오류")
            results['ghost'] = False
        else:
            key_id, secret = admin_key.split(':', 1)
            
            # JWT 토큰 생성
            iat = int(time.time())
            exp = iat + 300  # 5분
            
            payload = {
                'iat': iat,
                'exp': exp,
                'aud': '/admin/'
            }
            
            token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
            
            headers = {
                'Authorization': f'Ghost {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{api_url}/ghost/api/admin/site/",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                site_data = response.json()
                site_title = site_data.get('site', {}).get('title', 'Unknown')
                print(f"✅ Ghost API: 연결 성공 - {site_title}")
                results['ghost'] = True
            else:
                print(f"❌ Ghost API: 호출 실패 ({response.status_code})")
                results['ghost'] = False
                
    except Exception as e:
        print(f"❌ Ghost API: 연결 실패 - {e}")
        results['ghost'] = False
    
    # 4. Slack Webhook 테스트
    print("\n💬 Slack Webhook 테스트...")
    try:
        webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        
        message = {
            'text': f'🧪 최종 API 테스트 완료 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'username': 'Reddit Ghost Publisher',
            'icon_emoji': ':white_check_mark:'
        }
        
        response = requests.post(
            webhook_url,
            json=message,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Slack Webhook: 메시지 전송 성공")
            results['slack'] = True
        else:
            print(f"❌ Slack Webhook: 전송 실패 ({response.status_code})")
            results['slack'] = False
            
    except Exception as e:
        print(f"❌ Slack Webhook: 연결 실패 - {e}")
        results['slack'] = False
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 최종 테스트 결과:")
    
    for service, result in results.items():
        status = "✅ 성공" if result else "❌ 실패"
        print(f"   {service.upper()}: {status}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n🎯 총 {success_count}/{total_count} API 연결 성공")
    
    if success_count == total_count:
        print("🎉 모든 외부 API 연결이 완벽하게 작동합니다!")
        print("✨ 외부 API 키 설정 태스크 완료!")
        return 0
    else:
        print("⚠️  일부 API에 문제가 있습니다. 위의 오류 메시지를 확인하세요.")
        return 1

if __name__ == "__main__":
    sys.exit(test_all_apis())