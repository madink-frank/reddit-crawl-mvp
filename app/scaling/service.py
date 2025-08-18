"""
Auto-scaling service initialization and management
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.scaling.auto_scaler import scaling_manager
from app.scaling.resource_monitor import resource_monitor_service, ResourceAlert
from app.config import get_settings

logger = logging.getLogger(__name__)

class ScalingService:
    """Main service for managing auto-scaling components"""
    
    def __init__(self):
        self.settings = get_settings()
        self.scaling_manager = scaling_manager
        self.resource_monitor = resource_monitor_service
        self._initialized = False
    
    async def initialize(self):
        """Initialize the scaling service"""
        if self._initialized:
            logger.warning("Scaling service already initialized")
            return
        
        try:
            # Add alert callback for resource monitoring
            self.resource_monitor.monitor.add_alert_callback(self._handle_resource_alert)
            
            # Start services if auto-scaling is enabled
            if self.settings.AUTO_SCALING_ENABLED:
                await self.start_services()
            
            self._initialized = True
            logger.info("Scaling service initialized")
            
        except Exception as e:
            logger.error(f"Error initializing scaling service: {e}")
            raise
    
    async def start_services(self):
        """Start auto-scaling and resource monitoring services"""
        try:
            # Start resource monitoring first
            await self.resource_monitor.start()
            logger.info("Resource monitoring service started")
            
            # Start auto-scaling
            await self.scaling_manager.start()
            logger.info("Auto-scaling service started")
            
        except Exception as e:
            logger.error(f"Error starting scaling services: {e}")
            # Try to stop any started services
            await self.stop_services()
            raise
    
    async def stop_services(self):
        """Stop auto-scaling and resource monitoring services"""
        try:
            # Stop auto-scaling first
            await self.scaling_manager.stop()
            logger.info("Auto-scaling service stopped")
            
            # Stop resource monitoring
            await self.resource_monitor.stop()
            logger.info("Resource monitoring service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping scaling services: {e}")
    
    def _handle_resource_alert(self, alert: ResourceAlert):
        """Handle resource alerts from the monitoring system"""
        try:
            # Log the alert
            log_func = logger.critical if alert.severity == 'critical' else logger.warning
            log_func(f"Resource alert received: {alert.message}")
            
            # Here you could add additional alert handling:
            # - Send to external monitoring systems
            # - Trigger immediate scaling actions for critical alerts
            # - Update scaling thresholds dynamically
            
            if alert.severity == 'critical':
                # For critical alerts, we might want to trigger immediate scaling
                asyncio.create_task(self._handle_critical_alert(alert))
                
        except Exception as e:
            logger.error(f"Error handling resource alert: {e}")
    
    async def _handle_critical_alert(self, alert: ResourceAlert):
        """Handle critical resource alerts with immediate actions"""
        try:
            if alert.resource == 'cpu' and alert.current_value >= 90:
                # Critical CPU usage - try to scale up API instances
                logger.critical("Critical CPU usage detected, attempting emergency scaling")
                success = await self.scaling_manager.manual_scale_api(
                    min(self.scaling_manager.current_api_instances + 1, 6)
                )
                if success:
                    logger.info("Emergency API scaling completed")
                else:
                    logger.error("Emergency API scaling failed")
            
            elif alert.resource == 'memory' and alert.current_value >= 95:
                # Critical memory usage - restart workers to free memory
                logger.critical("Critical memory usage detected, considering worker restart")
                # This would typically trigger a graceful worker restart
                
            elif alert.resource == 'disk' and alert.current_value >= 95:
                # Critical disk usage - trigger cleanup
                logger.critical("Critical disk usage detected, triggering cleanup")
                # This would typically trigger log rotation and temp file cleanup
                
        except Exception as e:
            logger.error(f"Error handling critical alert: {e}")
    
    async def get_service_status(self) -> dict:
        """Get current status of all scaling services"""
        try:
            scaling_status = await self.scaling_manager.get_scaling_status()
            resource_status = self.resource_monitor.get_current_status()
            
            return {
                "initialized": self._initialized,
                "auto_scaling_enabled": scaling_status.get("auto_scaling_enabled", False),
                "resource_monitoring_enabled": resource_status.get("status") == "running",
                "scaling_status": scaling_status,
                "resource_status": resource_status,
                "settings": {
                    "auto_scaling_enabled": self.settings.AUTO_SCALING_ENABLED,
                    "instance_id": getattr(self.settings, 'INSTANCE_ID', 'default')
                }
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "initialized": self._initialized,
                "error": str(e)
            }

# Global scaling service instance
scaling_service = ScalingService()

@asynccontextmanager
async def scaling_service_lifespan() -> AsyncGenerator[None, None]:
    """Context manager for scaling service lifecycle"""
    try:
        await scaling_service.initialize()
        yield
    finally:
        await scaling_service.stop_services()

async def start_scaling_service():
    """Start the scaling service (for use in FastAPI startup)"""
    await scaling_service.initialize()

async def stop_scaling_service():
    """Stop the scaling service (for use in FastAPI shutdown)"""
    await scaling_service.stop_services()