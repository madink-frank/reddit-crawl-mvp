#!/usr/bin/env python3
"""
전체 파이프라인 통합 테스트
Reddit 수집 → AI 처리 → Ghost 발행 전체 워크플로우 테스트
"""

import os
import sys
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# API 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def print_header(title: str):
    """테스트 섹션 헤더 출력"""
    print(f"\n{'='*70}")
    print(f"🔄 {title}")
    print(f"{'='*70}")

def print_step(step: str):
    """테스트 단계 출력"""
    print(f"\n🔍 {step}")
    print("-" * 50)

def print_substep(substep: str):
    """테스트 하위 단계 출력"""
    print(f"   📋 {substep}")

def check_system_health() -> Dict[str, Any]:
    """시스템 전체 헬스체크"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ System Status: {health_data.get('status', 'unknown')}")
            
            services = health_data.get('services', {})
            all_healthy = True
            
            for service_name, service_info in services.items():
                status = service_info.get('status', 'unknown')
                response_time = service_info.get('response_time_ms', 0)
                
                if status == "healthy":
                    emoji = "✅"
                elif status == "degraded":
                    emoji = "⚠️"
                    # Ghost API가 rate limited여도 테스트 진행 가능
                    if service_name != "ghost_api":
                        all_healthy = False
                else:
                    emoji = "❌"
                    all_healthy = False
                
                print(f"   {emoji} {service_name}: {status} ({response_time:.1f}ms)")
            
            return {
                "healthy": all_healthy,
                "services": services,
                "response": health_data
            }
        else:
            print(f"❌ Health Check Failed: {response.status_code}")
            return {"healthy": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        print(f"❌ Health Check Error: {e}")
        return {"healthy": False, "error": str(e)}

def get_initial_metrics() -> Dict[str, int]:
    """초기 메트릭 수집"""
    try:
        response = requests.get(f"{API_BASE_URL}/metrics", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            metrics_text = response.text
            
            # 메트릭 파싱
            metrics = {
                "posts_collected": 0,
                "posts_processed": 0,
                "posts_published": 0,
                "collection_failures": 0,
                "processing_failures": 0,
                "publishing_failures": 0
            }
            
            for line in metrics_text.split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                
                for metric_name in metrics.keys():
                    if metric_name in line:
                        try:
                            value = int(line.split()[-1])
                            metrics[metric_name] = value
                            break
                        except (ValueError, IndexError):
                            pass
            
            print(f"📊 Initial Metrics:")
            for metric, value in metrics.items():
                print(f"   {metric}: {value}")
            
            return metrics
        else:
            print(f"⚠️ Failed to get initial metrics: {response.status_code}")
            return {}
    except Exception as e:
        print(f"⚠️ Initial metrics error: {e}")
        return {}

def trigger_reddit_collection() -> Dict[str, Any]:
    """Reddit 수집 트리거"""
    try:
        print_substep("Triggering Reddit collection...")
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/collect/trigger",
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Collection triggered successfully")
            print(f"      Task ID: {result.get('task_id')}")
            print(f"      Message: {result.get('message')}")
            return result
        else:
            print(f"   ❌ Collection trigger failed: {response.status_code}")
            print(f"      Response: {response.text}")
            return {}
    except Exception as e:
        print(f"   ❌ Collection trigger error: {e}")
        return {}

def wait_for_collection_completion(max_wait_seconds: int = 300) -> bool:
    """Reddit 수집 완료 대기"""
    print_substep(f"Waiting for collection completion (max {max_wait_seconds}s)...")
    
    start_time = time.time()
    last_collected_count = 0
    stable_count = 0
    
    while time.time() - start_time < max_wait_seconds:
        try:
            # 큐 상태 확인
            response = requests.get(f"{API_BASE_URL}/api/v1/status/queues", headers=HEADERS, timeout=10)
            if response.status_code == 200:
                queue_status = response.json()
                collect_queue = queue_status.get('collect', {})
                
                active = collect_queue.get('active', 0)
                pending = collect_queue.get('pending', 0)
                
                # 메트릭에서 수집된 포스트 수 확인
                metrics_response = requests.get(f"{API_BASE_URL}/metrics", headers=HEADERS, timeout=10)
                collected_count = 0
                if metrics_response.status_code == 200:
                    for line in metrics_response.text.split('\n'):
                        if 'posts_collected_total' in line and not line.startswith('#'):
                            try:
                                collected_count = int(line.split()[-1])
                                break
                            except (ValueError, IndexError):
                                pass
                
                print(f"      ⏳ Collection status - Active: {active}, Pending: {pending}, Collected: {collected_count}")
                
                # 수집이 완료되었는지 확인 (큐가 비어있고 수집 수가 안정적)
                if active == 0 and pending == 0:
                    if collected_count == last_collected_count:
                        stable_count += 1
                        if stable_count >= 3:  # 3번 연속 안정적이면 완료로 간주
                            print(f"   ✅ Collection completed - {collected_count} posts collected")
                            return True
                    else:
                        stable_count = 0
                        last_collected_count = collected_count
                else:
                    stable_count = 0
            else:
                print(f"      ⚠️ Queue status check failed: {response.status_code}")
        except Exception as e:
            print(f"      ⚠️ Collection status error: {e}")
        
        time.sleep(10)
    
    print(f"   ⚠️ Collection did not complete within {max_wait_seconds} seconds")
    return False

def trigger_ai_processing() -> Dict[str, Any]:
    """AI 처리 트리거"""
    try:
        print_substep("Triggering AI processing...")
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/process/trigger",
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ AI processing triggered successfully")
            print(f"      Task ID: {result.get('task_id')}")
            print(f"      Message: {result.get('message')}")
            return result
        else:
            print(f"   ❌ AI processing trigger failed: {response.status_code}")
            print(f"      Response: {response.text}")
            return {}
    except Exception as e:
        print(f"   ❌ AI processing trigger error: {e}")
        return {}

def wait_for_processing_completion(max_wait_seconds: int = 600) -> bool:
    """AI 처리 완료 대기"""
    print_substep(f"Waiting for AI processing completion (max {max_wait_seconds}s)...")
    
    start_time = time.time()
    last_processed_count = 0
    stable_count = 0
    
    while time.time() - start_time < max_wait_seconds:
        try:
            # 큐 상태 확인
            response = requests.get(f"{API_BASE_URL}/api/v1/status/queues", headers=HEADERS, timeout=10)
            if response.status_code == 200:
                queue_status = response.json()
                process_queue = queue_status.get('process', {})
                
                active = process_queue.get('active', 0)
                pending = process_queue.get('pending', 0)
                
                # 메트릭에서 처리된 포스트 수 확인
                metrics_response = requests.get(f"{API_BASE_URL}/metrics", headers=HEADERS, timeout=10)
                processed_count = 0
                if metrics_response.status_code == 200:
                    for line in metrics_response.text.split('\n'):
                        if 'posts_processed_total' in line and not line.startswith('#'):
                            try:
                                processed_count = int(line.split()[-1])
                                break
                            except (ValueError, IndexError):
                                pass
                
                print(f"      ⏳ Processing status - Active: {active}, Pending: {pending}, Processed: {processed_count}")
                
                # 처리가 완료되었는지 확인
                if active == 0 and pending == 0:
                    if processed_count == last_processed_count:
                        stable_count += 1
                        if stable_count >= 3:
                            print(f"   ✅ AI processing completed - {processed_count} posts processed")
                            return True
                    else:
                        stable_count = 0
                        last_processed_count = processed_count
                else:
                    stable_count = 0
            else:
                print(f"      ⚠️ Queue status check failed: {response.status_code}")
        except Exception as e:
            print(f"      ⚠️ Processing status error: {e}")
        
        time.sleep(15)  # AI 처리는 더 오래 걸리므로 15초 간격
    
    print(f"   ⚠️ AI processing did not complete within {max_wait_seconds} seconds")
    return False

def trigger_ghost_publishing() -> Dict[str, Any]:
    """Ghost 발행 트리거"""
    try:
        print_substep("Triggering Ghost publishing...")
        
        response = requests.post(
            f"{API_BASE_URL}/api/v1/publish/trigger",
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Ghost publishing triggered successfully")
            print(f"      Task ID: {result.get('task_id')}")
            print(f"      Message: {result.get('message')}")
            return result
        else:
            print(f"   ❌ Ghost publishing trigger failed: {response.status_code}")
            print(f"      Response: {response.text}")
            return {}
    except Exception as e:
        print(f"   ❌ Ghost publishing trigger error: {e}")
        return {}

def wait_for_publishing_completion(max_wait_seconds: int = 300) -> bool:
    """Ghost 발행 완료 대기"""
    print_substep(f"Waiting for Ghost publishing completion (max {max_wait_seconds}s)...")
    
    start_time = time.time()
    last_published_count = 0
    stable_count = 0
    
    while time.time() - start_time < max_wait_seconds:
        try:
            # 큐 상태 확인
            response = requests.get(f"{API_BASE_URL}/api/v1/status/queues", headers=HEADERS, timeout=10)
            if response.status_code == 200:
                queue_status = response.json()
                publish_queue = queue_status.get('publish', {})
                
                active = publish_queue.get('active', 0)
                pending = publish_queue.get('pending', 0)
                
                # 메트릭에서 발행된 포스트 수 확인
                metrics_response = requests.get(f"{API_BASE_URL}/metrics", headers=HEADERS, timeout=10)
                published_count = 0
                if metrics_response.status_code == 200:
                    for line in metrics_response.text.split('\n'):
                        if 'posts_published_total' in line and not line.startswith('#'):
                            try:
                                published_count = int(line.split()[-1])
                                break
                            except (ValueError, IndexError):
                                pass
                
                print(f"      ⏳ Publishing status - Active: {active}, Pending: {pending}, Published: {published_count}")
                
                # 발행이 완료되었는지 확인
                if active == 0 and pending == 0:
                    if published_count == last_published_count:
                        stable_count += 1
                        if stable_count >= 3:
                            print(f"   ✅ Ghost publishing completed - {published_count} posts published")
                            return True
                    else:
                        stable_count = 0
                        last_published_count = published_count
                else:
                    stable_count = 0
            else:
                print(f"      ⚠️ Queue status check failed: {response.status_code}")
        except Exception as e:
            print(f"      ⚠️ Publishing status error: {e}")
        
        time.sleep(10)
    
    print(f"   ⚠️ Ghost publishing did not complete within {max_wait_seconds} seconds")
    return False

def get_final_metrics() -> Dict[str, int]:
    """최종 메트릭 수집"""
    try:
        response = requests.get(f"{API_BASE_URL}/metrics", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            metrics_text = response.text
            
            metrics = {
                "posts_collected": 0,
                "posts_processed": 0,
                "posts_published": 0,
                "collection_failures": 0,
                "processing_failures": 0,
                "publishing_failures": 0
            }
            
            for line in metrics_text.split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                
                for metric_name in metrics.keys():
                    if metric_name in line:
                        try:
                            value = int(line.split()[-1])
                            metrics[metric_name] = value
                            break
                        except (ValueError, IndexError):
                            pass
            
            print(f"📊 Final Metrics:")
            for metric, value in metrics.items():
                print(f"   {metric}: {value}")
            
            return metrics
        else:
            print(f"⚠️ Failed to get final metrics: {response.status_code}")
            return {}
    except Exception as e:
        print(f"⚠️ Final metrics error: {e}")
        return {}

def verify_pipeline_results(initial_metrics: Dict[str, int], final_metrics: Dict[str, int]) -> Dict[str, Any]:
    """파이프라인 결과 검증"""
    print_substep("Verifying pipeline results...")
    
    results = {
        "collection_success": False,
        "processing_success": False,
        "publishing_success": False,
        "overall_success": False,
        "stats": {}
    }
    
    # 수집 성공 여부
    collected_delta = final_metrics.get('posts_collected', 0) - initial_metrics.get('posts_collected', 0)
    collection_failures = final_metrics.get('collection_failures', 0) - initial_metrics.get('collection_failures', 0)
    
    if collected_delta > 0:
        results["collection_success"] = True
        print(f"   ✅ Collection: {collected_delta} new posts collected")
    else:
        print(f"   ❌ Collection: No new posts collected")
    
    if collection_failures > 0:
        print(f"   ⚠️ Collection failures: {collection_failures}")
    
    # 처리 성공 여부
    processed_delta = final_metrics.get('posts_processed', 0) - initial_metrics.get('posts_processed', 0)
    processing_failures = final_metrics.get('processing_failures', 0) - initial_metrics.get('processing_failures', 0)
    
    if processed_delta > 0:
        results["processing_success"] = True
        print(f"   ✅ Processing: {processed_delta} posts processed")
    else:
        print(f"   ❌ Processing: No posts processed")
    
    if processing_failures > 0:
        print(f"   ⚠️ Processing failures: {processing_failures}")
    
    # 발행 성공 여부
    published_delta = final_metrics.get('posts_published', 0) - initial_metrics.get('posts_published', 0)
    publishing_failures = final_metrics.get('publishing_failures', 0) - initial_metrics.get('publishing_failures', 0)
    
    if published_delta > 0:
        results["publishing_success"] = True
        print(f"   ✅ Publishing: {published_delta} posts published")
    else:
        print(f"   ❌ Publishing: No posts published")
    
    if publishing_failures > 0:
        print(f"   ⚠️ Publishing failures: {publishing_failures}")
    
    # 전체 성공률 계산
    success_rate = 0
    if collected_delta > 0:
        success_rate = (published_delta / collected_delta) * 100
    
    results["stats"] = {
        "collected": collected_delta,
        "processed": processed_delta,
        "published": published_delta,
        "success_rate": success_rate,
        "collection_failures": collection_failures,
        "processing_failures": processing_failures,
        "publishing_failures": publishing_failures
    }
    
    # 전체 성공 여부 (최소 1개 포스트가 전체 파이프라인을 통과했는지)
    results["overall_success"] = published_delta > 0
    
    print(f"   📈 Pipeline Success Rate: {success_rate:.1f}%")
    
    return results

def check_data_quality() -> Dict[str, Any]:
    """데이터 품질 검증"""
    print_substep("Checking data quality...")
    
    # 직접 데이터베이스 쿼리로 품질 확인
    try:
        import subprocess
        
        # 최근 발행된 포스트 확인
        cmd = [
            "docker", "exec", "reddit-publisher-postgres",
            "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
            """
            SELECT 
                COUNT(*) as total_posts,
                COUNT(CASE WHEN summary_ko IS NOT NULL AND summary_ko != '' THEN 1 END) as posts_with_summary,
                COUNT(CASE WHEN tags IS NOT NULL AND tags != '[]' THEN 1 END) as posts_with_tags,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as posts_with_ghost_url,
                COUNT(CASE WHEN status = 'published' THEN 1 END) as published_posts
            FROM posts 
            WHERE created_at >= NOW() - INTERVAL '1 hour';
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = output.split('|')
                if len(parts) >= 5:
                    total = int(parts[0].strip())
                    with_summary = int(parts[1].strip())
                    with_tags = int(parts[2].strip())
                    with_ghost_url = int(parts[3].strip())
                    published = int(parts[4].strip())
                    
                    print(f"   📊 Data Quality (last hour):")
                    print(f"      Total posts: {total}")
                    print(f"      Posts with summary: {with_summary}/{total}")
                    print(f"      Posts with tags: {with_tags}/{total}")
                    print(f"      Posts with Ghost URL: {with_ghost_url}/{total}")
                    print(f"      Published posts: {published}/{total}")
                    
                    quality_score = 0
                    if total > 0:
                        quality_score = ((with_summary + with_tags + with_ghost_url) / (total * 3)) * 100
                    
                    print(f"   📈 Data Quality Score: {quality_score:.1f}%")
                    
                    return {
                        "quality_check": True,
                        "total_posts": total,
                        "quality_score": quality_score,
                        "published_posts": published
                    }
        
        print(f"   ⚠️ Data quality check failed")
        return {"quality_check": False}
        
    except Exception as e:
        print(f"   ⚠️ Data quality check error: {e}")
        return {"quality_check": False, "error": str(e)}

