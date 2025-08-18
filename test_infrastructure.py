#!/usr/bin/env python3
"""
Test script for Redis and Celery infrastructure setup
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.infrastructure import InfrastructureContext
from app.redis_client import redis_client
from app.vault_client import vault_client
from app.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_redis():
    """Test Redis connection and operations"""
    logger.info("Testing Redis connection...")
    
    try:
        # Test basic operations
        await redis_client.set("test_key", "test_value", ex=60)
        value = await redis_client.get("test_key")
        
        if value == "test_value":
            logger.info("✓ Redis basic operations working")
        else:
            logger.error("✗ Redis basic operations failed")
            return False
        
        # Test hash operations
        await redis_client.hset("test_hash", {"field1": "value1", "field2": {"nested": "data"}})
        hash_data = await redis_client.hgetall("test_hash")
        
        if hash_data.get("field1") == "value1" and isinstance(hash_data.get("field2"), dict):
            logger.info("✓ Redis hash operations working")
        else:
            logger.error("✗ Redis hash operations failed")
            return False
        
        # Test list operations
        await redis_client.lpush("test_list", "item1", {"complex": "item"})
        list_length = await redis_client.llen("test_list")
        
        if list_length == 2:
            logger.info("✓ Redis list operations working")
        else:
            logger.error("✗ Redis list operations failed")
            return False
        
        # Test queue stats
        queue_stats = await redis_client.get_queue_stats()
        logger.info(f"✓ Queue stats retrieved: {queue_stats}")
        
        # Cleanup
        await redis_client.delete("test_key", "test_hash", "test_list")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Redis test failed: {e}")
        return False


def test_celery():
    """Test Celery configuration"""
    logger.info("Testing Celery configuration...")
    
    try:
        # Check if Celery app is configured
        if not celery_app:
            logger.error("✗ Celery app not initialized")
            return False
        
        # Check broker connection
        broker_url = celery_app.conf.broker_url
        logger.info(f"✓ Celery broker URL: {broker_url}")
        
        # Check task routes
        task_routes = celery_app.conf.task_routes
        expected_routes = [
            "workers.collector.tasks.*",
            "workers.nlp_pipeline.tasks.*", 
            "workers.publisher.tasks.*"
        ]
        
        for route in expected_routes:
            if route in task_routes:
                logger.info(f"✓ Task route configured: {route} -> {task_routes[route]}")
            else:
                logger.error(f"✗ Task route missing: {route}")
                return False
        
        # Check queues
        queues = celery_app.conf.task_queues
        expected_queues = ["collect", "process", "publish"]
        
        queue_names = [q.name for q in queues]
        for expected_queue in expected_queues:
            if expected_queue in queue_names:
                logger.info(f"✓ Queue configured: {expected_queue}")
            else:
                logger.error(f"✗ Queue missing: {expected_queue}")
                return False
        
        # Check beat schedule
        beat_schedule = celery_app.conf.beat_schedule
        if beat_schedule:
            logger.info(f"✓ Beat schedule configured with {len(beat_schedule)} tasks")
            for task_name, config in beat_schedule.items():
                logger.info(f"  - {task_name}: {config['schedule']}s interval")
        else:
            logger.error("✗ Beat schedule not configured")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Celery test failed: {e}")
        return False


async def test_vault():
    """Test Vault connection (optional)"""
    logger.info("Testing Vault connection...")
    
    try:
        # Vault connection is optional, so don't fail if it's not available
        health = vault_client.health_check()
        
        if health["status"] == "healthy":
            logger.info("✓ Vault connection healthy")
            return True
        else:
            logger.warning(f"⚠ Vault not available: {health.get('error', 'Unknown error')}")
            logger.info("This is OK - system will use environment variables")
            return True
            
    except Exception as e:
        logger.warning(f"⚠ Vault test failed: {e}")
        logger.info("This is OK - system will use environment variables")
        return True


async def test_infrastructure():
    """Test complete infrastructure setup"""
    logger.info("Starting infrastructure tests...")
    
    async with InfrastructureContext() as infra:
        # Test individual components
        redis_ok = await test_redis()
        celery_ok = test_celery()
        vault_ok = await test_vault()
        
        # Test health check
        logger.info("Testing infrastructure health check...")
        health = await infra.health_check()
        logger.info(f"Overall health status: {health['overall_status']}")
        
        for component, status in health['components'].items():
            logger.info(f"  {component}: {status['status']}")
            if status['status'] != 'healthy' and 'error' in status:
                logger.info(f"    Error: {status['error']}")
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("INFRASTRUCTURE TEST SUMMARY")
        logger.info("="*50)
        logger.info(f"Redis:  {'✓ PASS' if redis_ok else '✗ FAIL'}")
        logger.info(f"Celery: {'✓ PASS' if celery_ok else '✗ FAIL'}")
        logger.info(f"Vault:  {'✓ PASS' if vault_ok else '✗ FAIL'}")
        logger.info(f"Overall: {'✓ PASS' if redis_ok and celery_ok else '✗ FAIL'}")
        
        if redis_ok and celery_ok:
            logger.info("\n🎉 Infrastructure setup is working correctly!")
            return True
        else:
            logger.error("\n❌ Infrastructure setup has issues that need to be resolved.")
            return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_infrastructure())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        sys.exit(1)