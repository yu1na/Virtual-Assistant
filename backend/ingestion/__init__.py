"""
Ingestion 모듈

보고서 데이터를 청킹, 임베딩하여 ChromaDB에 저장하는 파이프라인

주요 스크립트:
- ingest_mock_reports.py: 목업 데이터 일괄 처리 (신규 청킹 방식)
- auto_ingest.py: 보고서 생성 시 자동 저장
- chroma_client.py: ChromaDB 클라이언트
"""
from ingestion.chroma_client import (
    get_chroma_service,
    get_reports_collection
)

__all__ = [
    # Chroma Client
    "get_chroma_service",
    "get_reports_collection",
]

