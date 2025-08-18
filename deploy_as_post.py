#!/usr/bin/env python3
"""
Ghost에 어드민 대시보드를 포스트로 배포하는 스크립트
"""
import os
import jwt
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

# Ghost 설정
GHOST_API_URL = os.getenv('GHOST_API_URL', 'https://american-trends.ghost.io')
GHOST_ADMIN_KEY = os.getenv('GHOST_ADMIN_KEY')

def create_ghost_jwt():
    """Ghost Admin API용 JWT 토큰 생성"""
    try:
        # Admin Key에서 ID와 Secret 분리
        key_id, secret = GHOST_ADMIN_KEY.split(':')
        
        # JWT 페이로드
        iat = int(datetime.now().timestamp())
        exp = iat + 300  # 5분 후 만료
        
        payload = {
            'iat': iat,
            'exp': exp,
            'aud': '/admin/'
        }
        
        # JWT 토큰 생성
        token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
        
        return token
        
    except Exception as e:
        print(f"JWT 토큰 생성 오류: {e}")
        return None

def read_dashboard_html():
    """대시보드 HTML 파일 읽기"""
    try:
        with open('ghost_admin_dashboard.html', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"HTML 파일 읽기 오류: {e}")
        return None

def create_or_update_ghost_post(html_content):
    """Ghost에 포스트 생성 또는 업데이트"""
    try:
        token = create_ghost_jwt()
        if not token:
            return False
        
        headers = {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json'
        }
        
        # 기존 포스트 확인
        posts_url = f"{GHOST_API_URL}/ghost/api/admin/posts/"
        response = requests.get(posts_url, headers=headers)
        
        existing_post = None
        if response.status_code == 200:
            posts = response.json().get('posts', [])
            for post in posts:
                if post.get('slug') == 'admin-dashboard-app':
                    existing_post = post
                    break
        
        # Ghost의 mobiledoc 형식으로 HTML 콘텐츠 래핑
        mobiledoc = {
            "version": "0.3.1",
            "atoms": [],
            "cards": [
                ["html", {
                    "html": html_content
                }]
            ],
            "markups": [],
            "sections": [
                [10, 0]
            ]
        }
        
        # 포스트 데이터
        post_data = {
            'posts': [{
                'title': 'Reddit Ghost Publisher - Admin Dashboard App',
                'slug': 'admin-dashboard-app',
                'mobiledoc': json.dumps(mobiledoc),
                'status': 'published',
                'visibility': 'public',
                'meta_title': 'Reddit Ghost Publisher Admin Dashboard',
                'meta_description': 'Production admin dashboard for Reddit Ghost Publisher system',
                'og_title': 'Reddit Ghost Publisher Admin',
                'og_description': 'Real-time monitoring and control dashboard',
                'twitter_title': 'Reddit Ghost Publisher Admin',
                'twitter_description': 'Production admin dashboard',
                'custom_excerpt': 'Real-time admin dashboard for Reddit Ghost Publisher',
                'feature_image': None,
                'featured': True,
                'tags': ['admin', 'dashboard', 'reddit', 'ghost']
            }]
        }
        
        if existing_post:
            # 기존 포스트 업데이트
            post_data['posts'][0]['id'] = existing_post['id']
            post_data['posts'][0]['updated_at'] = existing_post['updated_at']
            
            update_url = f"{GHOST_API_URL}/ghost/api/admin/posts/{existing_post['id']}/"
            response = requests.put(update_url, headers=headers, json=post_data)
            
            if response.status_code == 200:
                post_url = f"{GHOST_API_URL}/admin-dashboard-app/"
                print(f"✅ 포스트 업데이트 성공!")
                print(f"📊 어드민 대시보드 URL: {post_url}")
                return True
            else:
                print(f"❌ 포스트 업데이트 실패: {response.status_code}")
                print(f"응답: {response.text}")
                return False
        else:
            # 새 포스트 생성
            response = requests.post(posts_url, headers=headers, json=post_data)
            
            if response.status_code == 201:
                result = response.json()
                post_url = f"{GHOST_API_URL}/admin-dashboard-app/"
                print(f"✅ 포스트 생성 성공!")
                print(f"📊 어드민 대시보드 URL: {post_url}")
                return True
            else:
                print(f"❌ 포스트 생성 실패: {response.status_code}")
                print(f"응답: {response.text}")
                return False
                
    except Exception as e:
        print(f"Ghost API 오류: {e}")
        return False

def main():
    """메인 배포 함수"""
    print("🚀 Ghost에 어드민 대시보드를 포스트로 배포 시작")
    print("=" * 50)
    
    # 환경 변수 확인
    if not GHOST_ADMIN_KEY:
        print("❌ GHOST_ADMIN_KEY 환경 변수가 설정되지 않았습니다.")
        return
    
    print(f"Ghost URL: {GHOST_API_URL}")
    print()
    
    # HTML 파일 읽기
    print("1. 대시보드 HTML 파일 읽기...")
    html_content = read_dashboard_html()
    if not html_content:
        print("❌ HTML 파일 읽기 실패. 배포를 중단합니다.")
        return
    
    print(f"✅ HTML 파일 읽기 성공 ({len(html_content):,} 문자)")
    print()
    
    # Ghost에 포스트 배포
    print("2. Ghost에 포스트로 배포...")
    if create_or_update_ghost_post(html_content):
        print()
        print("🎉 어드민 대시보드 포스트 배포 완료!")
        print("=" * 50)
        print(f"📊 대시보드 URL: {GHOST_API_URL}/admin-dashboard-app/")
        print("🌐 Ghost 블로그: https://american-trends.ghost.io")
        print()
        print("⚠️ 참고사항:")
        print("- 대시보드가 포스트로 배포되었습니다.")
        print("- HTML 카드를 통해 전체 대시보드가 표시됩니다.")
    else:
        print("❌ 어드민 대시보드 포스트 배포 실패")

if __name__ == "__main__":
    main()