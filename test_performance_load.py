#!/usr/bin/env python3
"""
대량 처리 성능 테스트
시스템 처리 능력, 병목 지점, 리소스 사용량 분석
"""

import os
import sys
import time
import json
import requests
import subprocess
import threading
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# 테스트 설정
API_BASE_URL = "http://localhost:8000"
API_KEY = "reddit-publisher-api-key-2024"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# 성능 테스트 설정
CONCURRENT_REQUESTS = 10  # 동시 요청 수
LOAD_TEST_DURATION = 60   # 부하 테스트 지속 시간 (초)
RESPONSE_TIME_THRESHOLD = 300  # 응답 시간 임계값 (ms)

def print_header(title: str):
    """테스트 섹션 헤더 출력"""
    print(f"\n{'='*70}")
    print(f"⚡ {title}")
    print(f"{'='*70}")

def print_step(step: str):
    """테스트 단계 출력"""
    print(f"\n🔍 {step}")
    print("-" * 50)

def print_substep(substep: str):
    """테스트 하위 단계 출력"""
    print(f"   📋 {substep}")

def get_system_resources() -> Dict[str, Any]:
    """시스템 리소스 사용량 확인"""
    try:
        print_substep("Checking system resources...")
        
        # Docker 컨테이너 리소스 사용량
        cmd = ["docker", "stats", "--no-stream", "--format", "table {{.Container}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.MemPerc}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        resources = {
            "containers": [],
            "total_cpu": 0.0,
            "total_memory_mb": 0.0
        }
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # 헤더 제외
                print(f"   📊 Container Resource Usage:")
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 4:
                            container = parts[0].strip()
                            cpu_perc = parts[1].strip().replace('%', '')
                            mem_usage = parts[2].strip()
                            mem_perc = parts[3].strip().replace('%', '')
                            
                            try:
                                cpu_val = float(cpu_perc)
                                resources["total_cpu"] += cpu_val
                                
                                # 메모리 사용량 파싱 (예: "123.4MiB / 2GiB")
                                if '/' in mem_usage:
                                    used_mem = mem_usage.split('/')[0].strip()
                                    if 'MiB' in used_mem:
                                        mem_mb = float(used_mem.replace('MiB', ''))
                                    elif 'GiB' in used_mem:
                                        mem_mb = float(used_mem.replace('GiB', '')) * 1024
                                    else:
                                        mem_mb = 0.0
                                    
                                    resources["total_memory_mb"] += mem_mb
                                
                                resources["containers"].append({
                                    "name": container,
                                    "cpu_percent": cpu_val,
                                    "memory_usage": mem_usage,
                                    "memory_percent": float(mem_perc) if mem_perc.replace('.', '').isdigit() else 0.0
                                })
                                
                                print(f"      {container}: CPU {cpu_perc}%, Memory {mem_usage}")
                            except (ValueError, IndexError):
                                pass
                
                print(f"   📈 Total System Usage:")
                print(f"      CPU: {resources['total_cpu']:.1f}%")
                print(f"      Memory: {resources['total_memory_mb']:.1f} MB")
        
        return resources
        
    except Exception as e:
        print(f"   ⚠️ Resource check error: {e}")
        return {"containers": [], "total_cpu": 0.0, "total_memory_mb": 0.0}

