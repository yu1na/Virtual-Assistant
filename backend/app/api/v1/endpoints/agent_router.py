"""
Agent Router API

MainRouterAgent를 통한 통합 API 엔드포인트
사용자 요청을 분석하여 적절한 전문 에이전트로 라우팅
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from multi_agent.agents.report_main_router import ReportMainRouterAgent
from app.infrastructure.database.session import get_db


router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    """에이전트 쿼리 요청"""
    query: str = Field(..., description="사용자 질문")
    owner: str = Field(..., description="작성자")
    target_date: Optional[date] = Field(None, description="대상 날짜")
    context: Optional[Dict[str, Any]] = Field(None, description="추가 컨텍스트")


class AgentQueryResponse(BaseModel):
    """에이전트 쿼리 응답"""
    intent: str = Field(..., description="분류된 Intent (planning|report|rag)")
    agent: str = Field(..., description="처리한 Agent 이름")
    response: str = Field(..., description="Agent 응답")
    context: Optional[Dict[str, Any]] = Field(None, description="처리 컨텍스트")


class ReportAgentRequest(BaseModel):
    """보고서 에이전트 요청 (멀티에이전트 supervisor 우회)"""
    query: str = Field(..., description="사용자 질문")
    session_id: Optional[str] = Field(None, description="세션 ID (선택)")
    user_id: Optional[int] = Field(None, description="사용자 ID (선택)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 컨텍스트")


class ReportAgentResponse(BaseModel):
    """보고서 에이전트 응답"""
    query: str = Field(..., description="원본 질문")
    answer: str = Field(..., description="에이전트 응답")
    agent_used: str = Field(..., description="사용된 에이전트 (planning|report|rag)")
    intent: str = Field(..., description="분류된 Intent (planning|report|rag|unknown)")
    processing_time: float = Field(..., description="처리 시간 (초)")
    session_id: Optional[str] = Field(None, description="세션 ID")


# 전역 ReportMainRouterAgent 인스턴스 (싱글톤)
_main_router: Optional[ReportMainRouterAgent] = None


def get_main_router() -> ReportMainRouterAgent:
    """ReportMainRouterAgent 싱글톤 인스턴스 반환"""
    global _main_router
    if _main_router is None:
        _main_router = ReportMainRouterAgent()
    return _main_router


@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(
    request: AgentQueryRequest,
    db: Session = Depends(get_db)
):
    """
    통합 Agent Query API
    
    사용자 요청을 분석하여 적절한 전문 에이전트로 라우팅하고 결과를 반환합니다.
    
    Args:
        request: 쿼리 요청
        db: 데이터베이스 세션
        
    Returns:
        Agent 처리 결과
    """
    try:
        router_agent = get_main_router()
        
        # 컨텍스트 구성
        context = {
            "owner": request.owner,
            "target_date": request.target_date or date.today(),
            "db": db,
            **(request.context or {})
        }
        
        # MainRouterAgent로 라우팅
        result = await router_agent.route_to_agent(
            query=request.query,
            owner=request.owner,
            target_date=request.target_date,
            **(request.context or {})
        )
        
        return AgentQueryResponse(
            intent=result["intent"],
            agent=result["agent"],
            response=result["response"],
            context=result.get("context")
        )
    
    except Exception as e:
        print(f"[ERROR] Agent Query 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Agent 처리 실패: {str(e)}"
        )


@router.post("/report", response_model=ReportAgentResponse)
async def report_agent_query(
    request: ReportAgentRequest
):
    """
    보고서 에이전트 직접 호출 API (멀티에이전트 supervisor 우회)
    
    보고서 팝업 전용: ReportMainRouterAgent를 직접 호출하여
    supervisor를 완전히 우회합니다.
    
    Args:
        request: 보고서 에이전트 요청
        
    Returns:
        보고서 에이전트 처리 결과
    """
    import time
    start_time = time.time()
    
    try:
        router_agent = get_main_router()
        
        # Context 구성 (owner는 더 이상 필수 아님)
        context = request.context or {}
        
        # target_date가 없으면 오늘 날짜로 설정
        if "target_date" not in context:
            context["target_date"] = date.today()
        
        # ReportMainRouterAgent.process() 직접 호출
        response = await router_agent.process(
            query=request.query,
            context=context
        )
        
        # Intent 분류 (응답에 포함)
        intent = await router_agent.classify_intent(request.query)
        
        # agent_used는 intent 기반으로 결정
        agent_used = intent if intent != "unknown" else "report"
        
        processing_time = time.time() - start_time
        
        return ReportAgentResponse(
            query=request.query,
            answer=response,
            agent_used=agent_used,
            intent=intent,
            processing_time=processing_time,
            session_id=request.session_id
        )
    
    except Exception as e:
        print(f"[ERROR] Report Agent Query 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Report Agent 처리 실패: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok", "service": "agent_router"}

