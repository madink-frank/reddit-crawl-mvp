#!/usr/bin/env python3
"""
Ghost에 어드민 대시보드 배포 스크립트
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

def create_or_update_ghost_page(html_content):
    """Ghost에 페이지 생성 또는 업데이트"""
    try:
        token = create_ghost_jwt()
        if not token:
            return False
        
        headers = {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json'
        }
        
        # 기존 페이지 확인
        pages_url = f"{GHOST_API_URL}/ghost/api/admin/pages/"
        response = requests.get(pages_url, headers=headers)
        
        existing_page = None
        if response.status_code == 200:
            pages = response.json().get('pages', [])
            for page in pages:
                if page.get('slug') == 'admin-dashboard':
                    existing_page = page
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
        
        # 페이지 데이터
        page_data = {
            'pages': [{
                'title': 'Reddit Ghost Publisher - Admin Dashboard',
                'slug': 'admin-dashboard',
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
                'featured': False,
                'page': True
            }]
        }
        
        if existing_page:
            # 기존 페이지 업데이트
            page_data['pages'][0]['id'] = existing_page['id']
            page_data['pages'][0]['updated_at'] = existing_page['updated_at']
            
            update_url = f"{GHOST_API_URL}/ghost/api/admin/pages/{existing_page['id']}/"
            response = requests.put(update_url, headers=headers, json=page_data)
            
            if response.status_code == 200:
                page_url = f"{GHOST_API_URL}/admin-dashboard/"
                print(f"✅ 페이지 업데이트 성공!")
                print(f"📊 어드민 대시보드 URL: {page_url}")
                return True
            else:
                print(f"❌ 페이지 업데이트 실패: {response.status_code}")
                print(f"응답: {response.text}")
                return False
        else:
            # 새 페이지 생성
            response = requests.post(pages_url, headers=headers, json=page_data)
            
            if response.status_code == 201:
                result = response.json()
                page_url = f"{GHOST_API_URL}/admin-dashboard/"
                print(f"✅ 페이지 생성 성공!")
                print(f"📊 어드민 대시보드 URL: {page_url}")
                return True
            else:
                print(f"❌ 페이지 생성 실패: {response.status_code}")
                print(f"응답: {response.text}")
                return False
                
    except Exception as e:
        print(f"Ghost API 오류: {e}")
        return False

def test_ghost_connection():
    """Ghost API 연결 테스트"""
    try:
        token = create_ghost_jwt()
        if not token:
            return False
        
        headers = {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json'
        }
        
        # 사이트 정보 조회
        site_url = f"{GHOST_API_URL}/ghost/api/admin/site/"
        response = requests.get(site_url, headers=headers)
        
        if response.status_code == 200:
            site_info = response.json()
            print(f"✅ Ghost API 연결 성공")
            print(f"사이트: {site_info.get('site', {}).get('title', 'Unknown')}")
            print(f"URL: {site_info.get('site', {}).get('url', 'Unknown')}")
            return True
        else:
            print(f"❌ Ghost API 연결 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Ghost 연결 테스트 오류: {e}")
        return False

def main():
    """메인 배포 함수"""
    print("🚀 Ghost에 어드민 대시보드 배포 시작")
    print("=" * 50)
    
    # 환경 변수 확인
    if not GHOST_ADMIN_KEY:
        print("❌ GHOST_ADMIN_KEY 환경 변수가 설정되지 않았습니다.")
        return
    
    print(f"Ghost URL: {GHOST_API_URL}")
    print(f"Admin Key: {GHOST_ADMIN_KEY[:20]}...")
    print()
    
    # Ghost API 연결 테스트
    print("1. Ghost API 연결 테스트...")
    if not test_ghost_connection():
        print("❌ Ghost API 연결 실패. 배포를 중단합니다.")
        return
    
    print()
    
    # HTML 파일 읽기
    print("2. 대시보드 HTML 파일 읽기...")
    html_content = read_dashboard_html()
    if not html_content:
        print("❌ HTML 파일 읽기 실패. 배포를 중단합니다.")
        return
    
    print(f"✅ HTML 파일 읽기 성공 ({len(html_content):,} 문자)")
    print()
    
    # Ghost에 페이지 배포
    print("3. Ghost에 페이지 배포...")
    if create_or_update_ghost_page(html_content):
        print()
        print("🎉 어드민 대시보드 배포 완료!")
        print("=" * 50)
        print(f"📊 대시보드 URL: {GHOST_API_URL}/admin-dashboard/")
        print("🌐 Ghost 블로그: https://american-trends.ghost.io")
        print()
        print("⚠️ 참고사항:")
        print("- 대시보드는 정적 HTML로 배포되었습니다.")
        print("- 실시간 API 연결을 위해서는 CORS 설정이 필요할 수 있습니다.")
        print("- 현재는 모의 데이터를 표시합니다.")
    else:
        print("❌ 어드민 대시보드 배포 실패")

if __name__ == "__main__":
    main()