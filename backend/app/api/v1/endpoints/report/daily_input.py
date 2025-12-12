"""
Daily Input API

태그 기반 일일보고서 입력 API

Author: AI Assistant
Created: 2025-12-10
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List
from datetime import date
from sqlalchemy.orm import Session
import uuid
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.domain.report.daily.repository import DailyReportRepository
from app.domain.report.core.canonical_models import (
    CanonicalReport,
    CanonicalDaily,
    DetailTask
)
from app.infrastructure.database.session import get_db
from app.reporting.html_renderer import render_report_html
from app.domain.report.core.chunker import chunk_canonical_report
from app.domain.report.core.embedding_pipeline import EmbeddingPipeline
from app.infrastructure.vector_store_report import get_report_vector_store
from app.domain.report.common.schemas import ReportMeta, ReportPeriod, ReportEnvelope
from app.domain.auth.dependencies import get_current_user_optional
from app.domain.user.models import User
from app.core.config import settings
from pathlib import Path

router = APIRouter(prefix="/reports/daily", tags=["daily-input"])

# 보고서 owner는 상수로 사용
REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER


def classify_task(text: str) -> str:
    """
    업무 텍스트를 카테고리로 분류
    
    카테고리:
    - 상담
    - 신규 계약
    - 유지 계약
    - 청구/사고 처리
    - 문서 작성
    - 기타
    
    Args:
        text: 업무 텍스트
        
    Returns:
        카테고리 문자열
    """
    t = text.replace(" ", "")

    if any(k in t for k in ["신규", "리드", "청약", "가입"]):
        return "신규 계약"

    if any(k in t for k in ["보장점검", "갱신", "전환", "유지", "미납", "기존고객"]):
        return "유지 계약"

    if any(k in t for k in ["실손", "청구", "사고", "보험금", "검사비"]):
        return "청구/사고 처리"

    if any(k in t for k in ["리포트", "작성", "제안서", "자료", "문서"]):
        return "문서 작성"

    if any(k in t for k in ["상담", "문의", "콜백", "설명", "니즈"]):
        return "상담"

    return "기타"


def expand_task_description(task_text: str, category: str) -> str:
    """
    LLM을 사용해 간단한 업무 텍스트를 보고서에 적합한 문장으로 확장
    
    Args:
        task_text: 사용자가 입력한 간단한 업무 텍스트
        category: 업무 카테고리
        
    Returns:
        확장된 업무 설명 (1-2문장)
    """
    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=settings.OPENAI_API_KEY
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 보험설계사의 일일 업무 보고서를 작성하는 어시스턴트입니다.
사용자가 간단하게 입력한 업무 내용을 보고서에 적합한 1-2문장의 명확한 문장으로 확장해주세요.

규칙:
1. 업무 카테고리를 참고하여 맥락에 맞게 작성
2. 1-2문장으로 간결하게 작성 (너무 길지 않게)
3. 존댓말 사용하지 않고 보고서 어투로 작성 ("~함", "~함." 등)
4. 구체적인 정보가 없으면 일반적인 업무 내용으로 작성
5. 입력 텍스트의 핵심 의미를 유지하되, 보고서답게 표현

예시:
입력: "연말 상담 일정 정리"
출력: "연말을 대비해 고객 상담 일정을 정리함."

입력: "신규 고객 미팅"
출력: "신규 고객과 보험 상품 안내를 위한 미팅을 진행함."

입력: "보장분석"
출력: "기존 고객의 보험 보장 내용을 분석하고 추가 보장이 필요한 부분을 파악함."
"""),
            ("user", "업무 카테고리: {category}\n입력: {task_text}\n출력:")
        ])
        
        chain = prompt | llm
        response = chain.invoke({
            "category": category,
            "task_text": task_text
        })
        
        expanded = response.content.strip()
        
        # 응답이 너무 길면 첫 2문장만 사용
        sentences = expanded.split('.')
        if len(sentences) > 2:
            expanded = '.'.join(sentences[:2]) + '.'
        
        return expanded if expanded else task_text
        
    except Exception as e:
        print(f"⚠️  업무 내용 확장 실패: {str(e)}")
        # LLM 호출 실패 시 원본 반환
        return task_text


