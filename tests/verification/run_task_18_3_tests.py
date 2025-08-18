#!/usr/bin/env python3
"""
Task 18.3: System Quality Verification Test Runner
Comprehensive test runner for Requirements 11.23-11.33
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
import subprocess
import concurrent.futures

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from tests.verification.system_quality_tests import SystemQualityVerifier
from tests.verification.test_config_18_3 import (
    get_test_config, 
    REQUIREMENT_TEST_MAPPING, 
    EXPECTED_OUTCOMES,
    list_all_requirements
)

class Task18_3TestRunner:
    """Test runner for Task 18.3 system quality verification"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = get_test_config()
        self.verifier = SystemQualityVerifier()
        self.start_time = datetime.utcnow()
        self.test_results = {}
        self.requirement_results = {}
        
        # Load custom config if provided
        if config_file and os.path.exists(config_file):
            self.load_custom_config(config_file)
    
    def load_custom_config(self, config_file: str):
        """Load custom configuration from file"""
        try:
            with open(config_file, 'r') as f:
                custom_config = json.load(f)
            
            # Update configuration with custom values
            for section, values in custom_config.items():
                if hasattr(self.config, section):
                    section_config = getattr(self.config, section)
                    for key, value in values.items():
                        if hasattr(section_config, key):
                            setattr(section_config, key, value)
            
            print(f"Loaded custom configuration from {config_file}")
        except Exception as e:
            print(f"Warning: Could not load custom config: {e}")
    
    def run_requirement_test(self, requirement_id: str) -> Dict[str, Any]:
        """Run tests for a specific requirement"""
        req_info = REQUIREMENT_TEST_MAPPING.get(requirement_id)
        if not req_info:
            return {
                'requirement_id': requirement_id,
                'status': 'ERROR',
                'message': f'Unknown requirement: {requirement_id}',
                'tests': []
            }
        
        print(f"\n=== Testing Requirement {requirement_id}: {req_info['name']} ===")
        print(f"Description: {req_info['description']}")
        
        test_results = []
        overall_status = 'PASS'
        
        # Run each test method for this requirement
        for test_method in req_info['test_methods']:
            if hasattr(self.verifier, test_method):
                try:
                    # Capture test results before and after
                    initial_count = self.verifier.total_tests
                    
                    # Run the test method
                    getattr(self.verifier, test_method)()
                    
                    # Calculate results for this test method
                    new_tests = self.verifier.total_tests - initial_count
                    new_failures = len([r for r in self.verifier.results[-new_tests:] if not r['passed']])
                    
                    test_result = {
                        'method': test_method,
                        'tests_run': new_tests,
                        'failures': new_failures,
                        'status': 'PASS' if new_failures == 0 else 'FAIL'
                    }
                    
                    test_results.append(test_result)
                    
                    if new_failures > 0:
                        overall_status = 'FAIL'
                        
                except Exception as e:
                    test_result = {
                        'method': test_method,
                        'tests_run': 0,
                        'failures': 1,
                        'status': 'ERROR',
                        'error': str(e)
                    }
                    test_results.append(test_result)
                    overall_status = 'ERROR'
            else:
                test_result = {
                    'method': test_method,
                    'tests_run': 0,
                    'failures': 1,
                    'status': 'ERROR',
                    'error': f'Test method {test_method} not found'
                }
                test_results.append(test_result)
                overall_status = 'ERROR'
        
        return {
            'requirement_id': requirement_id,
            'name': req_info['name'],
            'description': req_info['description'],
            'status': overall_status,
            'tests': test_results,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def run_all_requirements(self, parallel: bool = False) -> Dict[str, Any]:
        """Run tests for all requirements"""
        requirements = list_all_requirements()
        
        print(f"Running tests for {len(requirements)} requirements...")
        print(f"Parallel execution: {parallel}")
        
        if parallel:
            # Run requirements in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_req = {
                    executor.submit(self.run_requirement_test, req_id): req_id 
                    for req_id in requirements
                }
                
                for future in concurrent.futures.as_completed(future_to_req):
                    req_id = future_to_req[future]
                    try:
                        result = future.result()
                        self.requirement_results[req_id] = result
                    except Exception as e:
                        self.requirement_results[req_id] = {
                            'requirement_id': req_id,
                            'status': 'ERROR',
                            'error': str(e),
                            'tests': []
                        }
        else:
            # Run requirements sequentially
            for req_id in requirements:
                result = self.run_requirement_test(req_id)
                self.requirement_results[req_id] = result
                
                # Stop on first failure if configured
                if self.config.stop_on_first_failure and result['status'] != 'PASS':
                    print(f"Stopping on first failure: {req_id}")
                    break
        
        return self.requirement_results
    
    def run_specific_requirements(self, requirement_ids: List[str]) -> Dict[str, Any]:
        """Run tests for specific requirements"""
        print(f"Running tests for specific requirements: {requirement_ids}")
        
        for req_id in requirement_ids:
            if req_id not in REQUIREMENT_TEST_MAPPING:
                print(f"Warning: Unknown requirement {req_id}")
                continue
            
            result = self.run_requirement_test(req_id)
            self.requirement_results[req_id] = result
        
        return self.requirement_results
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate summary report of all test results"""
        end_time = datetime.utcnow()
        duration = (end_time - self.start_time).total_seconds()
        
        # Calculate overall statistics
        total_requirements = len(self.requirement_results)
        passed_requirements = len([r for r in self.requirement_results.values() if r['status'] == 'PASS'])
        failed_requirements = len([r for r in self.requirement_results.values() if r['status'] == 'FAIL'])
        error_requirements = len([r for r in self.requirement_results.values() if r['status'] == 'ERROR'])
        
        # Calculate test statistics
        total_tests = self.verifier.total_tests
        passed_tests = self.verifier.passed_tests
        failed_tests = self.verifier.failed_tests
        
        summary = {
            'execution_info': {
                'start_time': self.start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'task': '18.3 시스템 품질 검증 테스트 실행'
            },
            'requirement_summary': {
                'total_requirements': total_requirements,
                'passed_requirements': passed_requirements,
                'failed_requirements': failed_requirements,
                'error_requirements': error_requirements,
                'success_rate': (passed_requirements / total_requirements * 100) if total_requirements > 0 else 0
            },
            'test_summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            'requirement_results': self.requirement_results,
            'detailed_results': self.verifier.results
        }
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]):
        """Print formatted summary to console"""
        print("\n" + "="*80)
        print("TASK 18.3: SYSTEM QUALITY VERIFICATION TEST RESULTS")
        print("="*80)
        
        # Execution info
        exec_info = summary['execution_info']
        print(f"Task: {exec_info['task']}")
        print(f"Duration: {exec_info['duration_seconds']:.2f} seconds")
        print(f"Completed: {exec_info['end_time']}")
        
        # Requirement summary
        req_summary = summary['requirement_summary']
        print(f"\nRequirement Results:")
        print(f"  Total Requirements: {req_summary['total_requirements']}")
        print(f"  Passed: {req_summary['passed_requirements']} ({req_summary['success_rate']:.1f}%)")
        print(f"  Failed: {req_summary['failed_requirements']}")
        print(f"  Errors: {req_summary['error_requirements']}")
        
        # Test summary
        test_summary = summary['test_summary']
        print(f"\nTest Results:")
        print(f"  Total Tests: {test_summary['total_tests']}")
        print(f"  Passed: {test_summary['passed_tests']} ({test_summary['success_rate']:.1f}%)")
        print(f"  Failed: {test_summary['failed_tests']}")
        
        # Detailed requirement results
        print(f"\nDetailed Requirement Results:")
        for req_id, result in summary['requirement_results'].items():
            status_symbol = "✓" if result['status'] == 'PASS' else "✗" if result['status'] == 'FAIL' else "!"
            print(f"  {status_symbol} {req_id}: {result['name']} - {result['status']}")
            
            if result['status'] != 'PASS' and 'tests' in result:
                for test in result['tests']:
                    if test['status'] != 'PASS':
                        print(f"    - {test['method']}: {test['status']}")
                        if 'error' in test:
                            print(f"      Error: {test['error']}")
        
        # Overall result
        overall_success = (req_summary['failed_requirements'] == 0 and 
                          req_summary['error_requirements'] == 0)
        
        print(f"\n{'='*80}")
        if overall_success:
            print("✓ OVERALL RESULT: ALL SYSTEM QUALITY VERIFICATION TESTS PASSED")
            print("The system meets all quality requirements for Task 18.3")
        else:
            print("✗ OVERALL RESULT: SOME SYSTEM QUALITY VERIFICATION TESTS FAILED")
            print("Please review and fix the failed tests before proceeding")
        print("="*80)
        
        return overall_success
    
    def save_results(self, filename: Optional[str] = None):
        """Save test results to file"""
        if filename is None:
            filename = f"task_18_3_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = self.generate_summary_report()
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Test results saved to {filename}")
        return filename
    
    def run_pre_checks(self) -> bool:
        """Run pre-checks to ensure environment is ready"""
        print("Running pre-checks...")
        
        checks_passed = True
        
        # Check if required directories exist
        required_dirs = ['app', 'workers', 'tests', 'scripts']
        for dir_name in required_dirs:
            if not os.path.exists(dir_name):
                print(f"✗ Required directory missing: {dir_name}")
                checks_passed = False
            else:
                print(f"✓ Directory exists: {dir_name}")
        
        # Check if key files exist
        key_files = ['app/main.py', 'docker-compose.yml', 'Dockerfile']
        for file_name in key_files:
            if not os.path.exists(file_name):
                print(f"✗ Key file missing: {file_name}")
                checks_passed = False
            else:
                print(f"✓ Key file exists: {file_name}")
        
        # Check if services are running (optional)
        try:
            import requests
            health_response = requests.get(f"{self.config.observability.api_base_url}/health", timeout=5)
            if health_response.status_code == 200:
                print("✓ API service is running")
            else:
                print(f"! API service returned status {health_response.status_code}")
        except Exception:
            print("! API service not responding (tests will be limited)")
        
        return checks_passed

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Task 18.3: System Quality Verification Tests')
    parser.add_argument('--requirements', '-r', nargs='+', 
                       help='Specific requirements to test (e.g., 11.23 11.24)')
    parser.add_argument('--parallel', '-p', action='store_true',
                       help='Run tests in parallel')
    parser.add_argument('--config', '-c', type=str,
                       help='Custom configuration file')
    parser.add_argument('--output', '-o', type=str,
                       help='Output file for results')
    parser.add_argument('--no-pre-checks', action='store_true',
                       help='Skip pre-checks')
    parser.add_argument('--list-requirements', action='store_true',
                       help='List all available requirements')
    
    args = parser.parse_args()
    
    # List requirements if requested
    if args.list_requirements:
        print("Available requirements for Task 18.3:")
        for req_id in list_all_requirements():
            req_info = REQUIREMENT_TEST_MAPPING[req_id]
            print(f"  {req_id}: {req_info['name']}")
        return 0
    
    # Initialize test runner
    runner = Task18_3TestRunner(config_file=args.config)
    
    try:
        # Run pre-checks unless disabled
        if not args.no_pre_checks:
            if not runner.run_pre_checks():
                print("Pre-checks failed. Some tests may not work correctly.")
                response = input("Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    return 1
        
        # Run tests
        if args.requirements:
            # Run specific requirements
            runner.run_specific_requirements(args.requirements)
        else:
            # Run all requirements
            runner.run_all_requirements(parallel=args.parallel)
        
        # Generate and display summary
        summary = runner.generate_summary_report()
        overall_success = runner.print_summary(summary)
        
        # Save results
        output_file = args.output or f"task_18_3_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        runner.save_results(output_file)
        
        # Return appropriate exit code
        return 0 if overall_success else 1
        
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        return 1
    except Exception as e:
        print(f"Test execution failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())