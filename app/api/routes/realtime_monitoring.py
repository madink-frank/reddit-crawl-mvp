"""
Real-time Monitoring and Dashboard Updates
Provides WebSocket connections and real-time data streaming for enhanced user experience
"""

import json
import asyncio
import time
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.monitoring.logging import get_logger
from app.infrastructure import get_database, get_redis_client
from app.api.middleware.performance_optimization import get_optimization_stats
from app.api.middleware.enhanced_error_handling import get_error_statistics

logger = get_logger(__name__)
router = APIRouter()


class ConnectionManager:
    """WebSocket connection manager for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.subscription_topics: Dict[str, Set[str]] = {}  # topic -> set of connection_ids
        
    async def connect(self, websocket: WebSocket, connection_id: str, topics: List[str] = None) -> None:
        """Accept WebSocket connection and setup subscriptions"""
        await websocket.accept()
        
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.now().isoformat(),
            "topics": topics or [],
            "last_ping": time.time()
        }
        
        # Subscribe to topics
        if topics:
            for topic in topics:
                if topic not in self.subscription_topics:
                    self.subscription_topics[topic] = set()
                self.subscription_topics[topic].add(connection_id)
        
        logger.info(f"WebSocket connection established: {connection_id} with topics: {topics}")
    
    def disconnect(self, connection_id: str) -> None:
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            # Remove from topic subscriptions
            topics = self.connection_metadata.get(connection_id, {}).get("topics", [])
            for topic in topics:
                if topic in self.subscription_topics:
                    self.subscription_topics[topic].discard(connection_id)
                    if not self.subscription_topics[topic]:
                        del self.subscription_topics[topic]
            
            # Remove connection
            del self.active_connections[connection_id]
            del self.connection_metadata[connection_id]
            
            logger.info(f"WebSocket connection closed: {connection_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], connection_id: str) -> None:
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def broadcast_to_topic(self, message: Dict[str, Any], topic: str) -> None:
        """Broadcast message to all connections subscribed to a topic"""
        if topic in self.subscription_topics:
            disconnected_connections = []
            
            for connection_id in self.subscription_topics[topic].copy():
                try:
                    websocket = self.active_connections[connection_id]
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Failed to broadcast to {connection_id}: {e}")
                    disconnected_connections.append(connection_id)
            
            # Clean up disconnected connections
            for connection_id in disconnected_connections:
                self.disconnect(connection_id)
    
    async def broadcast_to_all(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all active connections"""
        disconnected_connections = []
        
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to broadcast to {connection_id}: {e}")
                disconnected_connections.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected_connections:
            self.disconnect(connection_id)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "topics": {
                topic: len(connections) 
                for topic, connections in self.subscription_topics.items()
            },
            "connections": [
                {
                    "id": conn_id,
                    "connected_at": metadata["connected_at"],
                    "topics": metadata["topics"]
                }
                for conn_id, metadata in self.connection_metadata.items()
            ]
        }


class RealTimeDataCollector:
    """Collects and formats real-time data for dashboard updates"""
    
    def __init__(self):
        self.last_metrics = {}
        self.metrics_history = []
        
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics"""
        try:
            # Get database metrics
            database = get_database()
            
            with database.connect() as conn:
                # Get post counts
                result = conn.execute("""
                    SELECT 
                        COUNT(*) as total_posts,
                        COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as processed_posts,
                        COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published_posts,
                        COUNT(CASE WHEN created_at >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_posts
                    FROM posts
                """)
                
                row = result.fetchone()
                post_metrics = {
                    "total_posts": row.total_posts if row else 0,
                    "processed_posts": row.processed_posts if row else 0,
                    "published_posts": row.published_posts if row else 0,
                    "recent_posts": row.recent_posts if row else 0
                }
            
            # Get queue metrics
            import requests
            try:
                queue_response = requests.get("http://localhost:8000/api/v1/status/queues", timeout=5)
                queue_metrics = queue_response.json() if queue_response.status_code == 200 else {}
            except Exception:
                queue_metrics = {}
            
            # Get performance metrics
            performance_metrics = get_optimization_stats()
            
            # Get error metrics
            error_metrics = get_error_statistics()
            
            # Combine all metrics
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "posts": post_metrics,
                "queues": queue_metrics,
                "performance": performance_metrics,
                "errors": error_metrics,
                "system": {
                    "uptime_seconds": time.time() - getattr(self, 'start_time', time.time()),
                    "memory_usage_mb": self._get_memory_usage(),
                    "cpu_usage_percent": self._get_cpu_usage()
                }
            }
            
            # Store for history
            self.last_metrics = metrics
            self.metrics_history.append(metrics)
            
            # Keep only last 100 metrics
            if len(self.metrics_history) > 100:
                self.metrics_history.pop(0)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def collect_pipeline_status(self) -> Dict[str, Any]:
        """Collect pipeline status for real-time monitoring"""
        try:
            # Get current pipeline status from dashboard API
            import requests
            
            response = requests.get("http://localhost:8000/dashboard/api/pipeline/status", timeout=5)
            
            if response.status_code == 200:
                pipeline_data = response.json()
                
                return {
                    "timestamp": datetime.now().isoformat(),
                    "pipeline": pipeline_data.get("data", {}),
                    "monitoring_active": pipeline_data.get("monitoring_active", False)
                }
            else:
                return {
                    "timestamp": datetime.now().isoformat(),
                    "error": f"Pipeline status API returned {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Failed to collect pipeline status: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            import psutil
            return psutil.cpu_percent(interval=1)
        except Exception:
            return 0.0
    
    def get_metrics_history(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get metrics history for the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        return [
            metric for metric in self.metrics_history
            if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
        ]


# Global instances
connection_manager = ConnectionManager()
data_collector = RealTimeDataCollector()


@router.websocket("/ws/dashboard/{connection_id}")
async def websocket_dashboard(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for real-time dashboard updates"""
    await connection_manager.connect(websocket, connection_id, ["dashboard", "system", "pipeline"])
    
    try:
        # Send initial data
        initial_data = {
            "type": "initial_data",
            "data": await data_collector.collect_system_metrics()
        }
        await connection_manager.send_personal_message(initial_data, connection_id)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (ping/pong, subscription changes, etc.)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    data = json.loads(message)
                    await handle_websocket_message(data, connection_id)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from {connection_id}: {message}")
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.now().isoformat()
                }
                await connection_manager.send_personal_message(ping_message, connection_id)
                
    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        connection_manager.disconnect(connection_id)


