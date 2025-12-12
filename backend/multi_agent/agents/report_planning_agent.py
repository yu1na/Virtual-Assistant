"""
Report Planning Agent

업무 플래닝 전문 에이전트
- 최근 3일 일일보고서 기반 오늘 업무 추천
- today_plan_chain.py 기능 완전 이관
- RAG 미사용, 순수 LLM + rule 기반
"""

from typing import Any, Dict, Optional
from datetime import date

from multi_agent.agents.report_base import ReportBaseAgent
from multi_agent.agents.report_main_router import ReportPromptRegistry
from app.domain.report.planner.today_plan_chain import TodayPlanGenerator
from app.domain.report.planner.tools import YesterdayReportTool, get_yesterday_report
from app.domain.report.planner.schemas import TodayPlanRequest
from app.domain.report.search.retriever import UnifiedRetriever
from app.infrastructure.vector_store_report import get_report_vector_store
from app.llm.client import LLMClient


class ReportPlanningAgent(ReportBaseAgent):
    """업무 플래닝 에이전트"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None, prompt_registry=None):
        """초기화"""
        super().__init__(
            name="ReportPlanningAgent",
            description="업무 플래닝 및 일정 관리를 도와주는 에이전트입니다. 최근 일일보고서를 기반으로 오늘 해야 할 업무를 추천합니다.",
            llm_client=llm_client
        )
        self.prompt_registry = prompt_registry or ReportPromptRegistry
        
        # TodayPlanGenerator 초기화 (기존 로직 활용)
        from app.infrastructure.database.session import SessionLocal
        
        self.db_session_factory = SessionLocal
        # YesterdayReportTool은 db 세션이 필요하므로,
        # 여기서는 임시 세션으로 초기화
        # 실제로는 TodayPlanGenerator에서 사용할 때마다 새로운 세션을 생성해서 사용해야 하지만,
        # YesterdayReportTool의 구조상 초기화 시 세션이 필요하므로 임시로 생성
        temp_db = SessionLocal()
        retriever_tool = YesterdayReportTool(temp_db)
        temp_db.close()  # 임시 세션 닫기 (실제 사용 시에는 새로운 세션 사용)
        
        # VectorDB 검색기 초기화 (선택적)
        try:
            vector_store = get_report_vector_store()
            collection = vector_store.get_collection()
            self.vector_retriever = UnifiedRetriever(
                collection=collection,
                openai_api_key=None,
            )
        except Exception as e:
            print(f"[WARNING] VectorDB 초기화 실패 (업무 플래닝은 계속 가능): {e}")
            self.vector_retriever = None
        
        # TodayPlanGenerator 생성
        self.plan_generator = TodayPlanGenerator(
            retriever_tool=retriever_tool,
            llm_client=self.llm,
            vector_retriever=self.vector_retriever,
            prompt_registry=self.prompt_registry,
        )

    def configure_prompts(self, prompt_registry):
        """Prompt registry 주입 (router에서 호출)."""
        self.prompt_registry = prompt_registry or ReportPromptRegistry
        if hasattr(self.plan_generator, "prompt_registry"):
            self.plan_generator.prompt_registry = self.prompt_registry
    
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        업무 플래닝 요청 처리
        
        Args:
            query: 사용자 질문 (예: "오늘 업무 추천해줘")
            context: {"owner": str, "target_date": date} 포함
            
        Returns:
            플래닝 결과 문자열
        """
        if context and context.get("prompt_registry"):
            self.configure_prompts(context.get("prompt_registry"))

        # 컨텍스트에서 target_date 추출 (owner는 더 이상 필수 아님)
        if not context:
            context = {}
        
        target_date = context.get("target_date")
        if not target_date:
            target_date = date.today()
        
        # TodayPlanRequest 생성 (owner는 None으로 전달, 필터링에 사용하지 않음)
        request = TodayPlanRequest(
            owner=None,  # owner 필터링 제거
            target_date=target_date
        )
        
        try:
            # 업무 플래닝 생성
            response = await self.plan_generator.generate(request)
            
            # 응답 포맷팅
            result = f"📋 {target_date} 업무 플래닝\n\n"
            result += f"{response.summary}\n\n"
            
            for idx, task in enumerate(response.tasks, 1):
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task.priority, "⚪")
                result += f"{idx}. {priority_emoji} {task.title}\n"
                result += f"   설명: {task.description}\n"
                result += f"   우선순위: {task.priority}, 예상 시간: {task.expected_time}, 카테고리: {task.category}\n\n"
            
            if response.source_date:
                result += f"\n📅 참조 날짜: {response.source_date}"
            
            return result
            
        except Exception as e:
            print(f"[ERROR] ReportPlanningAgent 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            return f"업무 플래닝 생성 중 오류가 발생했습니다: {str(e)}"
    
    def generate_plan_sync(self, owner: Optional[str], target_date: date) -> Dict[str, Any]:
        """
        동기 버전: 업무 플래닝 생성 (API 엔드포인트용)
        
        Args:
            owner: 작성자 (deprecated, 필터링에 사용하지 않음)
            target_date: 대상 날짜
            
        Returns:
            플래닝 결과 딕셔너리
        """
        request = TodayPlanRequest(
            owner=owner,
            target_date=target_date
        )
        
        response = self.plan_generator.generate_sync(request)
        
        return {
            "tasks": [task.model_dump() for task in response.tasks],
            "summary": response.summary,
            "source_date": str(response.source_date) if response.source_date else None,
            "owner": response.owner,
            "target_date": str(response.target_date or target_date),
            "task_sources": [source.model_dump() for source in response.task_sources] if response.task_sources else []
        }

