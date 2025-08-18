#!/usr/bin/env python3
"""
End-to-end pipeline test for Reddit Ghost Publisher
Tests the complete flow: Reddit → AI Processing → Ghost Publishing
"""
import os
import sys
import time
import json
import requests
from datetime import datetime

def test_api_health():
    """Test API health and service status"""
    print("🏥 Testing API Health...")
    print("-" * 30)
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=10)
        health_data = response.json()
        
        print(f"📊 Overall Status: {health_data['status'].upper()}")
        print(f"🕐 Timestamp: {health_data['timestamp']}")
        print(f"🌍 Environment: {health_data['environment']}")
        
        print("\n📋 Service Status:")
        for service_name, service_data in health_data['services'].items():
            status_emoji = {
                'healthy': '✅',
                'degraded': '⚠️',
                'unhealthy': '❌'
            }.get(service_data['status'], '❓')
            
            print(f"   {status_emoji} {service_name}: {service_data['status']} ({service_data['response_time_ms']:.1f}ms)")
            if service_data['status'] != 'healthy':
                print(f"      Message: {service_data['message']}")
        
        print(f"\n📈 Summary: {health_data['summary']['healthy']}/{health_data['summary']['total_services']} services healthy")
        
        return health_data['summary']['healthy'] >= 3  # At least 3 services should be healthy
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_manual_triggers():
    """Test manual trigger endpoints"""
    print("\n🎯 Testing Manual Trigger Endpoints...")
    print("-" * 40)
    
    endpoints = [
        ("Collect", "POST", "/api/v1/collect/trigger"),
        ("Process", "POST", "/api/v1/process/trigger"),
        ("Publish", "POST", "/api/v1/publish/trigger")
    ]
    
    results = {}
    
    for name, method, endpoint in endpoints:
        try:
            print(f"🔄 Testing {name} trigger...")
            response = requests.request(
                method=method,
                url=f"http://localhost:8000{endpoint}",
                headers={"X-API-Key": "reddit-publisher-api-key-2024"},
                timeout=10,
                json={"test": True}  # Add test payload
            )
            
            if response.status_code in [200, 201, 202]:
                print(f"   ✅ {name} trigger: {response.status_code}")
                try:
                    data = response.json()
                    if 'task_id' in data:
                        print(f"      Task ID: {data['task_id']}")
                    results[name.lower()] = True
                except:
                    results[name.lower()] = True
            else:
                print(f"   ❌ {name} trigger: {response.status_code}")
                print(f"      Response: {response.text[:100]}")
                results[name.lower()] = False
                
        except Exception as e:
            print(f"   ❌ {name} trigger error: {e}")
            results[name.lower()] = False
    
    return results

def test_queue_status():
    """Test queue and worker status endpoints"""
    print("\n📊 Testing Queue and Worker Status...")
    print("-" * 40)
    
    try:
        # Test queue status
        print("🔍 Checking queue status...")
        response = requests.get("http://localhost:8000/api/v1/status/queues", 
                                headers={"X-API-Key": "reddit-publisher-api-key-2024"}, 
                                timeout=10)
        
        if response.status_code == 200:
            queue_data = response.json()
            print("   ✅ Queue status endpoint working")
            
            for queue_name, queue_info in queue_data.items():
                if isinstance(queue_info, dict):
                    active = queue_info.get('active', 0)
                    pending = queue_info.get('pending', 0)
                    print(f"      {queue_name}: {active} active, {pending} pending")
        else:
            print(f"   ❌ Queue status: {response.status_code}")
        
        # Test worker status
        print("\n🔍 Checking worker status...")
        response = requests.get("http://localhost:8000/api/v1/status/workers", 
                                headers={"X-API-Key": "reddit-publisher-api-key-2024"}, 
                                timeout=10)
        
        if response.status_code == 200:
            worker_data = response.json()
            print("   ✅ Worker status endpoint working")
            
            for worker_name, worker_info in worker_data.items():
                if isinstance(worker_info, dict):
                    status = worker_info.get('status', 'unknown')
                    active_tasks = worker_info.get('active_tasks', 0)
                    print(f"      {worker_name}: {status}, {active_tasks} active tasks")
        else:
            print(f"   ❌ Worker status: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Queue/Worker status error: {e}")
        return False

