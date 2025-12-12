from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
import sys

from app.core.config import settings
from app.api.v1 import api_router
from app.infrastructure.database import engine, Base

import warnings
# LangSmith UUID v7 경고 억제
warnings.filterwarnings("ignore", message=".*LangSmith now uses UUID v7.*")
warnings.filterwarnings("ignore", message=".*Future versions will require UUID v7.*")

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Virtual-Assistant 루트

# 모듈 RAG 초기화
from app.load_modules import init_all_modules

# Tools Router 추가
import sys
from pathlib import Path
tools_path = Path(__file__).resolve().parent.parent.parent / "tools"
if str(tools_path) not in sys.path:
    sys.path.insert(0, str(tools_path))

try:
    from tools.router import tools_router
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    print("⚠️ Tools module not available.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 시작/종료 시 실행되는 함수
    """
    # 시작 시
    print("🚀 Starting Virtual Desk Assistant API...")
    print(f"📊 Database: {settings.DATABASE_URL}")
    
    # 데이터베이스 테이블 생성 (개발용)
    # 프로덕션에서는 Alembic 마이그레이션 사용
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")
    
    # 모듈별 RAG 초기화 (load_modules)
    try:
        init_all_modules()
    except Exception as e:
        print(f"⚠️  Module initialization error: {e}")
    
    yield
    
    # 종료 시
    print("👋 Shutting down...")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered Multi-Agent Virtual Desktop Assistant",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API 라우터 등록
app.include_router(api_router, prefix=settings.API_PREFIX)

# Tools 라우터 등록
if TOOLS_AVAILABLE:
    app.include_router(tools_router, prefix="/api/tools", tags=["tools"])


# 정적 파일 경로 설정
FRONTEND_DIR = BASE_DIR / "frontend"
PUBLIC_DIR = BASE_DIR / "public"
RENDERER_DIR = BASE_DIR / "renderer"

# 보고서 HTML 파일 서빙 (타입별로 분리)
# 중요: 더 구체적인 경로를 먼저 마운트해야 함
REPORTS_BASE_DIR = BASE_DIR / "backend" / "output"
# 디렉토리가 없으면 생성
REPORTS_BASE_DIR.mkdir(parents=True, exist_ok=True)

# 일일보고서 (더 구체적인 경로를 먼저 마운트)
daily_dir = REPORTS_BASE_DIR / "daily"
daily_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/reports/daily", StaticFiles(directory=str(daily_dir)), name="reports_daily")

# 주간보고서
weekly_dir = REPORTS_BASE_DIR / "weekly"
weekly_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/reports/weekly", StaticFiles(directory=str(weekly_dir)), name="reports_weekly")

# 월간보고서
monthly_dir = REPORTS_BASE_DIR / "monthly"
monthly_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/reports/monthly", StaticFiles(directory=str(monthly_dir)), name="reports_monthly")

# 정적 파일 서빙 (보고서 경로 이후에 마운트)
app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/renderer", StaticFiles(directory=str(RENDERER_DIR)), name="renderer")

print(f"✅ 보고서 HTML 서빙 경로 등록:")
print(f"   - /static/reports/daily -> {daily_dir}")
print(f"   - /static/reports/weekly -> {weekly_dir}")
print(f"   - /static/reports/monthly -> {monthly_dir}")


# Health Check
@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/")
async def root():
    """루트 엔드포인트 - 랜딩 페이지"""
    landing_page = FRONTEND_DIR / "Landing" / "index.html"
    if landing_page.exists():
        return FileResponse(landing_page)
    else:
        return {
            "message": "Welcome to Virtual Desk Assistant API",
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health"
        }


@app.get("/landing")
async def landing_page():
    """랜딩 페이지 (첫 화면)"""
    landing_page_path = FRONTEND_DIR / "Landing" / "index.html"
    if landing_page_path.exists():
        return FileResponse(landing_page_path)
    else:
        return {"error": "Landing page not found"}


@app.get("/login")
async def login_page():
    """로그인 페이지"""
    login_page = FRONTEND_DIR / "Login" / "index.html"
    if login_page.exists():
        return FileResponse(login_page)
    else:
        return {"error": "Login page not found"}


@app.get("/start")
async def start_page():
    """시작 페이지 (로그인 완료 후) - Landing 페이지로 리다이렉트"""
    landing_page_path = FRONTEND_DIR / "Landing" / "index.html"
    if landing_page_path.exists():
        return FileResponse(landing_page_path)
    else:
        return {"error": "Landing page not found"}


@app.get("/main")
async def main_page():
    """메인 페이지 - 캐릭터 화면 (일렉트론용)"""
    main_page = BASE_DIR / "index.html"
    if main_page.exists():
        return FileResponse(main_page)
    else:
        return {"error": "Main page not found"}


@app.get("/report")
async def report_page():
    """보고서 팝업 페이지 (일렉트론용)"""
    report_page = BASE_DIR / "report-popup.html"
    if report_page.exists():
        return FileResponse(report_page)
    else:
        return {"error": "Report page not found"}


@app.get("/brainstorming-popup")
async def brainstorming_popup_page():
    """브레인스토밍 팝업 페이지 (일렉트론용)"""
    brainstorming_page = BASE_DIR / "brainstorming-popup.html"
    if brainstorming_page.exists():
        return FileResponse(brainstorming_page)
    else:
        return {"error": "Brainstorming page not found"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
