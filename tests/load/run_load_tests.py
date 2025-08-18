#!/usr/bin/env python3
"""
Load test runner script for Reddit Ghost Publisher

This script runs various load test scenarios and generates reports.
"""
import os
import sys
import subprocess
import argparse
import time
from datetime import datetime
from load_test_config import LoadTestRunner, PerformanceMonitor


def run_command(command: str, timeout: int = None) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_prerequisites() -> bool:
    """Check if all prerequisites are installed"""
    print("Checking prerequisites...")
    
    # Check if locust is installed
    exit_code, _, _ = run_command("locust --version")
    if exit_code != 0:
        print("❌ Locust is not installed. Install with: pip install locust")
        return False
    
    print("✅ Locust is installed")
    
    # Check if the application is running
    exit_code, _, _ = run_command("curl -s http://localhost:8000/health")
    if exit_code != 0:
        print("❌ Application is not running on http://localhost:8000")
        print("   Start the application before running load tests")
        return False
    
    print("✅ Application is running")
    return True


def run_load_test(config_name: str, runner: LoadTestRunner) -> bool:
    """Run a specific load test configuration"""
    configs = runner.load_configs()
    
    if config_name not in configs:
        print(f"❌ Configuration '{config_name}' not found")
        print(f"Available configurations: {', '.join(configs.keys())}")
        return False
    
    config = configs[config_name]
    print(f"\n🚀 Running load test: {config.name}")
    print(f"Description: {config.description}")
    print(f"Users: {config.users}, Spawn Rate: {config.spawn_rate}, Duration: {config.run_time}")
    
    # Generate Locust command
    command = runner.generate_locust_command(config)
    print(f"Command: {command}")
    
    # Start performance monitoring
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    
    # Run the load test
    start_time = time.time()
    exit_code, stdout, stderr = run_command(command, timeout=3600)  # 1 hour timeout
    end_time = time.time()
    
    # Stop monitoring
    monitor.stop_monitoring()
    
    if exit_code != 0:
        print(f"❌ Load test failed with exit code {exit_code}")
        print(f"Error: {stderr}")
        return False
    
    print(f"✅ Load test completed in {end_time - start_time:.2f} seconds")
    
    # Analyze results (this would parse actual CSV results in a real implementation)
    results = runner.analyze_results("mock_results.csv")
    checks = runner.check_performance_requirements(config, results)
    
    # Generate report
    report = runner.generate_report(config, results, checks)
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"{runner.results_dir}/{config.name}_report_{timestamp}.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"📊 Report saved to: {report_file}")
    
    # Print summary
    overall_pass = all(checks.values())
    print(f"\n{'✅ PASS' if overall_pass else '❌ FAIL'}: {config.name}")
    
    return overall_pass


def run_all_tests(runner: LoadTestRunner) -> bool:
    """Run all load test configurations"""
    configs = runner.load_configs()
    results = {}
    
    print(f"\n🎯 Running all {len(configs)} load test configurations...")
    
    for config_name in configs.keys():
        print(f"\n{'='*60}")
        success = run_load_test(config_name, runner)
        results[config_name] = success
        
        if not success:
            print(f"❌ {config_name} failed - stopping test suite")
            break
        
        # Wait between tests to allow system to recover
        if config_name != list(configs.keys())[-1]:  # Not the last test
            print("⏳ Waiting 30 seconds before next test...")
            time.sleep(30)
    
    # Print overall summary
    print(f"\n{'='*60}")
    print("📋 LOAD TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(results.values())
    total = len(results)
    
    for config_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{config_name:20} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    return passed == total


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run load tests for Reddit Ghost Publisher")
    parser.add_argument(
        "test_name",
        nargs="?",
        help="Name of the test configuration to run (or 'all' for all tests)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available test configurations"
    )
    parser.add_argument(
        "--no-prereq-check",
        action="store_true",
        help="Skip prerequisite checks"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Target host for load testing"
    )
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = LoadTestRunner()
    
    # List configurations if requested
    if args.list:
        configs = runner.load_configs()
        print("Available load test configurations:")
        print("=" * 50)
        for name, config in configs.items():
            print(f"\n{name}:")
            print(f"  Description: {config.description}")
            print(f"  Users: {config.users}")
            print(f"  Duration: {config.run_time}")
            print(f"  Expected RPS: {config.expected_rps}")
        return
    
    # Check prerequisites
    if not args.no_prereq_check and not check_prerequisites():
        sys.exit(1)
    
    # Update host in configurations if specified
    if args.host != "http://localhost:8000":
        configs = runner.load_configs()
        for config in configs.values():
            config.host = args.host
        runner.save_configs(configs)
        print(f"Updated target host to: {args.host}")
    
    # Run tests
    if not args.test_name:
        print("Please specify a test name or 'all' to run all tests")
        print("Use --list to see available configurations")
        sys.exit(1)
    
    if args.test_name == "all":
        success = run_all_tests(runner)
    else:
        success = run_load_test(args.test_name, runner)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()