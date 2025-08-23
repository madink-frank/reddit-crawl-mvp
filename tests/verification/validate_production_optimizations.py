#!/usr/bin/env python3
"""
Production Optimization Validation Test
Validates all production optimizations including performance, error handling, and monitoring
"""

import os
import sys
import json
import time
import asyncio
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/verification/logs/production_optimization_validation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ProductionOptimizationValidator:
    """Validates production optimizations and enhancements"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url.rstrip('/')
        self.test_results = {}
        
        logger.info(f"Initialized production optimization validator for: {api_base_url}")
    
    async def run_validation_tests(self) -> Dict[str, Any]:
        """Run comprehensive validation tests for production optimizations"""
        logger.info("=== Starting Production Optimization Validation ===")
        
        validation_results = {
            "test_name": "production_optimization_validation",
            "start_time": datetime.now().isoformat(),
            "api_base_url": self.api_base_url,
            "test_categories": {},
            "overall_success": False,
            "optimization_scores": {}
        }
        
        try:
            # Category 1: API Response Speed Optimization
            logger.info("Category 1: API Response Speed Optimization")
            api_speed_results = await self._test_api_response_speed()
            validation_results["test_categories"]["api_response_speed"] = api_speed_results
            
            # Category 2: Dashboard Real-time Updates
            logger.info("Category 2: Dashboard Real-time Updates")
            dashboard_results = await self._test_dashboard_realtime_updates()
            validation_results["test_categories"]["dashboard_realtime"] = dashboard_results
            
            # Category 3: Enhanced Error Handling
            logger.info("Category 3: Enhanced Error Handling")
            error_handling_results = await self._test_enhanced_error_handling()
            validation_results["test_categories"]["error_handling"] = error_handling_results
            
            # Category 4: Performance Monitoring
            logger.info("Category 4: Performance Monitoring")
            monitoring_results = await self._test_performance_monitoring()
            validation_results["test_categories"]["performance_monitoring"] = monitoring_results
            
            # Category 5: Caching and Compression
            logger.info("Category 5: Caching and Compression")
            caching_results = await self._test_caching_compression()
            validation_results["test_categories"]["caching_compression"] = caching_results
            
            # Category 6: Security Enhancements
            logger.info("Category 6: Security Enhancements")
            security_results = await self._test_security_enhancements()
            validation_results["test_categories"]["security"] = security_results
            
            # Calculate optimization scores
            validation_results["optimization_scores"] = self._calculate_optimization_scores(
                validation_results["test_categories"]
            )
            
            # Determine overall success
            validation_results["overall_success"] = self._determine_overall_success(
                validation_results["test_categories"]
            )
            
            logger.info(f"=== Production Optimization Validation Complete: {'SUCCESS' if validation_results['overall_success'] else 'FAILED'} ===")
            
        except Exception as e:
            logger.error(f"Validation failed with exception: {e}")
            validation_results["error"] = str(e)
            validation_results["overall_success"] = False
        
        validation_results["end_time"] = datetime.now().isoformat()
        validation_results["duration_seconds"] = (
            datetime.fromisoformat(validation_results["end_time"]) - 
            datetime.fromisoformat(validation_results["start_time"])
        ).total_seconds()
        
        # Save results
        await self._save_validation_results(validation_results)
        
        return validation_results
    
    async def _test_api_response_speed(self) -> Dict[str, Any]:
        """Test API response speed optimizations"""
        results = {
            "category": "api_response_speed",
            "tests": {},
            "success": False,
            "performance_metrics": {}
        }
        
        try:
            # Test 1: Basic endpoint response times
            logger.info("Testing basic endpoint response times...")
            
            endpoints = [
                "/health",
                "/metrics", 
                "/api/v1/status/queues",
                "/api/v1/status/workers",
                "/dashboard/api/pipeline/status"
            ]
            
            response_times = []
            endpoint_results = {}
            
            for endpoint in endpoints:
                start_time = time.time()
                
                try:
                    response = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
                    response_time = (time.time() - start_time) * 1000  # Convert to ms
                    
                    endpoint_results[endpoint] = {
                        "success": response.status_code == 200,
                        "response_time_ms": response_time,
                        "status_code": response.status_code
                    }
                    
                    if response.status_code == 200:
                        response_times.append(response_time)
                
                except Exception as e:
                    endpoint_results[endpoint] = {
                        "success": False,
                        "error": str(e),
                        "response_time_ms": (time.time() - start_time) * 1000
                    }
            
            results["tests"]["endpoint_response_times"] = {
                "success": len(response_times) >= len(endpoints) * 0.8,  # 80% success rate
                "endpoints": endpoint_results,
                "average_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
                "max_response_time_ms": max(response_times) if response_times else 0,
                "p95_target_met": max(response_times) <= 300 if response_times else False  # 300ms target
            }
            
            # Test 2: Load testing with concurrent requests
            logger.info("Testing concurrent request handling...")
            
            concurrent_results = await self._test_concurrent_requests("/health", 20, 5)
            results["tests"]["concurrent_requests"] = concurrent_results
            
            # Test 3: Caching effectiveness
            logger.info("Testing caching effectiveness...")
            
            caching_results = await self._test_caching_effectiveness()
            results["tests"]["caching_effectiveness"] = caching_results
            
            # Calculate performance metrics
            results["performance_metrics"] = {
                "average_response_time_ms": results["tests"]["endpoint_response_times"]["average_response_time_ms"],
                "p95_response_time_ms": results["tests"]["endpoint_response_times"]["max_response_time_ms"],
                "concurrent_success_rate": concurrent_results.get("success_rate", 0),
                "cache_hit_rate": caching_results.get("cache_hit_rate", 0)
            }
            
            # Overall success criteria
            results["success"] = (
                results["tests"]["endpoint_response_times"]["success"] and
                results["tests"]["endpoint_response_times"]["p95_target_met"] and
                concurrent_results.get("success_rate", 0) >= 0.9  # 90% success rate for concurrent requests
            )
            
        except Exception as e:
            logger.error(f"API response speed test failed: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _test_dashboard_realtime_updates(self) -> Dict[str, Any]:
        """Test dashboard real-time update functionality"""
        results = {
            "category": "dashboard_realtime",
            "tests": {},
            "success": False
        }
        
        try:
            # Test 1: Dashboard endpoint accessibility
            logger.info("Testing dashboard endpoint accessibility...")
            
            dashboard_endpoints = [
                "/dashboard/pipeline-monitor",
                "/dashboard/api/pipeline/status",
                "/dashboard/api/pipeline/published-posts"
            ]
            
            dashboard_accessibility = {}
            accessible_count = 0
            
            for endpoint in dashboard_endpoints:
                try:
                    response = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
                    success = response.status_code == 200
                    
                    dashboard_accessibility[endpoint] = {
                        "success": success,
                        "status_code": response.status_code,
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                    }
                    
                    if success:
                        accessible_count += 1
                
                except Exception as e:
                    dashboard_accessibility[endpoint] = {
                        "success": False,
                        "error": str(e)
                    }
            
            results["tests"]["dashboard_accessibility"] = {
                "success": accessible_count >= len(dashboard_endpoints) * 0.8,
                "accessible_endpoints": accessible_count,
                "total_endpoints": len(dashboard_endpoints),
                "endpoints": dashboard_accessibility
            }
            
            # Test 2: Real-time data updates
            logger.info("Testing real-time data updates...")
            
            realtime_results = await self._test_realtime_data_updates()
            results["tests"]["realtime_updates"] = realtime_results
            
            # Test 3: WebSocket connectivity (if available)
            logger.info("Testing WebSocket connectivity...")
            
            websocket_results = await self._test_websocket_connectivity()
            results["tests"]["websocket_connectivity"] = websocket_results
            
            # Overall success
            results["success"] = (
                results["tests"]["dashboard_accessibility"]["success"] and
                realtime_results.get("success", False)
            )
            
        except Exception as e:
            logger.error(f"Dashboard real-time updates test failed: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _test_enhanced_error_handling(self) -> Dict[str, Any]:
        """Test enhanced error handling and user experience"""
        results = {
            "category": "error_handling",
            "tests": {},
            "success": False
        }
        
        try:
            # Test 1: Error response format
            logger.info("Testing error response format...")
            
            # Trigger various error types
            error_tests = [
                {"endpoint": "/api/v1/nonexistent", "expected_status": 404, "error_type": "not_found"},
                {"endpoint": "/api/v1/collect/trigger", "method": "POST", "data": {"invalid": "data"}, "expected_status": 422, "error_type": "validation"}
            ]
            
            error_format_results = {}
            
            for test in error_tests:
                try:
                    if test.get("method") == "POST":
                        response = requests.post(
                            f"{self.api_base_url}{test['endpoint']}", 
                            json=test.get("data", {}),
                            timeout=10
                        )
                    else:
                        response = requests.get(f"{self.api_base_url}{test['endpoint']}", timeout=10)
                    
                    # Check error response format
                    if response.status_code == test["expected_status"]:
                        try:
                            error_data = response.json()
                            
                            # Check for enhanced error structure
                            has_error_structure = (
                                "error" in error_data and
                                "id" in error_data.get("error", {}) and
                                "title" in error_data.get("error", {}) and
                                "message" in error_data.get("error", {}) and
                                "suggestions" in error_data.get("error", {})
                            )
                            
                            error_format_results[test["error_type"]] = {
                                "success": has_error_structure,
                                "status_code": response.status_code,
                                "has_enhanced_format": has_error_structure,
                                "error_id": error_data.get("error", {}).get("id"),
                                "has_suggestions": len(error_data.get("error", {}).get("suggestions", [])) > 0
                            }
                            
                        except json.JSONDecodeError:
                            error_format_results[test["error_type"]] = {
                                "success": False,
                                "error": "Invalid JSON response"
                            }
                    else:
                        error_format_results[test["error_type"]] = {
                            "success": False,
                            "expected_status": test["expected_status"],
                            "actual_status": response.status_code
                        }
                
                except Exception as e:
                    error_format_results[test["error_type"]] = {
                        "success": False,
                        "error": str(e)
                    }
            
            results["tests"]["error_response_format"] = {
                "success": all(result.get("success", False) for result in error_format_results.values()),
                "error_types": error_format_results
            }
            
            # Test 2: Error statistics tracking
            logger.info("Testing error statistics tracking...")
            
            try:
                response = requests.get(f"{self.api_base_url}/api/v1/monitoring/error-stats", timeout=10)
                
                error_stats_results = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code
                }
                
                if response.status_code == 200:
                    stats_data = response.json()
                    error_stats_results["has_statistics"] = (
                        "total_errors" in stats_data and
                        "errors_by_category" in stats_data
                    )
                
                results["tests"]["error_statistics"] = error_stats_results
                
            except Exception as e:
                results["tests"]["error_statistics"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Overall success
            results["success"] = results["tests"]["error_response_format"]["success"]
            
        except Exception as e:
            logger.error(f"Enhanced error handling test failed: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _test_performance_monitoring(self) -> Dict[str, Any]:
        """Test performance monitoring capabilities"""
        results = {
            "category": "performance_monitoring",
            "tests": {},
            "success": False
        }
        
        try:
            # Test 1: Performance metrics endpoint
            logger.info("Testing performance metrics endpoint...")
            
            try:
                response = requests.get(f"{self.api_base_url}/api/v1/monitoring/performance", timeout=10)
                
                perf_metrics_results = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code
                }
                
                if response.status_code == 200:
                    metrics_data = response.json()
                    perf_metrics_results["has_performance_data"] = (
                        "performance" in metrics_data and
                        "cache" in metrics_data
                    )
                
                results["tests"]["performance_metrics"] = perf_metrics_results
                
            except Exception as e:
                results["tests"]["performance_metrics"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Test 2: Real-time monitoring endpoint
            logger.info("Testing real-time monitoring endpoint...")
            
            try:
                response = requests.get(f"{self.api_base_url}/dashboard/api/realtime/metrics", timeout=10)
                
                realtime_metrics_results = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code
                }
                
                if response.status_code == 200:
                    realtime_data = response.json()
                    realtime_metrics_results["has_realtime_data"] = (
                        "data" in realtime_data and
                        "timestamp" in realtime_data.get("data", {})
                    )
                
                results["tests"]["realtime_monitoring"] = realtime_metrics_results
                
            except Exception as e:
                results["tests"]["realtime_monitoring"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Test 3: Performance headers
            logger.info("Testing performance headers...")
            
            try:
                response = requests.get(f"{self.api_base_url}/health", timeout=10)
                
                headers_results = {
                    "success": response.status_code == 200,
                    "has_response_time_header": "X-Response-Time" in response.headers,
                    "has_cache_header": "X-Cache" in response.headers,
                    "response_headers": dict(response.headers)
                }
                
                results["tests"]["performance_headers"] = headers_results
                
            except Exception as e:
                results["tests"]["performance_headers"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Overall success
            results["success"] = (
                results["tests"]["performance_metrics"].get("success", False) and
                results["tests"]["realtime_monitoring"].get("success", False)
            )
            
        except Exception as e:
            logger.error(f"Performance monitoring test failed: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _test_caching_compression(self) -> Dict[str, Any]:
        """Test caching and compression optimizations"""
        results = {
            "category": "caching_compression",
            "tests": {},
            "success": False
        }
        
        try:
            # Test 1: Response caching
            logger.info("Testing response caching...")
            
            caching_results = await self._test_response_caching()
            results["tests"]["response_caching"] = caching_results
            
            # Test 2: Compression
            logger.info("Testing response compression...")
            
            compression_results = await self._test_response_compression()
            results["tests"]["response_compression"] = compression_results
            
            # Overall success
            results["success"] = (
                caching_results.get("success", False) or  # Caching might not be enabled in all environments
                compression_results.get("success", False)
            )
            
        except Exception as e:
            logger.error(f"Caching and compression test failed: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _test_security_enhancements(self) -> Dict[str, Any]:
        """Test security enhancements"""
        results = {
            "category": "security",
            "tests": {},
            "success": False
        }
        
        try:
            # Test 1: Security headers
            logger.info("Testing security headers...")
            
            try:
                response = requests.get(f"{self.api_base_url}/health", timeout=10)
                
                security_headers = [
                    "X-Content-Type-Options",
                    "X-Frame-Options", 
                    "X-XSS-Protection"
                ]
                
                present_headers = [header for header in security_headers if header in response.headers]
                
                security_headers_results = {
                    "success": len(present_headers) >= 2,  # At least 2 security headers
                    "present_headers": present_headers,
                    "total_expected": len(security_headers),
                    "all_headers": dict(response.headers)
                }
                
                results["tests"]["security_headers"] = security_headers_results
                
            except Exception as e:
                results["tests"]["security_headers"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Test 2: Input validation
            logger.info("Testing input validation...")
            
            try:
                # Test with invalid JSON
                response = requests.post(
                    f"{self.api_base_url}/api/v1/collect/trigger",
                    data="invalid json",
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                input_validation_results = {
                    "success": response.status_code in [400, 422],  # Should reject invalid input
                    "status_code": response.status_code,
                    "rejects_invalid_input": response.status_code in [400, 422]
                }
                
                results["tests"]["input_validation"] = input_validation_results
                
            except Exception as e:
                results["tests"]["input_validation"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Overall success
            results["success"] = (
                results["tests"]["security_headers"].get("success", False) and
                results["tests"]["input_validation"].get("success", False)
            )
            
        except Exception as e:
            logger.error(f"Security enhancements test failed: {e}")
            results["error"] = str(e)
        
        return results
    
    # Helper methods
    
    async def _test_concurrent_requests(self, endpoint: str, num_requests: int, concurrency: int) -> Dict[str, Any]:
        """Test concurrent request handling"""
        import aiohttp
        
        async def make_request(session, url):
            try:
                start_time = time.time()
                async with session.get(url, timeout=10) as response:
                    response_time = (time.time() - start_time) * 1000
                    return {
                        "success": response.status == 200,
                        "status_code": response.status,
                        "response_time_ms": response_time
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "response_time_ms": (time.time() - start_time) * 1000
                }
        
        try:
            url = f"{self.api_base_url}{endpoint}"
            
            async with aiohttp.ClientSession() as session:
                # Create semaphore to limit concurrency
                semaphore = asyncio.Semaphore(concurrency)
                
                async def bounded_request():
                    async with semaphore:
                        return await make_request(session, url)
                
                # Execute concurrent requests
                tasks = [bounded_request() for _ in range(num_requests)]
                results = await asyncio.gather(*tasks)
            
            # Analyze results
            successful_requests = [r for r in results if r.get("success", False)]
            response_times = [r["response_time_ms"] for r in results if "response_time_ms" in r]
            
            return {
                "success": len(successful_requests) >= num_requests * 0.9,  # 90% success rate
                "total_requests": num_requests,
                "successful_requests": len(successful_requests),
                "success_rate": len(successful_requests) / num_requests,
                "average_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
                "max_response_time_ms": max(response_times) if response_times else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _test_caching_effectiveness(self) -> Dict[str, Any]:
        """Test caching effectiveness"""
        try:
            endpoint = "/api/v1/status/queues"
            
            # First request (cache miss)
            start_time = time.time()
            response1 = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
            first_response_time = (time.time() - start_time) * 1000
            
            # Second request (potential cache hit)
            start_time = time.time()
            response2 = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
            second_response_time = (time.time() - start_time) * 1000
            
            # Check for cache headers
            cache_hit = response2.headers.get("X-Cache") == "HIT"
            
            return {
                "success": response1.status_code == 200 and response2.status_code == 200,
                "first_response_time_ms": first_response_time,
                "second_response_time_ms": second_response_time,
                "cache_hit": cache_hit,
                "cache_hit_rate": 1.0 if cache_hit else 0.0,
                "performance_improvement": (first_response_time - second_response_time) / first_response_time if first_response_time > 0 else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _test_realtime_data_updates(self) -> Dict[str, Any]:
        """Test real-time data update functionality"""
        try:
            # Get initial status
            response1 = requests.get(f"{self.api_base_url}/dashboard/api/pipeline/status", timeout=10)
            
            if response1.status_code != 200:
                return {
                    "success": False,
                    "error": f"Initial status request failed: {response1.status_code}"
                }
            
            initial_data = response1.json()
            initial_timestamp = initial_data.get("data", {}).get("last_updated")
            
            # Wait a moment
            await asyncio.sleep(2)
            
            # Get updated status
            response2 = requests.get(f"{self.api_base_url}/dashboard/api/pipeline/status", timeout=10)
            
            if response2.status_code != 200:
                return {
                    "success": False,
                    "error": f"Updated status request failed: {response2.status_code}"
                }
            
            updated_data = response2.json()
            updated_timestamp = updated_data.get("data", {}).get("last_updated")
            
            # Check if data is being updated
            data_updated = initial_timestamp != updated_timestamp
            
            return {
                "success": True,
                "data_updated": data_updated,
                "initial_timestamp": initial_timestamp,
                "updated_timestamp": updated_timestamp,
                "has_realtime_data": "last_updated" in updated_data.get("data", {})
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _test_websocket_connectivity(self) -> Dict[str, Any]:
        """Test WebSocket connectivity (basic test)"""
        try:
            # This is a basic test - in a real implementation, you'd use websockets library
            # For now, just check if the WebSocket endpoint exists
            
            # Check if WebSocket endpoint is documented or accessible
            response = requests.get(f"{self.api_base_url}/dashboard/api/realtime/connections", timeout=10)
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "websocket_endpoint_available": response.status_code == 200
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _test_response_caching(self) -> Dict[str, Any]:
        """Test response caching"""
        try:
            # Test cacheable endpoint multiple times
            endpoint = "/health"
            responses = []
            
            for i in range(3):
                start_time = time.time()
                response = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
                response_time = (time.time() - start_time) * 1000
                
                responses.append({
                    "status_code": response.status_code,
                    "response_time_ms": response_time,
                    "cache_header": response.headers.get("X-Cache", "MISS"),
                    "headers": dict(response.headers)
                })
                
                await asyncio.sleep(0.5)  # Small delay between requests
            
            # Check for cache hits
            cache_hits = [r for r in responses if r["cache_header"] == "HIT"]
            
            return {
                "success": len(responses) == 3 and all(r["status_code"] == 200 for r in responses),
                "total_requests": len(responses),
                "cache_hits": len(cache_hits),
                "cache_hit_rate": len(cache_hits) / len(responses) if responses else 0,
                "responses": responses
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _test_response_compression(self) -> Dict[str, Any]:
        """Test response compression"""
        try:
            # Request with compression support
            headers = {"Accept-Encoding": "gzip, deflate"}
            response = requests.get(f"{self.api_base_url}/metrics", headers=headers, timeout=10)
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "content_encoding": response.headers.get("Content-Encoding"),
                "is_compressed": "gzip" in response.headers.get("Content-Encoding", ""),
                "content_length": len(response.content),
                "headers": dict(response.headers)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _calculate_optimization_scores(self, test_categories: Dict[str, Any]) -> Dict[str, float]:
        """Calculate optimization scores for each category"""
        scores = {}
        
        for category_name, category_results in test_categories.items():
            if category_results.get("success", False):
                # Base score for successful category
                base_score = 80.0
                
                # Bonus points for specific optimizations
                bonus_points = 0.0
                
                if category_name == "api_response_speed":
                    # Bonus for meeting performance targets
                    perf_metrics = category_results.get("performance_metrics", {})
                    if perf_metrics.get("p95_response_time_ms", 1000) <= 300:
                        bonus_points += 10.0
                    if perf_metrics.get("concurrent_success_rate", 0) >= 0.95:
                        bonus_points += 10.0
                
                elif category_name == "dashboard_realtime":
                    # Bonus for real-time functionality
                    if category_results.get("tests", {}).get("realtime_updates", {}).get("data_updated", False):
                        bonus_points += 15.0
                
                elif category_name == "error_handling":
                    # Bonus for enhanced error format
                    error_tests = category_results.get("tests", {}).get("error_response_format", {})
                    if error_tests.get("success", False):
                        bonus_points += 15.0
                
                elif category_name == "caching_compression":
                    # Bonus for caching effectiveness
                    caching_test = category_results.get("tests", {}).get("response_caching", {})
                    if caching_test.get("cache_hit_rate", 0) > 0:
                        bonus_points += 10.0
                
                scores[category_name] = min(100.0, base_score + bonus_points)
            else:
                scores[category_name] = 20.0  # Minimum score for failed categories
        
        # Calculate overall score
        if scores:
            scores["overall"] = sum(scores.values()) / len(scores)
        else:
            scores["overall"] = 0.0
        
        return scores
    
    def _determine_overall_success(self, test_categories: Dict[str, Any]) -> bool:
        """Determine overall success based on test results"""
        # Critical categories that must pass
        critical_categories = ["api_response_speed", "error_handling"]
        
        # Check critical categories
        for category in critical_categories:
            if not test_categories.get(category, {}).get("success", False):
                return False
        
        # Check overall success rate
        successful_categories = sum(1 for cat in test_categories.values() if cat.get("success", False))
        total_categories = len(test_categories)
        
        success_rate = successful_categories / total_categories if total_categories > 0 else 0
        
        return success_rate >= 0.7  # 70% of categories must pass
    
    async def _save_validation_results(self, results: Dict[str, Any]) -> None:
        """Save validation results to file"""
        try:
            # Create results directory
            results_dir = Path("tests/verification/reports")
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"production_optimization_validation_{timestamp}.json"
            filepath = results_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Validation results saved to: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save validation results: {e}")


async def main():
    """Main entry point for production optimization validation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Production Optimizations")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run validator
    validator = ProductionOptimizationValidator(args.api_url)
    results = await validator.run_validation_tests()
    
    # Print summary
    print("\n" + "="*80)
    print("PRODUCTION OPTIMIZATION VALIDATION SUMMARY")
    print("="*80)
    print(f"API URL: {args.api_url}")
    print(f"Overall Success: {'✓ PASSED' if results['overall_success'] else '✗ FAILED'}")
    print(f"Duration: {results.get('duration_seconds', 0):.1f} seconds")
    
    # Category results
    print("\nCategory Results:")
    for category_name, category_result in results.get("test_categories", {}).items():
        status = "✓ PASSED" if category_result.get("success", False) else "✗ FAILED"
        print(f"  {category_name.replace('_', ' ').title()}: {status}")
    
    # Optimization scores
    if "optimization_scores" in results:
        print(f"\nOptimization Scores:")
        for category, score in results["optimization_scores"].items():
            print(f"  {category.replace('_', ' ').title()}: {score:.1f}/100")
    
    print("="*80)
    
    # Exit with appropriate code
    sys.exit(0 if results["overall_success"] else 1)


if __name__ == "__main__":
    asyncio.run(main())