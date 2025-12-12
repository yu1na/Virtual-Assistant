"""
RAG Pipeline - Orchestrator
"""
import time
from typing import Optional, Dict, Any
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from .models import Query, GenerationResult
from ..config import insurance_config
from .exceptions import InsuranceRAGException
from .providers import SimpleVectorStore, SimpleEmbeddingProvider, SimpleLLMProvider

from .retriever import Retriever
from .hybrid_retriever import HybridRetriever
from .generator import Generator



class RAGPipeline:
    """RAG 전체 파이프라인 오케스트레이터"""
    
    def __init__(
        self,
        vector_store: Optional[SimpleVectorStore] = None,
        embedding_provider: Optional[SimpleEmbeddingProvider] = None,
        llm_provider: Optional[SimpleLLMProvider] = None,
        retriever: Optional[Retriever] = None,
        generator: Optional[Generator] = None
    ):
        """
        RAG 파이프라인 초기화
        
        Args:
            vector_store: 벡터 스토어 (None이면 기본 ChromaDB 사용)
            embedding_provider: 임베딩 제공자 (None이면 기본 OpenAI 사용)
            llm_provider: LLM 제공자 (None이면 기본 OpenAI 사용)
            retriever: 검색기
            generator: 답변 생성기
        """
        # Infrastructure 레이어 초기화
        self.embedding_provider = embedding_provider or self._create_default_embedding_provider()
        self.vector_store = vector_store or self._create_default_vector_store()
        self.llm_provider = llm_provider or self._create_default_llm_provider()
        
        # Service 레이어 초기화
        self.retriever = retriever or HybridRetriever(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
            dense_weight=0.7,  # Dense (벡터) 검색 70%
            sparse_weight=0.3  # Sparse (BM25) 검색 30%
        )
        self.generator = generator or Generator(
            llm_provider=self.llm_provider
        )
    
    def run(
        self,
        question: str,
        top_k: Optional[int] = None,
        validate_answer: bool = False,
        user_id: Optional[str] = None
    ) -> GenerationResult:
        """
        전체 RAG 파이프라인 실행
        
        Args:
            question: 사용자 질문
            top_k: 검색할 문서 개수
            validate_answer: 답변 검증 수행 여부
            user_id: 사용자 ID
            
        Returns:
            답변 생성 결과
        """
        try:
            # 1. 쿼리 객체 생성
            query = Query(question=question, user_id=user_id)
            
            # 2. 검색 (Retrieval)
            retrieval_result = self.retriever.retrieve(query=query, top_k=top_k)
            
            if not retrieval_result.documents:
                # 검색 결과가 없는 경우
                return GenerationResult(
                    answer="죄송합니다. 관련된 정보를 찾을 수 없습니다.",
                    query=query,
                    source_documents=[],
                    confidence_score=0.0,
                    generation_time_ms=0.0,
                    metadata={"error": "no_documents_found"}
                )
            
            # 3. 답변 생성 (Generation)
            generation_result = self.generator.generate(
                query=query,
                context_documents=retrieval_result.documents
            )
            
            # 4. 답변 검증 (선택사항)
            if validate_answer:
                context = self.retriever.get_relevant_context(query)
                is_valid, validated_answer = self.generator.validate_answer(
                    question=question,
                    context=context,
                    generated_answer=generation_result.answer
                )
                
                if not is_valid:
                    generation_result.answer = validated_answer
                    generation_result.confidence_score = 0.1
                    generation_result.metadata["validated"] = False
                else:
                    generation_result.metadata["validated"] = True
            
            # 메타데이터에 검색 정보 추가
            generation_result.metadata.update({
                "retrieval_time_ms": retrieval_result.retrieval_time_ms,
                "num_retrieved_docs": len(retrieval_result.documents),
                "retrieval_scores": retrieval_result.scores
            })
            
            return generation_result
            
        except Exception as e:
            raise InsuranceRAGException(
                f"RAG pipeline failed: {str(e)}",
                details={"question": question}
            )
    
    def run_simple(self, question: str) -> str:
        """
        간단한 질의응답 (답변 문자열만 반환)
        
        Args:
            question: 질문
            
        Returns:
            답변 문자열
        """
        result = self.run(question=question)
        return result.answer
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        파이프라인 정보 반환
        
        Returns:
            파이프라인 구성 정보
        """
        return {
            "vector_store": self.vector_store.__class__.__name__,
            "vector_store_info": self.vector_store.get_collection_info(),
            "embedding_model": self.embedding_provider.get_model_name(),
            "embedding_dimension": self.embedding_provider.get_embedding_dimension(),
            "llm_model": self.llm_provider.get_model_name(),
            "config": {
                "top_k": insurance_config.RAG_TOP_K,
                "similarity_threshold": insurance_config.RAG_MIN_SIMILARITY_THRESHOLD,
                "chunk_size": insurance_config.RAG_CHUNK_SIZE,
                "chunk_overlap": insurance_config.RAG_CHUNK_OVERLAP
            }
        }
    
    def _create_default_vector_store(self) -> SimpleVectorStore:
        """기본 벡터 스토어 생성 (ChromaDB)"""
        embedding_function = OpenAIEmbeddingFunction(
            api_key=insurance_config.OPENAI_API_KEY,
            model_name=insurance_config.EMBEDDING_MODEL
        )
        
        return SimpleVectorStore(
            collection_name=insurance_config.CHROMA_COLLECTION_NAME,
            persist_directory=insurance_config.CHROMA_PERSIST_DIRECTORY,
            embedding_function=embedding_function
        )
    
    def _create_default_embedding_provider(self) -> SimpleEmbeddingProvider:
        """기본 임베딩 제공자 생성 (OpenAI)"""
        return SimpleEmbeddingProvider(
            model=insurance_config.EMBEDDING_MODEL,
            dimensions=insurance_config.EMBEDDING_DIMENSION
        )
    
    def _create_default_llm_provider(self) -> SimpleLLMProvider:
        """기본 LLM 제공자 생성 (OpenAI)"""
        return SimpleLLMProvider(
            model=insurance_config.OPENAI_MODEL,
            temperature=insurance_config.OPENAI_TEMPERATURE,
            max_tokens=insurance_config.OPENAI_MAX_TOKENS
        )


# 편의 함수: 즉시 사용 가능한 파이프라인 생성
def create_insurance_rag_pipeline() -> RAGPipeline:
    """
    기본 설정으로 RAG 파이프라인 생성
    
    Returns:
        RAGPipeline 인스턴스
    """
    return RAGPipeline()
