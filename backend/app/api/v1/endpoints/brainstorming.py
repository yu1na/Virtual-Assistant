"""
브레인스토밍 API 엔드포인트

아이디어 생성 워크플로우:
1. POST /session - 세션 시작
2. POST /purpose - Q1 목적 입력
3. GET /warmup/{session_id} - Q2 워밍업 질문 생성
4. POST /confirm/{session_id} - Q2 확인
5. POST /associations/{session_id} - Q3 자유연상 입력
6. GET /ideas/{session_id} - 아이디어 생성 및 분석
7. DELETE /session/{session_id} - 세션 삭제

변경사항 (2024-11-30):
- Ephemeral RAG: ChromaDB → JSON 기반으로 변경
- 영구 RAG: ChromaDB 유지 (data/chroma/)
- 임시 RAG: JSON 파일 (data/ephemeral/{session_id}/associations.json)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import sys
from pathlib import Path
import shutil
from datetime import datetime, timedelta

# 브레인스토밍 모듈 경로 추가
brainstorming_path = Path(__file__).resolve().parent.parent.parent.parent / "domain" / "brainstorming"
sys.path.insert(0, str(brainstorming_path))

from session_manager import SessionManager
from ephemeral_rag import EphemeralRAG, cleanup_old_sessions as cleanup_ephemeral_sessions
from domain_hints import get_domain_hint, format_hint_for_prompt

# ChromaDB import (영구 RAG 전용)
import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter()

# 전역 인스턴스
session_manager = SessionManager()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
llm_model = os.getenv("LLM_MODEL", "gpt-4o")
embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

# ============================================================
# 영구 RAG ChromaDB 클라이언트 (브레인스토밍 기법만!)
# ============================================================
module_dir = brainstorming_path
persist_directory = str(module_dir / "data" / "chroma")

chroma_client = chromadb.PersistentClient(
    path=persist_directory,
    settings=ChromaSettings(anonymized_telemetry=False)
)

try:
    permanent_collection = chroma_client.get_collection(
        name="brainstorming_techniques"
    )
    print("✅ 영구 RAG 컬렉션 로드 완료 (brainstorming API)")
    print(f"   📁 경로: {persist_directory}")
    print(f"   📊 문서 수: {permanent_collection.count()}개")
except Exception as e:
    print(f"⚠️  영구 RAG 컬렉션 로드 실패: {e}")
    permanent_collection = None


# === Pydantic 모델 ===

class SessionResponse(BaseModel):
    """세션 생성 응답"""
    session_id: str
    message: str


class PurposeRequest(BaseModel):
    """Q1 목적 입력 요청"""
    session_id: str
    purpose: str


class PurposeResponse(BaseModel):
    """Q1 목적 입력 응답"""
    message: str
    purpose: str


class WarmupResponse(BaseModel):
    """Q2 워밍업 질문 응답"""
    questions: List[str]


class ConfirmResponse(BaseModel):
    """Q2 확인 응답"""
    message: str


class AssociationsRequest(BaseModel):
    """Q3 자유연상 입력 요청"""
    session_id: str
    associations: List[str]


class AssociationsResponse(BaseModel):
    """Q3 자유연상 입력 응답"""
    message: str
    count: int


class IdeaResponse(BaseModel):
    """아이디어 생성 응답"""
    ideas: List[Dict[str, str]]  # [{"title": "...", "description": "...", "analysis": "..."}]


class DeleteResponse(BaseModel):
    """세션 삭제 응답"""
    message: str


# === API 엔드포인트 ===

@router.post("/session", response_model=SessionResponse)
async def create_session():
    """
    새로운 브레인스토밍 세션 시작
    
    시작 전에 오래된 Ephemeral RAG 데이터를 자동으로 청소합니다.
    
    Returns:
        SessionResponse: 세션 ID와 메시지
    """
    try:
        # 🧹 1. 오래된 세션 청소 (5분 이상)
        # Ephemeral 데이터는 임시 데이터이므로 빠르게 정리
        cleanup_ephemeral_sessions(max_age_seconds=300)
        
        # 2. 새 세션 생성
        session_id = session_manager.create_session()
        return SessionResponse(
            session_id=session_id,
            message="새로운 브레인스토밍 세션이 시작되었습니다."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 생성 실패: {str(e)}")


@router.post("/purpose", response_model=PurposeResponse)
async def submit_purpose(request: PurposeRequest):
    """
    Q1: 목적/도메인 입력
    
    Args:
        request: 세션 ID와 목적
        
    Returns:
        PurposeResponse: 확인 메시지
    """
    try:
        # 세션 존재 여부 확인
        session = session_manager.get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # 세션에 목적 저장
        session_manager.update_session(request.session_id, {
            'q1_purpose': request.purpose
        })
        
        return PurposeResponse(
            message="목적이 설정되었습니다.",
            purpose=request.purpose
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목적 입력 실패: {str(e)}")


@router.get("/warmup/{session_id}", response_model=WarmupResponse)
async def get_warmup_questions(session_id: str):
    """
    Q2: LLM 기반 워밍업 질문 생성
    
    Args:
        session_id: 세션 ID
        
    Returns:
        WarmupResponse: 워밍업 질문 리스트 (2-3개)
    """
    try:
        # 세션 존재 여부 확인
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        purpose = session.get('q1_purpose')
        if not purpose:
            raise HTTPException(status_code=400, detail="Q1 목적이 입력되지 않았습니다.")
        
        # LLM으로 워밍업 질문 생성
        prompt = f"""사용자가 "{purpose}"에 대한 아이디어를 생성하려고 합니다.

