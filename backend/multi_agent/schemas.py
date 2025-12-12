"""
Multi-Agent 시스템 스키마
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    """에이전트 정보"""
    name: str = Field(..., description="에이전트 이름")
    description: str = Field(..., description="에이전트 설명")
    capabilities: List[str] = Field(default_factory=list, description="에이전트 기능 목록")


class MultiAgentRequest(BaseModel):
    """Multi-Agent 요청"""
    query: str = Field(..., description="사용자 질문", min_length=1)
    session_id: Optional[str] = Field(None, description="세션 ID (선택)")
    user_id: Optional[int] = Field(None, description="사용자 ID (선택)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 컨텍스트")


class AgentResponse(BaseModel):
    """개별 에이전트 응답"""
    agent_name: str = Field(..., description="에이전트 이름")
    response: str = Field(..., description="에이전트 응답")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="메타데이터")


class MultiAgentResponse(BaseModel):
    """Multi-Agent 응답"""
    query: str = Field(..., description="원본 질문")
    answer: str = Field(..., description="최종 답변")
    agent_used: str = Field(..., description="사용된 에이전트")
    intent: Optional[str] = Field(None, description="인텐트 분류 결과 (lookup, planning, report_write 등)")
    intermediate_steps: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, 
        description="중간 단계 (디버깅용)"
    )
    processing_time: float = Field(..., description="처리 시간 (초)")
    session_id: Optional[str] = Field(None, description="세션 ID")


class SessionCreateRequest(BaseModel):
    """세션 생성 요청"""
    user_id: Optional[int] = Field(None, description="사용자 ID")


class SessionCreateResponse(BaseModel):
    """세션 생성 응답"""
    session_id: str = Field(..., description="생성된 세션 ID")
    created_at: str = Field(..., description="생성 시간")

