"""
Monthly Report API

Generates monthly reports from aggregated daily/weekly data.
"""
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.domain.auth.dependencies import get_current_user_optional
from app.domain.report.common.schemas import ReportEnvelope, ReportMeta, ReportPeriod
from app.domain.report.core.canonical_models import CanonicalReport
from app.domain.report.monthly.chain import generate_monthly_report
from app.domain.report.monthly.repository import MonthlyReportRepository
from app.domain.report.monthly.schemas import (
    MonthlyReportCreate,
    MonthlyReportListResponse,
    MonthlyReportResponse,
)
from app.domain.user.models import User
from app.infrastructure.database.session import get_db
from app.reporting.html_renderer import render_report_html


router = APIRouter(prefix="/monthly", tags=["monthly_report"])


class MonthlyReportGenerateRequest(BaseModel):
    """Request body for monthly report generation."""
    year: int = Field(..., description="Year")
    month: int = Field(..., description="Month (1~12)")


class MonthlyReportGenerateResponse(BaseModel):
    """Response body for monthly report generation."""
    role: str = "assistant"
    type: str = "monthly_report"
    message: str
    period: dict | None = None
    report_data: dict | None = None
    owner: str | None = None
    success: bool = True
    report: CanonicalReport | None = None
    envelope: ReportEnvelope


@router.post("/generate", response_model=MonthlyReportGenerateResponse)
async def generate_monthly(
    request: MonthlyReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    Generate a monthly report and store it.
    
    인증 비활성화: current_user가 없어도 동작합니다.
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        resolved_owner = current_user.name if current_user and current_user.name else "사용자"

        # ReportGenerationAgent 사용
        from multi_agent.tools.report_tools import get_report_generation_agent
        
        generation_agent = get_report_generation_agent()
        report = generation_agent.generate_monthly_report(
            db=db,
            owner=resolved_owner,
            year=request.year,
            month=request.month,
            display_name=resolved_owner
        )

        report_dict = report.model_dump(mode="json")
        # owner는 상수로 사용 (실제 사용자 이름과 분리)
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        report_create = MonthlyReportCreate(
            owner=REPORT_OWNER,  # 상수 owner 사용
            period_start=report.period_start,
            period_end=report.period_end,
            report_json=report_dict
        )

        db_report, is_created = MonthlyReportRepository.create_or_update(
            db, report_create
        )

        action = "생성" if is_created else "업데이트"
        print(f"Monthly report saved ({action}): {report.owner} - {report.period_start}~{report.period_end}")

        html_path = None
        html_url = None
        html_filename = None
        try:
            # KPI 데이터는 이미 report 객체에 저장되어 있음 (chain.py에서 계산됨)
            # report 객체에서 kpi_data 추출
            kpi_data = getattr(report, '_kpi_data', None)
            
            # kpi_data가 없으면 직접 계산 (fallback)
            if not kpi_data:
                from app.domain.report.monthly.kpi_calculator import calculate_monthly_kpi
                kpi_data = calculate_monthly_kpi(db=db, year=request.year, month=request.month)
                print(f"[WARN] report 객체에 kpi_data가 없어서 직접 계산: new_contracts={kpi_data.get('new_contracts', 0)}, renewals={kpi_data.get('renewals', 0)}, consultations={kpi_data.get('consultations', 0)}")
            else:
                print(f"[INFO] report 객체에서 KPI 데이터 사용: new_contracts={kpi_data.get('new_contracts', 0)}, renewals={kpi_data.get('renewals', 0)}, consultations={kpi_data.get('consultations', 0)}")
            
            # HTML 보고서에 표시할 이름 전달
            html_path = render_report_html(
                report_type="monthly",
                data=report.model_dump(mode="json"),
                output_filename=f"monthly_report_{resolved_owner}_{report.period_start}.html",
                display_name=resolved_owner,  # HTML 보고서에 표시할 이름
                kpi_data=kpi_data  # 카테고리 기반으로 계산된 KPI 데이터 전달
            )

            html_filename = html_path.name
            html_url = f"/static/reports/monthly/{quote(html_filename)}"
            print(f"Monthly report HTML generated: {html_path}")
        except Exception as html_error:
            print(f"HTML generation failed (report saved): {str(html_error)}")

        done_tasks = 0
        if report.monthly and report.monthly.weekly_summaries:
            for week_key, week_tasks in report.monthly.weekly_summaries.items():
                if isinstance(week_tasks, list):
                    done_tasks += len(week_tasks)

        return MonthlyReportGenerateResponse(
            role="assistant",
            type="monthly_report",
            message=f"월간 보고서 {action}되었습니다.",
            period={
                "start": str(report.period_start),
                "end": str(report.period_end),
                "done_tasks": done_tasks
            },
            report_data={
                "url": html_url,
                "file_name": html_filename
            } if html_url else None,
            owner=report.owner,
            success=True,
            report=report,
            envelope=ReportEnvelope(
                meta=ReportMeta(
                    owner=report.owner,
                    period=ReportPeriod(start=str(report.period_start), end=str(report.period_end)),
                    report_type="monthly",
                    report_id=str(report.report_id) if getattr(report, "report_id", None) else None,
                ),
                data=report.model_dump(mode="json"),
                html={"url": html_url, "file_name": html_filename} if html_url else None,
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"월간 보고서 생성 실패: {str(e)}")


@router.get("/list/{owner}", response_model=MonthlyReportListResponse)
async def list_monthly_reports(
    owner: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List monthly reports for an owner.
    """
    try:
        reports = MonthlyReportRepository.list_by_owner(db, owner, skip, limit)
        total = MonthlyReportRepository.count_by_owner(db, owner)

        report_responses = [MonthlyReportResponse(**report.to_dict()) for report in reports]

        return MonthlyReportListResponse(
            total=total,
            reports=report_responses
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok", "service": "monthly_report"}
