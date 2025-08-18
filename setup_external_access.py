#!/usr/bin/env python3
"""
외부 접근을 위한 설정 스크립트
서버 IP를 자동으로 감지하고 대시보드를 업데이트
"""

import requests
import socket
import subprocess
import os
import re

def get_public_ip():
    """공인 IP 주소 가져오기"""
    try:
        response = requests.get('https://api.ipify.org?format=text', timeout=5)
        return response.text.strip()
    except:
        try:
            response = requests.get('https://icanhazip.com', timeout=5)
            return response.text.strip()
        except:
            return None

def get_local_ip():
    """로컬 IP 주소 가져오기"""
    try:
        # 외부 서버에 연결을 시도하여 로컬 IP 확인
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

def update_dashboard_with_ip(server_ip):
    """대시보드 HTML에서 서버 IP 업데이트"""
    try:
        with open('ghost_external_dashboard.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # API_BASE_URL 업데이트
        updated_content = re.sub(
            r"const API_BASE_URL = 'http://YOUR_SERVER_IP:8000';",
            f"const API_BASE_URL = 'http://{server_ip}:8000';",
            content
        )
        
        # 정보 섹션의 서버 IP도 업데이트
        updated_content = re.sub(
            r"API 서버: YOUR_SERVER_IP:8000",
            f"API 서버: {server_ip}:8000",
            updated_content
        )
        
        with open('ghost_external_dashboard.html', 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"✅ 대시보드가 서버 IP {server_ip}로 업데이트되었습니다.")
        return True
    except Exception as e:
        print(f"❌ 대시보드 업데이트 실패: {e}")
        return False

def restart_docker_services():
    """Docker 서비스 재시작"""
    try:
        print("🔄 Docker 서비스를 재시작합니다...")
        subprocess.run(['docker-compose', 'restart', 'api'], check=True)
        print("✅ API 서버가 재시작되었습니다.")
        return True
    except Exception as e:
        print(f"❌ Docker 재시작 실패: {e}")
        return False

def upload_to_ghost():
    """업데이트된 대시보드를 Ghost에 업로드"""
    try:
        print("📤 Ghost에 외부 제어 대시보드를 업로드합니다...")
        result = subprocess.run(['python', 'upload_external_dashboard_to_ghost.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ghost 업로드 완료")
            return True
        else:
            print(f"❌ Ghost 업로드 실패: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Ghost 업로드 오류: {e}")
        return False

def main():
    print("🌐 Reddit Ghost Publisher 외부 접근 설정")
    print("=" * 60)
    
    # 1. IP 주소 확인
    print("🔍 서버 IP 주소를 확인합니다...")
    public_ip = get_public_ip()
    local_ip = get_local_ip()
    
    print(f"📍 공인 IP: {public_ip or '확인 불가'}")
    print(f"📍 로컬 IP: {local_ip}")
    
    # 사용할 IP 결정
    server_ip = public_ip if public_ip else local_ip
    print(f"🎯 사용할 서버 IP: {server_ip}")
    
    # 2. 대시보드 업데이트
    if update_dashboard_with_ip(server_ip):
        print("✅ 대시보드 IP 설정 완료")
    else:
        print("❌ 대시보드 IP 설정 실패")
        return
    
    # 3. Docker 서비스 재시작
    if restart_docker_services():
        print("✅ 서비스 재시작 완료")
    else:
        print("❌ 서비스 재시작 실패")
    
    # 4. Ghost 업로드
    if upload_to_ghost():
        print("✅ Ghost 배포 완료")
    else:
        print("❌ Ghost 배포 실패")
    
    print("\n🎉 외부 접근 설정 완료!")
    print(f"🌐 외부 제어 대시보드: https://american-trends.ghost.io/external-control/")
    print(f"🔗 API 서버: http://{server_ip}:8000")
    print(f"❤️ 헬스체크: http://{server_ip}:8000/health")
    
    print("\n📋 추가 설정 필요사항:")
    print("1. 방화벽에서 8000 포트 개방")
    print("2. 라우터에서 8000 포트 포워딩 설정 (필요시)")
    print("3. Ghost 네비게이션에 'External Control' 메뉴 추가")

if __name__ == "__main__":
    main()