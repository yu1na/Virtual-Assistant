"""
브레인스토밍 아이디어 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class IdeaBase(BaseModel):
    """아이디어 기본 스키마"""
    title: str = Field(..., description="아이디어 제목", min_length=1, max_length=255)
    description: str = Field(..., description="아이디어 상세 내용 (JSON 형식)")


class IdeaCreate(IdeaBase):
    """아이디어 생성 스키마"""
    pass


class IdeaUpdate(BaseModel):
    """아이디어 수정 스키마 (필요 시 추가)"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class IdeaResponse(IdeaBase):
    """아이디어 응답 스키마"""
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True  # SQLAlchemy 모델을 Pydantic 모델로 변환 가능


class IdeaListResponse(BaseModel):
    """아이디어 목록 응답 스키마"""
    total: int
    ideas: list[IdeaResponse]
