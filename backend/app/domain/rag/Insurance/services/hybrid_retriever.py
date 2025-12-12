"""
Hybrid Retriever for Insurance RAG
Dense (Vector) + Sparse (BM25) 하이브리드 검색
"""
import time
from typing import List, Tuple, Optional, Dict, Any
from rank_bm25 import BM25Okapi
import numpy as np

from .models import Query, InsuranceDocument, RetrievalResult
from ..config import insurance_config
from .exceptions import RetrievalException
from .providers import SimpleEmbeddingProvider, SimpleVectorStore


class HybridRetriever:
    """하이브리드 검색기 (Dense + Sparse)"""
    
    def __init__(
        self,
        vector_store: SimpleVectorStore,
        embedding_provider: SimpleEmbeddingProvider,
        dense_weight: float = 0.7,  # Dense 가중치 (기본 70%)
        sparse_weight: float = 0.3,  # Sparse 가중치 (기본 30%)
        top_k: int = None,
        similarity_threshold: float = None
    ):
        """
        하이브리드 검색기 초기화
        
        Args:
            vector_store: 벡터 스토어
            embedding_provider: 임베딩 제공자
            dense_weight: Dense (벡터) 검색 가중치 (0~1)
            sparse_weight: Sparse (BM25) 검색 가중치 (0~1)
            top_k: 반환할 문서 개수
            similarity_threshold: 유사도 임계값
        """
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.top_k = top_k or insurance_config.RAG_TOP_K
        self.similarity_threshold = similarity_threshold or insurance_config.RAG_MIN_SIMILARITY_THRESHOLD
        
        # BM25 인덱스 (lazy loading)
        self._bm25_index = None
        self._bm25_documents = None
        self._bm25_metadata = None
    
    def _initialize_bm25(self):
        """BM25 인덱스 초기화 (모든 문서 로드)"""
        if self._bm25_index is not None:
            return
        
        print("[HYBRID] BM25 인덱스 초기화 중...")
        
        # 벡터 스토어에서 모든 문서 가져오기
        try:
            # ChromaDB에서 모든 문서 조회
            collection = self.vector_store.collection
            all_data = collection.get()
            
            if not all_data or not all_data.get('documents'):
                print("[HYBRID] 경고: 문서가 없습니다. BM25 인덱스를 생성할 수 없습니다.")
                self._bm25_documents = []
                self._bm25_metadata = []
                self._bm25_index = None
                return
            
            self._bm25_documents = all_data['documents']
            self._bm25_metadata = all_data.get('metadatas', [{}] * len(self._bm25_documents))
            
            # 문서를 토큰화 (공백 기준 분리)
            tokenized_docs = [doc.lower().split() for doc in self._bm25_documents]
            
            # BM25 인덱스 생성
            self._bm25_index = BM25Okapi(tokenized_docs)
            
            print(f"[HYBRID] BM25 인덱스 생성 완료: {len(self._bm25_documents)}개 문서")
            
        except Exception as e:
            print(f"[HYBRID] BM25 인덱스 초기화 실패: {e}")
            self._bm25_documents = []
            self._bm25_metadata = []
            self._bm25_index = None
    
    def _bm25_search(self, query: str, top_k: int) -> Tuple[List[InsuranceDocument], List[float]]:
        """
        BM25 검색 수행
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 개수
            
        Returns:
            (문서 리스트, 점수 리스트)
        """
        self._initialize_bm25()
        
        if self._bm25_index is None or not self._bm25_documents:
            print("[HYBRID] BM25 인덱스가 없습니다. 빈 결과 반환")
            return [], []
        
        # 쿼리 토큰화
        tokenized_query = query.lower().split()
        
        # BM25 점수 계산
        scores = self._bm25_index.get_scores(tokenized_query)
        
        # 점수 순으로 정렬하여 top_k 선택
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        documents = []
        doc_scores = []
        
        for idx in top_indices:
            if idx < len(self._bm25_documents):
                doc = InsuranceDocument(
                    content=self._bm25_documents[idx],
                    metadata=self._bm25_metadata[idx] if idx < len(self._bm25_metadata) else {}
                )
                documents.append(doc)
                doc_scores.append(float(scores[idx]))
        
        return documents, doc_scores
    
    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """
        점수 정규화 (0~1 범위로)
        
        Args:
            scores: 원본 점수 리스트
            
        Returns:
            정규화된 점수 리스트
        """
        if not scores:
            return []
        
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return [1.0] * len(scores)
        
        return [(s - min_score) / (max_score - min_score) for s in scores]
    
    def _merge_results(
        self,
        dense_docs: List[InsuranceDocument],
        dense_scores: List[float],
        sparse_docs: List[InsuranceDocument],
        sparse_scores: List[float],
        top_k: int
    ) -> Tuple[List[InsuranceDocument], List[float]]:
        """
        Dense와 Sparse 결과를 가중치 기반으로 병합
        
        Args:
            dense_docs: Dense 검색 문서
            dense_scores: Dense 검색 점수
            sparse_docs: Sparse 검색 문서
            sparse_scores: Sparse 검색 점수
            top_k: 최종 반환할 문서 개수
            
        Returns:
            (병합된 문서 리스트, 병합된 점수 리스트)
        """
        # 점수 정규화
        dense_scores_norm = self._normalize_scores(dense_scores)
        sparse_scores_norm = self._normalize_scores(sparse_scores)
        
        # 문서별 점수 집계 (content 기준으로 중복 제거)
        doc_scores = {}
        
        # Dense 결과 추가
        for doc, score in zip(dense_docs, dense_scores_norm):
            content = doc.content
            if content not in doc_scores:
                doc_scores[content] = {
                    'doc': doc,
                    'dense_score': score * self.dense_weight,
                    'sparse_score': 0.0
                }
            else:
                doc_scores[content]['dense_score'] = max(
                    doc_scores[content]['dense_score'],
                    score * self.dense_weight
                )
        
        # Sparse 결과 추가
        for doc, score in zip(sparse_docs, sparse_scores_norm):
            content = doc.content
            if content not in doc_scores:
                doc_scores[content] = {
                    'doc': doc,
                    'dense_score': 0.0,
                    'sparse_score': score * self.sparse_weight
                }
            else:
                doc_scores[content]['sparse_score'] = max(
                    doc_scores[content]['sparse_score'],
                    score * self.sparse_weight
                )
        
        # 최종 점수 계산 (dense + sparse)
        final_results = []
        for content, data in doc_scores.items():
            final_score = data['dense_score'] + data['sparse_score']
            final_results.append((data['doc'], final_score))
        
        # 점수 순으로 정렬
        final_results.sort(key=lambda x: x[1], reverse=True)
        
        # Top-K 선택
        final_results = final_results[:top_k]
        
        merged_docs = [doc for doc, _ in final_results]
        merged_scores = [score for _, score in final_results]
        
        return merged_docs, merged_scores
    
    def retrieve(
        self,
        query: Query,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """
        하이브리드 검색 수행 (Dense + Sparse)
        
        Args:
            query: 쿼리 객체
            top_k: 반환할 문서 개수
            filter_metadata: 메타데이터 필터
            
        Returns:
            검색 결과
        """
        start_time = time.time()
        
        try:
            k = top_k or self.top_k
            
            print(f"[HYBRID] 하이브리드 검색 시작: '{query.question}' (Top-{k})")
            print(f"[HYBRID] 가중치 - Dense: {self.dense_weight}, Sparse: {self.sparse_weight}")
            
            # 1. Dense (벡터) 검색
            dense_start = time.time()
            query_embedding = self.embedding_provider.embed_text(query.question)
            dense_docs, dense_scores = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=k * 2,  # 더 많이 가져와서 병합
                filter_metadata=filter_metadata
            )
            dense_time = (time.time() - dense_start) * 1000
            print(f"[HYBRID] Dense 검색 완료: {len(dense_docs)}개 문서 ({dense_time:.2f}ms)")
            
            # 2. Sparse (BM25) 검색
            sparse_start = time.time()
            sparse_docs, sparse_scores = self._bm25_search(query.question, k * 2)
            sparse_time = (time.time() - sparse_start) * 1000
            print(f"[HYBRID] Sparse 검색 완료: {len(sparse_docs)}개 문서 ({sparse_time:.2f}ms)")
            
            # 3. 결과 병합
            merge_start = time.time()
            merged_docs, merged_scores = self._merge_results(
                dense_docs, dense_scores,
                sparse_docs, sparse_scores,
                k
            )
            merge_time = (time.time() - merge_start) * 1000
            print(f"[HYBRID] 결과 병합 완료: {len(merged_docs)}개 문서 ({merge_time:.2f}ms)")
            
            # 4. 유사도 임계값 필터링
            filtered_docs = []
            filtered_scores = []
            
            for doc, score in zip(merged_docs, merged_scores):
                if score >= self.similarity_threshold:
                    filtered_docs.append(doc)
                    filtered_scores.append(score)
            
            print(f"[HYBRID] Threshold 필터링: {len(filtered_docs)}/{len(merged_docs)} 문서")
            
            retrieval_time = (time.time() - start_time) * 1000
            
            return RetrievalResult(
                documents=filtered_docs,
                scores=filtered_scores,
                query=query,
                retrieval_time_ms=retrieval_time,
                metadata={
                    "top_k": k,
                    "threshold": self.similarity_threshold,
                    "filtered_count": len(filtered_docs),
                    "total_count": len(merged_docs),
                    "dense_weight": self.dense_weight,
                    "sparse_weight": self.sparse_weight,
                    "dense_time_ms": dense_time,
                    "sparse_time_ms": sparse_time,
                    "merge_time_ms": merge_time
                }
            )
            
        except Exception as e:
            raise RetrievalException(
                f"하이브리드 검색 실패: {str(e)}",
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
