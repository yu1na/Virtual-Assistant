"""
심리 상담 API Endpoints

아들러 개인심리학 기반 RAG 상담 시스템
- 사용자 입력을 받아 심리 상담 응답 생성
- Vector DB 기반 관련 자료 검색
- 아들러 페르소나 적용
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.domain.therapy.service import TherapyService

router = APIRouter()

# TherapyService 싱글톤 인스턴스
therapy_service = TherapyService()

# 심리 상담 요청 클래스
class TherapyRequest(BaseModel):
    message: str
    enable_scoring: Optional[bool] = True  # 답변 품질 스코어링 활성화 (기본값: True)
    user_id: Optional[str] = None  # 사용자 ID (선택적, 세션 관리용)

# 프로토콜 정보 클래스
class ProtocolInfo(BaseModel):
    protocol_type: Optional[str] = None  # eap, sfbt, integrated
    current_stage: Optional[str] = None  # emotion_exploration, strength_resources, solution_focused, action_plan
    severity_level: Optional[str] = None  # low, medium, high, critical
    stage_guideline: Optional[dict] = None  # 현재 단계 가이드라인

# 심리 상담 응답 클래스
class TherapyResponse(BaseModel):
    answer: str
    mode: str
    used_chunks: List[str]
    continue_conversation: bool
    protocol_info: Optional[ProtocolInfo] = None  # 프로토콜 정보 추가 

# 심리 상담 채팅 엔드포인트
@router.post("/chat", response_model=TherapyResponse)
async def chat_therapy(request: TherapyRequest):

    try:
        # 서비스 사용 가능 여부 확인
        if not therapy_service.is_available():
            raise HTTPException(
                status_code=503, 
                detail="심리 상담 시스템이 현재 사용 불가능합니다. Vector DB를 확인해주세요."
            )
        
        # 상담 진행 (스코어링 옵션 및 사용자 ID 전달)
        response = await therapy_service.chat(
            request.message, 
            enable_scoring=request.enable_scoring,
            user_id=request.user_id
        )
        
        # 프로토콜 정보 추출
        protocol_info = None
        if response.get("protocol_info"):
            protocol_info = ProtocolInfo(**response["protocol_info"])
        
        return TherapyResponse(
            answer=response["answer"],
            mode=response["mode"],
            used_chunks=response.get("used_chunks", []),
            continue_conversation=response.get("continue_conversation", True),
            protocol_info=protocol_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"상담 처리 중 오류가 발생했습니다: {str(e)}"
        )

# 심리 상담 시스템 확인 엔드포인트
@router.get("/status")
async def get_therapy_status():

    return {
        "available": therapy_service.is_available(),
        "system": "RAG 기반 아들러 심리 상담",
        "persona": "Alfred Adler (개인심리학) + EAP + SFBT"
    }

# 세션 초기화 요청 클래스
class ResetSessionRequest(BaseModel):
    user_id: Optional[str] = None  # 사용자 ID (선택적, 없으면 기본 세션 초기화)

# 세션 초기화 엔드포인트
@router.post("/reset-session")
async def reset_session(request: ResetSessionRequest):
    """사용자 상담 세션 초기화"""
    
    try:
        success = therapy_service.reset_session(user_id=request.user_id)
        if success:
            return {
                "message": "세션이 성공적으로 초기화되었습니다.",
                "user_id": request.user_id
            }
        else:
            raise HTTPException(
                status_code=503,
                detail="상담 시스템이 현재 사용 불가능합니다."
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"세션 초기화 중 오류가 발생했습니다: {str(e)}"
        )