class DailyInputRequest(BaseModel):
    """일일보고서 입력 요청"""
    model_config = {"populate_by_name": True}
    
    report_date: date = Field(..., description="보고서 날짜", alias="date")
    owner_id: int = Field(..., description="사용자 ID")
    tasks: List[str] = Field(..., description="업무 목록")


class DailyInputResponse(BaseModel):
    """일일보고서 입력 응답"""
    success: bool
    message: str
    report_id: str
    report_url: str = ""  # 자동 열기 방지를 위해 기본값 빈 문자열


@router.post("/input", response_model=DailyInputResponse)
async def submit_daily_input(
    request: DailyInputRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    태그 기반 일일보고서 입력
    
    입력된 업무 목록을 카테고리로 분류하고,
    CanonicalDailyReport로 변환하여 저장합니다.
    """
    try:
        # 사용자 정보 확인 및 display_name 결정 (주간보고서와 동일한 구조)
        # 주간보고서: resolved_owner = current_user.name if current_user and current_user.name else "사용자"
        resolved_owner = current_user.name if current_user and current_user.name else "사용자"
        
        # 업무 목록이 비어있으면 에러
        if not request.tasks:
            raise HTTPException(
                status_code=400,
                detail="업무 목록이 비어있습니다."
            )
        
        # 카테고리 분류 및 DetailTask 생성 (LLM으로 상세내용 확장)
        detail_tasks = []
        for task in request.tasks:
            if not task.strip():
                continue
            
            category = classify_task(task)
            # LLM으로 상세내용 확장
            expanded_text = expand_task_description(task.strip(), category)
            
            detail_tasks.append(DetailTask(
                time_start=None,
                time_end=None,
                text=expanded_text,
                note=f"카테고리: {category}"
            ))
        
        # CanonicalDaily 생성 (주간보고서와 동일한 구조)
        # 주간보고서: header["성명"] = actual_display_name (display_name or owner)
        canonical_daily = CanonicalDaily(
            header={
                "작성일자": request.report_date.isoformat(),
                "성명": resolved_owner  # 주간보고서와 동일: resolved_owner 사용
            },
            todo_tasks=request.tasks,  # Summary: 입력된 업무 그대로
            detail_tasks=detail_tasks,  # Detail: 카테고리 포함
            pending=[],  # 빈 값
            plans=[],  # 빈 값
            notes="",  # 빈 값
            summary=""  # 빈 값
        )
        
        # DB 저장 (먼저 기존 보고서 확인)
        from app.domain.report.daily.schemas import DailyReportCreate
        existing_report = DailyReportRepository.get_by_owner_and_date(
            db, REPORT_OWNER, request.report_date
        )
        
        # CanonicalReport 생성 (DB ID는 저장 후 설정)
        canonical_report = CanonicalReport(
            report_id="",  # DB 저장 후 실제 ID로 업데이트
            report_type="daily",
            owner=REPORT_OWNER,  # 상수 owner 사용
            period_start=request.report_date,
            period_end=request.report_date,
            daily=canonical_daily
        )
        
        # DB 저장 및 커밋 확인
        try:
            if existing_report:
                # 기존 보고서 업데이트
                from app.domain.report.daily.schemas import DailyReportUpdate
                # report_id를 DB의 실제 ID로 설정
                canonical_report.report_id = str(existing_report.id)
                updated_report = DailyReportRepository.update(
                    db,
                    existing_report,
                    DailyReportUpdate(report_json=canonical_report.model_dump(mode='json'))
                )
                report_id = str(updated_report.id)  # DB의 실제 ID 사용
                print(f"💾 일일보고서 업데이트 완료: {REPORT_OWNER} - {request.report_date}, report_id: {report_id}")
            else:
                # 새 보고서 생성
                created_report = DailyReportRepository.create(
                    db,
                    DailyReportCreate(
                        owner=REPORT_OWNER,
                        report_date=request.report_date,
                        report_json=canonical_report.model_dump(mode='json')
                    )
                )
                report_id = str(created_report.id)  # DB의 실제 ID 사용
                # 생성된 report_id를 canonical_report에 반영 (다음 저장 시 사용)
                canonical_report.report_id = report_id
                print(f"💾 일일보고서 생성 완료: {REPORT_OWNER} - {request.report_date}, report_id: {report_id}")
            
            # DB 커밋 확인 (Repository에서 이미 commit하지만, 명시적으로 확인)
            db.commit()
            print(f"✅ DB 커밋 확인 완료: report_id={report_id}")
        except Exception as db_error:
            db.rollback()
            print(f"❌ DB 저장 실패: {str(db_error)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"일일보고서 저장 중 데이터베이스 오류가 발생했습니다: {str(db_error)}"
            )
        
        # ChromaDB 저장 (청크 생성 및 임베딩)
        try:
            vector_store = get_report_vector_store()
            embedding_pipeline = EmbeddingPipeline(
                vector_store=vector_store
            )
            
            # 청크 생성 및 저장
            chunks = chunk_canonical_report(canonical=canonical_report)
            if chunks:
                embedding_pipeline.process_and_store(chunks)
            print(f"✅ ChromaDB 저장 완료: {request.report_date}")
        except Exception as e:
            print(f"⚠️  ChromaDB 저장 실패 (DB 저장은 성공): {str(e)}")
            # ChromaDB 저장 실패해도 DB 저장은 성공했으므로 계속 진행
        
        # HTML 생성 (주간보고서와 동일한 구조)
        try:
            # 주간보고서: display_name=resolved_owner 전달
            html_path = render_report_html(
                report_type="daily",
                data=canonical_report.model_dump(mode='json'),
                output_filename=None,
                display_name=resolved_owner  # 주간보고서와 동일: resolved_owner 전달
            )
            
            # URL 생성
            report_url = f"/static/reports/daily/{html_path.name}"
            print(f"✅ HTML 생성 완료: {html_path}")
        except Exception as e:
            print(f"⚠️  HTML 생성 실패: {str(e)}")
            report_url = ""
        
        return DailyInputResponse(
            success=True,
            message="일일보고서가 저장되었습니다.",
            report_id=report_id,
            report_url=""  # 자동 열기 방지를 위해 빈 문자열로 설정
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"일일보고서 저장 실패: {str(e)}"
        )


class DailyNotesUpdate(BaseModel):
    """일일보고서 특이사항 업데이트 요청"""
    notes: str = Field(..., description="특이사항")


@router.patch("/{report_id}/notes", response_model=DailyInputResponse)
async def update_daily_notes(
    report_id: str,
    request: DailyNotesUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    일일보고서 특이사항 업데이트
    
    Args:
        report_id: 보고서 UUID
        request: 특이사항 내용
        db: 데이터베이스 세션
        
    Returns:
        업데이트된 보고서 정보
    """
    try:
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        
        # 보고서 조회
        try:
            import uuid
            report_uuid = uuid.UUID(report_id)
            report = DailyReportRepository.get_by_id(db, report_uuid)
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=404,
                detail=f"보고서를 찾을 수 없습니다. (report_id={report_id})"
            )
        
        if not report or not report.report_json:
            raise HTTPException(
                status_code=404,
                detail=f"보고서 데이터를 찾을 수 없습니다."
            )
        
        # CanonicalReport 객체 생성
        canonical_report = CanonicalReport(**report.report_json)
        
        # 특이사항 업데이트
        if canonical_report.daily:
            canonical_report.daily.notes = request.notes
        
        # DB 업데이트
        from app.domain.report.daily.schemas import DailyReportUpdate
        DailyReportRepository.update(
            db,
            report,
            DailyReportUpdate(report_json=canonical_report.model_dump(mode='json'))
        )
        
        # HTML 재생성 (주간보고서와 동일한 구조)
        # 사용자 정보 확인 및 display_name 결정
        resolved_owner = current_user.name if current_user and current_user.name else "사용자"
        
        report_url = ""
        try:
            html_path = render_report_html(
                report_type="daily",
                data=canonical_report.model_dump(mode='json'),
                output_filename=None,
                display_name=resolved_owner  # 주간보고서와 동일: resolved_owner 사용
            )
            report_url = f"/static/reports/daily/{html_path.name}"
        except Exception as e:
            print(f"⚠️  HTML 재생성 실패: {str(e)}")
        
        return DailyInputResponse(
            success=True,
            message="특이사항이 업데이트되었습니다.",
            report_id=report_id,
            report_url=report_url
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"특이사항 업데이트 실패: {str(e)}"
        )

