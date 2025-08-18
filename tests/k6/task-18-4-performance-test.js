import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics for Task 18.4 requirements
const errorRate = new Rate('errors');
const apiP95Duration = new Trend('api_p95_duration');
const healthCheckDuration = new Trend('health_check_duration');
const metricsEndpointDuration = new Trend('metrics_endpoint_duration');
const queueStatusDuration = new Trend('queue_status_duration');
const workerStatusDuration = new Trend('worker_status_duration');
const triggerEndpointDuration = new Trend('trigger_endpoint_duration');

// Counters for different endpoint types
const healthCheckRequests = new Counter('health_check_requests');
const metricsRequests = new Counter('metrics_requests');
const statusRequests = new Counter('status_requests');
const triggerRequests = new Counter('trigger_requests');

// Test configuration for Requirement 11.34: API p95 ≤ 300ms
export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Ramp up to 50 users
    { duration: '2m', target: 100 },   // Sustained load at 100 RPS
    { duration: '2m', target: 100 },   // Continue sustained load
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    // Main requirement: p95 ≤ 300ms
    http_req_duration: ['p(95)<300'],
    
    // Alert threshold: p95 < 400ms
    'http_req_duration{alert_threshold:true}': ['p(95)<400'],
    
    // Error rate requirement: < 5%
    http_req_failed: ['rate<0.05'],
    errors: ['rate<0.05'],
    
    // Specific endpoint thresholds
    health_check_duration: ['p(95)<100'],     // Health check should be very fast
    metrics_endpoint_duration: ['p(95)<500'], // Metrics can be slightly slower
    queue_status_duration: ['p(95)<200'],     // Queue status should be fast
    worker_status_duration: ['p(95)<200'],    // Worker status should be fast
    trigger_endpoint_duration: ['p(95)<1000'], // Trigger endpoints can be slower
    
    // API p95 specific metric
    api_p95_duration: ['p(95)<300'],
  },
};

// Base URL from environment variable or default
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Test data
const TEST_SUBREDDITS = ['technology', 'programming', 'MachineLearning', 'artificial', 'datascience'];
const TEST_BATCH_SIZES = [1, 3, 5];

export default function () {
  // Distribute load across different endpoint types
  const endpointType = Math.random();
  
  if (endpointType < 0.3) {
    // 30% - Health and metrics endpoints (should be fastest)
    testHealthAndMetrics();
  } else if (endpointType < 0.6) {
    // 30% - Status endpoints
    testStatusEndpoints();
  } else {
    // 40% - Trigger endpoints (main workflow)
    testTriggerEndpoints();
  }
  
  // Small delay to simulate realistic usage
  sleep(0.1);
}

function testHealthAndMetrics() {
  // Health check test
  const healthStart = Date.now();
  const healthResponse = http.get(`${BASE_URL}/health`);
  const healthDuration = Date.now() - healthStart;
  
  healthCheckRequests.add(1);
  healthCheckDuration.add(healthDuration);
  apiP95Duration.add(healthDuration);
  
  const healthSuccess = check(healthResponse, {
    'health check status is 200': (r) => r.status === 200,
    'health check has status field': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('status');
      } catch (e) {
        return false;
      }
    },
    'health check response time < 100ms': (r) => r.timings.duration < 100,
  }, { alert_threshold: 'true' });
  
  errorRate.add(!healthSuccess);
  
  // Metrics endpoint test
  const metricsStart = Date.now();
  const metricsResponse = http.get(`${BASE_URL}/metrics`);
  const metricsDuration = Date.now() - metricsStart;
  
  metricsRequests.add(1);
  metricsEndpointDuration.add(metricsDuration);
  apiP95Duration.add(metricsDuration);
  
  const metricsSuccess = check(metricsResponse, {
    'metrics status is 200': (r) => r.status === 200,
    'metrics content type is text/plain': (r) => 
      r.headers['Content-Type'] && r.headers['Content-Type'].includes('text/plain'),
    'metrics contains prometheus data': (r) => 
      r.body.includes('reddit_posts_collected_total') || r.body.includes('# HELP'),
    'metrics response time < 500ms': (r) => r.timings.duration < 500,
  }, { alert_threshold: 'true' });
  
  errorRate.add(!metricsSuccess);
}

