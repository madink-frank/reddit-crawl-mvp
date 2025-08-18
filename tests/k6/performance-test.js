import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const healthCheckDuration = new Trend('health_check_duration');
const apiResponseTime = new Trend('api_response_time');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 }, // Ramp up to 10 users over 2 minutes
    { duration: '5m', target: 10 }, // Stay at 10 users for 5 minutes
    { duration: '2m', target: 20 }, // Ramp up to 20 users over 2 minutes
    { duration: '5m', target: 20 }, // Stay at 20 users for 5 minutes
    { duration: '2m', target: 0 },  // Ramp down to 0 users over 2 minutes
  ],
  thresholds: {
    // Performance requirements from the spec
    http_req_duration: ['p(95)<300'], // 95% of requests must be below 300ms
    http_req_failed: ['rate<0.05'],   // Error rate must be below 5%
    errors: ['rate<0.05'],            // Custom error rate must be below 5%
    
    // Custom thresholds for specific endpoints
    health_check_duration: ['p(95)<100'], // Health check should be very fast
    api_response_time: ['p(95)<300'],     // API endpoints should meet the 300ms target
  },
};

// Base URL from environment variable or default
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Test data
const TEST_SUBREDDITS = ['technology', 'programming', 'MachineLearning'];
const TEST_REDDIT_POST_ID = `perf_test_${Date.now()}`;

export default function () {
  // Test 1: Health Check (should be very fast)
  testHealthCheck();
  
  // Test 2: Metrics endpoint
  testMetricsEndpoint();
  
  // Test 3: Queue status
  testQueueStatus();
  
  // Test 4: Worker status
  testWorkerStatus();
  
  // Test 5: Collection trigger (main workflow)
  testCollectionTrigger();
  
  // Test 6: Processing trigger
  testProcessingTrigger();
  
  // Test 7: Publishing trigger
  testPublishingTrigger();
  
  // Small delay between iterations
  sleep(1);
}

function testHealthCheck() {
  const response = http.get(`${BASE_URL}/health`);
  
  const success = check(response, {
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
  });
  
  healthCheckDuration.add(response.timings.duration);
  errorRate.add(!success);
}

function testMetricsEndpoint() {
  const response = http.get(`${BASE_URL}/metrics`);
  
  const success = check(response, {
    'metrics status is 200': (r) => r.status === 200,
    'metrics content type is text/plain': (r) => r.headers['Content-Type'].includes('text/plain'),
    'metrics contains prometheus data': (r) => r.body.includes('reddit_posts_collected_total'),
    'metrics response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  apiResponseTime.add(response.timings.duration);
  errorRate.add(!success);
}

function testQueueStatus() {
  const response = http.get(`${BASE_URL}/api/v1/status/queues`);
  
  const success = check(response, {
    'queue status is 200': (r) => r.status === 200,
    'queue status has collect queue': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('collect');
      } catch (e) {
        return false;
      }
    },
    'queue status response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  apiResponseTime.add(response.timings.duration);
  errorRate.add(!success);
}

function testWorkerStatus() {
  const response = http.get(`${BASE_URL}/api/v1/status/workers`);
  
  const success = check(response, {
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
  });
  
  apiResponseTime.add(response.timings.duration);
  errorRate.add(!success);
}

function testCollectionTrigger() {
  const payload = JSON.stringify({
    subreddits: [TEST_SUBREDDITS[Math.floor(Math.random() * TEST_SUBREDDITS.length)]],
    batch_size: 5
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const response = http.post(`${BASE_URL}/api/v1/collect/trigger`, payload, params);
  
  const success = check(response, {
    'collection trigger status is 200': (r) => r.status === 200,
    'collection trigger has task_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('task_id');
      } catch (e) {
        return false;
      }
    },
    'collection trigger response time < 1000ms': (r) => r.timings.duration < 1000,
  });
  
  apiResponseTime.add(response.timings.duration);
  errorRate.add(!success);
}

function testProcessingTrigger() {
  const payload = JSON.stringify({
    reddit_post_id: TEST_REDDIT_POST_ID
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const response = http.post(`${BASE_URL}/api/v1/process/trigger`, payload, params);
  
  const success = check(response, {
    'processing trigger status is 200': (r) => r.status === 200,
    'processing trigger has task_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('task_id');
      } catch (e) {
        return false;
      }
    },
    'processing trigger response time < 1000ms': (r) => r.timings.duration < 1000,
  });
  
  apiResponseTime.add(response.timings.duration);
  errorRate.add(!success);
}

function testPublishingTrigger() {
  const payload = JSON.stringify({
    reddit_post_id: TEST_REDDIT_POST_ID
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  const response = http.post(`${BASE_URL}/api/v1/publish/trigger`, payload, params);
  
  const success = check(response, {
    'publishing trigger status is 200': (r) => r.status === 200,
    'publishing trigger has task_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.hasOwnProperty('task_id');
      } catch (e) {
        return false;
      }
    },
    'publishing trigger response time < 1000ms': (r) => r.timings.duration < 1000,
  });
  
  apiResponseTime.add(response.timings.duration);
  errorRate.add(!success);
}

// Setup function - runs once before the test
export function setup() {
  console.log('Starting Reddit Ghost Publisher Performance Test');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Test Reddit Post ID: ${TEST_REDDIT_POST_ID}`);
  
  // Verify the API is accessible
  const response = http.get(`${BASE_URL}/health`);
  if (response.status !== 200) {
    throw new Error(`API health check failed with status ${response.status}`);
  }
  
  return { testStartTime: Date.now() };
}

// Teardown function - runs once after the test
export function teardown(data) {
  const testDuration = (Date.now() - data.testStartTime) / 1000;
  console.log(`Performance test completed in ${testDuration} seconds`);
}