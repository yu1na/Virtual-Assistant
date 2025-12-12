from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from chromadb import Collection
from pydantic import BaseModel, Field

from ingestion.embed import get_embedding_service
from app.domain.report.core.chunker import (
    ALLOWED_CHUNK_TYPES,
    validate_metadata,
    ChunkValidationError,
)


class UnifiedSearchResult(BaseModel):
    chunk_id: str = Field(..., description="Chunk ID")
    doc_id: str = Field(..., description="Document ID")
    doc_type: str = Field(..., description="Document type")
    chunk_type: str = Field(..., description="Chunk type")
    text: str = Field(..., description="Chunk text")
    score: float = Field(..., description="Similarity score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata payload")


class UnifiedRetriever:
    """Minimal retriever that works with the new daily report metadata schema."""

    def __init__(
        self,
        collection: Collection,
        openai_api_key: Optional[str] = None,
    ) -> None:
        self.collection = collection
        self.embedding_service = get_embedding_service(
            api_key=openai_api_key,
            model="text-embedding-3-large",
            dimension=3072,
        )

    def _build_date_list(self, start: date, end: date) -> List[str]:
        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return dates

    def _execute(self, query: str, where: Dict[str, Any], n_results: int) -> List[UnifiedSearchResult]:
        query_embedding = self.embedding_service.embed_text(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None,
        )

        search_results: List[UnifiedSearchResult] = []
        if not results or not results.get("ids"):
            return search_results

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for i in range(len(ids)):
            metadata = metadatas[i] or {}
            try:
                metadata = validate_metadata(metadata)
            except ChunkValidationError:
                continue

            if metadata.get("chunk_type") not in ALLOWED_CHUNK_TYPES:
                continue
            if metadata.get("report_type") != "daily":
                continue

            score = 1.0 / (1.0 + distances[i])
            search_results.append(
                UnifiedSearchResult(
                    chunk_id=ids[i],
                    doc_id=metadata.get("doc_id", ""),
                    doc_type=metadata.get("report_type", "daily"),
                    chunk_type=metadata.get("chunk_type", ""),
                    text=documents[i],
                    score=score,
                    metadata=metadata,
                )
            )
        return search_results

    def search_daily(
        self,
        query: str,
        owner: Optional[str] = None,
        single_date: Optional[str] = None,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        date_range: Optional[tuple[date, date]] = None,
        week: Optional[int] = None,
        n_results: int = 5,
        top_k: Optional[int] = None,
        chunk_types: Optional[List[str]] = None,
        report_ids: Optional[List[str]] = None,
    ) -> List[UnifiedSearchResult]:
        conditions: List[Dict[str, Any]] = [{"report_type": "daily"}]

        if chunk_types:
            valid = [ctype for ctype in chunk_types if ctype in ALLOWED_CHUNK_TYPES]
            if valid:
                conditions.append({"chunk_type": {"$in": valid}})

        # owner 필터링 제거: 단일 워크스페이스로 동작
        # if owner:
        #     conditions.append({"owner": owner})

        if week is not None:
            try:
                week_int = int(week)
                conditions.append({"week": week_int})
            except (TypeError, ValueError):
                # Ignore invalid week formats to avoid crashing upstream callers.
                pass

        if report_ids:
            conditions.append({"report_id": {"$in": report_ids}})

        if single_date:
            conditions.append({"date": single_date})
        elif date_range:
            start, end = date_range
            date_list = self._build_date_list(start, end)
            conditions.append({"date": {"$in": date_list}})
        elif period_start and period_end:
            try:
                start = date.fromisoformat(period_start)
                end = date.fromisoformat(period_end)
                date_list = self._build_date_list(start, end)
                conditions.append({"date": {"$in": date_list}})
            except ValueError:
                pass

        where = {"$and": conditions} if len(conditions) > 1 else conditions[0]
        return self._execute(query, where, top_k or n_results)

    def search_all(self, query: str, n_results: int = 10) -> List[UnifiedSearchResult]:
        return self._execute(query, {"report_type": "daily"}, n_results)

    def search_by_doc_type(self, query: str, doc_type: str, n_results: int = 5, **filters: Any) -> List[UnifiedSearchResult]:
        if doc_type != "daily":
            return []
        # owner 필터링 제거: 단일 워크스페이스로 동작
        return self.search_daily(query=query, n_results=n_results, owner=None)

    def search_kpi(self, query: str, category: Optional[str] = None, n_results: int = 5) -> List[UnifiedSearchResult]:
        # KPI documents are not stored in the daily report collection after the reset.
        return []

    def search_template(self, query: str, n_results: int = 3) -> List[UnifiedSearchResult]:
        # Templates are not stored in the daily report collection after the reset.
        return []
