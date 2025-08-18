#!/usr/bin/env python3
"""
Ghost API 진단 스크립트
"""

import sys
import requests
import jwt
from datetime import datetime, timedelta
sys.path.append('/app')

from app.config import settings

def diagnose_ghost_api():
    """Ghost API 상세 진단"""
    
    print("🔍 Ghost API 진단 시작")
    print("=" * 50)
    
    # 1. 설정 확인
    print("\n1️⃣ 설정 확인:")
    ghost_url = settings.ghost_api_url
    admin_key = settings.ghost_admin_key
    
    print(f"   Ghost URL: {ghost_url}")
    print(f"   Admin Key: {admin_key[:20]}..." if admin_key else "   Admin Key: None")
    
    if not ghost_url or not admin_key:
        print("❌ Ghost 설정이 누락되었습니다.")
        return False
    
    # 2. URL 구조 분석
    print("\n2️⃣ URL 구조 분석:")
    base_url = ghost_url
    if not base_url.endswith('/'):
        base_url += '/'
    if not base_url.endswith('ghost/api/v4/admin/'):
        base_url += 'ghost/api/v4/admin/'
    
    print(f"   Base URL: {base_url}")
    
    # 3. Admin Key 파싱
    print("\n3️⃣ Admin Key 파싱:")
    try:
        if ':' not in admin_key:
            print("❌ Admin Key 형식이 잘못되었습니다. 'key_id:secret' 형식이어야 합니다.")
            return False
        
        key_id, secret = admin_key.split(':', 1)
        print(f"   Key ID: {key_id}")
        print(f"   Secret: {secret[:10]}..." if secret else "   Secret: None")
        
        if not key_id or not secret:
            print("❌ Key ID 또는 Secret이 비어있습니다.")
            return False
            
    except Exception as e:
        print(f"❌ Admin Key 파싱 오류: {e}")
        return False
    
    # 4. JWT 토큰 생성 테스트
    print("\n4️⃣ JWT 토큰 생성 테스트:")
    try:
        # JWT 페이로드 생성
        now = datetime.utcnow()
        payload = {
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(minutes=5)).timestamp()),
            'aud': '/v4/admin/'
        }
        
        # JWT 토큰 생성 (kid 헤더 포함)
        token = jwt.encode(
            payload, 
            bytes.fromhex(secret), 
            algorithm='HS256',
            headers={'kid': key_id}
        )
        print(f"   ✅ JWT 토큰 생성 성공: {len(token)} characters")
        print(f"   토큰 샘플: {token[:50]}...")
        
    except Exception as e:
        print(f"❌ JWT 토큰 생성 실패: {e}")
        return False
    
    # 5. 기본 연결 테스트
    print("\n5️⃣ 기본 연결 테스트:")
    try:
        # Ghost 사이트 루트 접근 테스트
        site_url = ghost_url.replace('/ghost/api/v5/admin/', '').rstrip('/')
        print(f"   사이트 URL 테스트: {site_url}")
        
        response = requests.get(site_url, timeout=10)
        print(f"   사이트 응답: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ Ghost 사이트 접근 가능")
        else:
            print(f"   ⚠️ Ghost 사이트 응답 코드: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 기본 연결 테스트 실패: {e}")
    
    # 6. API 엔드포인트 테스트
    print("\n6️⃣ API 엔드포인트 테스트:")
    headers = {
        'Authorization': f'Ghost {token}',
        'Content-Type': 'application/json'
    }
    
    # 다양한 엔드포인트 테스트
    endpoints_to_test = [
        ('site/', 'Site Info'),
        ('posts/', 'Posts'),
        ('tags/', 'Tags'),
        ('users/', 'Users')
    ]
    
    for endpoint, description in endpoints_to_test:
        try:
            url = base_url + endpoint
            print(f"   테스트 중: {description} ({url})")
            
            response = requests.get(url, headers=headers, timeout=10)
            print(f"      응답 코드: {response.status_code}")
            
            if response.status_code == 200:
                print(f"      ✅ {description} 접근 성공")
            elif response.status_code == 401:
                print(f"      ❌ {description} 인증 실패")
            elif response.status_code == 403:
                print(f"      ❌ {description} 권한 없음")
            elif response.status_code == 404:
                print(f"      ❌ {description} 엔드포인트 없음")
            else:
                print(f"      ⚠️ {description} 예상치 못한 응답: {response.status_code}")
                
            # 응답 내용 일부 출력
            if response.text:
                content = response.text[:200]
                print(f"      응답 내용: {content}...")
                
        except Exception as e:
            print(f"      ❌ {description} 테스트 오류: {e}")
    
    # 7. API 버전 확인
    print("\n7️⃣ API 버전 확인:")
    try:
        # v3, v4, v5 버전 테스트
        versions_to_test = ['v3', 'v4', 'v5']
        
        for version in versions_to_test:
            version_url = ghost_url.replace('/ghost/api/v5/admin/', f'/ghost/api/{version}/admin/')
            if not version_url.endswith('/'):
                version_url += '/'
            version_url += 'site/'
            
            print(f"   테스트 중: API {version} ({version_url})")
            
            response = requests.get(version_url, headers=headers, timeout=5)
            print(f"      {version} 응답: {response.status_code}")
            
            if response.status_code == 200:
                print(f"      ✅ API {version} 사용 가능")
            elif response.status_code == 404:
                print(f"      ❌ API {version} 지원하지 않음")
                
    except Exception as e:
        print(f"❌ API 버전 확인 오류: {e}")
    
    print("\n" + "=" * 50)
    print("🔍 Ghost API 진단 완료")
    
    return True

if __name__ == "__main__":
    success = diagnose_ghost_api()
    sys.exit(0 if success else 1)