async def handle_websocket_message(data: Dict[str, Any], connection_id: str) -> None:
    """Handle incoming WebSocket messages"""
    message_type = data.get("type")
    
    if message_type == "pong":
        # Update last ping time
        if connection_id in connection_manager.connection_metadata:
            connection_manager.connection_metadata[connection_id]["last_ping"] = time.time()
    
    elif message_type == "request_data":
        # Send requested data
        data_type = data.get("data_type", "system")
        
        if data_type == "system":
            response_data = await data_collector.collect_system_metrics()
        elif data_type == "pipeline":
            response_data = await data_collector.collect_pipeline_status()
        elif data_type == "history":
            minutes = data.get("minutes", 60)
            response_data = data_collector.get_metrics_history(minutes)
        else:
            response_data = {"error": f"Unknown data type: {data_type}"}
        
        response = {
            "type": "data_response",
            "data_type": data_type,
            "data": response_data
        }
        
        await connection_manager.send_personal_message(response, connection_id)


@router.get("/api/realtime/connections")
async def get_connection_stats():
    """Get WebSocket connection statistics"""
    return JSONResponse(content={
        "success": True,
        "data": connection_manager.get_connection_stats()
    })


@router.get("/api/realtime/metrics")
async def get_current_metrics():
    """Get current system metrics"""
    metrics = await data_collector.collect_system_metrics()
    
    return JSONResponse(content={
        "success": True,
        "data": metrics
    })


@router.get("/api/realtime/metrics/history")
async def get_metrics_history(minutes: int = 60):
    """Get metrics history"""
    history = data_collector.get_metrics_history(minutes)
    
    return JSONResponse(content={
        "success": True,
        "data": {
            "history": history,
            "minutes": minutes,
            "count": len(history)
        }
    })


@router.post("/api/realtime/broadcast")
async def broadcast_message(message: Dict[str, Any], topic: str = "dashboard"):
    """Broadcast message to WebSocket connections (admin only)"""
    try:
        broadcast_data = {
            "type": "broadcast",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        await connection_manager.broadcast_to_topic(broadcast_data, topic)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Message broadcasted to topic: {topic}",
            "recipients": len(connection_manager.subscription_topics.get(topic, set()))
        })
        
    except Exception as e:
        logger.error(f"Failed to broadcast message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task for periodic updates
async def periodic_updates():
    """Send periodic updates to connected clients"""
    while True:
        try:
            # Collect current metrics
            system_metrics = await data_collector.collect_system_metrics()
            pipeline_status = await data_collector.collect_pipeline_status()
            
            # Broadcast system metrics
            system_update = {
                "type": "system_update",
                "data": system_metrics
            }
            await connection_manager.broadcast_to_topic(system_update, "system")
            
            # Broadcast pipeline status
            pipeline_update = {
                "type": "pipeline_update", 
                "data": pipeline_status
            }
            await connection_manager.broadcast_to_topic(pipeline_update, "pipeline")
            
            # Wait 10 seconds before next update
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"Periodic update failed: {e}")
            await asyncio.sleep(30)  # Wait longer on error


# Start periodic updates when module is imported
asyncio.create_task(periodic_updates())