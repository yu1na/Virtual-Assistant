from typing import List, Dict, Any
import os
import math

import numpy as np

from .config import (
    SMALL_SEG_THRESHOLD,
    LARGE_SEG_THRESHOLD,
    SIMILARITY_MERGE_THRESHOLD,
    SIMILARITY_SPLIT_THRESHOLD,
    EMBEDDING_MODEL,
)
from .utils import get_logger

logger = get_logger(__name__)


def _sentence_split(text: str) -> List[str]:
    # simple sentence split
    parts = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in ".!?\n":
            s = "".join(buf).strip()
            if s:
                parts.append(s)
            buf = []
    if buf:
        s = "".join(buf).strip()
        if s:
            parts.append(s)
    return parts


def _embed_sentences(sentences: List[str]) -> np.ndarray:
    # Local embedding fallback: use bag-of-words hashing into fixed dims to avoid network
    dim = 256
    vecs = np.zeros((len(sentences), dim), dtype=np.float32)
    for i, s in enumerate(sentences):
        h = 0
        for ch in s:
            h = (h * 131 + ord(ch)) % (1 << 32)
        # spread hash into pseudo vector
        np.random.seed(h % (2**32 - 1))
        v = np.random.rand(dim).astype(np.float32)
        vecs[i] = v / (np.linalg.norm(v) + 1e-8)
    return vecs


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def _merge_small_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for seg in segments:
        content = seg["content"].strip()
        if merged and len(content) < SMALL_SEG_THRESHOLD:
            prev = merged[-1]
            prev_vec = prev.get("_vec_mean")
            # compute current vector
            sents = _sentence_split(content)
            vecs = _embed_sentences(sents) if sents else np.zeros((1,256), dtype=np.float32)
            cur_mean = vecs.mean(axis=0) if len(vecs) else np.zeros(256, dtype=np.float32)
            sim = _cosine_sim(prev_vec, cur_mean) if prev_vec is not None else 0.0
            if sim >= SIMILARITY_MERGE_THRESHOLD:
                prev["content"] = prev["content"].rstrip() + "\n" + content
                prev["source_pages"] = sorted(set(prev.get("source_pages", [])) | set(seg.get("source_pages", [])))
                # update vector mean
                prev["_vec_mean"] = (prev["_vec_mean"] + cur_mean) / 2.0
                continue
        # initialize vec mean
        sents = _sentence_split(content)
        vecs = _embed_sentences(sents) if sents else np.zeros((1,256), dtype=np.float32)
        seg["_vec_mean"] = vecs.mean(axis=0) if len(vecs) else np.zeros(256, dtype=np.float32)
        merged.append(seg)
    return merged


def _split_large_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for seg in segments:
        content = seg["content"]
        if len(content) <= LARGE_SEG_THRESHOLD:
            out.append(seg)
            continue
        sents = _sentence_split(content)
        if not sents:
            out.append(seg)
            continue
        # split by similarity low points
        vecs = _embed_sentences(sents)
        # compute similarity between consecutive sentences
        sims = [
            _cosine_sim(vecs[i], vecs[i+1]) for i in range(len(vecs)-1)
        ]
        # cut where similarity is low
        cut_indices = [i for i, s in enumerate(sims) if s < SIMILARITY_SPLIT_THRESHOLD]
        if not cut_indices:
            out.append(seg)
            continue
        start = 0
        for ci in cut_indices + [len(sents)-1]:
            chunk_text = " ".join(sents[start:ci+1]).strip()
            if chunk_text:
                out.append({
                    "segment_id": seg.get("segment_id"),
                    "content": chunk_text,
                    "source_pages": seg.get("source_pages", []),
                })
            start = ci + 1
    return out


def refine_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not segments:
        return []
    merged = _merge_small_segments(segments)
    refined = _split_large_segments(merged)
    for seg in refined:
        seg.pop("_vec_mean", None)
    return refined