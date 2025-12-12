"""
Insurance RAG Agent

보험 상품, 청구 절차, 규정 등 보험 관련 질문을 처리하는 에이전트입니다.
보험 매뉴얼 문서 기반 RAG를 활용합니다.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent

# 보험 문서 검색 에이전트
class InsuranceRAGAgent(BaseAgent):

    # 초기화 함수
    def __init__(self):
        super().__init__(
            name="insurance_rag",
            description="보험 상품, 청구 절차, 규정, 특약 등 보험 관련 질문에 답변하는 에이전트입니다. "
                       "보험 매뉴얼 문서를 기반으로 정확한 정보를 제공합니다."
        )
        # Lazy loading: 실제 사용 시에만 RAGPipeline 로드
        self._rag_pipeline = None
    
    # @property: 메소드를 변수처럼 사용할 수 있게 해주는 기능
    @property
    def rag_pipeline(self):
        """Insurance RAG Pipeline lazy loading"""
        if self._rag_pipeline is None:
            from app.domain.rag.Insurance.services.rag_pipeline import RAGPipeline
            # Insurance RAG 파이프라인 초기화
            self._rag_pipeline = RAGPipeline()
        return self._rag_pipeline
    
    # 문서 검색 및 답변을 생성해주는 비동기 함수
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:

        print(f"\n[INSURANCE AGENT] Processing query: {query[:100]}...")
        
        try:
            # 컨텍스트에서 top_k 추출 (기본값: 5)
            top_k = 5
            if context and "top_k" in context:
                top_k = context["top_k"]
            
            print(f"[INSURANCE AGENT] Using top_k={top_k}")
            
            # RAG 파이프라인으로 답변 생성
            result = self.rag_pipeline.run(
                question=query,
                top_k=top_k
            )
            
            print(f"[INSURANCE AGENT] Generated answer length: {len(result.answer)} chars")
            print(f"[INSURANCE AGENT] Answer: {result.answer[:200]}...")  # 첫 200자만 출력
            
            # 답변 반환
            return result.answer
            
        except Exception as e:
            error_msg = f"보험 문서 검색 중 오류가 발생했습니다: {str(e)}"
            print(f"[INSURANCE AGENT ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            return error_msg
    
    # 에이전트 기능 목록 리턴 함수
    def get_capabilities(self) -> list:

        return [
            "보험 상품 조회",
            "청구 절차 안내",
            "보험 규정 설명",
            "특약 정보",
            "보험금 보장 범위",
            "프리미엄/보험료 정보",
        ]
