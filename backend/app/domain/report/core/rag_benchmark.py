"""
Benchmarking utilities for the Report RAG pipeline.

Provides timing helpers, metric calculation, JSONL logging, and convenience
functions to run single/batch benchmarks without changing the RAG API surface.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.domain.report.search.hybrid_search import QueryAnalyzer, SearchKeywords
from app.domain.report.search.retriever import UnifiedSearchResult

# Path: backend/logs/rag_bench.jsonl (relative to backend root)
LOG_PATH = Path(__file__).resolve().parents[4] / "logs" / "rag_bench.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _append_jsonl(entry: Dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")


def _safe_id(result: UnifiedSearchResult) -> str:
    return result.doc_id or result.chunk_id or ""


def evaluate_retrieval_accuracy(
    query: Optional[str] = None,
    results: Optional[List[UnifiedSearchResult]] = None,
    top_k: Optional[int] = None,
) -> float:
    """
    Approximate retrieval accuracy by checking how many requested chunk-types
    (from the query analyzer) are represented in the returned results. Falls
    back to coverage of returned results vs. requested top_k.
    """
    if query is None or results is None:
        return summarize_accuracy_from_log()

    keywords: SearchKeywords = QueryAnalyzer.extract_keywords(query)
    chunk_types = keywords.chunk_types or []
    if chunk_types and results:
        matched = sum(1 for r in results if r.chunk_type in chunk_types)
        return matched / max(len(chunk_types), 1)

    if top_k:
        return min(1.0, len(results) / max(top_k, 1))
    return 1.0 if results else 0.0


def summarize_accuracy_from_log(log_path: Path = LOG_PATH) -> float:
    """Average retrieval_accuracy across log entries."""
    if not log_path.exists():
        return 0.0
    scores: List[float] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
            if "retrieval_accuracy" in obj:
                scores.append(float(obj["retrieval_accuracy"]))
        except Exception:
            continue
    return sum(scores) / len(scores) if scores else 0.0


def evaluate_consistency(
    first_results: Optional[List[UnifiedSearchResult]] = None,
    second_results: Optional[List[UnifiedSearchResult]] = None,
) -> float:
    """
    Consistency = Jaccard similarity between two retrieval passes (by doc_id or chunk_id).
    """
    if first_results is None or second_results is None:
        return summarize_consistency_from_log()

    set_a = { _safe_id(r) for r in first_results if _safe_id(r) }
    set_b = { _safe_id(r) for r in second_results if _safe_id(r) }
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def summarize_consistency_from_log(log_path: Path = LOG_PATH) -> float:
    """Average consistency_score across log entries."""
    if not log_path.exists():
        return 0.0
    scores: List[float] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
            if "consistency_score" in obj:
                scores.append(float(obj["consistency_score"]))
        except Exception:
            continue
    return sum(scores) / len(scores) if scores else 0.0


def estimate_generation_quality(_: str) -> float:
    """
    Stub for generation quality. Replace with manual scoring or LLM-based grading.
    """
    return 0.0


def log_benchmark_entry(
    *,
    query: str,
    retrieval_time_ms: float,
    llm_time_ms: float,
    total_time_ms: float,
    retrieval_accuracy: float,
    consistency_score: float,
    generation_quality: float,
) -> Dict[str, Any]:
    entry = {
        "timestamp": _timestamp(),
        "query": query,
        "retrieval_time": round(retrieval_time_ms, 3),
        "llm_time": round(llm_time_ms, 3),
        "total_time": round(total_time_ms, 3),
        "retrieval_accuracy": round(retrieval_accuracy, 3),
        "consistency_score": round(consistency_score, 3),
        "generation_quality": round(generation_quality, 3),
    }
    _append_jsonl(entry)
    return entry


def run_single_benchmark(
    query: str,
    owner: str = "default",
    *,
    top_k: int = 5,
    date_range: Optional[Dict[str, Any]] = None,
    reference_date: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run one benchmark synchronously (convenience wrapper around ReportRAGChain).
    """
    from app.domain.report.core.rag_chain import ReportRAGChain

    async def _run() -> Dict[str, Any]:
        chain = ReportRAGChain(owner=owner, top_k=top_k)
        return await chain.generate_response(query=query, date_range=date_range, reference_date=reference_date)

    return asyncio.run(_run())


def run_batch_benchmark(
    queries: Iterable[str],
    owner: str = "default",
    *,
    top_k: int = 5,
    date_range: Optional[Dict[str, Any]] = None,
    reference_date: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Run a batch of queries sequentially and return their responses.
    """
    results: List[Dict[str, Any]] = []
    for q in queries:
        results.append(run_single_benchmark(q, owner, top_k=top_k, date_range=date_range, reference_date=reference_date))
    return results
