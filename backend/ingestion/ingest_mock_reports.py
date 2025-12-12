from __future__ import annotations

"""
Ingest mock daily reports: canonical -> chunk -> embed -> store.
The report collection is reset before ingestion.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")
report_env = project_root / ".env.report"
if report_env.exists():
    load_dotenv(report_env, override=False)

from app.domain.report.core.chunker import ChunkValidationError, chunk_canonical_report  # noqa: E402
from app.domain.report.core.embedding_pipeline import EmbeddingPipeline  # noqa: E402
from app.domain.report.core.service import ReportProcessingService  # noqa: E402
from app.infrastructure.vector_store_report import get_report_vector_store  # noqa: E402

MOCK_DATA_DIR = project_root / "Data" / "mock_reports" / "daily"
BATCH_SIZE = 64


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_daily_files() -> List[Path]:
    if not MOCK_DATA_DIR.exists():
        return []
    # 파일명 기준으로 정렬하여 날짜 순서 보장
    return sorted(MOCK_DATA_DIR.rglob("*.txt"), key=lambda p: p.name)


def ingest_daily_reports() -> None:
    files = collect_daily_files()
    if not files:
        print("No mock daily reports found.")
        return

    owner = os.getenv("REPORT_OWNER") or os.getenv("MOCK_OWNER")
    if not owner or not owner.strip():
        print("REPORT_OWNER (or MOCK_OWNER) must be set to ingest reports. Aborting.")
        return
    owner = owner.strip()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set. Aborting ingestion.")
        return

    service = ReportProcessingService(api_key=api_key)
    vector_store = get_report_vector_store()
    pipeline = EmbeddingPipeline(vector_store=vector_store)

    all_chunks: List[Dict[str, Any]] = []
    total_files = len(files)
    print(f"   처리 중... ({total_files}개 파일)", end="", flush=True)
    
    for idx, path in enumerate(files, 1):
        try:
            raw = read_json(path)
            canonical = service.normalize_daily(raw, owner_override=owner)
            chunks = chunk_canonical_report(canonical)
            all_chunks.extend(chunks)
        except ChunkValidationError:
            # 스킵 (조용히 처리)
            pass
        except Exception:  # noqa: BLE001
            # 에러 (조용히 처리)
            pass
        
        # 진행률 표시 (10% 단위)
        if idx % max(1, total_files // 10) == 0 or idx == total_files:
            progress = int((idx / total_files) * 100)
            print(f"\r   처리 중... {progress}% ({idx}/{total_files})", end="", flush=True)
    
    print()  # 줄바꿈

    if not all_chunks:
        print("No chunks were generated. Nothing to store.")
        return

    result = pipeline.process_and_store(all_chunks, batch_size=BATCH_SIZE)
    # 결과는 report_loader.py에서 표시하므로 여기서는 출력하지 않음


def main() -> None:
    print("Ingesting mock daily reports...")
    ingest_daily_reports()


if __name__ == "__main__":
    main()
