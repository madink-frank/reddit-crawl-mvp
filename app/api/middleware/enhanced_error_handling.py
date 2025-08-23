"""
Enhanced Error Handling and User Experience Middleware
Provides improved error messages, user-friendly responses, and better error tracking
"""

import time
import json
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings
from app.monitoring.logging import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better classification"""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    INTERNAL = "internal"
    NETWORK = "network"
    TIMEOUT = "timeout"


class EnhancedErrorHandler:
    """Enhanced error handler with user-friendly messages"""
    
    def __init__(self):
        self.error_stats = {
            "total_errors": 0,
            "errors_by_category": {},
            "errors_by_severity": {},
            "recent_errors": []
        }
        
        # User-friendly error messages
        self.error_messages = {
            ErrorCategory.VALIDATION: {
                "title": "Invalid Input",
                "message": "The information you provided is not valid. Please check your input and try again.",
                "suggestions": [
                    "Verify all required fields are filled out",
                    "Check that data formats are correct (e.g., email addresses, dates)",
                    "Ensure numeric values are within acceptable ranges"
                ]
            },
            ErrorCategory.AUTHENTICATION: {
                "title": "Authentication Required",
                "message": "You need to be authenticated to access this resource.",
                "suggestions": [
                    "Check that your API key is valid and properly formatted",
                    "Ensure you're using the correct authentication method",
                    "Verify your credentials haven't expired"
                ]
            },
            ErrorCategory.AUTHORIZATION: {
                "title": "Access Denied",
                "message": "You don't have permission to access this resource.",
                "suggestions": [
                    "Contact your administrator to request access",
                    "Verify you're using the correct account",
                    "Check that your permissions are up to date"
                ]
            },
            ErrorCategory.NOT_FOUND: {
                "title": "Resource Not Found",
                "message": "The requested resource could not be found.",
                "suggestions": [
                    "Check that the URL or ID is correct",
                    "Verify the resource hasn't been deleted or moved",
                    "Try refreshing the page or searching again"
                ]
            },
            ErrorCategory.RATE_LIMIT: {
                "title": "Too Many Requests",
                "message": "You've made too many requests. Please wait before trying again.",
                "suggestions": [
                    "Wait a few minutes before making another request",
                    "Consider reducing the frequency of your requests",
                    "Contact support if you need higher rate limits"
                ]
            },
            ErrorCategory.EXTERNAL_SERVICE: {
                "title": "External Service Error",
                "message": "A required external service is currently unavailable.",
                "suggestions": [
                    "Try again in a few minutes",
                    "Check if the service is experiencing known issues",
                    "Contact support if the problem persists"
                ]
            },
            ErrorCategory.DATABASE: {
                "title": "Database Error",
                "message": "There was a problem accessing the database.",
                "suggestions": [
                    "Try your request again in a moment",
                    "Check if you're requesting too much data at once",
                    "Contact support if the issue continues"
                ]
            },
            ErrorCategory.NETWORK: {
                "title": "Network Error",
                "message": "There was a network connectivity issue.",
                "suggestions": [
                    "Check your internet connection",
                    "Try refreshing the page",
                    "Wait a moment and try again"
                ]
            },
            ErrorCategory.TIMEOUT: {
                "title": "Request Timeout",
                "message": "Your request took too long to process.",
                "suggestions": [
                    "Try breaking your request into smaller parts",
                    "Wait a moment and try again",
                    "Contact support if timeouts persist"
                ]
            },
            ErrorCategory.INTERNAL: {
                "title": "Internal Server Error",
                "message": "An unexpected error occurred on our end.",
                "suggestions": [
                    "Try your request again in a few minutes",
                    "Contact support if the problem persists",
                    "Include the error ID when contacting support"
                ]
            }
        }
    
    def categorize_error(self, error: Exception, status_code: int) -> ErrorCategory:
        """Categorize error based on type and status code"""
        if status_code == 400:
            return ErrorCategory.VALIDATION
        elif status_code == 401:
            return ErrorCategory.AUTHENTICATION
        elif status_code == 403:
            return ErrorCategory.AUTHORIZATION
        elif status_code == 404:
            return ErrorCategory.NOT_FOUND
        elif status_code == 429:
            return ErrorCategory.RATE_LIMIT
        elif status_code == 408:
            return ErrorCategory.TIMEOUT
        elif 500 <= status_code < 600:
            # Determine internal error type
            error_str = str(error).lower()
            if any(keyword in error_str for keyword in ["database", "sql", "connection"]):
                return ErrorCategory.DATABASE
            elif any(keyword in error_str for keyword in ["network", "connection", "timeout"]):
                return ErrorCategory.NETWORK
            elif any(keyword in error_str for keyword in ["external", "api", "service"]):
                return ErrorCategory.EXTERNAL_SERVICE
            else:
                return ErrorCategory.INTERNAL
        else:
            return ErrorCategory.INTERNAL
    
    def determine_severity(self, error: Exception, status_code: int, category: ErrorCategory) -> ErrorSeverity:
        """Determine error severity"""
        if status_code >= 500:
            if category in [ErrorCategory.DATABASE, ErrorCategory.EXTERNAL_SERVICE]:
                return ErrorSeverity.HIGH
            else:
                return ErrorSeverity.CRITICAL
        elif status_code in [401, 403]:
            return ErrorSeverity.MEDIUM
        elif status_code == 429:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def create_error_response(
        self, 
        error: Exception, 
        status_code: int, 
        request: Request,
        include_debug: bool = False
    ) -> Dict[str, Any]:
        """Create enhanced error response"""
        
        # Generate unique error ID
        error_id = f"err_{int(time.time())}_{hash(str(error))}"
        
        # Categorize error
        category = self.categorize_error(error, status_code)
        severity = self.determine_severity(error, status_code, category)
        
        # Get user-friendly message
        error_info = self.error_messages.get(category, self.error_messages[ErrorCategory.INTERNAL])
        
        # Create response
        response = {
            "error": {
                "id": error_id,
                "title": error_info["title"],
                "message": error_info["message"],
                "category": category.value,
                "severity": severity.value,
                "status_code": status_code,
                "timestamp": datetime.now().isoformat(),
                "suggestions": error_info["suggestions"]
            },
            "request": {
                "method": request.method,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent", "unknown")
            }
        }
        
        # Add debug information in development
        if include_debug or get_settings().debug:
            response["debug"] = {
                "original_error": str(error),
                "error_type": type(error).__name__,
                "traceback": traceback.format_exc() if include_debug else None
            }
        
        # Track error statistics
        self._track_error(category, severity, error_id, str(error))
        
        return response
    
    def _track_error(self, category: ErrorCategory, severity: ErrorSeverity, error_id: str, error_message: str) -> None:
        """Track error statistics"""
        self.error_stats["total_errors"] += 1
        
        # Track by category
        category_key = category.value
        if category_key not in self.error_stats["errors_by_category"]:
            self.error_stats["errors_by_category"][category_key] = 0
        self.error_stats["errors_by_category"][category_key] += 1
        
        # Track by severity
        severity_key = severity.value
        if severity_key not in self.error_stats["errors_by_severity"]:
            self.error_stats["errors_by_severity"][severity_key] = 0
        self.error_stats["errors_by_severity"][severity_key] += 1
        
        # Track recent errors (keep last 50)
        self.error_stats["recent_errors"].append({
            "id": error_id,
            "category": category.value,
            "severity": severity.value,
            "message": error_message[:200],  # Truncate long messages
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self.error_stats["recent_errors"]) > 50:
            self.error_stats["recent_errors"].pop(0)
        
        # Log high severity errors
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.error(
                f"High severity error: {error_id}",
                error_id=error_id,
                category=category.value,
                severity=severity.value,
                message=error_message
            )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return self.error_stats.copy()


class EnhancedErrorMiddleware(BaseHTTPMiddleware):
    """Enhanced error handling middleware"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.error_handler = EnhancedErrorHandler()
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as exc:
            # Handle FastAPI HTTP exceptions
            error_response = self.error_handler.create_error_response(
                exc, exc.status_code, request
            )
            
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response,
                headers={"X-Error-ID": error_response["error"]["id"]}
            )
            
        except Exception as exc:
            # Handle unexpected exceptions
            error_response = self.error_handler.create_error_response(
                exc, 500, request, include_debug=get_settings().debug
            )
            
            # Log the full error for debugging
            logger.error(
                f"Unhandled exception: {error_response['error']['id']}",
                error_id=error_response["error"]["id"],
                error_type=type(exc).__name__,
                error_message=str(exc),
                request_path=request.url.path,
                request_method=request.method,
                traceback=traceback.format_exc()
            )
            
            return JSONResponse(
                status_code=500,
                content=error_response,
                headers={"X-Error-ID": error_response["error"]["id"]}
            )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return self.error_handler.get_error_stats()


