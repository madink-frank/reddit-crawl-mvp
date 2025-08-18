#!/usr/bin/env python3
"""
Reddit 크롤링 시작 스크립트
API를 통해 수집, 처리, 발행을 트리거합니다.
"""
import requests
import json
import time
from datetime import datetime

# API 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"  # .env 파일의 API_KEY와 일치해야 함

def trigger_collection(subreddits=None, batch_size=20, force=False):
    """Reddit 수집 트리거"""
    print("🔍 Reddit 수집 시작...")
    
    url = f"{API_BASE_URL}/api/v1/collect/trigger"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    data = {
        "subreddits": subreddits or ["programming", "technology", "webdev"],
        "batch_size": batch_size,
        "force": force
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 수집 트리거 성공!")
            print(f"   Task ID: {result.get('task_id')}")
            print(f"   메시지: {result.get('message')}")
            return result.get('task_id')
        else:
            print(f"❌ 수집 트리거 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 수집 트리거 오류: {e}")
        return None

def trigger_full_pipeline(subreddits=None, batch_size=20):
    """전체 파이프라인 트리거 (수집 → 처리 → 발행)"""
    print("🚀 전체 파이프라인 시작...")
    
    url = f"{API_BASE_URL}/api/v1/pipeline/trigger"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    data = {
        "subreddits": subreddits or ["programming", "technology", "webdev"],
        "batch_size": batch_size
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 파이프라인 트리거 성공!")
            print(f"   Task ID: {result.get('task_id')}")
            print(f"   메시지: {result.get('message')}")
            return result.get('task_id')
        else:
            print(f"❌ 파이프라인 트리거 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 파이프라인 트리거 오류: {e}")
        return None

def check_system_status():
    """시스템 상태 확인"""
    print("🔍 시스템 상태 확인...")
    
    try:
        # 헬스체크
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if health_response.status_code == 200:
            print("✅ API 서버 정상")
        else:
            print(f"❌ API 서버 문제: {health_response.status_code}")
            return False
        
        # 큐 상태 확인
        status_response = requests.get(
            f"{API_BASE_URL}/api/v1/status/queues",
            headers={"X-API-Key": API_KEY},
            timeout=10
        )
        
        if status_response.status_code == 200:
            status_data = status_response.json()
            print("📊 큐 상태:")
            for queue_name, queue_info in status_data.get("queues", {}).items():
                print(f"   {queue_name}: {queue_info.get('length', 0)} 작업 대기 중")
        
        return True
        
    except Exception as e:
        print(f"❌ 상태 확인 오류: {e}")
        return False

def monitor_task(task_id, timeout=300):
    """작업 진행 상황 모니터링"""
    if not task_id:
        return
    
    print(f"📊 작업 {task_id} 모니터링 중...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # 작업 상태 확인 (실제 구현에서는 task status API 사용)
            print(f"   작업 진행 중... ({int(time.time() - start_time)}초 경과)")
            time.sleep(10)
            
            # 간단한 상태 확인 (실제로는 Celery task status API 사용)
            status_response = requests.get(
                f"{API_BASE_URL}/api/v1/status/queues",
                headers={"X-API-Key": API_KEY},
                timeout=10
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                total_queued = sum(
                    queue_info.get('length', 0) 
                    for queue_info in status_data.get("queues", {}).values()
                )
                
                if total_queued == 0:
                    print("✅ 모든 작업이 완료된 것 같습니다!")
                    break
                else:
                    print(f"   대기 중인 작업: {total_queued}개")
            
        except Exception as e:
            print(f"   모니터링 오류: {e}")
            break
    
    print("📊 모니터링 완료")

def main():
    """메인 실행 함수"""
    print("🚀 Reddit Ghost Publisher 크롤링 시작")
    print("=" * 50)
    
    # 1. 시스템 상태 확인
    if not check_system_status():
        print("❌ 시스템 상태에 문제가 있습니다. 먼저 시스템을 시작하세요.")
        print("\n시스템 시작 명령어:")
        print("  make run  # 또는 docker-compose up -d")
        return
    
    print("\n" + "=" * 50)
    
    # 2. 사용자 선택
    print("크롤링 옵션을 선택하세요:")
    print("1. Reddit 수집만 실행")
    print("2. 전체 파이프라인 실행 (수집 → 처리 → 발행)")
    print("3. 커스텀 설정으로 수집")
    
    try:
        choice = input("\n선택 (1-3): ").strip()
        
        if choice == "1":
            # 기본 수집
            task_id = trigger_collection()
            monitor_task(task_id)
            
        elif choice == "2":
            # 전체 파이프라인
            task_id = trigger_full_pipeline()
            monitor_task(task_id)
            
        elif choice == "3":
            # 커스텀 설정
            subreddits_input = input("서브레딧 목록 (쉼표로 구분, 기본값: programming,technology,webdev): ").strip()
            batch_size_input = input("배치 크기 (기본값: 20): ").strip()
            
            subreddits = [s.strip() for s in subreddits_input.split(",")] if subreddits_input else None
            batch_size = int(batch_size_input) if batch_size_input.isdigit() else 20
            
            task_id = trigger_collection(subreddits, batch_size)
            monitor_task(task_id)
            
        else:
            print("잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")

if __name__ == "__main__":
    main()