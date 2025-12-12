from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.report.reports import router as reports_router
from app.api.v1.endpoints.report.plan import router as plan_router
from app.api.v1.endpoints.report.daily import router as daily_router
from app.api.v1.endpoints.report.daily_report import router as daily_report_router
from app.api.v1.endpoints.report.daily_input import router as daily_input_router
from app.api.v1.endpoints.report.pdf_export import router as pdf_export_router
from app.api.v1.endpoints.report.weekly_report import router as weekly_report_router
from app.api.v1.endpoints.report.monthly_report import router as monthly_report_router
from app.api.v1.endpoints.rag import router as rag_router
from app.api.v1.endpoints.brainstorming import router as brainstorming_router
from app.api.v1.endpoints.chatbot import router as chatbot_router
from app.api.v1.endpoints.therapy import router as therapy_router
from app.api.v1.endpoints.multi_agent import router as multi_agent_router
from app.api.v1.endpoints.agent_router import router as agent_router  # 보고서 Agent 시스템
from app.api.v1.endpoints.report.report_chat import router as report_chat_router  # 보고서 RAG 챗봇

api_router = APIRouter()

# 보고서 Agent API (최우선)
api_router.include_router(agent_router)

# Auth 엔드포인트
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"]
)

# Users 엔드포인트
api_router.include_router(
    users_router,
    prefix="/users",
    tags=["Users"]
)

# Reports 엔드포인트
api_router.include_router(
    reports_router,
    tags=["Reports"]
)

# Plan 엔드포인트
api_router.include_router(
    plan_router,
    tags=["Plan"]
)

# Daily 엔드포인트
api_router.include_router(
    daily_router,
    tags=["Daily"]
)

# Daily Report (운영 DB) 엔드포인트
api_router.include_router(
    daily_report_router,
    tags=["Daily Report"]
)

# Daily Input (태그 기반 입력) 엔드포인트
api_router.include_router(
    daily_input_router,
    tags=["Daily Input"]
)

# PDF Export (WeasyPrint) 엔드포인트
api_router.include_router(
    pdf_export_router,
    tags=["PDF Export"]
)

# Weekly Report (주간 보고서) 엔드포인트
api_router.include_router(
    weekly_report_router,
    tags=["Weekly Report"]
)

# Monthly Report (월간 보고서) 엔드포인트
api_router.include_router(
    monthly_report_router,
    tags=["Monthly Report"]
)

# RAG 엔드포인트
api_router.include_router(
    rag_router,
    prefix="/rag",
    tags=["RAG"]
)

# Brainstorming 엔드포인트
api_router.include_router(
    brainstorming_router,
    prefix="/brainstorming",
    tags=["Brainstorming"]
)

# Chatbot 엔드포인트
api_router.include_router(
    chatbot_router,
    prefix="/chatbot",
    tags=["Chatbot"]
)

# Therapy 엔드포인트
api_router.include_router(
    therapy_router,
    prefix="/therapy",
    tags=["Therapy"]
)

# Multi-Agent 엔드포인트 (통합 AI 시스템)
api_router.include_router(
    multi_agent_router,
    prefix="/multi-agent",
    tags=["Multi-Agent"]
)

# 보고서 RAG 챗봇 엔드포인트
api_router.include_router(
    report_chat_router,
    tags=["Report Chat"]
)
