#!/usr/bin/env python3
"""
Ghost 사이트 구조 탐색 스크립트
"""

import sys
import requests
import re
from urllib.parse import urljoin
sys.path.append('/app')

from app.config import settings

def explore_ghost_structure():
    """Ghost 사이트 구조 탐색"""
    
    print("🔍 Ghost 사이트 구조 탐색")
    print("=" * 50)
    
    base_site_url = "https://american-trends.ghost.io"
    
    # 1. 메인 페이지 분석
    print("\n1️⃣ 메인 페이지 분석:")
    try:
        response = requests.get(base_site_url, timeout=10)
        print(f"   상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            print(f"   페이지 크기: {len(content)} characters")
            
            # Ghost 버전 찾기
            version_match = re.search(r'generator.*ghost["\s]*([0-9.]+)', content, re.IGNORECASE)
            if version_match:
                ghost_version = version_match.group(1)
                print(f"   ✅ Ghost 버전: {ghost_version}")
            else:
                print("   ⚠️ Ghost 버전 정보를 찾을 수 없음")
            
            # API 관련 정보 찾기
            api_patterns = [
                r'api["\s]*:.*?["\s]([^"]+)',
                r'ghost.*api.*?([v\d/]+)',
                r'/ghost/api/([^"\']+)'
            ]
            
            for pattern in api_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    print(f"   API 패턴 발견: {matches}")
        
    except Exception as e:
        print(f"❌ 메인 페이지 분석 오류: {e}")
    
    # 2. 일반적인 Ghost API 경로 테스트
    print("\n2️⃣ 일반적인 Ghost API 경로 테스트:")
    
    api_paths_to_test = [
        # Content API (공개)
        "/ghost/api/content/",
        "/ghost/api/v3/content/",
        "/ghost/api/v4/content/",
        "/ghost/api/v5/content/",
        
        # Admin API (인증 필요)
        "/ghost/api/admin/",
        "/ghost/api/v3/admin/",
        "/ghost/api/v4/admin/",
        "/ghost/api/v5/admin/",
        
        # 기타 가능한 경로
        "/api/",
        "/api/v1/",
        "/api/admin/",
        "/admin/api/",
    ]
    
    for api_path in api_paths_to_test:
        try:
            url = base_site_url + api_path
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"   ✅ {api_path}: 접근 가능 (200)")
                # 응답 내용 확인
                try:
                    json_data = response.json()
                    if 'version' in json_data:
                        print(f"      버전: {json_data['version']}")
                except:
                    pass
            elif response.status_code == 401:
                print(f"   🔐 {api_path}: 인증 필요 (401)")
            elif response.status_code == 403:
                print(f"   🚫 {api_path}: 권한 없음 (403)")
            elif response.status_code == 404:
                print(f"   ❌ {api_path}: 없음 (404)")
            else:
                print(f"   ⚠️ {api_path}: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ {api_path}: 오류 ({e})")
    
    # 3. Content API 테스트 (공개 API)
    print("\n3️⃣ Content API 테스트:")
    
    content_endpoints = [
        "/ghost/api/content/posts/",
        "/ghost/api/v3/content/posts/",
        "/ghost/api/v4/content/posts/",
        "/ghost/api/v5/content/posts/",
    ]
    
    for endpoint in content_endpoints:
        try:
            url = base_site_url + endpoint
            # Content API는 key 파라미터가 필요할 수 있음
            params = {"key": "demo_key"}  # 임시 키
            
            response = requests.get(url, params=params, timeout=5)
            print(f"   {endpoint}: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'posts' in data:
                        print(f"      ✅ Posts 데이터 발견: {len(data['posts'])} posts")
                except:
                    pass
            elif response.status_code == 401:
                print(f"      🔐 API 키 필요")
            elif response.status_code == 403:
                print(f"      🚫 유효하지 않은 API 키")
                
        except Exception as e:
            print(f"   ❌ {endpoint}: 오류 ({e})")
    
    # 4. robots.txt 및 sitemap 확인
    print("\n4️⃣ 사이트 메타데이터 확인:")
    
    meta_urls = [
        "/robots.txt",
        "/sitemap.xml",
        "/.well-known/",
        "/admin/",
        "/ghost/",
    ]
    
    for meta_url in meta_urls:
        try:
            url = base_site_url + meta_url
            response = requests.get(url, timeout=5)
            print(f"   {meta_url}: {response.status_code}")
            
            if response.status_code == 200 and meta_url in ["/robots.txt", "/sitemap.xml"]:
                content_preview = response.text[:200].replace('\n', ' ')
                print(f"      내용: {content_preview}...")
                
        except Exception as e:
            print(f"   ❌ {meta_url}: 오류 ({e})")
    
    print("\n" + "=" * 50)
    print("🔍 Ghost 사이트 구조 탐색 완료")
    
    return True

if __name__ == "__main__":
    success = explore_ghost_structure()
    sys.exit(0 if success else 1)