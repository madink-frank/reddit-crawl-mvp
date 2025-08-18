#!/usr/bin/env python3
"""
Ghost CMS에 Production 대시보드 페이지를 업로드하는 스크립트
"""
import requests
import jwt
import time
import os
from dotenv import load_dotenv

load_dotenv()

def upload_production_dashboard():
    """Ghost CMS에 Production 대시보드 페이지 업로드"""
    try:
        # Ghost 설정
        ghost_api_url = os.getenv('GHOST_API_URL')
        ghost_admin_key = os.getenv('GHOST_ADMIN_KEY')
        
        if ':' not in ghost_admin_key:
            print("❌ Ghost Admin Key 형식 오류")
            return False
        
        key_id, secret = ghost_admin_key.split(':', 1)
        
        # JWT 토큰 생성
        iat = int(time.time())
        exp = iat + 300  # 5분
        
        payload = {
            'iat': iat,
            'exp': exp,
            'aud': '/admin/'
        }
        
        token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers={'kid': key_id})
        
        # Ghost API 헤더
        headers = {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json'
        }
        
        # HTML 파일 읽기
        with open('ghost_production_dashboard.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Ghost 페이지 데이터
        page_data = {
            "pages": [{
                "title": "Production Dashboard",
                "slug": "production-dashboard",
                "html": html_content,
                "status": "published",
                "visibility": "public",
                "meta_title": "Reddit Ghost Publisher - Production Dashboard",
                "meta_description": "Reddit Ghost Publisher Production 환경 실시간 모니터링 및 제어 대시보드",
                "custom_excerpt": "Production 환경에서 실행되는 Reddit Ghost Publisher 시스템을 실시간으로 모니터링하고 제어할 수 있는 대시보드입니다.",
                "feature_image": None,
                "featured": True
            }]
        }
        
        print(f"👻 Ghost CMS에 Production 대시보드 업로드 중...")
        
        # 기존 페이지 확인
        existing_response = requests.get(
            f"{ghost_api_url}/ghost/api/admin/pages/slug/production-dashboard/",
            headers=headers,
            timeout=10
        )
        
        if existing_response.status_code == 200:
            # 기존 페이지 업데이트
            existing_page = existing_response.json()['pages'][0]
            page_id = existing_page['id']
            
            # 업데이트용 데이터 (updated_at 필요)
            page_data['pages'][0]['updated_at'] = existing_page['updated_at']
            
            response = requests.put(
                f"{ghost_api_url}/ghost/api/admin/pages/{page_id}/",
                headers=headers,
                json=page_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                page_url = result['pages'][0]['url']
                print(f"✅ Production 대시보드 업데이트 성공!")
                print(f"🔗 페이지 URL: {ghost_api_url}{page_url}")
                return page_url
            else:
                print(f"❌ 페이지 업데이트 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                return False
        else:
            # 새 페이지 생성
            response = requests.post(
                f"{ghost_api_url}/ghost/api/admin/pages/",
                headers=headers,
                json=page_data,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                page_url = result['pages'][0]['url']
                print(f"✅ Production 대시보드 생성 성공!")
                print(f"🔗 페이지 URL: {ghost_api_url}{page_url}")
                return page_url
            else:
                print(f"❌ 페이지 생성 실패: {response.status_code}")
                print(f"   응답: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Production 대시보드 업로드 오류: {e}")
        return False

def create_navigation_guide():
    """Ghost 네비게이션 설정 안내"""
    print("\n📋 Ghost 관리자 설정 안내:")
    print("1. Ghost 관리자 패널에 로그인하세요")
    print("2. Settings > Design > Navigation으로 이동하세요")
    print("3. 새 메뉴 항목을 추가하세요:")
    print("   - Label: 'Production Dashboard'")
    print("   - URL: '/production-dashboard/'")
    print("4. 저장하세요")
    print("\n이제 Ghost 사이트 메뉴에서 Production 대시보드에 접근할 수 있습니다!")

def main():
    """메인 실행 함수"""
    print("🚀 Ghost CMS Production 대시보드 배포")
    print("=" * 60)
    
    # HTML 파일 존재 확인
    if not os.path.exists('ghost_production_dashboard.html'):
        print("❌ ghost_production_dashboard.html 파일을 찾을 수 없습니다.")
        return
    
    # Ghost에 페이지 업로드
    page_url = upload_production_dashboard()
    
    if page_url:
        print(f"\n🎉 Production 대시보드가 성공적으로 배포되었습니다!")
        print(f"📱 접근 방법:")
        print(f"   1. 직접 URL: https://american-trends.ghost.io{page_url}")
        print(f"   2. Ghost 사이트 메뉴에서 'Production Dashboard' 클릭")
        
        create_navigation_guide()
        
        print(f"\n✨ 이제 어디서든 Production 대시보드에 접근할 수 있습니다!")
        print(f"🌐 외부 접근: https://american-trends.ghost.io{page_url}")
        print(f"🏠 로컬 접근: http://localhost:8083 (완전한 기능)")
        
    else:
        print("❌ Production 대시보드 배포에 실패했습니다.")

if __name__ == "__main__":
    main()