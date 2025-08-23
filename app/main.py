"""
FastAPI Gateway Application - MVP Version
Main entry point for the Reddit Ghost Publisher API
"""
import time
from contextlib import asynccontextmanager
from typing import Dict, Any
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.monitoring.logging import configure_logging, get_logger
from app.monitoring.enhanced_logging import setup_enhanced_logging, get_enhanced_logger
from app.api.middleware.security_mvp import (
    SecurityHeadersMiddleware,
    InputValidationMiddleware,
    EnvironmentAuthMiddleware,
    setup_cors_middleware
)
from app.api.middleware.performance_optimization import setup_production_optimizations
from app.api.middleware.enhanced_error_handling import setup_enhanced_error_handling

# Configure enhanced logging system
configure_logging()
setup_enhanced_logging()
logger = get_enhanced_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced logging middleware with structured logging and PII masking"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Log incoming request
        safe_headers = {
            k: v for k, v in request.headers.items() 
            if k.lower() not in ['authorization', 'cookie', 'x-api-key']
        }
        
        logger.info(
            f"Incoming request: {method} {path}",
            method=method,
            path=path,
            query_params=dict(request.query_params),
            headers=safe_headers,
            remote_addr=request.client.host if request.client else "unknown"
        )
        
        try:
            response = await call_next(request)
            
            # Log response
            duration = time.time() - start_time
            logger.info(
                f"Request completed: {method} {path}",
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2)
            )
            
            return response
            
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {method} {path}",
                method=method,
                path=path,
                error_type=type(exc).__name__,
                error_message=str(exc),
                duration_ms=round(duration * 1000, 2)
            )
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events - MVP version"""
    settings = get_settings()
    
    # Startup
    logger.info(
        "Starting Reddit Ghost Publisher API - MVP",
        app_name=settings.app_name,
        environment=settings.environment,
        debug=settings.debug,
        version="1.0.0"
    )
    
    # Test basic dependencies
    try:
        # Test database connection
        from app.infrastructure import get_database
        from sqlalchemy import text
        
        database = get_database()
        with database.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
        
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        # Don't raise in MVP - allow startup even if DB is temporarily unavailable
    
    try:
        # Test Redis connection
        from app.infrastructure import get_redis_client
        
        redis_client = get_redis_client()
        await redis_client.ping()
        logger.info("Redis connection verified")
        
    except Exception as e:
        logger.error("Failed to initialize Redis", error=str(e))
        # Don't raise in MVP - allow startup even if Redis is temporarily unavailable
    
    yield
    
    # Shutdown
    logger.info("Shutting down Reddit Ghost Publisher API")
    
    # Basic cleanup
    try:
        from app.infrastructure import close_database, close_redis
        close_database()
        await close_redis()
        logger.info("Connections closed")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))


def create_app() -> FastAPI:
    """Create and configure FastAPI application - MVP version"""
    settings = get_settings()
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        description="Automated Reddit content collection, AI processing, and Ghost CMS publishing - MVP",
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None
    )
    
    # Add basic middleware (simplified for MVP)
    
    # 1. Logging middleware (outermost)
    app.add_middleware(LoggingMiddleware)
    
    # 2. Performance monitoring
    from app.api.middleware.performance_monitoring import APIPerformanceMiddleware
    app.add_middleware(APIPerformanceMiddleware, slow_request_threshold_ms=300.0)
    
    # 3. Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 4. Input validation
    app.add_middleware(InputValidationMiddleware, max_request_size=10 * 1024 * 1024)
    
    # 5. Environment-based authentication
    app.add_middleware(EnvironmentAuthMiddleware, protected_paths=["/api/v1/"])
    
    # 6. CORS middleware (innermost)
    setup_cors_middleware(app)
    
    # Setup production optimizations
    setup_production_optimizations(app)
    setup_enhanced_error_handling(app)
    
    # Include MVP routers
    from app.api.routes import (
        health_mvp, triggers_mvp, status_mvp, metrics_mvp, takedown_mvp, 
        monitoring, manual_scaling, performance, dashboard, realtime_monitoring
    )
    
    app.include_router(health_mvp.router, tags=["Health"])
    app.include_router(triggers_mvp.router, prefix="/api/v1", tags=["Triggers"])
    app.include_router(status_mvp.router, prefix="/api/v1", tags=["Status"])
    app.include_router(metrics_mvp.router, tags=["Metrics"])
    app.include_router(takedown_mvp.router, prefix="/api/v1", tags=["Takedown"])
    app.include_router(monitoring.router, prefix="/api/v1", tags=["Monitoring"])
    app.include_router(manual_scaling.router, prefix="/api/v1", tags=["Manual Scaling"])
    app.include_router(performance.router, prefix="/api/v1", tags=["Performance"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
    app.include_router(realtime_monitoring.router, prefix="/dashboard", tags=["Real-time Monitoring"])
    
    return app


# Global exception handlers - MVP version
def setup_exception_handlers(app: FastAPI):
    """Setup basic exception handlers with PII masking"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        logger.warning(
            f"HTTP exception: {exc.status_code}",
            status_code=exc.status_code,
            detail=str(exc.detail),
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": str(exc.detail),
                "status_code": exc.status_code,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle validation errors"""
        logger.error(
            "Validation error",
            error=str(exc),
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation failed",
                "detail": str(exc),
                "status_code": 422,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions"""
        logger.error(
            "Unhandled exception",
            error_type=type(exc).__name__,
            error=str(exc),
            path=request.url.path,
            method=request.method
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "status_code": 500,
                "timestamp": datetime.utcnow().isoformat(),
                "path": request.url.path
            }
        )


# Create app instance
app = create_app()
setup_exception_handlers(app)


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        workers=1 if settings.debug else settings.api_workers
    )