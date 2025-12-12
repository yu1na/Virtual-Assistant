"""
Multi-Agent API 엔드포인트

중앙 Supervisor Agent를 통한 통합 질의응답 API
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
import sys
from pathlib import Path

# multi_agent 모듈 경로 추가
backend_path = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from multi_agent.supervisor import SupervisorAgent
from multi_agent.schemas import (
    MultiAgentRequest,
    MultiAgentResponse,
    AgentInfo,
    SessionCreateRequest,
    SessionCreateResponse,
)

router = APIRouter()

# Supervisor Agent 싱글톤
_supervisor_agent = None

# Supervisor agent 싱글톤 가져오는 함수
def get_supervisor_agent() -> SupervisorAgent:
    
    global _supervisor_agent
    if _supervisor_agent is None:
        _supervisor_agent = SupervisorAgent()
    return _supervisor_agent

# 사용자 질문을 적절한 에이전트에게 전달하는 함수
@router.post("/query", response_model=MultiAgentResponse)
async def multi_agent_query(
    request: MultiAgentRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor_agent)
):
    # 세션 ID가 있으면 대화 히스토리 주입
    if request.session_id:
        from app.domain.chatbot.session_manager import SessionManager
        session_manager = SessionManager()
        
        # 히스토리 가져오기
        history = session_manager.get_history(request.session_id)
        
        # Context 초기화 및 히스토리 추가
        if request.context is None:
            request.context = {}
            
        request.context["conversation_history"] = history
        request.context["session_id"] = request.session_id
        
        # 사용자 ID도 context에 추가
        if request.user_id:
            request.context["user_id"] = request.user_id

    try:
        response = await supervisor.process(request)
        return response
    except Exception as e:
        import traceback
        print(f"❌ [Multi-Agent API] 처리 중 에러 발생:")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Multi-Agent 처리 중 오류 발생: {str(e)}"
        )

# 사용 가능한 에이전트 목록 조회
@router.get("/agents", response_model=List[Dict[str, Any]])
async def get_available_agents(
    supervisor: SupervisorAgent = Depends(get_supervisor_agent)
):

    try:
        agents = supervisor.get_available_agents()
        return agents
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"에이전트 목록 조회 중 오류 발생: {str(e)}"
        )


@router.get("/health")
async def health_check():

    return {
        "status": "healthy",
        "service": "multi-agent",
        "version": "1.0.0"
    }


# 선택적: 세션 관리 엔드포인트
@router.post("/session", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest):

    import uuid
    from datetime import datetime
    
    session_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    return SessionCreateResponse(
        session_id=session_id,
        created_at=created_at
    )

