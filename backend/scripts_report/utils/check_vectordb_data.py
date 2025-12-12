"""
Quick inspection script for the report collection.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# 환경 변수 로드 (config 설정을 위해 필요)
load_dotenv(project_root / ".env")
report_env = project_root / ".env.report"
if report_env.exists():
    load_dotenv(report_env, override=False)

from app.domain.report.core.chunker import (  # noqa: E402
    ALLOWED_CHUNK_TYPES,
    ChunkValidationError,
    validate_metadata,
)
from app.infrastructure.vector_store_report import get_report_vector_store  # noqa: E402


def main() -> None:
    vector_store = get_report_vector_store()
    collection = vector_store.get_collection()

    total = collection.count()
    print("=" * 80)
    print("Report collection snapshot")
    print("=" * 80)
    print(f"Total documents: {total}")

    if total == 0:
        return

    results = collection.get(include=["metadatas", "documents"], limit=200)
    metadatas = results.get("metadatas", []) if results else []
    documents = results.get("documents", []) if results else []

    owners = Counter()
    chunk_types = Counter()
    dates = Counter()

    valid_indices = []

    for idx, meta in enumerate(metadatas):
        try:
            validated = validate_metadata(meta)
        except ChunkValidationError:
            continue
        valid_indices.append(idx)
        owners[validated.get("owner", "N/A")] += 1
        chunk_types[validated.get("chunk_type", "N/A")] += 1
        dates[validated.get("date", "N/A")] += 1

    print("\nOwners:", dict(owners))
    print("Chunk types:", dict(chunk_types))
    print("Dates (sample):", dict(list(dates.items())[:10]))

    bad_chunk_types = [c for c in chunk_types if c not in ALLOWED_CHUNK_TYPES]
    if bad_chunk_types:
        print(f"\nWARNING: Unknown chunk_type values detected: {bad_chunk_types}")

    print("\nSamples:")
    for pos, idx in enumerate(valid_indices[:5]):
        meta = metadatas[idx]
        doc = documents[idx][:120] + "..." if len(documents[idx]) > 120 else documents[idx]
        print(f"[{pos+1}] {results['ids'][idx]}")
        print(f"  date: {meta.get('date')}, owner: {meta.get('owner')}, chunk_type: {meta.get('chunk_type')}")
        print(f"  text: {doc}")


if __name__ == "__main__":
    main()
