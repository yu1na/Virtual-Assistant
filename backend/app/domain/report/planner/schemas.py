"""
Planner schemas

Request/response models for planning-related APIs.
"""
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field

from app.domain.report.common.schemas import Task, TaskSource


class TodayPlanRequest(BaseModel):
    """Request body for generating today's plan."""
    owner: str | None = Field(
        None,
        description="Owner name (optional when authenticated, required as fallback when not logged in)",
    )
    owner_id: int | None = Field(
        None,
        description="Owner ID (frontend compatibility; ignored when auth user is present)",
    )
    target_date: date | None = Field(
        None,
        description="Target date for the plan (defaults to today when omitted)"
    )


class TaskSource(BaseModel):
    """Source metadata for a generated task."""
    source_type: str = Field(
        ...,
        description="Source type: 'yesterday_plan', 'yesterday_unresolved', or 'chromadb_recommendation'",
    )
    source_description: str = Field(..., description="Human-friendly source description")
    task_index: int = Field(..., description="Index of the task in the returned list")


class TodayPlanResponse(BaseModel):
    """Response body for today's plan generation."""
    tasks: List[Task] = Field(default_factory=list, description="Recommended tasks")
    summary: str = Field("", description="Plan summary")
    source_date: Optional[str] = Field(None, description="Date used as source data")
    owner: Optional[str] = Field(None, description="Resolved owner name (deprecated, not used)")
    target_date: str = Field("", description="Target date for the generated plan")
    task_sources: List[TaskSource] = Field(default_factory=list, description="Source info for each task")

# Backward compatibility alias
TaskItem = Task
