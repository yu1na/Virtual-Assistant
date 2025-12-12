from typing import List, Dict, Any
import os

from .config import MIN_SEG_CHAR, MAX_SEG_CHAR, MODEL_NAME
from .utils import get_logger, generate_uuid

logger = get_logger(__name__)


def _join_document(pages: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for p in pages:
        header = f"\n\n[Page {p.get('page')}]\n"
        parts.append(header + (p.get("content") or ""))
    return "\n".join(parts)


def _local_fallback_segments(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # naive fallback: split every N chars while carrying page numbers
    doc = _join_document(pages)
    N_MIN, N_MAX = MIN_SEG_CHAR, MAX_SEG_CHAR
    segments: List[Dict[str, Any]] = []
    start = 0
    while start < len(doc):
        end = min(start + N_MAX, len(doc))
        chunk = doc[start:end]
        if len(chunk) < N_MIN and end < len(doc):
            end = min(start + N_MIN, len(doc))
            chunk = doc[start:end]
        if not chunk.strip():
            break
        seg_id = generate_uuid("seg")
        segments.append({
            "segment_id": seg_id,
            "content": chunk,
            "source_pages": sorted({p.get("page") for p in pages if p.get("content") and str(p.get("page")) in chunk}),
        })
        start = end
    if not segments:
        # at least create one segment
        segments.append({"segment_id": generate_uuid("seg"), "content": doc, "source_pages": [p.get("page") for p in pages]})
    return segments


def create_segments(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY missing; using local fallback segmentation.")
        return _local_fallback_segments(pages)

    # If an LLM client is available elsewhere in the repo, wire here.
    # To keep module self-contained and avoid external deps, fallback for now.
    logger.info("LLM segmentation not wired; using local heuristic fallback.")
    return _local_fallback_segments(pages)