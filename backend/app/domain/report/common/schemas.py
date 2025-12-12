"""
Common report schemas shared across report generation, planning, and RAG flows.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional, Dict, Any

from pydantic import BaseModel, Field, field_serializer


class ReportPeriod(BaseModel):
    """ISO date period for a report or query."""
    start: str | date = Field(..., description="Start date (YYYY-MM-DD)")
    end: str | date = Field(..., description="End date (YYYY-MM-DD)")

    @field_serializer("start", "end")
    def _serialize_dates(self, value: str | date) -> str:
        return value if isinstance(value, str) else value.isoformat()


class ReportMeta(BaseModel):
    """Metadata shared by all report responses."""
    owner: str = Field(..., description="Report owner")
    period: ReportPeriod = Field(..., description="Report period")
    report_type: Literal["daily", "weekly", "monthly"] = Field(..., description="Report type")
    report_id: Optional[str] = Field(None, description="Optional report identifier")


class Task(BaseModel):
    """Unified task shape."""
    title: str
    description: str = ""
    priority: str = "medium"
    expected_time: str = ""
    category: str = ""
    status: Optional[str] = None


class TaskSource(BaseModel):
    """Task provenance info."""
    type: str = Field(..., description="Source type (e.g., yesterday_plan, chromadb_recommendation)")
    description: str = Field(..., description="Human-friendly description of the source")
    task_index: int = Field(..., description="Index of the task in the returned list")


class ReportEnvelope(BaseModel):
    """Envelope for report responses."""
    meta: ReportMeta
    data: Dict[str, Any]
    html: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional HTML export metadata: { url, file_name }",
    )


class RAGSourceRef(BaseModel):
    """Reference to a retrieved chunk/source for RAG answers."""
    date: str = Field(..., description="Chunk date (ISO)")
    period: Optional[ReportPeriod] = Field(None, description="Associated report period if known")
    owner: str = Field(..., description="Owner of the source report")
    report_type: Optional[str] = Field(None, description="Report type (daily/weekly/monthly)")
    report_id: Optional[str] = Field(None, description="Report identifier, if available")
    chunk_type: Optional[str] = Field(None, description="Chunk type/category")
    text_preview: str = Field(..., description="Preview of the chunk text")
    score: float = Field(..., description="Similarity score")