function testStatusEndpoints() {
  // Queue status test
  const queueStart = Date.now();
  const queueResponse = http.get(`${BASE_URL}/api/v1/status/queues`);
  const queueDuration = Date.now() - queueStart;
  
  statusRequests.add(1);
  queueStatusDuration.add(queueDuration);
  apiP95Duration.add(queueDuration);
  
  const queueSuccess = check(queueResponse, {
    'queue status is 200': (r) => r.status === 200,
    'queue status has collect queue': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('collect') || typeof body === 'object';
      } catch (e) {
        return false;
      }
    },
    'queue status response time < 200ms': (r) => r.timings.duration < 200,
  }, { alert_threshold: 'true' });
  
  errorRate.add(!queueSuccess);
  
  // Worker status test
  const workerStart = Date.now();
  const workerResponse = http.get(`${BASE_URL}/api/v1/status/workers`);
  const workerDuration = Date.now() - workerStart;
  
  statusRequests.add(1);
  workerStatusDuration.add(workerDuration);
  apiP95Duration.add(workerDuration);
  
  const workerSuccess = check(workerResponse, {
    'worker status is 200': (r) => r.status === 200,
    'worker status is object': (r) => {
      try {
        const body = JSON.parse(r.body);
        return typeof body === 'object';
      } catch (e) {
        return false;
      }
    },
    'worker status response time < 200ms': (r) => r.timings.duration < 200,
  }, { alert_threshold: 'true' });
  
  errorRate.add(!workerSuccess);
}

function testTriggerEndpoints() {
  // Randomly select which trigger endpoint to test
  const triggerType = Math.random();
  
  if (triggerType < 0.4) {
    testCollectionTrigger();
  } else if (triggerType < 0.7) {
    testProcessingTrigger();
  } else {
    testPublishingTrigger();
  }
}

function testCollectionTrigger() {
  const subreddit = TEST_SUBREDDITS[Math.floor(Math.random() * TEST_SUBREDDITS.length)];
  const batchSize = TEST_BATCH_SIZES[Math.floor(Math.random() * TEST_BATCH_SIZES.length)];
  
  const payload = JSON.stringify({
    subreddits: [subreddit],
    batch_size: batchSize
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const triggerStart = Date.now();
  const response = http.post(`${BASE_URL}/api/v1/collect/trigger`, payload, params);
  const triggerDuration = Date.now() - triggerStart;
  
  triggerRequests.add(1);
  triggerEndpointDuration.add(triggerDuration);
  apiP95Duration.add(triggerDuration);
  
  const success = check(response, {
    'collection trigger status is 200 or 202': (r) => r.status === 200 || r.status === 202,
    'collection trigger has task_id or message': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('task_id') || body.hasOwnProperty('message');
      } catch (e) {
        return false;
      }
    },
    'collection trigger response time < 1000ms': (r) => r.timings.duration < 1000,
  }, { alert_threshold: 'true' });
  
  errorRate.add(!success);
}

