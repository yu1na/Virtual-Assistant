"""
RAG API 엔드포인트

질의응답 API를 제공합니다.
문서 업로드는 internal_docs/uploads 폴더에 직접 추가 후 별도 ingestion 스크립트로 처리합니다.
"""

from fastapi import APIRouter, HTTPException
import threading

from app.domain.rag.HR.config import rag_config
from app.domain.rag.HR.vector_store import VectorStore
from app.domain.rag.HR.retriever import RAGRetriever
from app.domain.rag.HR.schemas import (
    QueryRequest,
    QueryResponse
)
from app.domain.rag.HR.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()

# 전역 인스턴스 (lazy loading with thread-safe)
_vector_store = None
_retriever = None
_vector_store_lock = threading.Lock()
_retriever_lock = threading.Lock()

def get_vector_store():
    """벡터 저장소 lazy loading (thread-safe)"""
    global _vector_store
    if _vector_store is None:
        with _vector_store_lock:
            # Double-checked locking pattern
            if _vector_store is None:
                _vector_store = VectorStore()
                logger.info("VectorStore 인스턴스 생성")
    return _vector_store

def get_retriever():
    """RAG 검색기 lazy loading (thread-safe)"""
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            # Double-checked locking pattern
            if _retriever is None:
                _retriever = RAGRetriever()
                logger.info("RAGRetriever 인스턴스 생성")
    return _retriever


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    RAG 기반 질의응답
    
    동적 threshold가 항상 활성화되어 검색 결과에 따라 자동으로 조정됩니다.
    
    Args:
        request: 질의응답 요청
        
    Returns:
        QueryResponse: 질의응답 결과
    """
    try:
        logger.info(f"질의응답 요청: {request.query} (동적 threshold 자동 적용)")
        
        # 인스턴스 lazy loading
        retriever = get_retriever()
        
        response = retriever.query(request)
        
        return response
        
    except Exception as e:
        logger.exception("질의응답 중 오류")
        raise HTTPException(
            status_code=500,
            detail=f"질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """
    RAG 시스템 통계
    
    Returns:
        dict: 시스템 통계
    """
    try:
        # 인스턴스 lazy loading
        vector_store = get_vector_store()
        
        doc_count = vector_store.count_documents()
        
        stats = {
            "total_chunks": doc_count,
            "collection_name": rag_config.CHROMA_COLLECTION_NAME,
            "embedding_model": rag_config.EMBEDDING_MODEL,
            "translation_model": rag_config.TRANSLATION_MODEL,
            "llm_model": rag_config.OPENAI_MODEL,
            "top_k": rag_config.RAG_TOP_K,
            "dynamic_threshold_range": f"{rag_config.RAG_MIN_SIMILARITY_THRESHOLD} ~ {rag_config.RAG_MAX_SIMILARITY_THRESHOLD}",
            "chunk_size": rag_config.RAG_CHUNK_SIZE,
            "chunk_overlap": rag_config.RAG_CHUNK_OVERLAP
        }
        
        return stats
        
    except Exception as e:
        logger.exception("통계 조회 중 오류")
        raise HTTPException(
            status_code=500,
            detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )

