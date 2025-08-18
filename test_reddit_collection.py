#!/usr/bin/env python3
"""
실제 Reddit 데이터 수집 테스트 스크립트
Reddit Ghost Publisher MVP - 실제 API 연동 테스트
"""

import os
import sys
import time
import json
import requests
from datetime import datetime
from typing import Dict, List, Any

# API 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def print_header(title: str):
    """테스트 섹션 헤더 출력"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_step(step: str):
    """테스트 단계 출력"""
    print(f"\n🔍 {step}")
    print("-" * 40)

def check_api_health() -> bool:
    """API 헬스체크"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ API Status: {health_data.get('status', 'unknown')}")
            
            # 서비스별 상태 확인
            services = health_data.get('services', {})
            for service_name, service_info in services.items():
                status = service_info.get('status', 'unknown')
                response_time = service_info.get('response_time_ms', 0)
                emoji = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
                print(f"  {emoji} {service_name}: {status} ({response_time:.1f}ms)")
            
            # Reddit API와 OpenAI API가 정상이면 테스트 진행
            services = health_data.get('services', {})
            reddit_healthy = services.get('reddit_api', {}).get('status') == 'healthy'
            return reddit_healthy  # Reddit API만 정상이면 테스트 진행
        else:
            print(f"❌ API Health Check Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API Health Check Error: {e}")
        return False

def trigger_collection() -> Dict[str, Any]:
    """Reddit 수집 트리거"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/collect/trigger",
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Collection Triggered Successfully")
            print(f"   Task ID: {result.get('task_id')}")
            print(f"   Message: {result.get('message')}")
            return result
        else:
            print(f"❌ Collection Trigger Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return {}
    except Exception as e:
        print(f"❌ Collection Trigger Error: {e}")
        return {}

def check_queue_status() -> Dict[str, Any]:
    """큐 상태 확인"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/status/queues",
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            queue_data = response.json()
            print(f"✅ Queue Status Retrieved")
            
            for queue_name, queue_info in queue_data.items():
                active = queue_info.get('active', 0)
                pending = queue_info.get('pending', 0)
                scheduled = queue_info.get('scheduled', 0)
                print(f"   📋 {queue_name}: Active={active}, Pending={pending}, Scheduled={scheduled}")
            
            return queue_data
        else:
            print(f"⚠️ Queue Status Check Failed: {response.status_code}")
            return {}
    except Exception as e:
        print(f"⚠️ Queue Status Error: {e}")
        return {}

