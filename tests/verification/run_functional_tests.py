#!/usr/bin/env python3
"""
Functional Test Runner for Task 18.2
Executes all functional verification tests for Reddit Ghost Publisher MVP
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.verification.functional_tests import FunctionalVerificationTests
from tests.verification.test_config import get_test_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/verification/logs/functional_tests.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for functional test execution"""
    parser = argparse.ArgumentParser(description="Run functional verification tests for task 18.2")
    parser.add_argument("--environment", default="staging", choices=["staging", "production"],
                       help="Test environment to use")
    parser.add_argument("--suite", choices=["reddit", "ai", "ghost", "architecture", "all"], default="all",
                       help="Test suite to run")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", help="Output file for test results")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create test runner
    test_runner = FunctionalVerificationTests(args.environment)
    
    logger.info("=" * 80)
    logger.info("FUNCTIONAL VERIFICATION TESTS - TASK 18.2")
    logger.info("Reddit Ghost Publisher MVP System")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Test Suite: {args.suite}")
    logger.info("=" * 80)
    
    # Execute tests based on suite selection
    all_results = {}
    overall_passed = True
    
    try:
        if args.suite in ["reddit", "all"]:
            logger.info("\n" + "=" * 60)
            logger.info("REDDIT COLLECTION TESTS (Requirements 11.5-11.9)")
            logger.info("=" * 60)
            reddit_results = test_runner.run_reddit_collection_tests()
            all_results["reddit_collection"] = reddit_results
            
            if not reddit_results.get("passed", False):
                overall_passed = False
            
            # Print detailed results
            print_test_results("Reddit Collection", reddit_results)
        
        if args.suite in ["ai", "all"]:
            logger.info("\n" + "=" * 60)
            logger.info("AI PROCESSING TESTS (Requirements 11.10-11.14)")
            logger.info("=" * 60)
            ai_results = test_runner.run_ai_processing_tests()
            all_results["ai_processing"] = ai_results
            
            if not ai_results.get("passed", False):
                overall_passed = False
            
            print_test_results("AI Processing", ai_results)
        
        if args.suite in ["ghost", "all"]:
            logger.info("\n" + "=" * 60)
            logger.info("GHOST PUBLISHING TESTS (Requirements 11.15-11.20)")
            logger.info("=" * 60)
            ghost_results = test_runner.run_ghost_publishing_tests()
            all_results["ghost_publishing"] = ghost_results
            
            if not ghost_results.get("passed", False):
                overall_passed = False
            
            print_test_results("Ghost Publishing", ghost_results)
        
        if args.suite in ["architecture", "all"]:
            logger.info("\n" + "=" * 60)
            logger.info("ARCHITECTURE/QUEUE TESTS (Requirements 11.21-11.22)")
            logger.info("=" * 60)
            arch_results = test_runner.run_architecture_queue_tests()
            all_results["architecture_queue"] = arch_results
            
            if not arch_results.get("passed", False):
                overall_passed = False
            
            print_test_results("Architecture/Queue", arch_results)
        
        # Generate final summary
        generate_final_summary(all_results, overall_passed)
        
        # Save results to file if specified
        if args.output:
            save_results_to_file(all_results, args.output)
        
        # Exit with appropriate code
        sys.exit(0 if overall_passed else 1)
        
    except KeyboardInterrupt:
        logger.info("Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)

def print_test_results(suite_name: str, results: dict):
    """Print detailed test results for a suite"""
    print(f"\n{suite_name} Test Results:")
    print("-" * 50)
    
    if "tests" in results:
        for test_name, test_result in results["tests"].items():
            status = "✅ PASS" if test_result.get("passed", False) else "❌ FAIL"
            print(f"  {test_name}: {status}")
            
            if test_result.get("message"):
                print(f"    Message: {test_result['message']}")
            
            if test_result.get("error"):
                print(f"    Error: {test_result['error']}")
    
    pass_rate = results.get("pass_rate", 0.0)
    overall_status = "✅ PASS" if results.get("passed", False) else "❌ FAIL"
    print(f"\nOverall: {overall_status} (Pass Rate: {pass_rate:.1%})")

def generate_final_summary(all_results: dict, overall_passed: bool):
    """Generate final test summary"""
    logger.info("\n" + "=" * 80)
    logger.info("FINAL TEST SUMMARY - TASK 18.2")
    logger.info("=" * 80)
    
    total_tests = 0
    total_passed = 0
    
    for suite_name, suite_results in all_results.items():
        if "tests" in suite_results:
            suite_total = len(suite_results["tests"])
            suite_passed = sum(1 for test in suite_results["tests"].values() if test.get("passed", False))
            suite_pass_rate = suite_passed / suite_total if suite_total > 0 else 0.0
            
            total_tests += suite_total
            total_passed += suite_passed
            
            status = "✅ PASS" if suite_results.get("passed", False) else "❌ FAIL"
            logger.info(f"{suite_name.upper()}: {status} ({suite_passed}/{suite_total} - {suite_pass_rate:.1%})")
    
    overall_pass_rate = total_passed / total_tests if total_tests > 0 else 0.0
    final_status = "✅ PASS" if overall_passed else "❌ FAIL"
    
    logger.info("-" * 80)
    logger.info(f"OVERALL RESULT: {final_status}")
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed Tests: {total_passed}")
    logger.info(f"Failed Tests: {total_tests - total_passed}")
    logger.info(f"Pass Rate: {overall_pass_rate:.1%}")
    
    # Requirements compliance check
    logger.info("\nREQUIREMENTS COMPLIANCE:")
    logger.info("-" * 40)
    
    requirements_met = []
    requirements_failed = []
    
    for suite_name, suite_results in all_results.items():
        if suite_results.get("passed", False):
            if suite_name == "reddit_collection":
                requirements_met.extend(["11.5", "11.6", "11.7", "11.8", "11.9"])
            elif suite_name == "ai_processing":
                requirements_met.extend(["11.10", "11.11", "11.12", "11.13", "11.14"])
            elif suite_name == "ghost_publishing":
                requirements_met.extend(["11.15", "11.16", "11.17", "11.18", "11.19", "11.20"])
            elif suite_name == "architecture_queue":
                requirements_met.extend(["11.21", "11.22"])
        else:
            if suite_name == "reddit_collection":
                requirements_failed.extend(["11.5", "11.6", "11.7", "11.8", "11.9"])
            elif suite_name == "ai_processing":
                requirements_failed.extend(["11.10", "11.11", "11.12", "11.13", "11.14"])
            elif suite_name == "ghost_publishing":
                requirements_failed.extend(["11.15", "11.16", "11.17", "11.18", "11.19", "11.20"])
            elif suite_name == "architecture_queue":
                requirements_failed.extend(["11.21", "11.22"])
    
    logger.info(f"Requirements Met: {', '.join(requirements_met) if requirements_met else 'None'}")
    logger.info(f"Requirements Failed: {', '.join(requirements_failed) if requirements_failed else 'None'}")
    
    # Task 18.2 completion status
    task_completed = overall_passed and len(requirements_failed) == 0
    task_status = "✅ COMPLETED" if task_completed else "❌ INCOMPLETE"
    
    logger.info("\n" + "=" * 80)
    logger.info(f"TASK 18.2 STATUS: {task_status}")
    logger.info("=" * 80)
    
    if task_completed:
        logger.info("All functional verification tests have passed successfully.")
        logger.info("Task 18.2 (기능별 검증 테스트 실행) is now complete.")
        logger.info("The system is ready for the next verification phase.")
    else:
        logger.info("Some functional verification tests have failed.")
        logger.info("Please review the failed tests and fix the issues before proceeding.")
        logger.info("Task 18.2 requires all functional tests to pass.")

def save_results_to_file(results: dict, output_file: str):
    """Save test results to JSON file"""
    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Test results saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to save results to file: {e}")

if __name__ == "__main__":
    main()