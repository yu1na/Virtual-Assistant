"""
Daily Report API

시간대별 일일보고서 입력 API

Author: AI Assistant
Created: 2025-11-18
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from pathlib import Path
import os

from app.domain.report.daily.session_manager import get_session_manager
from app.domain.report.daily.main_tasks_store import get_main_tasks_store
from app.domain.report.daily.repository import DailyReportRepository
from app.domain.report.core.canonical_models import CanonicalReport
from app.infrastructure.database.session import get_db
from app.reporting.html_renderer import render_report_html
from app.domain.report.core.chunker import chunk_canonical_report
from app.domain.report.core.embedding_pipeline import EmbeddingPipeline
from app.infrastructure.vector_store_report import get_report_vector_store
from app.domain.report.common.schemas import ReportMeta, ReportPeriod, ReportEnvelope
from app.domain.auth.dependencies import get_current_user_optional
from app.domain.user.models import User
from app.core.config import settings
from urllib.parse import quote

# 보고서 owner는 상수로 사용 (실제 사용자 이름과 분리)
REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER


router = APIRouter(prefix="/daily", tags=["daily"])


# 요청/응답 스키마
class DailyStartRequest(BaseModel):
    """일일보고서 작성 시작 요청"""
    target_date: date = Field(..., description="보고서 날짜")
    time_ranges: List[str] = Field(
        default_factory=list,
        description="시간대 목록 (비어있으면 자동 생성)"
    )


class DailyStartResponse(BaseModel):
    """일일보고서 작성 시작 응답"""
    status: str = Field(default="in_progress", description="항상 in_progress")
    session_id: str
    question: str
    meta: Dict[str, Any] = Field(default_factory=dict, description="메타 정보")


class DailyAnswerRequest(BaseModel):
    """답변 입력 요청"""
    session_id: str = Field(..., description="세션 ID")
    answer: str = Field(..., description="사용자 답변")


class DailyAnswerResponse(BaseModel):
    """답변 입력 응답"""
    status: str = Field(..., description="in_progress 또는 finished")
    session_id: str
    question: Optional[str] = Field(None, description="다음 질문 (finished 시 None)")
    message: Optional[str] = Field(None, description="완료 메시지 (finished 시)")
    meta: Optional[Dict[str, Any]] = Field(None, description="메타 정보")
    report: Optional[CanonicalReport] = Field(None, description="완료 시 보고서")
    # 구조화된 응답 (finished 시)
    role: Optional[str] = Field(None, description="assistant")
    type: Optional[str] = Field(None, description="daily_report")
    period: Optional[Dict[str, Any]] = Field(None, description="기간 정보")
    report_data: Optional[Dict[str, Any]] = Field(None, description="보고서 데이터 (html_url 포함)")
    envelope: Optional[ReportEnvelope] = Field(None, description="통합 보고서 래퍼 (신규)")


@router.post("/start", response_model=DailyStartResponse)
async def start_daily_report(
    request: DailyStartRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    일일보고서 작성 시작
    
    저장소에서 금일 진행 업무(main_tasks)를 자동으로 불러와서
    FSM 세션을 시작하고, 첫 번째 시간대 질문을 반환합니다.
    
    main_tasks는 /select_main_tasks로 미리 저장되어 있어야 합니다.
    인증 비활성화: current_user가 없어도 동작합니다.
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        owner = current_user.name if current_user and current_user.name else "사용자"
        
        # ReportGenerationAgent 사용
        from multi_agent.tools.report_tools import get_report_generation_agent
        
        generation_agent = get_report_generation_agent()
        result = generation_agent.start_daily_report(
            owner=owner,
            target_date=request.target_date,
            time_ranges=request.time_ranges,
            db=db
        )
        
        return DailyStartResponse(
            status="in_progress",
            session_id=result["session_id"],
            question=result["question"],
            meta=result["meta"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 시작 실패: {str(e)}")


@router.post("/answer", response_model=DailyAnswerResponse)
async def answer_daily_question(
    request: DailyAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    시간대 질문에 답변
    
    사용자의 답변을 받아서 다음 질문을 반환하거나,
    모든 시간대가 완료되면 최종 보고서를 반환합니다.
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        owner = current_user.name if current_user and current_user.name else "사용자"
        
        # ReportGenerationAgent 사용
        from multi_agent.tools.report_tools import get_report_generation_agent
        
        generation_agent = get_report_generation_agent()
        result = generation_agent.answer_daily_question(
            session_id=request.session_id,
            answer=request.answer,
            owner=owner,
            db=db
        )
        
        if result["status"] == "finished":
            # 완료된 경우
            report = result["report"]
            html_url = result["html_url"]
            html_filename = result["html_filename"]
            
            # 세션 삭제
            session_manager = get_session_manager()
            session_manager.delete_session(request.session_id)
            
            # 벡터 DB 저장 (API에서 처리)
            try:
                print(f"⏳ 벡터 DB 저장 시작...")
                
                chunks = chunk_canonical_report(report)
                
                if chunks:
                    # 메타데이터 정리 (None 값 제거)
                    for chunk in chunks:
                        metadata = chunk["metadata"]
                        metadata_cleaned = {k: v for k, v in metadata.items() if v is not None}
                        chunk["metadata"] = metadata_cleaned
                    
                    # 임베딩 생성 및 저장
                    vector_store = get_report_vector_store()
                    embedding_pipeline = EmbeddingPipeline(vector_store=vector_store)
                    
                    result_vector = embedding_pipeline.process_and_store(chunks, batch_size=50)
                    
                    collection = embedding_pipeline.vector_store.get_collection()
                    print(f"✅ 벡터 DB 저장 완료: {result_vector['chunks_processed']}개 청크 (collection: reports, total={collection.count()})")
                else:
                    print(f"⚠️  청크가 생성되지 않음 (벡터 DB 저장 건너뜀)")
            
            except Exception as vector_error:
                print(f"⚠️  벡터 DB 저장 실패 (보고서는 저장됨): {str(vector_error)}")
            
            # 완료된 업무 수 계산
            done_tasks = len(report.daily.detail_tasks) if report.daily and report.daily.detail_tasks else 0
            
            return DailyAnswerResponse(
                status="finished",
                session_id=request.session_id,
                message="모든 시간대 입력이 완료되었습니다. 오늘 일일보고서를 정리했어요.",
                report=report,
                role="assistant",
                type="daily_report",
                period={
                    "start": str(report.period_start),
                    "end": str(report.period_end),
                    "done_tasks": done_tasks
                },
                report_data={
                    "url": html_url,
                    "file_name": html_filename
                } if html_url else None,
                envelope=ReportEnvelope(
                    meta=ReportMeta(
                        owner=REPORT_OWNER,
                        period=ReportPeriod(start=str(report.period_start), end=str(report.period_end)),
                        report_type="daily",
                        report_id=str(report.report_id) if getattr(report, "report_id", None) else None,
                    ),
                    data=report.model_dump(mode="json"),
                    html={"url": html_url, "file_name": html_filename} if html_url else None,
                )
            )
        else:
            # 진행 중
            return DailyAnswerResponse(
                status="in_progress",
                session_id=request.session_id,
                question=result["question"],
                meta=result["meta"]
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"답변 처리 실패: {str(e)}")


class SelectMainTasksRequest(BaseModel):
    """금일 진행 업무 선택 요청"""
    target_date: date = Field(..., description="보고서 날짜")
    main_tasks: List[Dict[str, Any]] = Field(
        ...,
        description="선택된 금일 진행 업무 리스트"
    )
    append: bool = Field(
        default=False,
        description="True면 기존 업무에 추가, False면 덮어쓰기"
    )


class SelectMainTasksResponse(BaseModel):
    """금일 진행 업무 선택 응답"""
    success: bool
    message: str
    saved_count: int


@router.post("/select_main_tasks", response_model=SelectMainTasksResponse)
async def select_main_tasks(
    request: SelectMainTasksRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    금일 진행 업무 선택 및 저장
    
    사용자가 TodayPlan Chain에서 추천받은 업무 중 
    실제로 수행할 업무를 선택하여 저장합니다.
    
    저장된 업무는:
    1. 메모리에 임시 저장 (FSM 시작 시 사용)
    2. PostgreSQL에 부분 저장 (금일 진행 업무만, status="in_progress")
    
    로그인한 사용자 이름을 owner로 사용합니다.
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        owner = current_user.name if current_user and current_user.name else "사용자"
        if not request.main_tasks:
            raise HTTPException(
                status_code=400,
                detail="최소 1개 이상의 업무를 선택해주세요."
            )
        
        # 최대 3개까지만 저장 가능
        if len(request.main_tasks) > 3:
            raise HTTPException(
                status_code=400,
                detail="금일 진행 업무는 최대 3개까지만 저장할 수 있습니다."
            )
        
        # 항상 덮어쓰기 (append 모드 무시)
        final_tasks = request.main_tasks[:3]  # 최대 3개까지만
        
        # 1. 메모리 저장 (FSM용) - 항상 덮어쓰기
        store = get_main_tasks_store()
        store.save(
            owner=owner,  # 로그인한 사용자 이름 사용
            target_date=request.target_date,
            main_tasks=final_tasks,
            append=False  # 항상 덮어쓰기
        )
        
        # 2. PostgreSQL에 부분 저장 (금일 진행 업무만) - 항상 덮어쓰기
        try:
            # 기존 보고서 확인 (owner는 상수로 사용)
            existing_report = DailyReportRepository.get_by_owner_and_date(
                db, REPORT_OWNER, request.target_date
            )
            
            if existing_report:
                # 기존 보고서가 있으면 tasks만 업데이트 (항상 덮어쓰기)
                report_json = existing_report.report_json.copy()
                report_json["tasks"] = final_tasks  # 항상 덮어쓰기
                
                report_json["metadata"] = report_json.get("metadata", {})
                report_json["metadata"]["status"] = "in_progress"
                
                from app.domain.report.daily.schemas import DailyReportUpdate
                DailyReportRepository.update(
                    db,
                    existing_report,
                    DailyReportUpdate(report_json=report_json)
                )
                print(f"💾 금일 진행 업무 업데이트 완료: {owner} - {request.target_date}")
            else:
                # 새로운 부분 보고서 생성
                partial_report = {
                    "report_type": "daily",
                    "owner": REPORT_OWNER,  # 상수 owner 사용
                    "period_start": request.target_date.isoformat(),
                    "period_end": request.target_date.isoformat(),
                    "tasks": final_tasks,  # 최대 3개까지만
                    "kpis": [],
                    "issues": [],
                    "plans": [],
                    "metadata": {"status": "in_progress", "main_tasks_only": True}
                }
                
                DailyReportRepository.create(
                    db,
                    DailyReportCreate(
                        owner=REPORT_OWNER,  # 상수 owner 사용
                        report_date=request.target_date,
                        report_json=partial_report
                    )
                )
                print(f"💾 금일 진행 업무 생성 완료: {owner} - {request.target_date}")
        
        except Exception as db_error:
            print(f"⚠️  PostgreSQL 저장 실패 (메모리 저장은 성공): {str(db_error)}")
            # DB 저장 실패해도 메모리 저장은 성공했으므로 계속 진행
        
        return SelectMainTasksResponse(
            success=True,
            message="금일 진행 업무가 저장되었습니다.",
            saved_count=len(final_tasks)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"업무 저장 실패: {str(e)}"
        )


class GetMainTasksRequest(BaseModel):
    """금일 진행 업무 조회 요청"""
    target_date: date = Field(..., description="보고서 날짜")


class GetMainTasksResponse(BaseModel):
    """금일 진행 업무 조회 응답"""
    success: bool
    main_tasks: List[Dict[str, Any]]
    count: int


@router.post("/get_main_tasks", response_model=GetMainTasksResponse)
async def get_main_tasks(
    request: GetMainTasksRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    저장된 금일 진행 업무 조회
    
    인증 비활성화: current_user가 없어도 동작합니다.
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        owner = current_user.name if current_user and current_user.name else "사용자"
        
        store = get_main_tasks_store()
        main_tasks = store.get(
            owner=owner,  # 로그인한 사용자 이름 사용
            target_date=request.target_date
        )
        
        if main_tasks is None:
            main_tasks = []
        
        return GetMainTasksResponse(
            success=True,
            main_tasks=main_tasks,
            count=len(main_tasks)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"업무 조회 실패: {str(e)}"
        )


class UpdateMainTasksRequest(BaseModel):
    """금일 진행 업무 수정 요청"""
    target_date: date = Field(..., description="보고서 날짜")
    main_tasks: List[Dict[str, Any]] = Field(
        ...,
        description="수정된 금일 진행 업무 리스트"
    )


class UpdateMainTasksResponse(BaseModel):
    """금일 진행 업무 수정 응답"""
    success: bool
    message: str
    updated_count: int


@router.put("/update_main_tasks", response_model=UpdateMainTasksResponse)
async def update_main_tasks(
    request: UpdateMainTasksRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    금일 진행 업무 수정
    
    저장된 금일 진행 업무를 수정합니다.
    - 메모리 (MainTasksStore) 업데이트
    - PostgreSQL 업데이트 (tasks 필드만)
    
    인증 비활성화: current_user가 없어도 동작합니다.
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        owner = current_user.name if current_user and current_user.name else "사용자"

        if not request.main_tasks:
            raise HTTPException(
                status_code=400,
                detail="최소 1개 이상의 업무가 필요합니다."
            )
        
        # 1. 메모리 업데이트
        store = get_main_tasks_store()
        store.save(
            owner=owner,  # 로그인한 사용자 이름 사용
            target_date=request.target_date,
            main_tasks=request.main_tasks,
            append=False  # 덮어쓰기
        )
        
        # 2. PostgreSQL 업데이트
        try:
            existing_report = DailyReportRepository.get_by_owner_and_date(
                db, REPORT_OWNER, request.target_date  # 상수 owner 사용
            )
            
            if existing_report:
                # tasks 필드만 업데이트
                report_json = existing_report.report_json.copy()
                report_json["tasks"] = request.main_tasks
                
                # status는 유지 (in_progress 또는 completed)
                if "metadata" not in report_json:
                    report_json["metadata"] = {}
                
                from app.domain.report.daily.schemas import DailyReportUpdate
                DailyReportRepository.update(
                    db,
                    existing_report,
                    DailyReportUpdate(report_json=report_json)
                )
                print(f"💾 금일 진행 업무 수정 완료 (DB): {REPORT_OWNER} - {request.target_date}")
            else:
                # 보고서가 없으면 새로 생성
                partial_report = {
                    "report_type": "daily",
                    "owner": REPORT_OWNER,  # 상수 owner 사용
                    "period_start": request.target_date.isoformat(),
                    "period_end": request.target_date.isoformat(),
                    "tasks": request.main_tasks,
                    "kpis": [],
                    "issues": [],
                    "plans": [],
                    "metadata": {"status": "in_progress", "main_tasks_only": True}
                }
                
                DailyReportRepository.create(
                    db,
                    DailyReportCreate(
                        owner=REPORT_OWNER,  # 상수 owner 사용
                        report_date=request.target_date,
                        report_json=partial_report
                    )
                )
                print(f"💾 금일 진행 업무 생성 완료 (DB): {owner} - {request.target_date}")
        
        except Exception as db_error:
            print(f"⚠️  PostgreSQL 업데이트 실패 (메모리는 성공): {str(db_error)}")
            # DB 실패해도 메모리는 성공했으므로 계속 진행
        
        return UpdateMainTasksResponse(
            success=True,
            message="금일 진행 업무가 수정되었습니다.",
            updated_count=len(request.main_tasks)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"업무 수정 실패: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok", "service": "daily"}
