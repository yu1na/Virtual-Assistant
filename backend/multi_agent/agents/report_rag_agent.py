"""
Report RAG Agent

일일보고서 데이터 검색 및 질의응답 전문 에이전트
- rag_chain.py, rag_service.py 기능 완전 이관
- 벡터 검색 기반 QA
- 날짜 필터링 로직 포함
"""

from typing import Any, Dict, Optional, List
from datetime import date

from multi_agent.agents.report_base import ReportBaseAgent
from multi_agent.agents.report_main_router import ReportPromptRegistry
from app.domain.report.core.rag_chain import ReportRAGChain
from app.domain.report.search.hybrid_search import HybridSearcher
from app.domain.report.search.intent_router import IntentRouter
from app.infrastructure.vector_store_report import get_report_vector_store
from app.llm.client import LLMClient


class ReportRAGAgent(ReportBaseAgent):
    """일일보고서 RAG 챗봇 에이전트"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None, prompt_registry=None):
        """초기화"""
        super().__init__(
            name="ReportRAGAgent",
            description="일일보고서 데이터를 검색하여 질문에 답변하는 에이전트입니다. 과거 업무 내역, 고객 상담 기록 등을 조회할 수 있습니다.",
            llm_client=llm_client
        )
        self.prompt_registry = prompt_registry or ReportPromptRegistry
        
        # VectorDB 초기화
        vector_store = get_report_vector_store()
        collection = vector_store.get_collection()
        
        # HybridSearcher 사용 (rag_chain.py가 기대하는 타입)
        self.retriever = HybridSearcher(collection=collection)
        
        # RAG Chain은 owner별로 생성되므로, 여기서는 초기화하지 않음
        self.rag_chains: Dict[str, ReportRAGChain] = {}

    def configure_prompts(self, prompt_registry):
        """Prompt registry 주입 (router에서 호출)."""
        self.prompt_registry = prompt_registry or ReportPromptRegistry
        for owner_key, chain in self.rag_chains.items():
            chain.prompt_registry = self.prompt_registry
    
    def _get_rag_chain(self, owner: str) -> ReportRAGChain:
        """
        Owner별 RAG Chain 가져오기 (캐싱)
        
        Args:
            owner: 작성자 (deprecated, 단일 워크스페이스이므로 하나만 사용)
            
        Returns:
            RAG Chain
        """
        # 단일 워크스페이스이므로 하나의 RAG Chain만 사용
        if owner not in self.rag_chains:
            self.rag_chains[owner] = ReportRAGChain(
                owner=owner,  # 호환성 유지 (실제로는 필터링에 사용 안 함)
                retriever=self.retriever,
                llm=self.llm,
                top_k=5,
                prompt_registry=self.prompt_registry,
            )
        return self.rag_chains[owner]
    
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        RAG 질의응답 처리
        
        Args:
            query: 사용자 질문 (예: "나 최근에 연금 상담 언제 했었지?")
            context: {"owner": str, "reference_date": date, "date_range": dict} 포함
            
        Returns:
            답변 문자열
        """
        if context and context.get("prompt_registry"):
            self.configure_prompts(context.get("prompt_registry"))

        # 컨텍스트에서 날짜 정보 추출 (owner는 더 이상 필수 아님)
        if not context:
            context = {}
        
        reference_date = context.get("reference_date", date.today())
        date_range = context.get("date_range")

        # 인텐트 라우터로 날짜 범위 추론 (context에 없을 때만)
        if not date_range:
            intent_router = IntentRouter()
            intent = intent_router.route(query, reference_date=reference_date)
            date_range = intent.filters.get("date_range")
        
        # RAG Chain 가져오기 (owner는 상수 사용, 필터링에 사용하지 않음)
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        rag_chain = self._get_rag_chain(REPORT_OWNER)
        
        print(f"[DEBUG] ReportRAGAgent.process 시작: query='{query}', date_range={date_range}")
        
        try:
            # RAG 파이프라인 실행
            print(f"[DEBUG] rag_chain.generate_response 호출 전")
            result = await rag_chain.generate_response(
                query=query,
                date_range=date_range,
                reference_date=reference_date
            )
            print(f"[DEBUG] rag_chain.generate_response 완료: answer 길이={len(result.get('answer', ''))}")
            
            # 응답 포맷팅
            answer = result["answer"]
            
            # 근거 문서 정보 추가 (있으면)
            if result.get("has_results") and result.get("sources"):
                answer += "\n\n📚 참고 문서:"
                for idx, source in enumerate(result["sources"][:3], 1):  # 최대 3개만
                    answer += f"\n{idx}. [{source['date']}] {source['text_preview']}"
            
            print(f"[DEBUG] ReportRAGAgent.process 완료: answer 반환 (길이={len(answer)})")
            return answer
            
        except Exception as e:
            print(f"[ERROR] ReportRAGAgent 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            return f"일일보고서 검색 중 오류가 발생했습니다: {str(e)}"
    
    async def search_reports(
        self,
        owner: str,
        query: str,
        date_range: Optional[Dict[str, date]] = None,
        reference_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        보고서 검색 (API 엔드포인트용)
        
        Args:
            owner: 작성자
            query: 검색 쿼리
            date_range: 날짜 범위
            reference_date: 기준 날짜
            
        Returns:
            검색 결과 딕셔너리
        """
        rag_chain = self._get_rag_chain(owner)
        
        result = await rag_chain.generate_response(
            query=query,
            date_range=date_range,
            reference_date=reference_date
        )
        
        return result

