"""
Infrastructure initialization and management
"""
import asyncio
import logging
from typing import Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
import redis.asyncio as redis

from app.config import get_settings, get_database_url, get_redis_url

logger = logging.getLogger(__name__)

# Global instances
_database_engine: Engine = None
_session_factory: sessionmaker = None
_async_database_engine: AsyncEngine = None
_async_session_factory: async_sessionmaker = None
_redis_client: redis.Redis = None


def get_database() -> Engine:
    """Get database engine instance"""
    global _database_engine
    
    if _database_engine is None:
        database_url = get_database_url()
        settings = get_settings()
        
        _database_engine = create_engine(
            database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            echo=settings.debug
        )
        
        logger.info("Database engine created", url=database_url.split('@')[-1] if '@' in database_url else database_url)
    
    return _database_engine


def get_async_database() -> AsyncEngine:
    """Get async database engine instance"""
    global _async_database_engine
    
    if _async_database_engine is None:
        database_url = get_database_url()
        settings = get_settings()
        
        # Convert sync URL to async URL
        if database_url.startswith("sqlite:"):
            async_database_url = database_url.replace("sqlite:", "sqlite+aiosqlite:")
        elif database_url.startswith("postgresql:"):
            async_database_url = database_url.replace("postgresql:", "postgresql+asyncpg:")
        else:
            async_database_url = database_url
        
        _async_database_engine = create_async_engine(
            async_database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            echo=settings.debug
        )
        
        logger.info("Async database engine created")
    
    return _async_database_engine


def get_session_factory() -> sessionmaker:
    """Get synchronous session factory"""
    global _session_factory
    
    if _session_factory is None:
        engine = get_database()
        _session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=False
        )
    
    return _session_factory


def get_database_session() -> Session:
    """Get synchronous database session"""
    session_factory = get_session_factory()
    return session_factory()


def get_async_session_factory() -> async_sessionmaker:
    """Get async session factory"""
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_async_database()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    return _async_session_factory


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session context manager"""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_redis_client() -> redis.Redis:
    """Get Redis client instance"""
    global _redis_client
    
    if _redis_client is None:
        redis_url = get_redis_url()
        settings = get_settings()
        
        _redis_client = redis.from_url(
            redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True
        )
        
        logger.info("Redis client created", url=redis_url.split('@')[-1] if '@' in redis_url else redis_url)
    
    return _redis_client


def close_database():
    """Close database connections"""
    global _database_engine, _session_factory
    
    if _database_engine is not None:
        _database_engine.dispose()
        _database_engine = None
        _session_factory = None
        logger.info("Database connections closed")


async def close_async_database():
    """Close async database connections"""
    global _async_database_engine, _async_session_factory
    
    if _async_database_engine is not None:
        await _async_database_engine.dispose()
        _async_database_engine = None
        _async_session_factory = None
        logger.info("Async database connections closed")


async def close_redis():
    """Close Redis connections"""
    global _redis_client
    
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connections closed")