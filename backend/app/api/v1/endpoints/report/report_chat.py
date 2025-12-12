"""
Report Chat API Endpoints

일일보고서 RAG 챗봇 API
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import date

from app.domain.auth.dependencies import get_current_user_optional
from app.domain.user.models import User
from app.domain.report.search.intent_router import IntentRouter
from app.domain.report.common.schemas import RAGSourceRef, ReportPeriod
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/report-chat", tags=["report-chat"])


class ChatRequest(BaseModel):
    """챗봇 질문 요청"""
    query: str
    date_start: Optional[str] = None  # YYYY-MM-DD 형식
    date_end: Optional[str] = None  # YYYY-MM-DD 형식
    reference_date: Optional[str] = None  # YYYY-MM-DD 형식, "이번 주" 같은 상대적 날짜 계산 기준


class ChatResponse(BaseModel):
    """챗봇 응답"""
    answer: str
    sources: List[RAGSourceRef]
    has_results: bool


@router.post("/chat", response_model=ChatResponse)
async def chat_with_reports(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    일일보고서 데이터 기반 RAG 챗봇 대화 (Agent 기반)
    
    인증 비활성화: current_user가 없어도 동작합니다.
    
    Args:
        request: ChatRequest (query, date_start, date_end)
        current_user: 현재 로그인한 사용자 (선택)
        
    Returns:
        ChatResponse (answer, sources, has_results)
        
    예시:
        - "나 최근에 연금 상담 언제 했었지?"
        - "최근에 상담했던 암보험 고객 이름 누구였지?"
        - "지난달에 실손 갱신 상담한 적 있었어?"
        - "올해 들어 내가 가장 많이 상담한 보험 종류가 뭐야?"
        - "지난주에 처리 못한 미종결 업무 뭐 있었지?"
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        resolved_owner = current_user.name if current_user and current_user.name else "사용자"
        from multi_agent.tools.report_tools import get_report_rag_agent
        
        intent_router = IntentRouter()

        # 기준 날짜 파싱 (상대적 날짜 계산용, 기본=오늘)
        reference_date = date.fromisoformat(request.reference_date) if request.reference_date else date.today()

        # 날짜 범위 파싱 (요청값 우선, 없으면 인텐트 기반)
        date_range: Dict[str, date] | None = None
        if request.date_start or request.date_end:
            date_range = {}
            if request.date_start:
                date_range["start"] = date.fromisoformat(request.date_start)
            if request.date_end:
                date_range["end"] = date.fromisoformat(request.date_end)
        else:
            intent = intent_router.route(request.query, reference_date=reference_date)
            if intent.filters.get("date_range"):
                date_range = intent.filters["date_range"]
        
        # ReportRAGAgent 사용
        # owner 필터링 제거: 단일 워크스페이스로 동작
        rag_agent = get_report_rag_agent()
        result = await rag_agent.search_reports(
            owner=None,  # owner 필터링 제거
            query=request.query,
            date_range=date_range,
            reference_date=reference_date
        )
        
        # SourceInfo 변환
        sources = [
            RAGSourceRef(**source) for source in result["sources"]
        ]
        
        return ChatResponse(
            answer=result["answer"],
            sources=sources,
            has_results=result["has_results"]
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"날짜 형식 오류: {str(e)}")
    except Exception as e:
        print(f"[ERROR] Report chat error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"챗봇 처리 중 오류: {str(e)}")

