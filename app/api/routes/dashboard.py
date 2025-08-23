"""
Dashboard Router - Production Admin Dashboard
API 서버에서 직접 대시보드를 호스팅하는 라우터
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

router = APIRouter()

# 템플릿 디렉토리 설정
templates_dir = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Global pipeline monitoring state
pipeline_monitor_state = {
    "active": False,
    "start_time": None,
    "current_status": {
        "overall_status": "idle",
        "current_stage": "none",
        "stages": {
            "collection": {"status": "pending", "progress": 0},
            "processing": {"status": "pending", "progress": 0},
            "publishing": {"status": "pending", "progress": 0},
            "verification": {"status": "pending", "progress": 0}
        },
        "metrics": {
            "posts_collected": 0,
            "posts_processed": 0,
            "posts_published": 0,
            "posts_verified": 0
        },
        "published_urls": [],
        "last_updated": datetime.now().isoformat()
    }
}

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """메인 대시보드 페이지"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Reddit Ghost Publisher Admin",
        "api_base_url": "http://localhost:8000"
    })

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """관리자 대시보드 페이지"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Reddit Ghost Publisher Admin",
        "api_base_url": "http://localhost:8000"
    })

@router.get("/simple", response_class=HTMLResponse)
async def simple_dashboard(request: Request):
    """간단한 대시보드 (CSP 문제 해결)"""
    return templates.TemplateResponse("simple_dashboard.html", {
        "request": request,
        "title": "Reddit Ghost Publisher Admin",
        "api_base_url": "http://localhost:8000"
    })

@router.get("/health-ui", response_class=HTMLResponse)
async def health_dashboard(request: Request):
    """헬스체크 대시보드"""
    return templates.TemplateResponse("health_dashboard.html", {
        "request": request,
        "title": "System Health Dashboard",
        "api_base_url": "http://localhost:8000"
    })

@router.get("/pipeline-monitor", response_class=HTMLResponse)
async def pipeline_monitor_dashboard(request: Request):
    """E2E 파이프라인 모니터링 대시보드"""
    return templates.TemplateResponse("pipeline_monitor.html", {
        "request": request,
        "title": "E2E Pipeline Monitor",
        "api_base_url": "http://localhost:8000"
    })

# Pipeline monitoring API endpoints

@router.get("/api/pipeline/status")
async def get_pipeline_status():
    """Get current pipeline status for real-time monitoring"""
    try:
        # Update current status with fresh data
        await _update_pipeline_status()
        
        return JSONResponse(content={
            "success": True,
            "data": pipeline_monitor_state["current_status"],
            "monitoring_active": pipeline_monitor_state["active"]
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/pipeline/start-monitoring")
async def start_pipeline_monitoring(background_tasks: BackgroundTasks):
    """Start pipeline monitoring"""
    try:
        if pipeline_monitor_state["active"]:
            return JSONResponse(content={
                "success": False,
                "message": "Pipeline monitoring is already active"
            })
        
        # Start monitoring in background
        pipeline_monitor_state["active"] = True
        pipeline_monitor_state["start_time"] = datetime.now()
        
        # Reset status
        pipeline_monitor_state["current_status"] = {
            "overall_status": "monitoring",
            "current_stage": "initializing",
            "stages": {
                "collection": {"status": "pending", "progress": 0},
                "processing": {"status": "pending", "progress": 0},
                "publishing": {"status": "pending", "progress": 0},
                "verification": {"status": "pending", "progress": 0}
            },
            "metrics": {
                "posts_collected": 0,
                "posts_processed": 0,
                "posts_published": 0,
                "posts_verified": 0
            },
            "published_urls": [],
            "last_updated": datetime.now().isoformat()
        }
        
        # Start background monitoring task
        background_tasks.add_task(_background_pipeline_monitoring)
        
        return JSONResponse(content={
            "success": True,
            "message": "Pipeline monitoring started",
            "start_time": pipeline_monitor_state["start_time"].isoformat()
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/pipeline/stop-monitoring")
async def stop_pipeline_monitoring():
    """Stop pipeline monitoring"""
    try:
        pipeline_monitor_state["active"] = False
        pipeline_monitor_state["current_status"]["overall_status"] = "stopped"
        
        return JSONResponse(content={
            "success": True,
            "message": "Pipeline monitoring stopped"
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/pipeline/published-posts")
async def get_published_posts():
    """Get list of published posts with verification status"""
    try:
        from app.infrastructure import get_database
        from sqlalchemy import text
        
        database = get_database()
        
        with database.connect() as conn:
            # Get recent published posts
            result = conn.execute(text("""
                SELECT id, title, ghost_url, created_at, updated_at
                FROM posts 
                WHERE ghost_url IS NOT NULL 
                ORDER BY updated_at DESC 
                LIMIT 20
            """))
            
            posts = []
            for row in result:
                post_data = {
                    "id": str(row.id),
                    "title": row.title,
                    "ghost_url": row.ghost_url,
                    "published_at": row.updated_at.isoformat() if row.updated_at else None,
                    "verified": False  # Will be updated by verification check
                }
                
                # Quick verification check
                try:
                    import requests
                    response = requests.get(row.ghost_url, timeout=5)
                    post_data["verified"] = response.status_code == 200
                except Exception:
                    post_data["verified"] = False
                
                posts.append(post_data)
        
        return JSONResponse(content={
            "success": True,
            "posts": posts,
            "total": len(posts)
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Helper functions

async def _update_pipeline_status():
    """Update pipeline status with current data"""
    try:
        from app.infrastructure import get_database
        from sqlalchemy import text
        import requests
        
        database = get_database()
        
        with database.connect() as conn:
            # Get post counts
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_posts,
                    COUNT(CASE WHEN summary_ko IS NOT NULL THEN 1 END) as processed_posts,
                    COUNT(CASE WHEN ghost_url IS NOT NULL THEN 1 END) as published_posts
                FROM posts
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """))
            
            row = result.fetchone()
            if row:
                pipeline_monitor_state["current_status"]["metrics"].update({
                    "posts_collected": row.total_posts,
                    "posts_processed": row.processed_posts,
                    "posts_published": row.published_posts
                })
        
        # Get queue status
        try:
            queue_response = requests.get("http://localhost:8000/api/v1/status/queues", timeout=5)
            if queue_response.status_code == 200:
                queue_data = queue_response.json()
                
                # Update stage status based on queue activity
                for queue_name, queue_info in queue_data.items():
                    stage_name = _queue_to_stage_name(queue_name)
                    if stage_name in pipeline_monitor_state["current_status"]["stages"]:
                        active = queue_info.get("active", 0)
                        pending = queue_info.get("pending", 0)
                        
                        if active > 0:
                            pipeline_monitor_state["current_status"]["stages"][stage_name]["status"] = "running"
                        elif pending > 0:
                            pipeline_monitor_state["current_status"]["stages"][stage_name]["status"] = "queued"
                        else:
                            # Check if stage has completed work
                            if _has_stage_completed_work(stage_name):
                                pipeline_monitor_state["current_status"]["stages"][stage_name]["status"] = "completed"
        
        except Exception as e:
            pass  # Ignore queue status errors
        
        # Update stage progress
        _update_stage_progress()
        
        # Determine overall status
        _determine_overall_status()
        
        # Update timestamp
        pipeline_monitor_state["current_status"]["last_updated"] = datetime.now().isoformat()
    
    except Exception as e:
        pass  # Ignore update errors to prevent breaking the API

