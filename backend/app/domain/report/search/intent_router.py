from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional
import re

from pydantic import BaseModel, Field

from app.domain.report.core.chunker import ALLOWED_CHUNK_TYPES


class QueryIntent(BaseModel):
    intent: Literal["daily", "mixed", "unknown"] = Field(..., description="Detected intent")
    reason: str = Field(..., description="Reasoning behind the routing decision")
    filters: dict = Field(default_factory=dict, description="Optional filters for retrieval")


class IntentRouter:
    """
    Lightweight intent router.
    We now store only daily report chunks, so the default intent is always "daily".
    """

    def __init__(self, *_: Optional[str], **__: Optional[str]) -> None:
        # Compatibility placeholder for previous API (api_key/model args)
        pass

    def _extract_date_range(self, query: str, reference_date: Optional[date] = None) -> Optional[dict]:
        """Very lightweight date-range extraction for relative phrases."""
        ref = reference_date or date.today()
        lower = query.lower()

        # 오늘
        if "오늘" in lower:
            return {"start": ref, "end": ref}

        # 어제
        if "어제" in lower:
            day = ref - timedelta(days=1)
            return {"start": day, "end": day}

        # 이번 주
        if "이번 주" in lower or "이번주" in lower:
            start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=6)
            return {"start": start, "end": end}

        # 지난주 / 지난 주 / 저번주 / 저번 주
        if "지난주" in lower or "지난 주" in lower or "저번주" in lower or "저번 주" in lower:
            start = ref - timedelta(days=ref.weekday() + 7)
            end = start + timedelta(days=6)
            return {"start": start, "end": end}

        # 지난 N일
        match = re.search(r"지난\s*(\d+)\s*일", lower)
        if match:
            days = int(match.group(1))
            start = ref - timedelta(days=max(days - 1, 0))
            return {"start": start, "end": ref}

        return None

    def _detect_chunk_types(self, query: str) -> list[str]:
        lower = query.lower()
        chunk_types = []
        if any(word in lower for word in ["계획", "plan", "익일"]):
            chunk_types.append("plan")
        if any(word in lower for word in ["미종결", "pending", "issue", "이슈"]):
            chunk_types.append("pending")
        if any(word in lower for word in ["todo", "할 일", "진행 업무"]):
            chunk_types.append("todo")
        if any(word in lower for word in ["요약", "summary"]):
            chunk_types.append("summary")
        if not chunk_types:
            chunk_types = list(ALLOWED_CHUNK_TYPES)
        return chunk_types

    def route(self, query: str, reference_date: Optional[date] = None) -> QueryIntent:
        filters = {"chunk_types": self._detect_chunk_types(query)}

        date_range = self._extract_date_range(query, reference_date)
        if date_range:
            filters["date_range"] = date_range

        return QueryIntent(
            intent="daily",
            reason="Default route to daily reports with constrained chunk_types filter.",
            filters=filters,
        )
