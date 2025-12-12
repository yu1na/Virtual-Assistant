from __future__ import annotations

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class DetailTask(BaseModel):
    """A single time-blocked task entry."""

    time_start: Optional[str] = Field(default=None, description="HH:MM start time")
    time_end: Optional[str] = Field(default=None, description="HH:MM end time")
    text: str = Field(..., description="Task description")
    note: str = Field(default="", description="Optional note")


class CanonicalDaily(BaseModel):
    """Canonical structure for a daily report."""

    model_config = ConfigDict(populate_by_name=True)

    header: Dict[str, str] = Field(default_factory=dict, description="Raw header key-values")
    todo_tasks: List[str] = Field(
        default_factory=list,
        description="금일_진행_업무 entries",
        alias="summary_tasks",
    )
    detail_tasks: List[DetailTask] = Field(default_factory=list, description="시간대별 업무 목록")
    pending: List[str] = Field(default_factory=list, description="미종결 업무")
    plans: List[str] = Field(default_factory=list, description="익일 계획")
    notes: str = Field(default="", description="Notes or remarks")
    summary: str = Field(default="", description="Optional explicit summary body")

    @property
    def summary_tasks(self) -> List[str]:
        # Backward-compatible access for legacy callers
        return self.todo_tasks


class CanonicalWeekly(BaseModel):
    """Canonical structure for a weekly report (kept for compatibility)."""

    header: Dict[str, str] = Field(default_factory=dict)
    weekly_goals: List[str] = Field(default_factory=list)
    weekday_tasks: Dict[str, List[str]] = Field(default_factory=dict)
    weekday_notes: Dict[str, str] = Field(default_factory=dict)  # 각 요일별 notes 정보 (KPI 집계용)
    weekly_highlights: List[str] = Field(default_factory=list)
    notes: str = Field(default="")


class CanonicalMonthly(BaseModel):
    """Canonical structure for a monthly report (kept for compatibility)."""

    header: Dict[str, str] = Field(default_factory=dict)
    weekly_summaries: Dict[str, List[str]] = Field(default_factory=dict)
    next_month_plan: str = Field(default="")


class CanonicalReport(BaseModel):
    """Unified canonical report wrapper."""

    report_id: Optional[str] = Field(default=None, description="Unique report identifier")
    report_type: Literal["daily", "weekly", "monthly"] = Field(..., description="Report type")
    owner: str = Field(default="", description="Report owner (display name)")
    period_start: Optional[date] = Field(default=None, description="Report date")
    period_end: Optional[date] = Field(default=None, description="Report end date")

    daily: Optional[CanonicalDaily] = Field(default=None, description="Daily payload")
    weekly: Optional[CanonicalWeekly] = Field(default=None, description="Weekly payload")
    monthly: Optional[CanonicalMonthly] = Field(default=None, description="Monthly payload")
