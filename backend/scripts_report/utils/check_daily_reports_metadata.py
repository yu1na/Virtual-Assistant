"""
Metadata validator for the daily report collection.
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
    REQUIRED_METADATA_KEYS,
    validate_metadata,
)
from app.infrastructure.vector_store_report import get_report_vector_store  # noqa: E402

BANNED_FIELDS = {
    "level",
    "period_start",
    "period_end",
    "time_start",
    "time_end",
    "start_time",
    "end_time",
    "time_range",
}


def main() -> None:
    vector_store = get_report_vector_store()
    collection = vector_store.get_collection()

    total = collection.count()
    print("=" * 80)
    print("Daily report metadata check")
    print("=" * 80)
    print(f"Total documents: {total}")

    if total == 0:
        return

    data = collection.get(include=["metadatas"], limit=50000)
    metadatas = data.get("metadatas", []) if data else []

    chunk_types = Counter()
    owners = Counter()
    dates = Counter()
    report_types = Counter()

    missing_required = 0
    banned_found = 0
    extra_fields = Counter()
    invalid_metadata = 0

    for meta in metadatas:
        if not meta:
            continue
        try:
            validated = validate_metadata(meta)
        except ChunkValidationError:
            invalid_metadata += 1
            for required in REQUIRED_METADATA_KEYS:
                if required not in meta:
                    missing_required += 1
            for banned in BANNED_FIELDS:
                if banned in meta:
                    banned_found += 1
            for key in meta:
                if key not in REQUIRED_METADATA_KEYS:
                    extra_fields[key] += 1
            continue

        chunk_types[validated.get("chunk_type", "N/A")] += 1
        owners[validated.get("owner", "N/A")] += 1
        dates[validated.get("date", "N/A")] += 1
        report_types[validated.get("report_type", "N/A")] += 1

    print("\nChunk type distribution:")
    for k, v in chunk_types.items():
        print(f"  {k}: {v}")

    print("\nOwner distribution:")
    for k, v in owners.items():
        print(f"  {k}: {v}")

    print("\nReport type distribution:")
    for k, v in report_types.items():
        print(f"  {k}: {v}")

    print("\nSample dates:")
    for k, v in list(dates.items())[:10]:
        print(f"  {k}: {v}")

    print("\nValidation summary:")
    if invalid_metadata:
        print(f"  WARNING: {invalid_metadata} metadata entries failed validation.")
    else:
        print("  All metadata entries passed validation.")

    if missing_required:
        print(f"  WARNING: {missing_required} metadata entries missing required fields.")
    else:
        print("  All required fields present.")

    if banned_found:
        print(f"  WARNING: {banned_found} metadata entries contain banned fields.")
    else:
        print("  No banned fields detected.")

    unexpected = {k: v for k, v in extra_fields.items() if k not in REQUIRED_METADATA_KEYS and k not in BANNED_FIELDS}
    if unexpected:
        print("  WARNING: Unexpected fields detected:")
        for k, v in unexpected.items():
            print(f"    {k}: {v}")
    else:
        print("  No unexpected fields detected.")

    bad_chunk_types = [k for k in chunk_types if k not in ALLOWED_CHUNK_TYPES]
    if bad_chunk_types:
        print(f"  WARNING: Unknown chunk_type values found: {bad_chunk_types}")


if __name__ == "__main__":
    main()
