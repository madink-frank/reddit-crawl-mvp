/**
 * Enhanced Network Utilities for Ghost Dashboard Integration
 * Provides robust error handling and retry logic for API calls
 */

class NetworkUtils {
    constructor() {
        this.defaultTimeout = 10000; // 10 seconds
        this.maxRetries = 3;
        this.retryDelay = 1000; // 1 second base delay
    }

    /**
     * Enhanced fetch with retry logic and error handling
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options
     * @param {number} retries - Number of retries remaining
     * @returns {Promise<Response>}
     */
    async fetchWithRetry(url, options = {}, retries = this.maxRetries) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.defaultTimeout);

        const enhancedOptions = {
            ...options,
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, enhancedOptions);
            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return response;
        } catch (error) {
            clearTimeout(timeoutId);

            if (retries > 0 && this.shouldRetry(error)) {
                console.warn(`Request failed, retrying... (${retries} attempts left)`, error.message);
                await this.delay(this.retryDelay * (this.maxRetries - retries + 1));
                return this.fetchWithRetry(url, options, retries - 1);
            }

            throw this.enhanceError(error, url);
        }
    }

    /**
     * Determine if an error should trigger a retry
     * @param {Error} error - The error to check
     * @returns {boolean}
     */
    shouldRetry(error) {
        // Retry on network errors, timeouts, and 5xx server errors
        return (
            error.name === 'AbortError' ||
            error.name === 'TypeError' ||
            error.message.includes('NetworkError') ||
            error.message.includes('Failed to fetch') ||
            error.message.includes('HTTP 5')
        );
    }

    /**
     * Enhance error with additional context
     * @param {Error} error - Original error
     * @param {string} url - Request URL
     * @returns {Error}
     */
    enhanceError(error, url) {
        const enhancedError = new Error();
        
        if (error.name === 'AbortError') {
            enhancedError.message = 'Request timeout - please check your connection';
            enhancedError.type = 'timeout';
        } else if (error.message.includes('Failed to fetch') || error.name === 'TypeError') {
            enhancedError.message = 'Network error - please check your internet connection';
            enhancedError.type = 'network';
        } else if (error.message.includes('HTTP 4')) {
            enhancedError.message = 'Client error - please check your request';
            enhancedError.type = 'client';
        } else if (error.message.includes('HTTP 5')) {
            enhancedError.message = 'Server error - please try again later';
            enhancedError.type = 'server';
        } else {
            enhancedError.message = error.message || 'Unknown error occurred';
            enhancedError.type = 'unknown';
        }

        enhancedError.originalError = error;
        enhancedError.url = url;
        return enhancedError;
    }

    /**
     * Delay execution for specified milliseconds
     * @param {number} ms - Milliseconds to delay
     * @returns {Promise<void>}
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Make a GET request with enhanced error handling
     * @param {string} url - API endpoint URL
     * @param {Object} headers - Additional headers
     * @returns {Promise<Object>}
     */
    async get(url, headers = {}) {
        const response = await this.fetchWithRetry(url, {
            method: 'GET',
            headers
        });
        return response.json();
    }

    /**
     * Make a POST request with enhanced error handling
     * @param {string} url - API endpoint URL
     * @param {Object} data - Request body data
     * @param {Object} headers - Additional headers
     * @returns {Promise<Object>}
     */
    async post(url, data = {}, headers = {}) {
        const response = await this.fetchWithRetry(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(data)
        });
        return response.json();
    }

    /**
     * Check if the API is reachable
     * @param {string} baseUrl - Base API URL
     * @returns {Promise<boolean>}
     */
    async checkConnectivity(baseUrl) {
        try {
            await this.get(`${baseUrl}/health`);
            return true;
        } catch (error) {
            console.warn('API connectivity check failed:', error.message);
            return false;
        }
    }

    /**
     * Get connection status with detailed information
     * @param {string} baseUrl - Base API URL
     * @returns {Promise<Object>}
     */
    async getConnectionStatus(baseUrl) {
        const startTime = Date.now();
        
        try {
            const response = await this.get(`${baseUrl}/health`);
            const responseTime = Date.now() - startTime;
            
            return {
                connected: true,
                responseTime,
                status: response.status || 'healthy',
                message: 'Connection successful'
            };
        } catch (error) {
            const responseTime = Date.now() - startTime;
            
            return {
                connected: false,
                responseTime,
                status: 'error',
                message: error.message,
                type: error.type,
                suggestions: this.getErrorSuggestions(error)
            };
        }
    }

    /**
     * Get user-friendly suggestions based on error type
     * @param {Error} error - The error object
     * @returns {Array<string>}
     */
    getErrorSuggestions(error) {
        switch (error.type) {
            case 'timeout':
                return [
                    'Check your internet connection',
                    'Try refreshing the page',
                    'The server might be busy - wait a moment and try again'
                ];
            case 'network':
                return [
                    'Check your internet connection',
                    'Verify the API server is running',
                    'Check if you\'re behind a firewall or proxy'
                ];
            case 'server':
                return [
                    'The server is experiencing issues',
                    'Try again in a few minutes',
                    'Contact support if the problem persists'
                ];
            case 'client':
                return [
                    'Check your request parameters',
                    'Verify your authentication credentials',
                    'Ensure you have the necessary permissions'
                ];
            default:
                return [
                    'Try refreshing the page',
                    'Check your internet connection',
                    'Contact support if the problem persists'
                ];
        }
    }
}

// Create global instance
window.networkUtils = new NetworkUtils();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NetworkUtils;
}