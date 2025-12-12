from __future__ import annotations

import hashlib
import uuid
import re
from datetime import date, datetime
from typing import Any, Dict, List

from app.domain.report.core.canonical_models import CanonicalReport, DetailTask

# Allowed metadata schema
ALLOWED_CHUNK_TYPES = {"summary", "todo", "detail", "pending", "plan"}
REQUIRED_METADATA_KEYS = [
    "owner",
    "report_type",
    "date",
    "chunk_type",
    "doc_id",
    "report_id",
    "week",
    "month",
]
OPTIONAL_METADATA_KEYS = {"times", "count"}  # times는 문자열로 저장됨
BANNED_METADATA_KEYS = {
    "level",
    "period_start",
    "period_end",
    "start_time",
    "end_time",
    "time_start",
    "time_end",
    "time_range",
}


class ChunkValidationError(ValueError):
    """Raised when chunk metadata or content is invalid."""


def _slugify_owner(owner: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", (owner or "").strip() or "unknown")
    return cleaned.strip("_").lower() or "unknown"


def _generate_chunk_id(doc_id: str, chunk_type: str, index: int) -> str:
    raw = f"{doc_id}|{chunk_type}|{index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _validate_date_string(date_str: str) -> None:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except Exception as exc:  # noqa: BLE001
        raise ChunkValidationError(f"Invalid date format for metadata: {date_str}") from exc


def validate_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure metadata matches the enforced schema."""
    missing = [key for key in REQUIRED_METADATA_KEYS if key not in metadata]
    if missing:
        raise ChunkValidationError(f"Missing required metadata fields: {missing}")

    banned = [key for key in metadata if key in BANNED_METADATA_KEYS]
    if banned:
        raise ChunkValidationError(f"Banned metadata fields present: {banned}")

    extras = [key for key in metadata if key not in REQUIRED_METADATA_KEYS and key not in OPTIONAL_METADATA_KEYS]
    if extras:
        raise ChunkValidationError(f"Unexpected metadata fields found: {extras}")

    if "times" in metadata and metadata["times"] is not None:
        if not isinstance(metadata["times"], str):
            raise ChunkValidationError("Optional field 'times' must be a string")
    if "count" in metadata and metadata["count"] is not None:
        if not isinstance(metadata["count"], int):
            raise ChunkValidationError("Optional field 'count' must be an integer")

    if metadata["chunk_type"] not in ALLOWED_CHUNK_TYPES:
        raise ChunkValidationError(f"Unsupported chunk_type: {metadata['chunk_type']}")

    if metadata["report_type"] != "daily":
        raise ChunkValidationError(f"report_type must be 'daily', got {metadata['report_type']}")

    _validate_date_string(metadata["date"])

    if not isinstance(metadata["week"], int) or not isinstance(metadata["month"], int):
        raise ChunkValidationError("week and month must be integers")

    for key in ("owner", "doc_id", "report_id"):
        if not isinstance(metadata[key], str) or not metadata[key].strip():
            raise ChunkValidationError(f"metadata field '{key}' must be a non-empty string")

    return metadata


def _base_metadata(canonical: CanonicalReport, report_date: date) -> Dict[str, Any]:
    iso_week = report_date.isocalendar().week
    report_id = canonical.report_id or str(uuid.uuid4())
    return {
        "owner": canonical.owner,
        "report_type": "daily",
        "date": report_date.isoformat(),
        "doc_id": f"daily_{report_date.isoformat()}_{_slugify_owner(canonical.owner)}",
        "report_id": report_id,
        "week": int(iso_week),
        "month": int(report_date.month),
    }


def _format_detail_task(task: DetailTask) -> str:
    prefix = ""
    if task.time_start and task.time_end:
        prefix = f"[{task.time_start}-{task.time_end}] "
    elif task.time_start:
        prefix = f"[{task.time_start}] "

    text = f"{prefix}{task.text}".strip()
    if task.note:
        text = f"{text} (note: {task.note})"
    return text


def _create_chunk(text: str, chunk_type: str, base_meta: Dict[str, Any], index: int) -> Dict[str, Any]:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise ChunkValidationError(f"Empty text for chunk_type={chunk_type}")

    metadata = {**base_meta, "chunk_type": chunk_type}
    validate_metadata(metadata)

    return {
        "id": _generate_chunk_id(base_meta["doc_id"], chunk_type, index),
        "text": cleaned_text,
        "metadata": metadata,
    }


def chunk_daily_report(canonical: CanonicalReport) -> List[Dict[str, Any]]:
    """Chunk a CanonicalReport (daily) into up to 5 chunks (one per type)."""
    if not canonical.daily:
        raise ChunkValidationError("Daily report payload is missing")

    report_date = canonical.period_start or date.today()
    base_meta = _base_metadata(canonical, report_date)
    daily = canonical.daily

    chunks: List[Dict[str, Any]] = []

    # 1) todo_chunk: join all todo tasks
    if daily.todo_tasks:
        todo_text = "\n".join([str(t).strip() for t in daily.todo_tasks if str(t).strip()])
        if todo_text:
            chunks.append(_create_chunk(todo_text, "todo", base_meta, 0))

    # 2) detail_chunk: join all detail tasks
    if daily.detail_tasks:
        detail_lines: List[str] = []
        times: List[str] = []
        for task in daily.detail_tasks:
            detail_lines.append(_format_detail_task(task))
            if task.time_start and task.time_end:
                times.append(f"{task.time_start}-{task.time_end}")
            elif task.time_start:
                times.append(str(task.time_start))
        detail_text = "\n".join([line for line in detail_lines if line.strip()])
        if detail_text:
            metadata = {**base_meta, "chunk_type": "detail"}
            if times:
                # ChromaDB는 리스트를 지원하지 않으므로 쉼표로 구분된 문자열로 변환
                metadata["times"] = ", ".join(times)
            metadata["count"] = len(daily.detail_tasks)
            metadata = validate_metadata(metadata)
            chunks.append(
                {
                    "id": _generate_chunk_id(base_meta["doc_id"], "detail", 0),
                    "text": detail_text,
                    "metadata": metadata,
                }
            )

    # 3) pending_chunk
    if daily.pending:
        pending_text = "\n".join([str(p).strip() for p in daily.pending if str(p).strip()])
        if pending_text:
            chunks.append(_create_chunk(pending_text, "pending", base_meta, 0))

    # 4) plan_chunk
    if daily.plans:
        plan_text = "\n".join([str(p).strip() for p in daily.plans if str(p).strip()])
        if plan_text:
            chunks.append(_create_chunk(plan_text, "plan", base_meta, 0))

    # 5) summary_chunk
    summary_text = getattr(daily, "summary", "") or ""
    if summary_text and summary_text.strip():
        chunks.append(_create_chunk(summary_text.strip(), "summary", base_meta, 0))

    return chunks


def chunk_canonical_report(canonical: CanonicalReport) -> List[Dict[str, Any]]:
    """Entry point for chunking. Daily is the only supported type for storage."""
    if canonical.report_type != "daily":
        return []
    return chunk_daily_report(canonical)