def check_database_performance() -> Dict[str, Any]:
    """데이터베이스 성능 확인"""
    try:
        print_substep("Checking database performance...")
        
        # 데이터베이스 연결 수 및 활성 쿼리 확인
        cmd = [
            "docker", "exec", "reddit-publisher-postgres",
            "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
            """
            SELECT 
                (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                (SELECT count(*) FROM pg_stat_activity) as total_connections,
                (SELECT count(*) FROM posts) as total_posts,
                (SELECT pg_size_pretty(pg_database_size('reddit_publisher'))) as db_size;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = [p.strip() for p in output.split('|')]
                if len(parts) >= 4:
                    active_conn = int(parts[0])
                    total_conn = int(parts[1])
                    total_posts = int(parts[2])
                    db_size = parts[3]
                    
                    print(f"   📊 Database Performance:")
                    print(f"      Active Connections: {active_conn}")
                    print(f"      Total Connections: {total_conn}")
                    print(f"      Total Posts: {total_posts}")
                    print(f"      Database Size: {db_size}")
                    
                    # 인덱스 사용률 확인
                    index_cmd = [
                        "docker", "exec", "reddit-publisher-postgres",
                        "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
                        """
                        SELECT 
                            schemaname,
                            tablename,
                            indexname,
                            idx_scan,
                            idx_tup_read,
                            idx_tup_fetch
                        FROM pg_stat_user_indexes 
                        WHERE schemaname = 'public' 
                        ORDER BY idx_scan DESC 
                        LIMIT 5;
                        """
                    ]
                    
                    index_result = subprocess.run(index_cmd, capture_output=True, text=True, timeout=10)
                    
                    if index_result.returncode == 0 and index_result.stdout.strip():
                        print(f"   📈 Top Index Usage:")
                        for line in index_result.stdout.strip().split('\n'):
                            if line.strip():
                                parts = [p.strip() for p in line.split('|')]
                                if len(parts) >= 6:
                                    index_name = parts[2]
                                    scans = parts[3]
                                    print(f"      {index_name}: {scans} scans")
                    
                    return {
                        "active_connections": active_conn,
                        "total_connections": total_conn,
                        "total_posts": total_posts,
                        "database_size": db_size,
                        "performance_ok": active_conn < 50 and total_conn < 100
                    }
        
        print(f"   ❌ Failed to get database performance data")
        return {"performance_ok": False}
        
    except Exception as e:
        print(f"   ⚠️ Database performance check error: {e}")
        return {"performance_ok": False, "error": str(e)}

def check_redis_performance() -> Dict[str, Any]:
    """Redis 성능 확인"""
    try:
        print_substep("Checking Redis performance...")
        
        # Redis 정보 확인
        cmd = ["docker", "exec", "reddit-publisher-redis", "redis-cli", "INFO", "memory"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        redis_info = {}
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if ':' in line and not line.startswith('#'):
                    key, value = line.strip().split(':', 1)
                    redis_info[key] = value
            
            used_memory = redis_info.get('used_memory_human', 'Unknown')
            max_memory = redis_info.get('maxmemory_human', 'No limit')
            connected_clients = redis_info.get('connected_clients', 'Unknown')
            
            print(f"   📊 Redis Performance:")
            print(f"      Used Memory: {used_memory}")
            print(f"      Max Memory: {max_memory}")
            
            # 연결된 클라이언트 수 확인
            client_cmd = ["docker", "exec", "reddit-publisher-redis", "redis-cli", "INFO", "clients"]
            client_result = subprocess.run(client_cmd, capture_output=True, text=True, timeout=5)
            
            if client_result.returncode == 0:
                for line in client_result.stdout.split('\n'):
                    if 'connected_clients:' in line:
                        clients = line.split(':')[1].strip()
                        print(f"      Connected Clients: {clients}")
                        break
            
            # 키 개수 확인
            keys_cmd = ["docker", "exec", "reddit-publisher-redis", "redis-cli", "DBSIZE"]
            keys_result = subprocess.run(keys_cmd, capture_output=True, text=True, timeout=5)
            
            if keys_result.returncode == 0:
                key_count = keys_result.stdout.strip()
                print(f"      Total Keys: {key_count}")
            
            return {
                "used_memory": used_memory,
                "max_memory": max_memory,
                "performance_ok": True
            }
        else:
            print(f"   ❌ Failed to get Redis performance data")
            return {"performance_ok": False}
        
    except Exception as e:
        print(f"   ⚠️ Redis performance check error: {e}")
        return {"performance_ok": False, "error": str(e)}

def measure_api_response_time(endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """API 응답 시간 측정"""
    try:
        start_time = time.time()
        
        if method == "GET":
            response = requests.get(f"{API_BASE_URL}{endpoint}", headers=HEADERS, timeout=10)
        elif method == "POST":
            response = requests.post(f"{API_BASE_URL}{endpoint}", headers=HEADERS, json=data, timeout=10)
        else:
            return {"success": False, "error": "Unsupported method"}
        
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        
        return {
            "success": True,
            "status_code": response.status_code,
            "response_time_ms": response_time_ms,
            "response_size": len(response.content) if response.content else 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response_time_ms": 0
        }

def run_concurrent_load_test(endpoint: str, duration_seconds: int = 60, concurrent_requests: int = 10) -> Dict[str, Any]:
    """동시 부하 테스트 실행"""
    print_substep(f"Running concurrent load test on {endpoint}...")
    print(f"      Duration: {duration_seconds}s, Concurrent: {concurrent_requests}")
    
    results = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "response_times": [],
        "status_codes": {},
        "errors": [],
        "start_time": time.time(),
        "end_time": None
    }
    
    def make_request():
        """단일 요청 실행"""
        result = measure_api_response_time(endpoint)
        
        with threading.Lock():
            results["total_requests"] += 1
            
            if result["success"]:
                results["successful_requests"] += 1
                results["response_times"].append(result["response_time_ms"])
                
                status_code = result["status_code"]
                if status_code not in results["status_codes"]:
                    results["status_codes"][status_code] = 0
                results["status_codes"][status_code] += 1
            else:
                results["failed_requests"] += 1
                results["errors"].append(result.get("error", "Unknown error"))
    
    # 부하 테스트 실행
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = []
        
        while time.time() - start_time < duration_seconds:
            # 동시 요청 수만큼 작업 제출
            for _ in range(concurrent_requests):
                if time.time() - start_time >= duration_seconds:
                    break
                future = executor.submit(make_request)
                futures.append(future)
            
            # 잠시 대기
            time.sleep(0.1)
        
        # 모든 작업 완료 대기
        concurrent.futures.wait(futures, timeout=30)
    
    results["end_time"] = time.time()
    
    # 통계 계산
    if results["response_times"]:
        results["avg_response_time"] = sum(results["response_times"]) / len(results["response_times"])
        results["min_response_time"] = min(results["response_times"])
        results["max_response_time"] = max(results["response_times"])
        
        # 백분위수 계산
        sorted_times = sorted(results["response_times"])
        results["p50_response_time"] = sorted_times[int(len(sorted_times) * 0.5)]
        results["p95_response_time"] = sorted_times[int(len(sorted_times) * 0.95)]
        results["p99_response_time"] = sorted_times[int(len(sorted_times) * 0.99)]
    else:
        results["avg_response_time"] = 0
        results["min_response_time"] = 0
        results["max_response_time"] = 0
        results["p50_response_time"] = 0
        results["p95_response_time"] = 0
        results["p99_response_time"] = 0
    
    # 처리량 계산 (RPS)
    duration = results["end_time"] - results["start_time"]
    results["requests_per_second"] = results["total_requests"] / duration if duration > 0 else 0
    
    # 결과 출력
    print(f"   📊 Load Test Results:")
    print(f"      Total Requests: {results['total_requests']}")
    print(f"      Successful: {results['successful_requests']}")
    print(f"      Failed: {results['failed_requests']}")
    print(f"      Success Rate: {(results['successful_requests'] / results['total_requests'] * 100):.1f}%")
    print(f"      Requests/Second: {results['requests_per_second']:.1f}")
    print(f"      Avg Response Time: {results['avg_response_time']:.1f}ms")
    print(f"      P95 Response Time: {results['p95_response_time']:.1f}ms")
    print(f"      P99 Response Time: {results['p99_response_time']:.1f}ms")
    
    if results["status_codes"]:
        print(f"   📈 Status Code Distribution:")
        for code, count in results["status_codes"].items():
            print(f"      {code}: {count} requests")
    
    if results["errors"]:
        print(f"   ❌ Common Errors:")
        error_counts = {}
        for error in results["errors"][:10]:  # 최대 10개만 표시
            if error not in error_counts:
                error_counts[error] = 0
            error_counts[error] += 1
        
        for error, count in error_counts.items():
            print(f"      {error}: {count} times")
    
    return results

def test_queue_processing_capacity() -> Dict[str, Any]:
    """큐 처리 용량 테스트"""
    try:
        print_substep("Testing queue processing capacity...")
        
        # 현재 큐 상태 확인
        queue_response = requests.get(f"{API_BASE_URL}/api/v1/status/queues", headers=HEADERS, timeout=10)
        
        if queue_response.status_code == 200:
            queue_data = queue_response.json()
            print(f"   📊 Current Queue Status:")
            
            total_pending = 0
            for queue_name, queue_info in queue_data.items():
                pending = queue_info.get('pending', 0)
                active = queue_info.get('active', 0)
                total_pending += pending
                
                print(f"      {queue_name}: {active} active, {pending} pending")
            
            # 큐 처리 능력 평가
            capacity_assessment = {
                "total_pending_jobs": total_pending,
                "queue_healthy": total_pending < 100,
                "capacity_utilization": min(total_pending / 500 * 100, 100)  # 500을 최대 용량으로 가정
            }
            
            print(f"   📈 Queue Capacity Assessment:")
            print(f"      Total Pending Jobs: {total_pending}")
            print(f"      Capacity Utilization: {capacity_assessment['capacity_utilization']:.1f}%")
            print(f"      Queue Health: {'Healthy' if capacity_assessment['queue_healthy'] else 'Overloaded'}")
            
            return capacity_assessment
        else:
            print(f"   ❌ Failed to get queue status: {queue_response.status_code}")
            return {"queue_healthy": False, "error": f"HTTP {queue_response.status_code}"}
        
    except Exception as e:
        print(f"   ⚠️ Queue capacity test error: {e}")
        return {"queue_healthy": False, "error": str(e)}

def analyze_bottlenecks(system_resources: Dict, db_performance: Dict, redis_performance: Dict, api_performance: Dict) -> List[str]:
    """병목 지점 분석"""
    bottlenecks = []
    
    # CPU 병목
    if system_resources.get("total_cpu", 0) > 80:
        bottlenecks.append(f"High CPU usage: {system_resources['total_cpu']:.1f}%")
    
    # 메모리 병목
    if system_resources.get("total_memory_mb", 0) > 2048:  # 2GB 이상
        bottlenecks.append(f"High memory usage: {system_resources['total_memory_mb']:.1f} MB")
    
    # 데이터베이스 병목
    if not db_performance.get("performance_ok", True):
        bottlenecks.append("Database performance issues detected")
    
    if db_performance.get("active_connections", 0) > 20:
        bottlenecks.append(f"High database connections: {db_performance['active_connections']}")
    
    # API 응답 시간 병목
    if api_performance.get("p95_response_time", 0) > RESPONSE_TIME_THRESHOLD:
        bottlenecks.append(f"Slow API responses: P95 {api_performance['p95_response_time']:.1f}ms")
    
    # 성공률 병목
    success_rate = (api_performance.get("successful_requests", 0) / max(api_performance.get("total_requests", 1), 1)) * 100
    if success_rate < 95:
        bottlenecks.append(f"Low API success rate: {success_rate:.1f}%")
    
    return bottlenecks

def run_performance_load_test():
    """대량 처리 성능 테스트 실행"""
    print_header("대량 처리 성능 테스트")
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = {
        "system_resources": {},
        "database_performance": {},
        "redis_performance": {},
        "api_load_test": {},
        "queue_capacity": {},
        "bottlenecks": [],
        "overall_performance": "unknown"
    }
    
    # 1. 시스템 리소스 확인
    print_step("1. System Resource Analysis")
    test_results["system_resources"] = get_system_resources()
    
    # 2. 데이터베이스 성능 확인
    print_step("2. Database Performance Analysis")
    test_results["database_performance"] = check_database_performance()
    
    # 3. Redis 성능 확인
    print_step("3. Redis Performance Analysis")
    test_results["redis_performance"] = check_redis_performance()
    
    # 4. API 부하 테스트
    print_step("4. API Load Testing")
    
    # 헬스체크 엔드포인트 부하 테스트
    health_load_test = run_concurrent_load_test("/health", duration_seconds=30, concurrent_requests=5)
    test_results["api_load_test"] = health_load_test
    
    # 5. 큐 처리 용량 테스트
    print_step("5. Queue Processing Capacity Test")
    test_results["queue_capacity"] = test_queue_processing_capacity()
    
    # 6. 병목 지점 분석
    print_step("6. Bottleneck Analysis")
    test_results["bottlenecks"] = analyze_bottlenecks(
        test_results["system_resources"],
        test_results["database_performance"],
        test_results["redis_performance"],
        test_results["api_load_test"]
    )
    
    if test_results["bottlenecks"]:
        print(f"   ⚠️ Identified Bottlenecks:")
        for bottleneck in test_results["bottlenecks"]:
            print(f"      • {bottleneck}")
    else:
        print(f"   ✅ No significant bottlenecks detected")
    
    # 7. 전체 성능 평가
    print_step("7. Overall Performance Assessment")
    
    # 성능 점수 계산
    performance_score = 0
    max_score = 100
    
    # API 응답 시간 점수 (40점)
    p95_time = test_results["api_load_test"].get("p95_response_time", 1000)
    if p95_time <= 100:
        performance_score += 40
    elif p95_time <= 300:
        performance_score += 30
    elif p95_time <= 500:
        performance_score += 20
    else:
        performance_score += 10
    
    # 성공률 점수 (30점)
    success_rate = (test_results["api_load_test"].get("successful_requests", 0) / 
                   max(test_results["api_load_test"].get("total_requests", 1), 1)) * 100
    if success_rate >= 99:
        performance_score += 30
    elif success_rate >= 95:
        performance_score += 25
    elif success_rate >= 90:
        performance_score += 20
    else:
        performance_score += 10
    
    # 리소스 사용률 점수 (20점)
    cpu_usage = test_results["system_resources"].get("total_cpu", 0)
    if cpu_usage <= 50:
        performance_score += 20
    elif cpu_usage <= 70:
        performance_score += 15
    elif cpu_usage <= 85:
        performance_score += 10
    else:
        performance_score += 5
    
    # 큐 건강성 점수 (10점)
    if test_results["queue_capacity"].get("queue_healthy", False):
        performance_score += 10
    else:
        performance_score += 5
    
    # 성능 등급 결정
    if performance_score >= 90:
        test_results["overall_performance"] = "Excellent"
        performance_emoji = "🚀"
    elif performance_score >= 75:
        test_results["overall_performance"] = "Good"
        performance_emoji = "✅"
    elif performance_score >= 60:
        test_results["overall_performance"] = "Fair"
        performance_emoji = "⚠️"
    else:
        test_results["overall_performance"] = "Poor"
        performance_emoji = "❌"
    
    print(f"   {performance_emoji} Overall Performance: {test_results['overall_performance']} ({performance_score}/100)")
    
    # 8. 성능 테스트 결과 요약
    print_header("대량 처리 성능 테스트 결과")
    
    print(f"📊 Performance Test Summary:")
    print(f"   🎯 Overall Score: {performance_score}/100 ({test_results['overall_performance']})")
    print(f"   ⚡ API Response Time (P95): {test_results['api_load_test'].get('p95_response_time', 0):.1f}ms")
    print(f"   📈 API Success Rate: {success_rate:.1f}%")
    print(f"   🔄 Requests per Second: {test_results['api_load_test'].get('requests_per_second', 0):.1f}")
    print(f"   💻 CPU Usage: {test_results['system_resources'].get('total_cpu', 0):.1f}%")
    print(f"   💾 Memory Usage: {test_results['system_resources'].get('total_memory_mb', 0):.1f} MB")
    
    # 데이터베이스 성능
    if test_results["database_performance"].get("total_posts"):
        print(f"\n📊 Database Performance:")
        print(f"   📝 Total Posts: {test_results['database_performance']['total_posts']}")
        print(f"   🔗 Active Connections: {test_results['database_performance'].get('active_connections', 0)}")
        print(f"   💾 Database Size: {test_results['database_performance'].get('database_size', 'Unknown')}")
    
    # 큐 상태
    if test_results["queue_capacity"]:
        print(f"\n🔄 Queue Performance:")
        print(f"   📋 Total Pending Jobs: {test_results['queue_capacity'].get('total_pending_jobs', 0)}")
        print(f"   📈 Capacity Utilization: {test_results['queue_capacity'].get('capacity_utilization', 0):.1f}%")
    
    # 병목 지점
    if test_results["bottlenecks"]:
        print(f"\n⚠️ Performance Bottlenecks:")
        for bottleneck in test_results["bottlenecks"]:
            print(f"   • {bottleneck}")
    
    # 권장사항
    print(f"\n🔧 Performance Recommendations:")
    
    if performance_score >= 90:
        print("   🚀 Excellent performance! System is ready for production scale.")
        print("   📈 Consider implementing auto-scaling for peak loads.")
    elif performance_score >= 75:
        print("   ✅ Good performance with minor optimization opportunities.")
        if p95_time > 200:
            print("   ⚡ Consider optimizing API response times.")
        if cpu_usage > 60:
            print("   💻 Monitor CPU usage during peak loads.")
    elif performance_score >= 60:
        print("   ⚠️ Fair performance with several areas for improvement:")
        if p95_time > 300:
            print("   ⚡ API response times need optimization.")
        if success_rate < 95:
            print("   🔧 Improve API reliability and error handling.")
        if cpu_usage > 70:
            print("   💻 Consider CPU optimization or scaling.")
    else:
        print("   ❌ Poor performance requires immediate attention:")
        print("   🔧 Review system architecture and resource allocation.")
        print("   📊 Investigate database and API performance issues.")
        print("   ⚡ Optimize critical performance bottlenecks.")
    
    # 처리량 예측
    rps = test_results["api_load_test"].get("requests_per_second", 0)
    if rps > 0:
        daily_capacity = rps * 86400  # 24시간
        print(f"\n📈 Estimated Daily Processing Capacity:")
        print(f"   🔄 {daily_capacity:.0f} requests per day at current performance")
        
        # Reddit 포스트 처리 예상
        if daily_capacity > 1000:
            estimated_posts = min(daily_capacity // 10, 1000)  # API 호출 대비 포스트 수 추정
            print(f"   📝 Estimated {estimated_posts:.0f} Reddit posts processable per day")
    
    # 성공 기준: 성능 점수 60점 이상
    overall_success = performance_score >= 60
    
    return overall_success

if __name__ == "__main__":
    try:
        success = run_performance_load_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Performance test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Performance test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)