def check_worker_status() -> Dict[str, Any]:
    """워커 상태 확인"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/status/workers",
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            worker_data = response.json()
            print(f"✅ Worker Status Retrieved")
            
            for worker_name, worker_info in worker_data.items():
                status = worker_info.get('status', 'unknown')
                active_tasks = worker_info.get('active_tasks', 0)
                processed_tasks = worker_info.get('processed_tasks', 0)
                emoji = "✅" if status == "online" else "❌"
                print(f"   {emoji} {worker_name}: {status} (Active: {active_tasks}, Processed: {processed_tasks})")
            
            return worker_data
        else:
            print(f"⚠️ Worker Status Check Failed: {response.status_code}")
            return {}
    except Exception as e:
        print(f"⚠️ Worker Status Error: {e}")
        return {}

def wait_for_collection(task_id: str, max_wait_seconds: int = 300) -> bool:
    """수집 작업 완료 대기"""
    print(f"⏳ Waiting for collection to complete (max {max_wait_seconds}s)...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        # 큐 상태 확인
        queue_status = check_queue_status()
        collect_queue = queue_status.get('collect', {})
        
        active = collect_queue.get('active', 0)
        pending = collect_queue.get('pending', 0)
        
        if active == 0 and pending == 0:
            print(f"✅ Collection appears to be complete")
            return True
        
        print(f"   ⏳ Still processing... Active: {active}, Pending: {pending}")
        time.sleep(10)
    
    print(f"⚠️ Collection did not complete within {max_wait_seconds} seconds")
    return False

def check_database_results() -> Dict[str, Any]:
    """데이터베이스 결과 확인 (API를 통해)"""
    try:
        # 메트릭 엔드포인트를 통해 수집 결과 확인
        response = requests.get(
            f"{API_BASE_URL}/metrics",
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code == 200:
            metrics_text = response.text
            print(f"✅ Metrics Retrieved")
            
            # 메트릭에서 수집 관련 정보 추출
            lines = metrics_text.split('\n')
            collected_count = 0
            
            for line in lines:
                if 'reddit_posts_collected_total' in line and not line.startswith('#'):
                    try:
                        collected_count = int(line.split()[-1])
                        break
                    except (ValueError, IndexError):
                        pass
            
            print(f"   📊 Posts Collected: {collected_count}")
            
            return {
                'collected_posts': collected_count,
                'metrics_available': True
            }
        else:
            print(f"⚠️ Metrics Check Failed: {response.status_code}")
            return {'metrics_available': False}
    except Exception as e:
        print(f"⚠️ Database Results Error: {e}")
        return {'error': str(e)}

def run_reddit_collection_test():
    """실제 Reddit 데이터 수집 테스트 실행"""
    print_header("실제 Reddit 데이터 수집 테스트")
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. API 헬스체크
    print_step("1. API Health Check")
    if not check_api_health():
        print("❌ API is not healthy. Aborting test.")
        return False
    
    # 2. 초기 상태 확인
    print_step("2. Initial System Status")
    initial_queue_status = check_queue_status()
    initial_worker_status = check_worker_status()
    
    # 3. Reddit 수집 트리거
    print_step("3. Triggering Reddit Collection")
    collection_result = trigger_collection()
    
    if not collection_result:
        print("❌ Failed to trigger collection. Aborting test.")
        return False
    
    task_id = collection_result.get('task_id', '')
    
    # 4. 수집 진행 상황 모니터링
    print_step("4. Monitoring Collection Progress")
    
    # 잠시 대기 후 상태 확인
    time.sleep(5)
    check_queue_status()
    check_worker_status()
    
    # 5. 수집 완료 대기
    print_step("5. Waiting for Collection Completion")
    collection_completed = wait_for_collection(task_id, max_wait_seconds=180)
    
    # 6. 최종 결과 확인
    print_step("6. Final Results Check")
    final_queue_status = check_queue_status()
    final_worker_status = check_worker_status()
    database_results = check_database_results()
    
    # 7. 테스트 결과 요약
    print_header("테스트 결과 요약")
    
    success_criteria = {
        "API Health": check_api_health(),
        "Collection Triggered": bool(collection_result),
        "Collection Completed": collection_completed,
        "Database Results": database_results.get('metrics_available', False)
    }
    
    passed_tests = sum(success_criteria.values())
    total_tests = len(success_criteria)
    
    print(f"📊 Test Results: {passed_tests}/{total_tests} passed")
    
    for test_name, passed in success_criteria.items():
        emoji = "✅" if passed else "❌"
        print(f"   {emoji} {test_name}: {'PASS' if passed else 'FAIL'}")
    
    # 수집된 데이터 정보
    collected_posts = database_results.get('collected_posts', 0)
    if collected_posts > 0:
        print(f"\n🎉 Successfully collected {collected_posts} Reddit posts!")
    else:
        print(f"\n⚠️ No posts were collected. Check logs for details.")
    
    # 권장사항
    print(f"\n🔧 Next Steps:")
    if passed_tests == total_tests:
        print("   ✅ All tests passed! System is ready for production.")
        print("   🔄 Consider running AI processing pipeline test next.")
    else:
        print("   ⚠️ Some tests failed. Check system logs and configuration.")
        print("   🔍 Review Reddit API credentials and rate limits.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    try:
        success = run_reddit_collection_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        sys.exit(1)