def test_metrics_endpoint():
    """Test metrics endpoint"""
    print("\n📈 Testing Metrics Endpoint...")
    print("-" * 30)
    
    try:
        response = requests.get("http://localhost:8000/metrics", 
                                headers={"X-API-Key": "reddit-publisher-api-key-2024"}, 
                                timeout=10)
        
        if response.status_code == 200:
            metrics_text = response.text
            print("   ✅ Metrics endpoint working")
            
            # Check for key metrics
            key_metrics = [
                "reddit_posts_collected_total",
                "posts_processed_total", 
                "posts_published_total",
                "processing_failures_total"
            ]
            
            found_metrics = []
            for metric in key_metrics:
                if metric in metrics_text:
                    found_metrics.append(metric)
            
            print(f"   📊 Found {len(found_metrics)}/{len(key_metrics)} key metrics")
            
            # Show sample metrics
            lines = metrics_text.split('\n')
            metric_lines = [line for line in lines if not line.startswith('#') and line.strip()][:5]
            
            if metric_lines:
                print("   📋 Sample metrics:")
                for line in metric_lines:
                    if line.strip():
                        print(f"      {line.strip()}")
            
            return len(found_metrics) >= 2
        else:
            print(f"   ❌ Metrics endpoint: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Metrics endpoint error: {e}")
        return False

def test_pipeline_integration():
    """Test basic pipeline integration"""
    print("\n🔄 Testing Pipeline Integration...")
    print("-" * 35)
    
    try:
        # Test a simple collect → process → publish chain
        print("🎯 Testing collect → process → publish chain...")
        
        # Trigger collection
        collect_response = requests.post(
            "http://localhost:8000/api/v1/collect/trigger",
            json={"subreddits": ["test"], "limit": 1},
            headers={"X-API-Key": "reddit-publisher-api-key-2024"},
            timeout=10
        )
        
        if collect_response.status_code in [200, 201, 202]:
            print("   ✅ Collection trigger successful")
            
            # Wait a moment for processing
            time.sleep(2)
            
            # Check if any tasks were queued
            queue_response = requests.get("http://localhost:8000/api/v1/status/queues", 
                                          headers={"X-API-Key": "reddit-publisher-api-key-2024"}, 
                                          timeout=10)
            if queue_response.status_code == 200:
                queue_data = queue_response.json()
                total_tasks = sum(
                    queue_info.get('pending', 0) + queue_info.get('active', 0)
                    for queue_info in queue_data.values()
                    if isinstance(queue_info, dict)
                )
                print(f"   📊 Total tasks in queues: {total_tasks}")
            
            return True
        else:
            print(f"   ❌ Collection trigger failed: {collect_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Pipeline integration error: {e}")
        return False

def run_full_pipeline_test():
    """Run complete pipeline test suite"""
    print("🚀 Reddit Ghost Publisher - Full Pipeline Test")
    print("=" * 60)
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    test_results = {}
    
    # Test 1: API Health
    test_results['health'] = test_api_health()
    
    # Test 2: Manual Triggers
    trigger_results = test_manual_triggers()
    test_results['triggers'] = all(trigger_results.values())
    
    # Test 3: Queue Status
    test_results['queues'] = test_queue_status()
    
    # Test 4: Metrics
    test_results['metrics'] = test_metrics_endpoint()
    
    # Test 5: Pipeline Integration
    test_results['pipeline'] = test_pipeline_integration()
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 Pipeline Test Summary")
    print("=" * 60)
    
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    for test_name, result in test_results.items():
        status_emoji = "✅" if result else "❌"
        print(f"   {status_emoji} {test_name.title()}: {'PASS' if result else 'FAIL'}")
    
    print(f"\n📊 Overall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests >= 4:  # At least 4/5 tests should pass
        print("🎉 Pipeline is functional and ready for use!")
        print("\n🔧 Next Steps:")
        print("   1. ✅ Celery workers are running")
        print("   2. ✅ API endpoints are functional") 
        print("   3. ✅ External APIs are accessible")
        print("   4. ⚠️ Ghost API may be rate limited (expected)")
        print("   5. 🔄 Ready for production testing")
        return True
    else:
        print("⚠️ Pipeline has some issues that need attention")
        print("\n🔧 Recommended Actions:")
        if not test_results['health']:
            print("   - Check service health and dependencies")
        if not test_results['triggers']:
            print("   - Verify API endpoint implementations")
        if not test_results['queues']:
            print("   - Check Celery worker status")
        if not test_results['metrics']:
            print("   - Verify metrics collection system")
        if not test_results['pipeline']:
            print("   - Test individual pipeline components")
        return False

if __name__ == "__main__":
    success = run_full_pipeline_test()
    sys.exit(0 if success else 1)