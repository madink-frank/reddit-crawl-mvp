import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiResponseTime = new Trend('api_response_time');

// Load test configuration
export const options = {
  stages: [
    { duration: '1m', target: 10 },  // Ramp up to 10 users
    { duration: '3m', target: 50 },  // Ramp up to 50 users
    { duration: '5m', target: 100 }, // Ramp up to 100 users (target load)
    { duration: '5m', target: 100 }, // Stay at 100 users
    { duration: '2m', target: 0 },   // Ramp down to 0 users
  ],
  
  thresholds: {
    // Performance requirements
    http_req_duration: ['p(95)<300'],     // 95% of requests under 300ms
    http_req_failed: ['rate<0.05'],       // Less than 5% failures
    errors: ['rate<0.05'],                // Less than 5% custom errors
    api_response_time: ['p(95)<300'],     // API response time under 300ms
    
    // Throughput requirements
    http_reqs: ['rate>100'],              // At least 100 requests per second
  },
};

// Base URL from environment variable or default
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Weighted endpoint selection for realistic load distribution
const ENDPOINTS = [
  { path: '/health', weight: 30, method: 'GET' },
  { path: '/metrics', weight: 20, method: 'GET' },
  { path: '/api/v1/status/queues', weight: 25, method: 'GET' },
  { path: '/api/v1/status/workers', weight: 15, method: 'GET' },
  { path: '/api/v1/collect/trigger', weight: 5, method: 'POST' },
  { path: '/api/v1/process/trigger', weight: 3, method: 'POST' },
  { path: '/api/v1/publish/trigger', weight: 2, method: 'POST' },
];

// Create weighted endpoint selector
function selectEndpoint() {
  const totalWeight = ENDPOINTS.reduce((sum, ep) => sum + ep.weight, 0);
  let random = Math.random() * totalWeight;
  
  for (const endpoint of ENDPOINTS) {
    random -= endpoint.weight;
    if (random <= 0) {
      return endpoint;
    }
  }
  
  return ENDPOINTS[0]; // Fallback
}

export default function () {
  const endpoint = selectEndpoint();
  let response;
  
  switch (endpoint.method) {
    case 'GET':
      response = testGetEndpoint(endpoint.path);
      break;
    case 'POST':
      response = testPostEndpoint(endpoint.path);
      break;
    default:
      console.error(`Unsupported method: ${endpoint.method}`);
      return;
  }
  
  // Record metrics
  if (response) {
    apiResponseTime.add(response.timings.duration);
    errorRate.add(response.status >= 400);
  }
  
  // Small delay to simulate realistic user behavior
  sleep(Math.random() * 2 + 0.5); // 0.5-2.5 seconds
}

function testGetEndpoint(path) {
  const response = http.get(`${BASE_URL}${path}`);
  
  const success = check(response, {
    [`${path} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
    [`${path} response time < 500ms`]: (r) => r.timings.duration < 500,
  });
  
  if (!success) {
    console.error(`GET ${path} failed with status ${response.status}`);
  }
  
  return response;
}

function testPostEndpoint(path) {
  let payload = '';
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  // Generate appropriate payload based on endpoint
  switch (path) {
    case '/api/v1/collect/trigger':
      payload = JSON.stringify({
        subreddits: ['technology'],
        batch_size: 5
      });
      break;
    case '/api/v1/process/trigger':
      payload = JSON.stringify({
        reddit_post_id: `load_test_${Date.now()}`
      });
      break;
    case '/api/v1/publish/trigger':
      payload = JSON.stringify({
        reddit_post_id: `load_test_${Date.now()}`
      });
      break;
    default:
      payload = '{}';
  }
  
  const response = http.post(`${BASE_URL}${path}`, payload, params);
  
  const success = check(response, {
    [`${path} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
    [`${path} response time < 1000ms`]: (r) => r.timings.duration < 1000,
    [`${path} has response body`]: (r) => r.body && r.body.length > 0,
  });
  
  if (!success) {
    console.error(`POST ${path} failed with status ${response.status}`);
  }
  
  return response;
}

export function setup() {
  console.log('Starting Load Test');
  console.log(`Base URL: ${BASE_URL}`);
  console.log('Target: 100 concurrent users for 5 minutes');
  
  // Verify the API is accessible
  const response = http.get(`${BASE_URL}/health`);
  if (response.status !== 200) {
    throw new Error(`API health check failed with status ${response.status}`);
  }
  
  console.log('API health check passed - starting load test');
  return { testStartTime: Date.now() };
}

export function teardown(data) {
  const testDuration = (Date.now() - data.testStartTime) / 1000;
  console.log(`Load test completed in ${testDuration} seconds`);
  
  // Log final summary
  console.log('Load test summary:');
  console.log('- Target: 100 concurrent users');
  console.log('- Duration: 16 minutes total');
  console.log('- Thresholds: p95 < 300ms, error rate < 5%');
}