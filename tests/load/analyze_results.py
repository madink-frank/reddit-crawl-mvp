#!/usr/bin/env python3
"""
Load test results analyzer for GitHub Actions
"""

import sys
import csv
import json
from pathlib import Path
from typing import Dict, List, Any


def analyze_load_test_results(stats_file: str) -> Dict[str, Any]:
    """Analyze Locust load test results and generate summary"""
    
    results = {
        'summary': {},
        'endpoints': [],
        'performance_grade': 'F',
        'recommendations': []
    }
    
    try:
        with open(stats_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Find aggregated row (Type = "Aggregated")
        aggregated = next((row for row in rows if row['Type'] == 'Aggregated'), None)
        
        if not aggregated:
            results['error'] = 'No aggregated results found'
            return results
        
        # Extract key metrics
        total_requests = int(aggregated['Request Count'])
        failure_count = int(aggregated['Failure Count'])
        avg_response_time = float(aggregated['Average Response Time'])
        p95_response_time = float(aggregated['95%'])
        p99_response_time = float(aggregated['99%'])
        requests_per_second = float(aggregated['Requests/s'])
        
        # Calculate derived metrics
        success_rate = ((total_requests - failure_count) / total_requests) * 100
        error_rate = (failure_count / total_requests) * 100
        
        results['summary'] = {
            'total_requests': total_requests,
            'success_rate': round(success_rate, 2),
            'error_rate': round(error_rate, 2),
            'avg_response_time': round(avg_response_time, 2),
            'p95_response_time': round(p95_response_time, 2),
            'p99_response_time': round(p99_response_time, 2),
            'requests_per_second': round(requests_per_second, 2)
        }
        
        # Analyze individual endpoints
        for row in rows:
            if row['Type'] not in ['Request', 'GET', 'POST', 'PUT', 'DELETE']:
                continue
                
            endpoint_data = {
                'name': row['Name'],
                'method': row['Type'],
                'request_count': int(row['Request Count']),
                'failure_count': int(row['Failure Count']),
                'avg_response_time': float(row['Average Response Time']),
                'p95_response_time': float(row['95%']),
                'requests_per_second': float(row['Requests/s'])
            }
            
            endpoint_data['success_rate'] = (
                (endpoint_data['request_count'] - endpoint_data['failure_count']) 
                / endpoint_data['request_count'] * 100
            )
            
            results['endpoints'].append(endpoint_data)
        
        # Performance grading
        grade = calculate_performance_grade(
            success_rate, avg_response_time, p95_response_time, requests_per_second
        )
        results['performance_grade'] = grade
        
        # Generate recommendations
        recommendations = generate_recommendations(
            success_rate, avg_response_time, p95_response_time, error_rate
        )
        results['recommendations'] = recommendations
        
    except Exception as e:
        results['error'] = f'Error analyzing results: {str(e)}'
    
    return results


def calculate_performance_grade(
    success_rate: float, 
    avg_response_time: float, 
    p95_response_time: float, 
    rps: float
) -> str:
    """Calculate performance grade based on key metrics"""
    
    score = 0
    
    # Success rate scoring (40% weight)
    if success_rate >= 99.9:
        score += 40
    elif success_rate >= 99.5:
        score += 35
    elif success_rate >= 99.0:
        score += 30
    elif success_rate >= 95.0:
        score += 20
    else:
        score += 10
    
    # Average response time scoring (30% weight)
    if avg_response_time <= 100:
        score += 30
    elif avg_response_time <= 250:
        score += 25
    elif avg_response_time <= 500:
        score += 20
    elif avg_response_time <= 1000:
        score += 15
    else:
        score += 5
    
    # P95 response time scoring (20% weight)
    if p95_response_time <= 300:
        score += 20
    elif p95_response_time <= 500:
        score += 15
    elif p95_response_time <= 1000:
        score += 10
    else:
        score += 5
    
    # Throughput scoring (10% weight)
    if rps >= 100:
        score += 10
    elif rps >= 50:
        score += 8
    elif rps >= 25:
        score += 6
    else:
        score += 3
    
    # Convert score to grade
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'


def generate_recommendations(
    success_rate: float, 
    avg_response_time: float, 
    p95_response_time: float, 
    error_rate: float
) -> List[str]:
    """Generate performance improvement recommendations"""
    
    recommendations = []
    
    if success_rate < 99.0:
        recommendations.append(
            f"🔴 Success rate is {success_rate:.1f}%. Investigate error causes and improve error handling."
        )
    
    if avg_response_time > 250:
        recommendations.append(
            f"🟡 Average response time is {avg_response_time:.0f}ms. Consider optimizing database queries and caching."
        )
    
    if p95_response_time > 500:
        recommendations.append(
            f"🟡 95th percentile response time is {p95_response_time:.0f}ms. Look for performance bottlenecks."
        )
    
    if error_rate > 5.0:
        recommendations.append(
            f"🔴 Error rate is {error_rate:.1f}%. Review application logs and fix critical issues."
        )
    
    if avg_response_time > 1000:
        recommendations.append(
            "🔴 Response times are very high. Consider horizontal scaling or infrastructure upgrades."
        )
    
    if not recommendations:
        recommendations.append("✅ Performance looks good! No immediate action required.")
    
    return recommendations


def generate_markdown_report(results: Dict[str, Any]) -> str:
    """Generate markdown report for GitHub PR comments"""
    
    if 'error' in results:
        return f"❌ **Error analyzing load test results:** {results['error']}"
    
    summary = results['summary']
    grade = results['performance_grade']
    recommendations = results['recommendations']
    
    # Grade emoji
    grade_emoji = {
        'A': '🟢', 'B': '🟡', 'C': '🟠', 'D': '🔴', 'F': '🔴'
    }
    
    report = f"""
### Performance Grade: {grade_emoji.get(grade, '❓')} **{grade}**

#### Summary Metrics
| Metric | Value |
|--------|-------|
| Total Requests | {summary['total_requests']:,} |
| Success Rate | {summary['success_rate']}% |
| Error Rate | {summary['error_rate']}% |
| Avg Response Time | {summary['avg_response_time']}ms |
| 95th Percentile | {summary['p95_response_time']}ms |
| 99th Percentile | {summary['p99_response_time']}ms |
| Requests/Second | {summary['requests_per_second']} |

#### Recommendations
"""
    
    for rec in recommendations:
        report += f"- {rec}\n"
    
    # Add endpoint breakdown if available
    if results['endpoints']:
        report += "\n#### Endpoint Performance\n"
        report += "| Endpoint | Success Rate | Avg Response | P95 Response | RPS |\n"
        report += "|----------|--------------|--------------|--------------|-----|\n"
        
        for endpoint in results['endpoints'][:10]:  # Top 10 endpoints
            report += f"| {endpoint['name']} | {endpoint['success_rate']:.1f}% | {endpoint['avg_response_time']:.0f}ms | {endpoint['p95_response_time']:.0f}ms | {endpoint['requests_per_second']:.1f} |\n"
    
    return report


def main():
    """Main function for CLI usage"""
    
    if len(sys.argv) != 2:
        print("Usage: python analyze_results.py <stats_file.csv>")
        sys.exit(1)
    
    stats_file = sys.argv[1]
    
    if not Path(stats_file).exists():
        print(f"Error: File {stats_file} not found")
        sys.exit(1)
    
    # Analyze results
    results = analyze_load_test_results(stats_file)
    
    # Generate markdown report
    markdown_report = generate_markdown_report(results)
    
    # Save markdown report for GitHub Actions
    with open('load-test-analysis.md', 'w') as f:
        f.write(markdown_report)
    
    # Print summary to console
    print("Load Test Analysis Complete")
    print("=" * 50)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        sys.exit(1)
    
    summary = results['summary']
    print(f"Performance Grade: {results['performance_grade']}")
    print(f"Total Requests: {summary['total_requests']:,}")
    print(f"Success Rate: {summary['success_rate']}%")
    print(f"Average Response Time: {summary['avg_response_time']}ms")
    print(f"95th Percentile: {summary['p95_response_time']}ms")
    print(f"Requests/Second: {summary['requests_per_second']}")
    
    print("\nRecommendations:")
    for rec in results['recommendations']:
        print(f"  - {rec}")
    
    # Exit with error code if performance is poor
    if results['performance_grade'] in ['D', 'F']:
        print("\n❌ Performance grade is poor. Please address the issues above.")
        sys.exit(1)
    else:
        print("\n✅ Load test analysis completed successfully.")


if __name__ == '__main__':
    main()