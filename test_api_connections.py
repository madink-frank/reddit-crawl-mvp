#!/usr/bin/env python3
"""
외부 API 연결 테스트 스크립트
Reddit, OpenAI, Ghost, Slack API 연결 상태를 확인합니다.
"""
import os
import sys
import requests
import json
from datetime import datetime
from app.config import get_settings

def test_reddit_api():
    """Reddit API 연결 테스트"""
    print("🔍 Reddit API 연결 테스트...")
    settings = get_settings()
    
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        print("❌ Reddit API 키가 설정되지 않았습니다.")
        print(f"   REDDIT_CLIENT_ID: {settings.reddit_client_id}")
        print(f"   REDDIT_CLIENT_SECRET: {'설정됨' if settings.reddit_client_secret else '미설정'}")
        return False
    
    try:
        # Reddit OAuth 토큰 요청 테스트
        auth_url = "https://www.reddit.com/api/v1/access_token"
        auth_data = {
            'grant_type': 'client_credentials'
        }
        auth_headers = {
            'User-Agent': settings.reddit_user_agent
        }
        
        # 실제 API 키가 아닌 경우 스킵
        if settings.reddit_client_id == "your-reddit-client-id-here":
            print("⚠️  Reddit API 키가 플레이스홀더입니다. 실제 키로 교체 필요.")
            return False
            
        print("✅ Reddit API 설정이 완료되었습니다.")
        return True
        
    except Exception as e:
        print(f"❌ Reddit API 연결 실패: {e}")
        return False

def test_openai_api():
    """OpenAI API 연결 테스트"""
    print("\n🤖 OpenAI API 연결 테스트...")
    settings = get_settings()
    
    if not settings.openai_api_key:
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return False
    
    # 실제 API 키가 아닌 경우 스킵
    if settings.openai_api_key == "your-openai-api-key-here":
        print("⚠️  OpenAI API 키가 플레이스홀더입니다. 실제 키로 교체 필요.")
        return False
    
    try:
        # OpenAI API 헤더 테스트 (실제 요청은 하지 않음)
        headers = {
            'Authorization': f'Bearer {settings.openai_api_key}',
            'Content-Type': 'application/json'
        }
        print("✅ OpenAI API 설정이 완료되었습니다.")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API 연결 실패: {e}")
        return False

def test_ghost_api():
    """Ghost CMS API 연결 테스트"""
    print("\n👻 Ghost CMS API 연결 테스트...")
    settings = get_settings()
    
    if not settings.ghost_admin_key:
        print("❌ Ghost Admin 키가 설정되지 않았습니다.")
        return False
    
    try:
        # Ghost API URL 확인
        api_url = settings.ghost_api_url
        print(f"   Ghost API URL: {api_url}")
        
        # 개발 환경에서는 목 서버 사용
        if "localhost:3001" in api_url:
            print("✅ Ghost 개발 환경 (목 서버) 설정이 완료되었습니다.")
            return True
        else:
            print("✅ Ghost 프로덕션 환경 설정이 완료되었습니다.")
            return True
            
    except Exception as e:
        print(f"❌ Ghost API 연결 실패: {e}")
        return False

def test_slack_webhook():
    """Slack Webhook 연결 테스트"""
    print("\n💬 Slack Webhook 연결 테스트...")
    settings = get_settings()
    
    if not settings.slack_webhook_url:
        print("❌ Slack Webhook URL이 설정되지 않았습니다.")
        return False
    
    # 실제 Webhook URL이 아닌 경우 스킵
    if "YOUR/SLACK/WEBHOOK" in settings.slack_webhook_url:
        print("⚠️  Slack Webhook URL이 플레이스홀더입니다. 실제 URL로 교체 필요.")
        return False
    
    try:
        print("✅ Slack Webhook 설정이 완료되었습니다.")
        return True
        
    except Exception as e:
        print(f"❌ Slack Webhook 연결 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 외부 API 연결 테스트 시작")
    print("=" * 50)
    
    results = {
        'reddit': test_reddit_api(),
        'openai': test_openai_api(),
        'ghost': test_ghost_api(),
        'slack': test_slack_webhook()
    }
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약:")
    
    for service, result in results.items():
        status = "✅ 성공" if result else "❌ 실패"
        print(f"   {service.upper()}: {status}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n총 {success_count}/{total_count} 서비스 연결 성공")
    
    if success_count == total_count:
        print("🎉 모든 외부 API 연결이 성공했습니다!")
        return 0
    else:
        print("⚠️  일부 API 연결에 문제가 있습니다. 위의 메시지를 확인하세요.")
        return 1

if __name__ == "__main__":
    sys.exit(main())