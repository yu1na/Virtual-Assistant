"""
Retrieval service
"""
import time
from typing import List, Tuple, Optional, Dict, Any

from .models import Query, InsuranceDocument, RetrievalResult
from ..config import insurance_config
from .exceptions import RetrievalException
from .providers import SimpleEmbeddingProvider, SimpleVectorStore



class Retriever:
    """검색 서비스"""
    
    def __init__(
        self,
        vector_store: SimpleVectorStore,
        embedding_provider: SimpleEmbeddingProvider,
        top_k: int = None,
        similarity_threshold: float = None
    ):
        """
        검색기 초기화
        
        Args:
            vector_store: 벡터 스토어
            embedding_provider: 임베딩 제공자
            top_k: 반환할 문서 개수
            similarity_threshold: 유사도 임계값
        """
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.top_k = top_k or insurance_config.RAG_TOP_K
        self.similarity_threshold = similarity_threshold or insurance_config.RAG_MIN_SIMILARITY_THRESHOLD
    
    def retrieve(
        self,
        query: Query,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """
        쿼리로 문서 검색
        
        Args:
            query: 쿼리 객체
            top_k: 반환할 문서 개수 (기본값: config.top_k)
            filter_metadata: 메타데이터 필터
            
        Returns:
            검색 결과
        """
        start_time = time.time()
        
        try:
            k = top_k or self.top_k
            
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_provider.embed_text(query.question)
            
            # 벡터 검색
            documents, scores = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=k,
                filter_metadata=filter_metadata
            )
            
            # 유사도 임계값 필터링
            filtered_docs = []
            filtered_scores = []
            
            print(f"[RETRIEVER DEBUG] Retrieved {len(documents)} documents")
            print(f"[RETRIEVER DEBUG] Similarity threshold: {self.similarity_threshold}")
            print(f"[RETRIEVER DEBUG] Scores: {scores[:5] if len(scores) > 0 else 'none'}")
            
            # 검색된 문서 내용 미리보기 (첫 번째 문서만)
            if documents:
                first_doc = documents[0].content[:200] if hasattr(documents[0], 'content') else str(documents[0])[:200]
                print(f"[RETRIEVER DEBUG] Top document preview: {first_doc}...")
            
            for doc, score in zip(documents, scores):
                if score >= self.similarity_threshold:
                    filtered_docs.append(doc)
                    filtered_scores.append(score)
            
            print(f"[RETRIEVER DEBUG] Filtered: {len(filtered_docs)}/{len(documents)} documents")
            
            retrieval_time = (time.time() - start_time) * 1000  # ms
            
            return RetrievalResult(
                documents=filtered_docs,
                scores=filtered_scores,
                query=query,
                retrieval_time_ms=retrieval_time,
                metadata={
                    "top_k": k,
                    "threshold": self.similarity_threshold,
                    "filtered_count": len(filtered_docs),
                    "total_count": len(documents)
                }
            )
            
        except Exception as e:
            raise RetrievalException(
                f"Failed to retrieve documents: {str(e)}",
                details={"query": query.question}
            )
    
    def retrieve_by_text(
        self,
        question: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """
        텍스트로 직접 검색 (Query 객체 자동 생성)
        
        Args:
            question: 질문 텍스트
            top_k: 반환할 문서 개수
            filter_metadata: 메타데이터 필터
            
        Returns:
            검색 결과
        """
        query = Query(question=question)
        return self.retrieve(query=query, top_k=top_k, filter_metadata=filter_metadata)
    
    def get_relevant_context(
        self,
        query: Query,
        top_k: Optional[int] = None,
        max_context_length: int = 4000
    ) -> str:
        """
        검색된 문서를 컨텍스트 문자열로 변환
        
        Args:
            query: 쿼리 객체
            top_k: 반환할 문서 개수
            max_context_length: 최대 컨텍스트 길이
            
        Returns:
            컨텍스트 문자열
        """
        result = self.retrieve(query=query, top_k=top_k)
        
        context_parts = []
        current_length = 0
        
        for idx, (doc, score) in enumerate(zip(result.documents, result.scores), 1):
            chunk_text = f"[문서 {idx}] (유사도: {score:.2f})\n{doc.content}\n"
            chunk_length = len(chunk_text)
            
            if current_length + chunk_length > max_context_length:
                break
            
            context_parts.append(chunk_text)
            current_length += chunk_length
        
        return "\n".join(context_parts)
