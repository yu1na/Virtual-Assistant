from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
import time

from app.domain.report.search.hybrid_search import HybridSearcher, QueryAnalyzer, SearchKeywords
from app.domain.report.search.retriever import UnifiedSearchResult
from app.llm.client import LLMClient
from multi_agent.agents.report_main_router import ReportPromptRegistry
from app.domain.report.core.rag_benchmark import (
    evaluate_consistency,
    evaluate_retrieval_accuracy,
    estimate_generation_quality,
    log_benchmark_entry,
)


class ReportRAGChain:
    """Lightweight RAG chain for daily reports."""

    def __init__(
        self,
        owner: str,
        retriever: Optional[HybridSearcher] = None,
        llm: Optional[LLMClient] = None,
        top_k: int = 5,
        prompt_registry=None,
    ) -> None:
        self.owner = owner
        self.top_k = top_k

        # Lazy import to avoid circular dependency
        from app.infrastructure.vector_store_report import get_report_vector_store
        vector_store = get_report_vector_store()
        collection = vector_store.get_collection()
        self.searcher = retriever or HybridSearcher(collection=collection)

        self.llm = llm or LLMClient(model="gpt-4o", temperature=0.7, max_tokens=2000)
        self.prompt_registry = prompt_registry or ReportPromptRegistry

    def retrieve(
        self,
        query: str,
        date_range: Optional[Dict[str, date]] = None,
    ) -> List[UnifiedSearchResult]:
        # Normalize tuple-based date_range into dict
        if date_range and not isinstance(date_range, dict):
            try:
                start, end = date_range  # type: ignore[misc]
                date_range = {"start": start, "end": end}
            except Exception:
                date_range = None

        keywords: SearchKeywords = QueryAnalyzer.extract_keywords(query)
        # owner 필터링 제거: 단일 워크스페이스로 동작
        results = self.searcher.search(
            query=query,
            keywords=keywords,
            owner=None,  # owner 필터링 제거
            base_date_range=date_range,
            top_k=self.top_k,
        )
        return results

    def format_context(self, results: List[UnifiedSearchResult]) -> str:
        if not results:
            return "검색 결과가 없습니다."

        lines = []
        for idx, result in enumerate(results, 1):
            meta = result.metadata
            date_str = meta.get("date", "")
            chunk_type = meta.get("chunk_type", "")
            lines.append(
                f"[{idx}] 날짜: {date_str}, 유형: {chunk_type}\n내용: {result.text}"
            )
        return "\n---\n".join(lines)

    async def generate_response(
        self,
        query: str,
        date_range: Optional[Dict[str, date]] = None,
        reference_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        total_start = time.perf_counter()
        retrieval_start = time.perf_counter()
        results = self.retrieve(query, date_range)
        retrieval_time_ms = (time.perf_counter() - retrieval_start) * 1000

        if not results:
            total_time_ms = (time.perf_counter() - total_start) * 1000
            log_benchmark_entry(
                query=query,
                retrieval_time_ms=retrieval_time_ms,
                llm_time_ms=0.0,
                total_time_ms=total_time_ms,
                retrieval_accuracy=evaluate_retrieval_accuracy(query, results, top_k=self.top_k),
                consistency_score=1.0,
                generation_quality=0.0,
            )
            return {
                "answer": "검색된 청크가 없습니다.",
                "sources": [],
                "has_results": False,
            }

        context = self.format_context(results)
        system_prompt = self.prompt_registry.rag_system()
        user_prompt = self.prompt_registry.rag_user(query=query, context=context)

        llm_start = time.perf_counter()
        answer = await self.llm.acomplete(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.5)
        llm_time_ms = (time.perf_counter() - llm_start) * 1000

        sources = []
        for result in results:
            meta = result.metadata
            period = None
            if meta.get("period_start") and meta.get("period_end"):
                period = {
                    "start": meta.get("period_start"),
                    "end": meta.get("period_end"),
                }
            sources.append(
                {
                    "date": meta.get("date", ""),
                    "period": period,
                    "owner": meta.get("owner", ""),
                    "report_type": meta.get("report_type", ""),
                    "report_id": meta.get("doc_id"),
                    "chunk_type": meta.get("chunk_type", ""),
                    "text_preview": result.text[:120],
                    "score": round(result.score, 3),
                }
            )

        consistency_results = self.retrieve(query, date_range)
        total_time_ms = (time.perf_counter() - total_start) * 1000

        log_benchmark_entry(
            query=query,
            retrieval_time_ms=retrieval_time_ms,
            llm_time_ms=llm_time_ms,
            total_time_ms=total_time_ms,
            retrieval_accuracy=evaluate_retrieval_accuracy(query, results, top_k=self.top_k),
            consistency_score=evaluate_consistency(results, consistency_results),
            generation_quality=estimate_generation_quality(answer if isinstance(answer, str) else str(answer)),
        )

        return {
            "answer": answer,
            "sources": sources,
            "has_results": True,
        }
