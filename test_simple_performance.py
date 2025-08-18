#!/usr/bin/env python3
"""
간단한 성능 테스트 - 시스템 리소스 및 데이터베이스 성능 분석
"""

import sys
import subprocess
import time
from datetime import datetime

def print_header(title: str):
    """테스트 섹션 헤더 출력"""
    print(f"\n{'='*60}")
    print(f"⚡ {title}")
    print(f"{'='*60}")

def print_step(step: str):
    """테스트 단계 출력"""
    print(f"\n🔍 {step}")
    print("-" * 40)

def check_container_resources():
    """컨테이너 리소스 사용량 확인"""
    try:
        print(f"📊 Container Resource Usage:")
        
        # Docker 컨테이너 상태 확인
        cmd = ["docker", "ps", "--format", "table {{.Names}}\\t{{.Status}}\\t{{.Size}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # 헤더 제외
                for line in lines[1:]:
                    if line.strip() and 'reddit-publisher' in line:
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            name = parts[0].strip()
                            status = parts[1].strip()
                            size = parts[2].strip()
                            
                            emoji = "✅" if "Up" in status else "❌" if "Exited" in status else "⚠️"
                            print(f"   {emoji} {name}")
                            print(f"      Status: {status}")
                            print(f"      Size: {size}")
        
        # 리소스 사용량 스냅샷
        print(f"\n💻 System Resource Snapshot:")
        stats_cmd = ["docker", "stats", "--no-stream", "--format", "table {{.Container}}\\t{{.CPUPerc}}\\t{{.MemUsage}}"]
        stats_result = subprocess.run(stats_cmd, capture_output=True, text=True, timeout=15)
        
        if stats_result.returncode == 0:
            lines = stats_result.stdout.strip().split('\n')
            if len(lines) > 1:  # 헤더 제외
                total_cpu = 0.0
                total_memory_mb = 0.0
                
                for line in lines[1:]:
                    if line.strip() and 'reddit-publisher' in line:
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            container = parts[0].strip()
                            cpu_perc = parts[1].strip().replace('%', '')
                            mem_usage = parts[2].strip()
                            
                            try:
                                cpu_val = float(cpu_perc)
                                total_cpu += cpu_val
                                
                                # 메모리 파싱
                                if '/' in mem_usage:
                                    used_mem = mem_usage.split('/')[0].strip()
                                    if 'MiB' in used_mem:
                                        mem_mb = float(used_mem.replace('MiB', ''))
                                    elif 'GiB' in used_mem:
                                        mem_mb = float(used_mem.replace('GiB', '')) * 1024
                                    else:
                                        mem_mb = 0.0
                                    
                                    total_memory_mb += mem_mb
                                
                                print(f"   📈 {container}: CPU {cpu_perc}%, Memory {mem_usage}")
                            except (ValueError, IndexError):
                                print(f"   ⚠️ {container}: Unable to parse resource data")
                
                print(f"\n   📊 Total System Usage:")
                print(f"      CPU: {total_cpu:.1f}%")
                print(f"      Memory: {total_memory_mb:.1f} MB")
                
                return {
                    "total_cpu": total_cpu,
                    "total_memory_mb": total_memory_mb,
                    "resource_check": True
                }
        
        return {"resource_check": False}
        
    except Exception as e:
        print(f"❌ Resource check error: {e}")
        return {"resource_check": False, "error": str(e)}

def check_database_performance():
    """데이터베이스 성능 분석"""
    try:
        print(f"📊 Database Performance Analysis:")
        
        # 기본 데이터베이스 통계
        cmd = [
            "docker", "exec", "reddit-publisher-postgres",
            "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
            """
            SELECT 
                (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                (SELECT count(*) FROM pg_stat_activity) as total_connections,
                (SELECT count(*) FROM posts) as total_posts,
                (SELECT count(*) FROM posts WHERE status = 'collected') as collected_posts,
                (SELECT count(*) FROM posts WHERE status = 'processed') as processed_posts,
                (SELECT count(*) FROM posts WHERE status = 'published') as published_posts,
                (SELECT pg_size_pretty(pg_database_size('reddit_publisher'))) as db_size;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = [p.strip() for p in output.split('|')]
                if len(parts) >= 7:
                    active_conn = int(parts[0])
                    total_conn = int(parts[1])
                    total_posts = int(parts[2])
                    collected_posts = int(parts[3])
                    processed_posts = int(parts[4])
                    published_posts = int(parts[5])
                    db_size = parts[6]
                    
                    print(f"   📊 Database Statistics:")
                    print(f"      Active Connections: {active_conn}")
                    print(f"      Total Connections: {total_conn}")
                    print(f"      Database Size: {db_size}")
                    
                    print(f"\n   📝 Post Processing Statistics:")
                    print(f"      Total Posts: {total_posts}")
                    print(f"      Collected: {collected_posts}")
                    print(f"      Processed: {processed_posts}")
                    print(f"      Published: {published_posts}")
                    
                    if total_posts > 0:
                        processing_rate = (processed_posts / total_posts) * 100
                        publishing_rate = (published_posts / total_posts) * 100
                        print(f"      Processing Rate: {processing_rate:.1f}%")
                        print(f"      Publishing Rate: {publishing_rate:.1f}%")
                    
                    # 성능 평가
                    performance_score = 0
                    
                    # 연결 수 평가 (30점)
                    if active_conn <= 5:
                        performance_score += 30
                    elif active_conn <= 10:
                        performance_score += 20
                    elif active_conn <= 20:
                        performance_score += 10
                    
                    # 데이터 처리율 평가 (40점)
                    if processing_rate >= 80:
                        performance_score += 40
                    elif processing_rate >= 50:
                        performance_score += 30
                    elif processing_rate >= 20:
                        performance_score += 20
                    elif processing_rate > 0:
                        performance_score += 10
                    
                    # 발행률 평가 (30점)
                    if publishing_rate >= 80:
                        performance_score += 30
                    elif publishing_rate >= 50:
                        performance_score += 20
                    elif publishing_rate >= 20:
                        performance_score += 10
                    elif publishing_rate > 0:
                        performance_score += 5
                    
                    print(f"\n   📈 Database Performance Score: {performance_score}/100")
                    
                    return {
                        "active_connections": active_conn,
                        "total_connections": total_conn,
                        "total_posts": total_posts,
                        "processed_posts": processed_posts,
                        "published_posts": published_posts,
                        "processing_rate": processing_rate if total_posts > 0 else 0,
                        "publishing_rate": publishing_rate if total_posts > 0 else 0,
                        "performance_score": performance_score,
                        "database_size": db_size,
                        "performance_ok": performance_score >= 50
                    }
        
        print(f"❌ Failed to get database performance data")
        return {"performance_ok": False}
        
    except Exception as e:
        print(f"❌ Database performance check error: {e}")
        return {"performance_ok": False, "error": str(e)}

def check_processing_logs():
    """처리 로그 분석"""
    try:
        print(f"📊 Processing Logs Analysis:")
        
        # 최근 처리 로그 확인
        cmd = [
            "docker", "exec", "reddit-publisher-postgres",
            "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
            """
            SELECT 
                service_name,
                status,
                COUNT(*) as count,
                AVG(processing_time_ms) as avg_time_ms,
                MAX(processing_time_ms) as max_time_ms
            FROM processing_logs 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY service_name, status
            ORDER BY service_name, status;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"   📊 Processing Performance (Last 24h):")
            
            total_success = 0
            total_failure = 0
            
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 5:
                        service = parts[0]
                        status = parts[1]
                        count = int(parts[2])
                        avg_time = float(parts[3]) if parts[3] else 0
                        max_time = float(parts[4]) if parts[4] else 0
                        
                        emoji = "✅" if status == "success" else "❌"
                        print(f"      {emoji} {service} ({status}): {count} operations")
                        print(f"         Avg Time: {avg_time:.1f}ms, Max Time: {max_time:.1f}ms")
                        
                        if status == "success":
                            total_success += count
                        else:
                            total_failure += count
            
            if total_success + total_failure > 0:
                success_rate = (total_success / (total_success + total_failure)) * 100
                print(f"\n   📈 Overall Success Rate: {success_rate:.1f}%")
                
                return {
                    "total_operations": total_success + total_failure,
                    "success_rate": success_rate,
                    "logs_available": True
                }
        else:
            print(f"   ⚠️ No processing logs found in the last 24 hours")
            return {"logs_available": False}
        
    except Exception as e:
        print(f"❌ Processing logs check error: {e}")
        return {"logs_available": False, "error": str(e)}

def estimate_processing_capacity(db_performance, logs_analysis):
    """처리 용량 추정"""
    try:
        print(f"📊 Processing Capacity Estimation:")
        
        total_posts = db_performance.get("total_posts", 0)
        processed_posts = db_performance.get("processed_posts", 0)
        published_posts = db_performance.get("published_posts", 0)
        
        # 현재 처리 상태 기반 용량 추정
        if total_posts > 0:
            processing_efficiency = processed_posts / total_posts
            publishing_efficiency = published_posts / total_posts
            
            print(f"   📈 Current Efficiency:")
            print(f"      Processing: {processing_efficiency:.1%}")
            print(f"      Publishing: {publishing_efficiency:.1%}")
            
            # 일일 처리 용량 추정 (가정: 현재 효율성 유지)
            if logs_analysis.get("logs_available") and logs_analysis.get("total_operations", 0) > 0:
                daily_capacity_estimate = logs_analysis["total_operations"] * 24  # 24시간 기준
                print(f"      Estimated Daily Operations: {daily_capacity_estimate}")
                
                # Reddit 포스트 처리 용량 추정
                if processing_efficiency > 0:
                    daily_post_capacity = int(daily_capacity_estimate * processing_efficiency)
                    print(f"      Estimated Daily Post Processing: {daily_post_capacity} posts")
                    
                    return {
                        "daily_operations": daily_capacity_estimate,
                        "daily_posts": daily_post_capacity,
                        "processing_efficiency": processing_efficiency,
                        "publishing_efficiency": publishing_efficiency,
                        "capacity_estimated": True
                    }
            
            # 로그가 없는 경우 기본 추정
            estimated_daily_posts = max(10, int(total_posts * 0.1))  # 보수적 추정
            print(f"      Conservative Daily Estimate: {estimated_daily_posts} posts")
            
            return {
                "daily_posts": estimated_daily_posts,
                "processing_efficiency": processing_efficiency,
                "publishing_efficiency": publishing_efficiency,
                "capacity_estimated": True
            }
        else:
            print(f"   ⚠️ Insufficient data for capacity estimation")
            return {"capacity_estimated": False}
        
    except Exception as e:
        print(f"❌ Capacity estimation error: {e}")
        return {"capacity_estimated": False, "error": str(e)}

def run_simple_performance_test():
    """간단한 성능 테스트 실행"""
    print_header("간단한 성능 테스트")
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = {
        "resource_analysis": {},
        "database_performance": {},
        "processing_logs": {},
        "capacity_estimation": {},
        "overall_score": 0
    }
    
    # 1. 컨테이너 리소스 분석
    print_step("1. Container Resource Analysis")
    test_results["resource_analysis"] = check_container_resources()
    
    # 2. 데이터베이스 성능 분석
    print_step("2. Database Performance Analysis")
    test_results["database_performance"] = check_database_performance()
    
    # 3. 처리 로그 분석
    print_step("3. Processing Logs Analysis")
    test_results["processing_logs"] = check_processing_logs()
    
    # 4. 처리 용량 추정
    print_step("4. Processing Capacity Estimation")
    test_results["capacity_estimation"] = estimate_processing_capacity(
        test_results["database_performance"],
        test_results["processing_logs"]
    )
    
    # 5. 전체 성능 점수 계산
    print_step("5. Overall Performance Assessment")
    
    overall_score = 0
    
    # 리소스 사용률 점수 (25점)
    if test_results["resource_analysis"].get("resource_check"):
        cpu_usage = test_results["resource_analysis"].get("total_cpu", 0)
        if cpu_usage <= 30:
            overall_score += 25
        elif cpu_usage <= 50:
            overall_score += 20
        elif cpu_usage <= 70:
            overall_score += 15
        else:
            overall_score += 10
    
    # 데이터베이스 성능 점수 (40점)
    db_score = test_results["database_performance"].get("performance_score", 0)
    overall_score += int(db_score * 0.4)  # 100점 만점을 40점으로 스케일링
    
    # 처리 로그 점수 (20점)
    if test_results["processing_logs"].get("logs_available"):
        success_rate = test_results["processing_logs"].get("success_rate", 0)
        if success_rate >= 95:
            overall_score += 20
        elif success_rate >= 85:
            overall_score += 15
        elif success_rate >= 70:
            overall_score += 10
        else:
            overall_score += 5
    
    # 용량 추정 점수 (15점)
    if test_results["capacity_estimation"].get("capacity_estimated"):
        processing_eff = test_results["capacity_estimation"].get("processing_efficiency", 0)
        if processing_eff >= 0.8:
            overall_score += 15
        elif processing_eff >= 0.5:
            overall_score += 12
        elif processing_eff >= 0.2:
            overall_score += 8
        elif processing_eff > 0:
            overall_score += 5
    
    test_results["overall_score"] = overall_score
    
    # 성능 등급 결정
    if overall_score >= 85:
        performance_grade = "Excellent"
        grade_emoji = "🚀"
    elif overall_score >= 70:
        performance_grade = "Good"
        grade_emoji = "✅"
    elif overall_score >= 55:
        performance_grade = "Fair"
        grade_emoji = "⚠️"
    else:
        performance_grade = "Poor"
        grade_emoji = "❌"
    
    print(f"   {grade_emoji} Overall Performance: {performance_grade} ({overall_score}/100)")
    
    # 6. 성능 테스트 결과 요약
    print_header("간단한 성능 테스트 결과")
    
    print(f"📊 Performance Test Summary:")
    print(f"   🎯 Overall Score: {overall_score}/100 ({performance_grade})")
    
    # 리소스 사용률
    if test_results["resource_analysis"].get("resource_check"):
        cpu_usage = test_results["resource_analysis"].get("total_cpu", 0)
        memory_usage = test_results["resource_analysis"].get("total_memory_mb", 0)
        print(f"   💻 CPU Usage: {cpu_usage:.1f}%")
        print(f"   💾 Memory Usage: {memory_usage:.1f} MB")
    
    # 데이터베이스 통계
    if test_results["database_performance"].get("performance_ok"):
        db_perf = test_results["database_performance"]
        print(f"   📊 Database Performance:")
        print(f"      Total Posts: {db_perf.get('total_posts', 0)}")
        print(f"      Processing Rate: {db_perf.get('processing_rate', 0):.1f}%")
        print(f"      Publishing Rate: {db_perf.get('publishing_rate', 0):.1f}%")
        print(f"      Active Connections: {db_perf.get('active_connections', 0)}")
    
    # 처리 용량
    if test_results["capacity_estimation"].get("capacity_estimated"):
        capacity = test_results["capacity_estimation"]
        print(f"   📈 Processing Capacity:")
        if capacity.get("daily_posts"):
            print(f"      Estimated Daily Posts: {capacity['daily_posts']}")
        print(f"      Processing Efficiency: {capacity.get('processing_efficiency', 0):.1%}")
        print(f"      Publishing Efficiency: {capacity.get('publishing_efficiency', 0):.1%}")
    
    # 권장사항
    print(f"\n🔧 Performance Recommendations:")
    
    if overall_score >= 85:
        print("   🚀 Excellent performance! System is production-ready.")
        print("   📈 Consider scaling up for higher throughput.")
    elif overall_score >= 70:
        print("   ✅ Good performance with optimization opportunities.")
        if test_results["database_performance"].get("processing_rate", 0) < 50:
            print("   🤖 Improve AI processing pipeline efficiency.")
        if test_results["database_performance"].get("publishing_rate", 0) < 30:
            print("   👻 Optimize Ghost publishing workflow.")
    elif overall_score >= 55:
        print("   ⚠️ Fair performance requiring attention:")
        print("   🔧 Review processing workflows and error handling.")
        print("   📊 Investigate database performance bottlenecks.")
    else:
        print("   ❌ Poor performance needs immediate improvement:")
        print("   🔧 Review system architecture and resource allocation.")
        print("   📊 Fix critical performance and reliability issues.")
    
    # 성공 기준: 성능 점수 55점 이상
    overall_success = overall_score >= 55
    
    return overall_success

if __name__ == "__main__":
    try:
        success = run_simple_performance_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Performance test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Performance test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)