**목표**: 사용자의 직군/상황에 맞는 구체적인 워밍업 질문 2-3개 생성

**직군 추론**: 목적을 보고 사용자가 속한 직군(유튜버, 소상공인, 직장인, 학생, 개발자 등)을 파악하세요.

**워밍업 질문 생성 규칙**:
1. 사용자의 직군/상황에 맞는 **구체적인 질문**
2. 예: "누군가에게 자랑하고 싶은 결과물이라면 누구인가요?"
3. 2-3개의 질문만 생성
4. 각 질문은 간결하고 명확하게
5. 질문만 출력 (다른 설명 없이)

**출력 형식**:
- 질문1
- 질문2
- 질문3 (선택)
"""
        
        response = openai_client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "당신은 유능한 기획자입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=300
        )
        
        # 질문 파싱
        content = response.choices[0].message.content.strip()
        questions = [q.strip().lstrip('-').strip() for q in content.split('\n') if q.strip()]
        
        # 세션에 저장
        session_manager.update_session(session_id, {
            'q2_warmup_questions': questions
        })
        
        return WarmupResponse(questions=questions)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"워밍업 질문 생성 실패: {str(e)}")


@router.post("/confirm/{session_id}", response_model=ConfirmResponse)
async def confirm_warmup(session_id: str):
    """
    Q2: 워밍업 확인 (프론트엔드에서 "네" 버튼 클릭 시)
    
    Args:
        session_id: 세션 ID
        
    Returns:
        ConfirmResponse: 확인 메시지
    """
    try:
        # 세션 존재 여부 확인
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        return ConfirmResponse(message="워밍업이 확인되었습니다. Q3로 진행하세요.")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"확인 실패: {str(e)}")


@router.post("/associations/{session_id}", response_model=AssociationsResponse)
async def submit_associations(session_id: str, request: AssociationsRequest):
    """
    Q3: 자유연상 입력 (JSON 기반 Ephemeral RAG)
    
    Args:
        session_id: 세션 ID
        request: 자유연상 키워드 리스트
        
    Returns:
        AssociationsResponse: 확인 메시지 및 입력 개수
    """
    try:
        # 세션 존재 여부 확인
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # Ephemeral RAG 초기화 (JSON 기반)
        ephemeral_rag = EphemeralRAG(session_id=session_id)
        
        # 임베딩 및 JSON 저장
        ephemeral_rag.add_associations(request.associations)
        
        # 세션에 저장
        session_manager.update_session(session_id, {
            'q3_associations': request.associations,
            'ephemeral_rag_initialized': True
        })
        
        return AssociationsResponse(
            message="자유연상 입력이 완료되었습니다.",
            count=len(request.associations)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"자유연상 입력 실패: {str(e)}")


@router.get("/ideas/{session_id}", response_model=IdeaResponse)
async def generate_ideas(session_id: str):
    """
    아이디어 생성 및 SWOT 분석
    
    idea_generator.py의 generate_ideas_for_api 메서드를 호출합니다.
    (트렌드 검색 + 80:20 비중 + 할루시네이션 방지 적용)
    
    Args:
        session_id: 세션 ID
        
    Returns:
        IdeaResponse: 아이디어 리스트
    """
    try:
        # 세션 존재 여부 확인
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        purpose = session.get('q1_purpose')
        associations = session.get('q3_associations', [])
        
        if not purpose or not associations:
            raise HTTPException(status_code=400, detail="Q1 또는 Q3 데이터가 없습니다.")
        
        # ============================================================
        # idea_generator.py 호출 (트렌드 검색 + 새 프롬프트 적용)
        # ============================================================
        from idea_generator import IdeaGenerator
        
        generator = IdeaGenerator()
        ideas = await generator.generate_ideas_for_api(
            session_id=session_id,
            purpose=purpose,
            associations=associations
        )
        
        # 아이디어 검증
        if not ideas:
            raise HTTPException(
                status_code=500,
                detail="아이디어 생성에 실패했습니다. 다시 시도해주세요."
            )
        
        # 세션에 저장
        session_manager.update_session(session_id, {
            'generated_ideas': ideas
        })
        
        return IdeaResponse(ideas=ideas)
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"아이디어 생성 실패: {str(e)}")


@router.delete("/session/{session_id}", response_model=DeleteResponse)
async def delete_session(session_id: str):
    """
    세션 삭제 (임시 데이터 모두 삭제)
    
    Args:
        session_id: 세션 ID
        
    Returns:
        DeleteResponse: 확인 메시지
    """
    try:
        # 세션 존재 여부 확인
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # Ephemeral RAG 데이터 삭제 (JSON 폴더)
        ephemeral_rag = EphemeralRAG(session_id=session_id)
        ephemeral_rag.delete_session_data()
        
        # 세션 매니저에서 삭제
        session_manager.delete_session(session_id)
        
        return DeleteResponse(message="세션이 삭제되었습니다.")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 삭제 실패: {str(e)}")


# ============================================================
# 아이디어 저장/조회 API (새로 추가)
# ============================================================

from fastapi import Depends
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.domain.user.models import User
from app.domain.auth.dependencies import get_current_user
from app.domain.brainstorming.ideasave.service import IdeaSaveService
from app.domain.brainstorming.ideasave.schemas import (
    IdeaCreate, 
    IdeaResponse as SavedIdeaResponse,  # DB용 스키마는 별칭 사용
    IdeaListResponse
)

idea_save_service = IdeaSaveService()


@router.post("/ideas", response_model=SavedIdeaResponse, status_code=201)
async def save_idea(
    idea: IdeaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    브레인스토밍 아이디어 저장
    
    Args:
        idea: 아이디어 데이터 (title, description)
        current_user: 현재 로그인한 사용자
        db: DB 세션
        
    Returns:
        SavedIdeaResponse: 저장된 아이디어
    """
    try:
        saved_idea = idea_save_service.save_idea(
            db=db,
            user_id=current_user.id,
            idea_data=idea
        )
        return saved_idea
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"아이디어 저장 실패: {str(e)}")


