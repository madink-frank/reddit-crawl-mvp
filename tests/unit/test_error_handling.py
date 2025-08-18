"""
Unit tests for error handling
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.error_handling import (
    ServiceError,
    RetryableError,
    NonRetryableError,
    RateLimitError,
    AuthenticationError,
    QuotaExceededError,
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerConfig,
    Bulkhead,
    BulkheadConfig,
    ResilienceManager,
    ErrorContext,
    ErrorSeverity,
    ServiceType
)


class TestCustomExceptions:
    """Test custom exception classes"""
    
    def test_service_error(self):
        """Test base ServiceError"""
        error = ServiceError("Service error message", ServiceType.REDDIT, ErrorSeverity.HIGH)
        
        assert str(error) == "Service error message"
        assert error.service == ServiceType.REDDIT
        assert error.severity == ErrorSeverity.HIGH
    
    def test_retryable_error(self):
        """Test RetryableError"""
        error = RetryableError("Temporary service unavailable", ServiceType.REDDIT)
        
        assert str(error) == "Temporary service unavailable"
        assert error.service == ServiceType.REDDIT
        assert isinstance(error, ServiceError)
    
    def test_non_retryable_error(self):
        """Test NonRetryableError"""
        error = NonRetryableError("Invalid API key", ServiceType.REDDIT)
        
        assert str(error) == "Invalid API key"
        assert error.service == ServiceType.REDDIT
        assert isinstance(error, ServiceError)
    
    def test_rate_limit_error(self):
        """Test RateLimitError"""
        error = RateLimitError(ServiceType.REDDIT, retry_after=60)
        
        assert error.service == ServiceType.REDDIT
        assert error.retry_after == 60
        assert isinstance(error, RetryableError)
    
    def test_authentication_error(self):
        """Test AuthenticationError"""
        error = AuthenticationError(ServiceType.REDDIT)
        
        assert error.service == ServiceType.REDDIT
        assert isinstance(error, NonRetryableError)
    
    def test_quota_exceeded_error(self):
        """Test QuotaExceededError"""
        error = QuotaExceededError(ServiceType.REDDIT, "daily_requests")
        
        assert error.service == ServiceType.REDDIT
        assert error.quota_type == "daily_requests"
        assert isinstance(error, NonRetryableError)


class TestCircuitBreaker:
    """Test CircuitBreaker functionality"""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create circuit breaker instance"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60,
            expected_exception=Exception
        )
        return CircuitBreaker("test_service", config)
    
    def test_circuit_breaker_initial_state(self, circuit_breaker):
        """Test circuit breaker initial state"""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_failure_time is None
    
    def test_circuit_breaker_success(self, circuit_breaker):
        """Test circuit breaker with successful calls"""
        def successful_function():
            return "success"
        
        result = circuit_breaker.call(successful_function)
        
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    def test_circuit_breaker_failure_threshold(self, circuit_breaker):
        """Test circuit breaker opening after failure threshold"""
        def failing_function():
            raise Exception("Service unavailable")
        
        # First two failures should keep circuit closed
        for i in range(2):
            with pytest.raises(Exception):
                circuit_breaker.call(failing_function)
            assert circuit_breaker.state == CircuitBreakerState.CLOSED
            assert circuit_breaker.failure_count == i + 1
        
        # Third failure should open the circuit
        with pytest.raises(Exception):
            circuit_breaker.call(failing_function)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3
    
    def test_circuit_breaker_open_state(self, circuit_breaker):
        """Test circuit breaker in open state"""
        # Force circuit to open state
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.failure_count = 3
        circuit_breaker.last_failure_time = datetime.utcnow()
        
        def any_function():
            return "should not be called"
        
        with pytest.raises(CircuitBreakerError):
            circuit_breaker.call(any_function)
    
    def test_circuit_breaker_half_open_state(self, circuit_breaker):
        """Test circuit breaker in half-open state"""
        # Force circuit to half-open state
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.failure_count = 3
        circuit_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=120)
        
        def successful_function():
            return "success"
        
        result = circuit_breaker.call(successful_function)
        
        assert result == "success"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    def test_circuit_breaker_recovery_timeout(self, circuit_breaker):
        """Test circuit breaker recovery after timeout"""
        # Force circuit to open state with old failure time
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.failure_count = 3
        circuit_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=120)
        
        def test_function():
            return "test"
        
        # Should transition to half-open and allow the call
        result = circuit_breaker.call(test_function)
        
        assert result == "test"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
    
    def test_circuit_breaker_reset(self, circuit_breaker):
        """Test circuit breaker reset"""
        # Set some failure state
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.failure_count = 5
        circuit_breaker.last_failure_time = datetime.utcnow()
        
        circuit_breaker.reset()
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_failure_time is None
    
    def test_circuit_breaker_specific_exception(self):
        """Test circuit breaker with specific exception type"""
        circuit_breaker = CircuitBreaker(
            name="specific_test",
            failure_threshold=2,
            recovery_timeout=60,
            expected_exception=ValueError
        )
        
        def function_with_value_error():
            raise ValueError("Specific error")
        
        def function_with_other_error():
            raise RuntimeError("Other error")
        
        # ValueError should count towards failure threshold
        with pytest.raises(ValueError):
            circuit_breaker.call(function_with_value_error)
        assert circuit_breaker.failure_count == 1
        
        # RuntimeError should not count towards failure threshold
        with pytest.raises(RuntimeError):
            circuit_breaker.call(function_with_other_error)
        assert circuit_breaker.failure_count == 1  # Should remain 1


class TestErrorContext:
    """Test ErrorContext class"""
    
    def test_error_context_creation(self):
        """Test creating error context"""
        context = ErrorContext(
            operation="reddit_api_call",
            service="reddit",
            user_id="user_123",
            request_id="req_456",
            additional_data={"subreddit": "technology"}
        )
        
        assert context.operation == "reddit_api_call"
        assert context.service == "reddit"
        assert context.user_id == "user_123"
        assert context.request_id == "req_456"
        assert context.additional_data == {"subreddit": "technology"}
    
    def test_error_context_to_dict(self):
        """Test converting error context to dictionary"""
        context = ErrorContext(
            operation="test_operation",
            service="test_service",
            user_id="test_user"
        )
        
        result = context.to_dict()
        
        assert result["operation"] == "test_operation"
        assert result["service"] == "test_service"
        assert result["user_id"] == "test_user"
        assert "timestamp" in result


class TestErrorHandler:
    """Test ErrorHandler class"""
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler instance"""
        return ErrorHandler()
    
    def test_error_handler_handle_error(self, error_handler):
        """Test error handler handling errors"""
        error = RedditAPIError("Test error", error_code="TEST_001")
        context = ErrorContext(operation="test_op", service="test_service")
        
        with patch('app.error_handling.logger') as mock_logger:
            result = error_handler.handle_error(error, context)
            
            assert result["error_code"] == "TEST_001"
            assert result["message"] == "Test error"
            assert result["severity"] == ErrorSeverity.MEDIUM.value
            assert "timestamp" in result
            assert "context" in result
            
            mock_logger.error.assert_called_once()
    
    def test_error_handler_should_retry(self, error_handler):
        """Test error handler retry logic"""
        retryable_error = RetryableError("Temporary error", max_retries=3)
        non_retryable_error = NonRetryableError("Permanent error")
        
        assert error_handler.should_retry(retryable_error, attempt=1) is True
        assert error_handler.should_retry(retryable_error, attempt=4) is False
        assert error_handler.should_retry(non_retryable_error, attempt=1) is False
    
    def test_error_handler_calculate_backoff(self, error_handler):
        """Test error handler backoff calculation"""
        error = RetryableError("Test error", backoff_factor=2.0)
        
        backoff_1 = error_handler.calculate_backoff(error, attempt=1)
        backoff_2 = error_handler.calculate_backoff(error, attempt=2)
        backoff_3 = error_handler.calculate_backoff(error, attempt=3)
        
        assert backoff_1 == 2.0  # 2^1 * 1
        assert backoff_2 == 4.0  # 2^2 * 1
        assert backoff_3 == 8.0  # 2^3 * 1
    
    def test_error_handler_get_error_metrics(self, error_handler):
        """Test error handler metrics collection"""
        # Simulate some errors
        error1 = RedditAPIError("Error 1", error_code="REDDIT_001")
        error2 = OpenAIError("Error 2", error_code="OPENAI_001")
        error3 = RedditAPIError("Error 3", error_code="REDDIT_001")
        
        context = ErrorContext(operation="test", service="test")
        
        error_handler.handle_error(error1, context)
        error_handler.handle_error(error2, context)
        error_handler.handle_error(error3, context)
        
        metrics = error_handler.get_error_metrics()
        
        assert metrics["total_errors"] == 3
        assert metrics["error_counts"]["REDDIT_001"] == 2
        assert metrics["error_counts"]["OPENAI_001"] == 1


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_error_response(self):
        """Test create_error_response function"""
        error = RedditAPIError(
            "Test error",
            error_code="TEST_001",
            context={"key": "value"}
        )
        
        response = create_error_response(error)
        
        assert response["error_code"] == "TEST_001"
        assert response["message"] == "Test error"
        assert response["severity"] == ErrorSeverity.MEDIUM.value
        assert "timestamp" in response
        assert response["context"] == {"key": "value"}
    
    def test_log_error(self):
        """Test log_error function"""
        error = OpenAIError("Test logging error", error_code="LOG_001")
        context = ErrorContext(operation="test_log", service="test")
        
        with patch('app.error_handling.logger') as mock_logger:
            log_error(error, context)
            
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Test logging error" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_api_error_decorator(self):
        """Test handle_api_error decorator"""
        @handle_api_error(service="test_service")
        async def test_function():
            raise RedditAPIError("API Error", error_code="API_001")
        
        with patch('app.error_handling.logger') as mock_logger:
            with pytest.raises(RedditAPIError):
                await test_function()
            
            mock_logger.error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_api_error_decorator_success(self):
        """Test handle_api_error decorator with successful function"""
        @handle_api_error(service="test_service")
        async def test_function():
            return "success"
        
        result = await test_function()
        assert result == "success"
    
    def test_error_severity_enum(self):
        """Test ErrorSeverity enum"""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"
    
    def test_circuit_breaker_state_enum(self):
        """Test CircuitBreakerState enum"""
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"