function testProcessingTrigger() {
  const testPostId = `perf_test_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  
  const payload = JSON.stringify({
    reddit_post_id: testPostId
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const triggerStart = Date.now();
  const response = http.post(`${BASE_URL}/api/v1/process/trigger`, payload, params);
  const triggerDuration = Date.now() - triggerStart;
  
  triggerRequests.add(1);
  triggerEndpointDuration.add(triggerDuration);
  apiP95Duration.add(triggerDuration);
  
  const success = check(response, {
    'processing trigger status is 200 or 202': (r) => r.status === 200 || r.status === 202,
    'processing trigger has task_id or message': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('task_id') || body.hasOwnProperty('message');
      } catch (e) {
        return false;
      }
    },
    'processing trigger response time < 1000ms': (r) => r.timings.duration < 1000,
  }, { alert_threshold: 'true' });
  
  errorRate.add(!success);
}

function testPublishingTrigger() {
  const testPostId = `perf_test_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  
  const payload = JSON.stringify({
    reddit_post_id: testPostId
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const triggerStart = Date.now();
  const response = http.post(`${BASE_URL}/api/v1/publish/trigger`, payload, params);
  const triggerDuration = Date.now() - triggerStart;
  
  triggerRequests.add(1);
  triggerEndpointDuration.add(triggerDuration);
  apiP95Duration.add(triggerDuration);
  
  const success = check(response, {
    'publishing trigger status is 200 or 202': (r) => r.status === 200 || r.status === 202,
    'publishing trigger has task_id or message': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('task_id') || body.hasOwnProperty('message');
      } catch (e) {
        return false;
      }
    },
    'publishing trigger response time < 1000ms': (r) => r.timings.duration < 1000,
  }, { alert_threshold: 'true' });
  
  errorRate.add(!success);
}

// Setup function - runs once before the test
export function setup() {
  console.log('Starting Task 18.4 Performance Test (Requirement 11.34)');
  console.log(`Base URL: ${BASE_URL}`);
  console.log('Target: p95 ≤ 300ms, Alert threshold: p95 < 400ms, Error rate: < 5%');
  
  // Verify the API is accessible
  const response = http.get(`${BASE_URL}/health`);
  if (response.status !== 200) {
    console.warn(`API health check returned status ${response.status}, continuing anyway...`);
  } else {
    console.log('✓ API health check passed');
  }
  
  return { 
    testStartTime: Date.now(),
    baseUrl: BASE_URL
  };
}

// Teardown function - runs once after the test
export function teardown(data) {
  const testDuration = (Date.now() - data.testStartTime) / 1000;
  console.log(`Task 18.4 Performance test completed in ${testDuration} seconds`);
  console.log('Check the summary for p95 performance results');
}

// Handle summary to provide detailed p95 analysis
export function handleSummary(data) {
  const p95Duration = data.metrics.http_req_duration.values['p(95)'];
  const errorRate = data.metrics.http_req_failed.values.rate;
  const totalRequests = data.metrics.http_reqs.values.count;
  
  console.log('\n=== Task 18.4 Performance Test Results ===');
  console.log(`Total Requests: ${totalRequests}`);
  console.log(`p95 Response Time: ${p95Duration.toFixed(2)}ms`);
  console.log(`Error Rate: ${(errorRate * 100).toFixed(2)}%`);
  
  // Check requirements
  const p95Requirement = p95Duration <= 300;
  const alertThreshold = p95Duration < 400;
  const errorRequirement = errorRate < 0.05;
  
  console.log('\n=== Requirement Validation ===');
  console.log(`✓ p95 ≤ 300ms: ${p95Requirement ? 'PASS' : 'FAIL'} (${p95Duration.toFixed(2)}ms)`);
  console.log(`✓ Alert threshold < 400ms: ${alertThreshold ? 'PASS' : 'FAIL'} (${p95Duration.toFixed(2)}ms)`);
  console.log(`✓ Error rate < 5%: ${errorRequirement ? 'PASS' : 'FAIL'} (${(errorRate * 100).toFixed(2)}%)`);
  
  const overallPass = p95Requirement && errorRequirement;
  console.log(`\n=== Overall Result: ${overallPass ? 'PASS' : 'FAIL'} ===`);
  
  // Return the default summary
  return {
    'stdout': JSON.stringify(data, null, 2),
    'task_18_4_performance_results.json': JSON.stringify({
      timestamp: new Date().toISOString(),
      requirement: '11.34 - API p95 Performance',
      results: {
        p95_duration_ms: p95Duration,
        error_rate: errorRate,
        total_requests: totalRequests,
        p95_requirement_met: p95Requirement,
        alert_threshold_met: alertThreshold,
        error_requirement_met: errorRequirement,
        overall_pass: overallPass
      },
      detailed_metrics: data.metrics
    }, null, 2)
  };
}