async def _background_pipeline_monitoring():
    """Background task for continuous pipeline monitoring"""
    try:
        while pipeline_monitor_state["active"]:
            await _update_pipeline_status()
            await asyncio.sleep(10)  # Update every 10 seconds
    
    except Exception as e:
        pipeline_monitor_state["active"] = False

def _queue_to_stage_name(queue_name: str) -> str:
    """Convert queue name to stage name"""
    mapping = {
        "collect": "collection",
        "process": "processing",
        "publish": "publishing"
    }
    return mapping.get(queue_name, queue_name)

def _has_stage_completed_work(stage_name: str) -> bool:
    """Check if a stage has completed some work"""
    metrics = pipeline_monitor_state["current_status"]["metrics"]
    
    if stage_name == "collection":
        return metrics["posts_collected"] > 0
    elif stage_name == "processing":
        return metrics["posts_processed"] > 0
    elif stage_name == "publishing":
        return metrics["posts_published"] > 0
    elif stage_name == "verification":
        return metrics["posts_verified"] > 0
    
    return False

def _update_stage_progress():
    """Update progress for each stage"""
    metrics = pipeline_monitor_state["current_status"]["metrics"]
    stages = pipeline_monitor_state["current_status"]["stages"]
    
    # Collection progress (assume target of 5 posts)
    collected = metrics["posts_collected"]
    stages["collection"]["progress"] = min(int((collected / 5) * 100), 100)
    
    # Processing progress
    if collected > 0:
        processed = metrics["posts_processed"]
        stages["processing"]["progress"] = min(int((processed / collected) * 100), 100)
    
    # Publishing progress
    if metrics["posts_processed"] > 0:
        published = metrics["posts_published"]
        stages["publishing"]["progress"] = min(int((published / metrics["posts_processed"]) * 100), 100)
    
    # Verification progress
    if metrics["posts_published"] > 0:
        verified = metrics["posts_verified"]
        stages["verification"]["progress"] = min(int((verified / metrics["posts_published"]) * 100), 100)

def _determine_overall_status():
    """Determine overall pipeline status"""
    stages = pipeline_monitor_state["current_status"]["stages"]
    
    # Check if any stage is running
    if any(stage["status"] == "running" for stage in stages.values()):
        pipeline_monitor_state["current_status"]["overall_status"] = "running"
        # Find current running stage
        for stage_name, stage in stages.items():
            if stage["status"] == "running":
                pipeline_monitor_state["current_status"]["current_stage"] = stage_name
                break
    
    # Check if any stage is queued
    elif any(stage["status"] == "queued" for stage in stages.values()):
        pipeline_monitor_state["current_status"]["overall_status"] = "queued"
        for stage_name, stage in stages.items():
            if stage["status"] == "queued":
                pipeline_monitor_state["current_status"]["current_stage"] = stage_name
                break
    
    # Check if all stages are completed
    elif all(stage["status"] == "completed" for stage in stages.values()):
        pipeline_monitor_state["current_status"]["overall_status"] = "completed"
        pipeline_monitor_state["current_status"]["current_stage"] = "completed"
    
    # Check for errors
    elif any(stage["status"] == "error" for stage in stages.values()):
        pipeline_monitor_state["current_status"]["overall_status"] = "error"
    
    # Default to monitoring if active
    elif pipeline_monitor_state["active"]:
        pipeline_monitor_state["current_status"]["overall_status"] = "monitoring"