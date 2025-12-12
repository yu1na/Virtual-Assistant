"""
Weekly Report API

Generates weekly reports from daily data.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import date
from sqlalchemy.orm import Session

from app.domain.report.weekly.chain import generate_weekly_report
from app.domain.report.weekly.repository import WeeklyReportRepository
from app.domain.report.weekly.schemas import WeeklyReportCreate, WeeklyReportResponse, WeeklyReportListResponse
from app.domain.report.core.canonical_models import CanonicalReport
from app.domain.report.common.schemas import ReportMeta, ReportPeriod, ReportEnvelope
from app.infrastructure.database.session import get_db
from app.reporting.html_renderer import render_report_html
from app.domain.auth.dependencies import get_current_user_optional
from app.domain.user.models import User
from urllib.parse import quote


router = APIRouter(prefix="/weekly", tags=["weekly_report"])


class WeeklyReportGenerateRequest(BaseModel):
    """Request body for weekly report generation."""
    target_date: date = Field(..., description="Any date within the target week")


class WeeklyReportGenerateResponse(BaseModel):
    """Response body for weekly report generation."""
    role: str = "assistant"
    type: str = "weekly_report"
    message: str
    period: dict | None = None
    report_data: dict | None = None
    owner: str | None = None
    success: bool = True
    report: CanonicalReport | None = None
    envelope: ReportEnvelope


@router.post("/generate", response_model=WeeklyReportGenerateResponse)
async def generate_weekly(
    request: WeeklyReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional)
):
    """
    Generate a weekly report and store it.
    
    인증 비활성화: current_user가 없어도 동작합니다.
    """
    try:
        # 사용자 이름 결정: current_user 우선, 없으면 report 생성 후 확인
        # 일일보고서와 동일하게 처리 (get_current_user 사용 권장)
        if current_user and current_user.name:
            resolved_owner = current_user.name
        else:
            # current_user가 없으면 일단 "사용자"로 설정하고, 
            # report 생성 후 실제 이름이 있는지 확인
            resolved_owner = "사용자"

        # ReportGenerationAgent 사용
        from multi_agent.tools.report_tools import get_report_generation_agent
        
        generation_agent = get_report_generation_agent()
        report = generation_agent.generate_weekly_report(
            db=db,
            owner=resolved_owner,
            target_date=request.target_date,
            display_name=resolved_owner
        )

        # report 생성 후 실제 사용자 이름 확인 (report.weekly.header의 성명 우선)
        if report.weekly and report.weekly.header and report.weekly.header.get("성명"):
            actual_name = report.weekly.header.get("성명")
            if actual_name and actual_name != "사용자":
                resolved_owner = actual_name
        elif current_user and current_user.name:
            # current_user가 있으면 사용
            resolved_owner = current_user.name

        # report의 owner와 header 성명을 실제 사용자 이름으로 업데이트
        if report.owner != resolved_owner:
            report_dict = report.model_dump(mode="json")
            report_dict["owner"] = resolved_owner
            if "weekly" in report_dict and "header" in report_dict["weekly"]:
                report_dict["weekly"]["header"]["성명"] = resolved_owner

        report_dict = report.model_dump(mode="json")
        # owner는 상수로 사용 (실제 사용자 이름과 분리)
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        report_create = WeeklyReportCreate(
            owner=REPORT_OWNER,  # 상수 owner 사용
            period_start=report.period_start,
            period_end=report.period_end,
            report_json=report_dict
        )

        db_report, is_created = WeeklyReportRepository.create_or_update(
            db, report_create
        )

        action = "생성" if is_created else "업데이트"
        print(f"Weekly report saved ({action}): {report.owner} - {report.period_start}~{report.period_end}")

        html_path = None
        html_url = None
        html_filename = None
        try:
            # HTML 보고서에 표시할 이름 전달
            html_path = render_report_html(
                report_type="weekly",
                data=report.model_dump(mode="json"),
                output_filename=f"weekly_report_{resolved_owner}_{report.period_start}.html",
                display_name=resolved_owner  # HTML 보고서에 표시할 이름
            )

            html_filename = html_path.name
            html_url = f"/static/reports/weekly/{quote(html_filename)}"
            print(f"Weekly report HTML generated: {html_path}")
        except Exception as html_error:
            print(f"HTML generation failed (report saved): {str(html_error)}")

        done_tasks = 0
        if report.weekly and report.weekly.weekday_tasks:
            for day_tasks in report.weekly.weekday_tasks.values():
                if isinstance(day_tasks, list):
                    done_tasks += len(day_tasks)

        return WeeklyReportGenerateResponse(
            role="assistant",
            type="weekly_report",
            message=f"주간 보고서가 {action}되었습니다.",
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
                    report_type="weekly",
                    report_id=str(report.report_id) if getattr(report, "report_id", None) else None,
                ),
                data=report.model_dump(mode="json"),
                html={"url": html_url, "file_name": html_filename} if html_url else None,
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"주간 보고서 생성 실패: {str(e)}")


@router.get("/list/{owner}", response_model=WeeklyReportListResponse)
async def list_weekly_reports(
    owner: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List weekly reports for an owner.
    """
    try:
        reports = WeeklyReportRepository.list_by_owner(db, owner, skip, limit)
        total = WeeklyReportRepository.count_by_owner(db, owner)

        report_responses = [WeeklyReportResponse(**report.to_dict()) for report in reports]

        return WeeklyReportListResponse(
            total=total,
            reports=report_responses
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"목록 조회 실패: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok", "service": "weekly_report"}