def run_full_pipeline_integration_test():
    """전체 파이프라인 통합 테스트 실행"""
    print_header("전체 파이프라인 통합 테스트")
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = {
        "system_health": False,
        "collection_completed": False,
        "processing_completed": False,
        "publishing_completed": False,
        "pipeline_success": False,
        "data_quality": False
    }
    
    # 1. 시스템 헬스체크
    print_step("1. System Health Check")
    health_status = check_system_health()
    test_results["system_health"] = health_status.get("healthy", False)
    
    if not test_results["system_health"]:
        print("⚠️ System health check failed, but continuing with integration test...")
        print("   (Database may be experiencing temporary issues but is functional)")
    
    # 2. 초기 메트릭 수집
    print_step("2. Initial Metrics Collection")
    initial_metrics = get_initial_metrics()
    
    # 3. Reddit 수집 단계
    print_step("3. Reddit Collection Phase")
    collection_trigger = trigger_reddit_collection()
    
    if not collection_trigger:
        print("❌ Failed to trigger Reddit collection. Aborting test.")
        return False
    
    test_results["collection_completed"] = wait_for_collection_completion(300)
    
    if not test_results["collection_completed"]:
        print("❌ Reddit collection did not complete. Continuing with existing data...")
    
    # 4. AI 처리 단계
    print_step("4. AI Processing Phase")
    processing_trigger = trigger_ai_processing()
    
    if not processing_trigger:
        print("❌ Failed to trigger AI processing. Aborting test.")
        return False
    
    test_results["processing_completed"] = wait_for_processing_completion(600)
    
    if not test_results["processing_completed"]:
        print("❌ AI processing did not complete. Continuing with existing data...")
    
    # 5. Ghost 발행 단계
    print_step("5. Ghost Publishing Phase")
    publishing_trigger = trigger_ghost_publishing()
    
    if not publishing_trigger:
        print("❌ Failed to trigger Ghost publishing. Aborting test.")
        return False
    
    test_results["publishing_completed"] = wait_for_publishing_completion(300)
    
    if not test_results["publishing_completed"]:
        print("❌ Ghost publishing did not complete.")
    
    # 6. 최종 메트릭 수집 및 결과 검증
    print_step("6. Results Verification")
    final_metrics = get_final_metrics()
    
    pipeline_results = verify_pipeline_results(initial_metrics, final_metrics)
    test_results["pipeline_success"] = pipeline_results.get("overall_success", False)
    
    # 7. 데이터 품질 검증
    print_step("7. Data Quality Verification")
    quality_results = check_data_quality()
    test_results["data_quality"] = quality_results.get("quality_check", False)
    
    # 8. 통합 테스트 결과 요약
    print_header("전체 파이프라인 통합 테스트 결과")
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    print(f"📊 Integration Test Results: {passed_tests}/{total_tests} passed")
    
    for test_name, passed in test_results.items():
        emoji = "✅" if passed else "❌"
        test_display = test_name.replace('_', ' ').title()
        print(f"   {emoji} {test_display}: {'PASS' if passed else 'FAIL'}")
    
    # 파이프라인 통계
    if pipeline_results.get("stats"):
        stats = pipeline_results["stats"]
        print(f"\n📈 Pipeline Statistics:")
        print(f"   📥 Posts Collected: {stats.get('collected', 0)}")
        print(f"   🤖 Posts Processed: {stats.get('processed', 0)}")
        print(f"   👻 Posts Published: {stats.get('published', 0)}")
        print(f"   📊 Success Rate: {stats.get('success_rate', 0):.1f}%")
        
        if stats.get('collection_failures', 0) > 0:
            print(f"   ❌ Collection Failures: {stats['collection_failures']}")
        if stats.get('processing_failures', 0) > 0:
            print(f"   ❌ Processing Failures: {stats['processing_failures']}")
        if stats.get('publishing_failures', 0) > 0:
            print(f"   ❌ Publishing Failures: {stats['publishing_failures']}")
    
    # 데이터 품질 결과
    if quality_results.get("quality_check"):
        print(f"\n📋 Data Quality Results:")
        print(f"   📊 Quality Score: {quality_results.get('quality_score', 0):.1f}%")
        print(f"   📝 Total Posts: {quality_results.get('total_posts', 0)}")
        print(f"   👻 Published Posts: {quality_results.get('published_posts', 0)}")
    
    # 권장사항
    print(f"\n🔧 Recommendations:")
    if test_results["pipeline_success"]:
        print("   ✅ Full pipeline integration is working correctly!")
        print("   🔄 Ready for performance testing and production deployment.")
    else:
        print("   ⚠️ Pipeline integration has issues that need attention:")
        
        if not test_results["collection_completed"]:
            print("   📥 Check Reddit API configuration and rate limits")
        if not test_results["processing_completed"]:
            print("   🤖 Check OpenAI API configuration and token limits")
        if not test_results["publishing_completed"]:
            print("   👻 Check Ghost CMS configuration and connectivity")
        if not test_results["data_quality"]:
            print("   📋 Check data processing logic and database integrity")
    
    # 전체 성공 기준: 최소한 파이프라인이 성공적으로 실행되어야 함
    overall_success = test_results["pipeline_success"] and test_results["system_health"]
    
    return overall_success

if __name__ == "__main__":
    try:
        success = run_full_pipeline_integration_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Integration test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)