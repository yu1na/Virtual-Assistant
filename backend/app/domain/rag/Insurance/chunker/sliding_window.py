from typing import List, Dict, Any, Tuple

from .config import MAX_TOKENS, OVERLAP_TOKENS
from .token_utils import tokenize, detokenize
from .utils import generate_uuid


def _build_stream_with_index(segments: List[Dict[str, Any]]) -> Tuple[List[int], List[Tuple[int, int, List[int]]]]:
    """Return concatenated token stream and index mapping of token ranges to source_pages.
    mapping entries: (start_idx, end_idx, source_pages)
    """
    all_tokens: List[int] = []
    index: List[Tuple[int, int, List[int]]] = []
    cur = 0
    for seg in segments:
        text = seg.get("content", "")
        seg_tokens = tokenize(text)
        start = cur
        end = cur + len(seg_tokens)
        pages = seg.get("source_pages", [])
        index.append((start, end, pages))
        all_tokens.extend(seg_tokens)
        cur = end
        # add separator between segments
        sep_tokens = tokenize("\n\n")
        if sep_tokens:
            all_tokens.extend(sep_tokens)
            cur += len(sep_tokens)
    return all_tokens, index


def _pages_for_slice(idx: List[Tuple[int, int, List[int]]], start: int, end: int) -> List[int]:
    pages: set[int] = set()
    for s, e, p in idx:
        if e <= start:
            continue
        if s >= end:
            break
        pages.update(p)
    return sorted(pages)


def create_chunks(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not segments:
        return []

    stream, index = _build_stream_with_index(segments)
    window = MAX_TOKENS
    stride = MAX_TOKENS - OVERLAP_TOKENS
    chunks: List[Dict[str, Any]] = []

    start = 0
    while start < len(stream):
        end = min(start + window, len(stream))
        slice_tokens = stream[start:end]
        content = detokenize(slice_tokens)
        pages = _pages_for_slice(index, start, end)
        chunks.append({
            "chunk_id": generate_uuid("ins"),
            "content": content,
            "tokens": len(slice_tokens),
            "source_pages": pages,
        })
        if end == len(stream):
            break
        start += stride

    return chunks