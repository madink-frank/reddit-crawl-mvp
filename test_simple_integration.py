#!/usr/bin/env python3
"""
간단한 통합 테스트 - 기존 데이터 기반
"""

import sys
import subprocess
import json
from datetime import datetime

def print_header(title: str):
    """테스트 섹션 헤더 출력"""
    print(f"\n{'='*60}")
    print(f"🔄 {title}")
    print(f"{'='*60}")

def print_step(step: str):
    """테스트 단계 출력"""
    print(f"\n🔍 {step}")
    print("-" * 40)

def check_database_data():
    """데이터베이스 데이터 확인"""
    try:
        cmd = [
            "docker", "exec", "reddit-publisher-postgres",
            "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
            """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'collected' THEN 1 END) as collected,
                COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed,
                COUNT(CASE WHEN status = 'published' THEN 1 END) as published,
                COUNT(CASE WHEN summary_ko IS NOT NULL AND summary_ko != '' THEN 1 END) as with_summary,
                COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as with_ghost_url
            FROM posts;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = [p.strip() for p in output.split('|')]
                if len(parts) >= 6:
                    total = int(parts[0])
                    collected = int(parts[1])
                    processed = int(parts[2])
                    published = int(parts[3])
                    with_summary = int(parts[4])
                    with_ghost_url = int(parts[5])
                    
                    print(f"✅ Database Data Summary:")
                    print(f"   📊 Total Posts: {total}")
                    print(f"   📥 Collected: {collected}")
                    print(f"   🤖 Processed: {processed}")
                    print(f"   👻 Published: {published}")
                    print(f"   📝 With Summary: {with_summary}")
                    print(f"   🔗 With Ghost URL: {with_ghost_url}")
                    
                    return {
                        "total": total,
                        "collected": collected,
                        "processed": processed,
                        "published": published,
                        "with_summary": with_summary,
                        "with_ghost_url": with_ghost_url
                    }
        
        print(f"❌ Failed to get database data")
        return None
        
    except Exception as e:
        print(f"❌ Database check error: {e}")
        return None

def check_worker_status():
    """워커 상태 확인"""
    try:
        print(f"🔍 Checking worker containers...")
        
        # 컨테이너 상태 확인
        cmd = ["docker", "ps", "--filter", "name=reddit-publisher-worker", "--format", "table {{.Names}}\\t{{.Status}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # 헤더 제외
                print(f"✅ Worker Containers:")
                for line in lines[1:]:
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            name = parts[0].strip()
                            status = parts[1].strip()
                            emoji = "✅" if "Up" in status else "❌"
                            print(f"   {emoji} {name}: {status}")
                return True
            else:
                print(f"❌ No worker containers found")
                return False
        else:
            print(f"❌ Failed to check worker status")
            return False
            
    except Exception as e:
        print(f"❌ Worker status check error: {e}")
        return False

def test_direct_processing():
    """직접 처리 테스트"""
    try:
        print(f"🔍 Testing direct processing...")
        
        # 처리되지 않은 포스트가 있는지 확인
        cmd = [
            "docker", "exec", "reddit-publisher-postgres",
            "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
            "SELECT id FROM posts WHERE status = 'collected' LIMIT 1;"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            post_id = result.stdout.strip()
            if post_id:
                print(f"   📋 Found unprocessed post: {post_id}")
                
                # 직접 AI 처리 실행
                print(f"   🤖 Running AI processing...")
                process_cmd = [
                    "docker", "exec", "reddit-publisher-worker-nlp",
                    "python3", "-c",
                    f"""
import sys
sys.path.append('/app')
from workers.processor.tasks import process_content_with_ai
result = process_content_with_ai('{post_id}')
print(f'Processing result: {{result}}')
"""
                ]
                
                process_result = subprocess.run(process_cmd, capture_output=True, text=True, timeout=120)
                
                if process_result.returncode == 0:
                    print(f"   ✅ AI processing completed")
                    print(f"   📄 Output: {process_result.stdout.strip()}")
                    
                    # 처리 결과 확인
                    check_cmd = [
                        "docker", "exec", "reddit-publisher-postgres",
                        "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
                        f"SELECT status, summary_ko IS NOT NULL, tags FROM posts WHERE id = '{post_id}';"
                    ]
                    
                    check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                    
                    if check_result.returncode == 0:
                        output = check_result.stdout.strip()
                        parts = [p.strip() for p in output.split('|')]
                        if len(parts) >= 3:
                            status = parts[0]
                            has_summary = parts[1] == 't'
                            tags = parts[2]
                            
                            print(f"   📊 Processing Results:")
                            print(f"      Status: {status}")
                            print(f"      Has Summary: {has_summary}")
                            print(f"      Tags: {tags}")
                            
                            return status == 'processed' and has_summary
                else:
                    print(f"   ❌ AI processing failed: {process_result.stderr}")
                    return False
            else:
                print(f"   ⚠️ No unprocessed posts found")
                return True  # 처리할 것이 없으면 성공으로 간주
        else:
            print(f"   ❌ Failed to check for unprocessed posts")
            return False
            
    except Exception as e:
        print(f"❌ Direct processing test error: {e}")
        return False

def test_direct_publishing():
    """직접 발행 테스트"""
    try:
        print(f"🔍 Testing direct publishing...")
        
        # 처리된 포스트가 있는지 확인
        cmd = [
            "docker", "exec", "reddit-publisher-postgres",
            "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
            "SELECT id FROM posts WHERE status = 'processed' LIMIT 1;"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            post_id = result.stdout.strip()
            if post_id:
                print(f"   📋 Found processed post: {post_id}")
                
                # 직접 Ghost 발행 실행
                print(f"   👻 Running Ghost publishing...")
                publish_cmd = [
                    "docker", "exec", "reddit-publisher-worker-publisher",
                    "python3", "-c",
                    f"""
import sys
sys.path.append('/app')
from workers.publisher.tasks import publish_to_ghost
result = publish_to_ghost('{post_id}')
print(f'Publishing result: {{result}}')
"""
                ]
                
                publish_result = subprocess.run(publish_cmd, capture_output=True, text=True, timeout=60)
                
                if publish_result.returncode == 0:
                    print(f"   ✅ Ghost publishing completed")
                    print(f"   📄 Output: {publish_result.stdout.strip()}")
                    
                    # 발행 결과 확인
                    check_cmd = [
                        "docker", "exec", "reddit-publisher-postgres",
                        "psql", "-U", "reddit_publisher", "-d", "reddit_publisher", "-t", "-c",
                        f"SELECT status, ghost_url IS NOT NULL, ghost_post_id FROM posts WHERE id = '{post_id}';"
                    ]
                    
                    check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                    
                    if check_result.returncode == 0:
                        output = check_result.stdout.strip()
                        parts = [p.strip() for p in output.split('|')]
                        if len(parts) >= 3:
                            status = parts[0]
                            has_ghost_url = parts[1] == 't'
                            ghost_post_id = parts[2]
                            
                            print(f"   📊 Publishing Results:")
                            print(f"      Status: {status}")
                            print(f"      Has Ghost URL: {has_ghost_url}")
                            print(f"      Ghost Post ID: {ghost_post_id}")
                            
                            return status == 'published' and has_ghost_url
                else:
                    print(f"   ❌ Ghost publishing failed: {publish_result.stderr}")
                    return False
            else:
                print(f"   ⚠️ No processed posts found")
                return True  # 발행할 것이 없으면 성공으로 간주
        else:
            print(f"   ❌ Failed to check for processed posts")
            return False
            
    except Exception as e:
        print(f"❌ Direct publishing test error: {e}")
        return False

def run_simple_integration_test():
    """간단한 통합 테스트 실행"""
    print_header("간단한 통합 테스트 (기존 데이터 기반)")
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = {
        "database_data": False,
        "worker_status": False,
        "direct_processing": False,
        "direct_publishing": False
    }
    
    # 1. 데이터베이스 데이터 확인
    print_step("1. Database Data Check")
    db_data = check_database_data()
    test_results["database_data"] = db_data is not None and db_data["total"] > 0
    
    # 2. 워커 상태 확인
    print_step("2. Worker Status Check")
    test_results["worker_status"] = check_worker_status()
    
    # 3. 직접 처리 테스트
    print_step("3. Direct Processing Test")
    test_results["direct_processing"] = test_direct_processing()
    
    # 4. 직접 발행 테스트
    print_step("4. Direct Publishing Test")
    test_results["direct_publishing"] = test_direct_publishing()
    
    # 5. 결과 요약
    print_header("간단한 통합 테스트 결과")
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    print(f"📊 Integration Test Results: {passed_tests}/{total_tests} passed")
    
    for test_name, passed in test_results.items():
        emoji = "✅" if passed else "❌"
        test_display = test_name.replace('_', ' ').title()
        print(f"   {emoji} {test_display}: {'PASS' if passed else 'FAIL'}")
    
    # 최종 데이터베이스 상태 확인
    if db_data:
        print(f"\n📈 Final Database Statistics:")
        print(f"   📊 Total Posts: {db_data['total']}")
        print(f"   📥 Collected: {db_data['collected']}")
        print(f"   🤖 Processed: {db_data['processed']}")
        print(f"   👻 Published: {db_data['published']}")
        
        if db_data['total'] > 0:
            processing_rate = (db_data['processed'] / db_data['total']) * 100
            publishing_rate = (db_data['published'] / db_data['total']) * 100
            print(f"   📈 Processing Rate: {processing_rate:.1f}%")
            print(f"   📈 Publishing Rate: {publishing_rate:.1f}%")
    
    # 권장사항
    print(f"\n🔧 Recommendations:")
    if passed_tests >= 3:
        print("   ✅ Core pipeline components are working!")
        print("   🔄 Ready for performance testing.")
    else:
        print("   ⚠️ Some pipeline components need attention:")
        
        if not test_results["database_data"]:
            print("   📊 Check database connectivity and data integrity")
        if not test_results["worker_status"]:
            print("   🔧 Check worker container status and configuration")
        if not test_results["direct_processing"]:
            print("   🤖 Check AI processing logic and OpenAI API")
        if not test_results["direct_publishing"]:
            print("   👻 Check Ghost publishing logic and API")
    
    # 성공 기준: 최소 3개 테스트 통과
    overall_success = passed_tests >= 3
    
    return overall_success

if __name__ == "__main__":
    try:
        success = run_simple_integration_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Integration test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)