class TestErrorHandlingIntegration:
    """Test error handling integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_error_flow(self):
        """Test complete error handling flow"""
        circuit_breaker = CircuitBreaker(
            name="integration_test",
            failure_threshold=2,
            recovery_timeout=60
        )
        
        error_handler = ErrorHandler()
        
        def failing_service():
            raise RedditAPIError("Service unavailable", error_code="INTEGRATION_001")
        
        context = ErrorContext(
            operation="integration_test",
            service="reddit_api",
            user_id="test_user"
        )
        
        # First failure
        with pytest.raises(RedditAPIError) as exc_info:
            circuit_breaker.call(failing_service)
        
        error_response = error_handler.handle_error(exc_info.value, context)
        assert error_response["error_code"] == "INTEGRATION_001"
        assert circuit_breaker.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(RedditAPIError):
            circuit_breaker.call(failing_service)
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Third call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            circuit_breaker.call(failing_service)
    
    def test_error_context_propagation(self):
        """Test error context propagation through error handling"""
        original_context = {
            "user_id": "user_123",
            "request_id": "req_456",
            "operation": "reddit_collection"
        }
        
        error = RedditAPIError(
            "Context propagation test",
            error_code="CONTEXT_001",
            context=original_context
        )
        
        response = create_error_response(error)
        
        assert response["context"] == original_context
        assert response["error_code"] == "CONTEXT_001"
    
    def test_multiple_error_types_handling(self):
        """Test handling multiple error types"""
        error_handler = ErrorHandler()
        context = ErrorContext(operation="multi_test", service="test")
        
        errors = [
            RedditAPIError("Reddit error", error_code="REDDIT_001"),
            OpenAIError("OpenAI error", error_code="OPENAI_001"),
            GhostCMSError("Ghost error", error_code="GHOST_001"),
            DatabaseError("DB error", error_code="DB_001"),
            VaultError("Vault error", error_code="VAULT_001")
        ]
        
        responses = []
        for error in errors:
            response = error_handler.handle_error(error, context)
            responses.append(response)
        
        # Verify all errors were handled
        assert len(responses) == 5
        error_codes = [r["error_code"] for r in responses]
        assert "REDDIT_001" in error_codes
        assert "OPENAI_001" in error_codes
        assert "GHOST_001" in error_codes
        assert "DB_001" in error_codes
        assert "VAULT_001" in error_codes


if __name__ == "__main__":
    pytest.main([__file__])