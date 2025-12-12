"""
Plan API Endpoint

Generates today's plan based on recent reports and recommendations.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.domain.auth.dependencies import get_current_user_optional
from app.domain.report.planner.schemas import (
    TaskItem,
    TaskSource,
    TodayPlanRequest,
    TodayPlanResponse,
)
from app.domain.user.models import User
from app.infrastructure.database.session import get_db


router = APIRouter(prefix="/plan", tags=["plan"])


@router.post("/today", response_model=TodayPlanResponse)
async def generate_today_plan(
    request: TodayPlanRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> TodayPlanResponse:
    """
    Generate today's plan (agent powered).

    인증 비활성화: current_user가 없어도 동작합니다.
    """
    try:
        # 인증 비활성화: current_user가 없어도 동작
        resolved_owner = current_user.name if current_user and current_user.name else "사용자"

        target_date = request.target_date or date.today()

        # ReportPlanningAgent 사용
        from multi_agent.tools.report_tools import get_planning_agent

        planning_agent = get_planning_agent()

        # owner 필터링 제거: 단일 워크스페이스로 동작
        # owner는 더 이상 사용하지 않지만, 호환성을 위해 전달
        result_dict = planning_agent.generate_plan_sync(
            owner=None,  # owner 필터링 제거
            target_date=target_date,
        )

        tasks = [TaskItem(**task) for task in result_dict["tasks"]]
        task_sources = [
            TaskSource(**source) for source in result_dict.get("task_sources", [])
        ]

        return TodayPlanResponse(
            tasks=tasks,
            summary=result_dict["summary"],
            source_date=result_dict["source_date"],
            owner=result_dict.get("owner"),  # None일 수 있음
            target_date=result_dict["target_date"],
            task_sources=task_sources,
        )

    except Exception as e:
        import traceback

        print(f"[ERROR] Today plan generation failed: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Plan generation failed: {str(e)}",
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "plan"}
