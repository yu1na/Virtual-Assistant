from __future__ import annotations

"""
Utility to ingest a single canonical daily report into ChromaDB.
The report collection is reset before ingestion.
"""

from typing import Any, Dict

from app.domain.report.core.canonical_models import CanonicalReport
from app.domain.report.core.chunker import ChunkValidationError, chunk_canonical_report
from app.domain.report.core.embedding_pipeline import get_embedding_pipeline
from app.infrastructure.vector_store_report import get_report_vector_store


def ingest_single_report(report: CanonicalReport) -> Dict[str, Any]:
    """Chunk -> embed -> store a single canonical daily report."""
    try:
        vector_store = get_report_vector_store()

        chunks = chunk_canonical_report(report)
        if not chunks:
            raise ChunkValidationError("No chunks generated for the provided report")

        pipeline = get_embedding_pipeline()
        pipeline.vector_store = vector_store
        result = pipeline.process_and_store(chunks)

        return {
            "success": True,
            "uploaded_chunks": result["chunks_processed"],
            "total_documents": result["total_documents"],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "message": str(exc),
        }


def ingest_single_report_silent(report: CanonicalReport) -> bool:
    """Thin wrapper to return boolean success."""
    return ingest_single_report(report).get("success", False)