class UserExperienceEnhancer:
    """User experience enhancement utilities"""
    
    @staticmethod
    def create_success_response(
        data: Any,
        message: str = "Operation completed successfully",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create standardized success response"""
        response = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if metadata:
            response["metadata"] = metadata
        
        return response
    
    @staticmethod
    def create_paginated_response(
        items: List[Any],
        total: int,
        page: int,
        page_size: int,
        message: str = "Data retrieved successfully"
    ) -> Dict[str, Any]:
        """Create standardized paginated response"""
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "success": True,
            "message": message,
            "data": {
                "items": items,
                "pagination": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_items": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def create_progress_response(
        current: int,
        total: int,
        stage: str,
        message: str = "Operation in progress"
    ) -> Dict[str, Any]:
        """Create progress response for long-running operations"""
        progress_percent = (current / total * 100) if total > 0 else 0
        
        return {
            "success": True,
            "message": message,
            "data": {
                "progress": {
                    "current": current,
                    "total": total,
                    "percentage": round(progress_percent, 2),
                    "stage": stage,
                    "completed": current >= total
                }
            },
            "timestamp": datetime.now().isoformat()
        }


# Global error handler instance
enhanced_error_handler = EnhancedErrorHandler()


def get_error_statistics() -> Dict[str, Any]:
    """Get global error statistics"""
    return enhanced_error_handler.get_error_stats()


def setup_enhanced_error_handling(app) -> None:
    """Setup enhanced error handling"""
    logger.info("Setting up enhanced error handling...")
    
    # Add enhanced error middleware
    app.add_middleware(EnhancedErrorMiddleware)
    
    logger.info("Enhanced error handling enabled")