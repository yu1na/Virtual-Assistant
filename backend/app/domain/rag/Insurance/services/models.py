"""
간단한 Insurance RAG 모델 정의 (core 디렉토리 불필요)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Query:
    """사용자 쿼리 모델"""
    question: str
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsuranceDocument:
    """보험 문서 모델"""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    doc_id: Optional[str] = None
    
    def __post_init__(self):
        if self.doc_id is None and 'id' in self.metadata:
            self.doc_id = self.metadata['id']


@dataclass
class Chunk:
    """문서 청크 모델"""
    text: str
    chunk_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """검색 결과 모델"""
    documents: List[InsuranceDocument]
    scores: List[float]
    query: Query
    retrieval_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    """답변 생성 결과 모델"""
    answer: str
    query: Query
    source_documents: List[InsuranceDocument]
    confidence_score: float
    generation_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentType:
    """문서 타입"""
    PDF = "pdf"
    TEXT = "text"
    JSON = "json"
