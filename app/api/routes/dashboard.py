"""
Dashboard Router - Production Admin Dashboard
API 서버에서 직접 대시보드를 호스팅하는 라우터
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path

router = APIRouter()

# 템플릿 디렉토리 설정
templates_dir = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

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