@router.get("/ideas", response_model=IdeaListResponse)
async def get_my_ideas(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    내 아이디어 목록 조회 (최신순)
    
    Args:
        limit: 최대 개수 (기본값: 100)
        offset: 시작 위치 (기본값: 0)
        current_user: 현재 로그인한 사용자
        db: DB 세션
        
    Returns:
        IdeaListResponse: {"total": int, "ideas": List[IdeaResponse]}
    """
    try:
        result = idea_save_service.get_user_ideas(
            db=db,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"아이디어 목록 조회 실패: {str(e)}")


@router.get("/ideas/{idea_id}", response_model=SavedIdeaResponse)
async def get_idea_detail(
    idea_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    아이디어 상세 조회
    
    Args:
        idea_id: 아이디어 ID
        current_user: 현재 로그인한 사용자
        db: DB 세션
        
    Returns:
        SavedIdeaResponse: 아이디어 상세 정보
    """
    try:
        idea = idea_save_service.get_idea_by_id(
            db=db,
            idea_id=idea_id,
            user_id=current_user.id
        )
        
        if not idea:
            raise HTTPException(status_code=404, detail="아이디어를 찾을 수 없거나 권한이 없습니다.")
        
        return idea
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"아이디어 조회 실패: {str(e)}")


@router.delete("/ideas/{idea_id}")
async def delete_idea(
    idea_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    아이디어 삭제
    
    Args:
        idea_id: 아이디어 ID
        current_user: 현재 로그인한 사용자
        db: DB 세션
        
    Returns:
        Dict: {"message": "삭제되었습니다."}
    """
    try:
        success = idea_save_service.delete_idea(
            db=db,
            idea_id=idea_id,
            user_id=current_user.id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="아이디어를 찾을 수 없거나 권한이 없습니다.")
        
        return {"message": "아이디어가 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"아이디어 삭제 실패: {str(e)}")
