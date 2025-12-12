"""
Report Agent

보고서 메인 에이전트 - ReportMainRouterAgent를 래핑
업무 플래닝, 보고서 작성, 보고서 검색을 전문 에이전트에게 라우팅
"""

from typing import Dict, Any, Optional
from datetime import date
from .base_agent import BaseAgent


class ReportAgent(BaseAgent):
    """
    보고서 메인 에이전트
    
    ReportMainRouterAgent를 래핑하여 3가지 기능 제공:
    1. 업무 플래닝 (ReportPlanningAgent)
    2. 보고서 작성 (ReportGenerationAgent)
    3. 보고서 검색 (ReportRAGAgent)
    """
    
    def __init__(self):
        super().__init__(
            name="report",
            description="업무 플래닝, 보고서 작성, 보고서 검색을 수행하는 에이전트입니다. "
                       "금일 추천 업무, 일간/주간/월간 보고서 작성, 과거 보고서 검색(RAG)을 제공합니다."
        )
        # Lazy loading: 실제 사용 시에만 라우터 로드
        self._router = None
    
    @property
    def router(self):
        """ReportMainRouterAgent lazy loading"""
        if self._router is None:
            from multi_agent.agents.report_main_router import ReportMainRouterAgent
            self._router = ReportMainRouterAgent()
        return self._router
    
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        리포트 관련 작업 수행 (라우터에게 위임)
        
        Args:
            query: 사용자 질문
            context: 추가 컨텍스트 (owner, target_date 등)
            
        Returns:
            str: 리포트 응답 (intent 정보 포함 가능)
        """
        try:
            # 기본 컨텍스트 설정
            if context is None:
                context = {}
            
            # owner는 더 이상 필수 아님 (단일 워크스페이스로 동작)
            if "target_date" not in context:
                context["target_date"] = date.today()
            
            # ReportMainRouterAgent에게 라우팅
            # intent를 확인하기 위해 classify_intent 사용
            intent = await self.router.classify_intent(query)
            
            print(f"[DEBUG] ReportAgent.process - Intent: {intent}, Query: {query}")
            
            # intent가 lookup이면 특수 마커 추가 (프론트엔드에서 파싱)
            if intent == "lookup" or intent == "lookup":
                response = await self.router.process(query, context)
                marked_response = f"__INTENT_LOOKUP__{response}"
                print(f"[DEBUG] ReportAgent - Lookup intent 감지, 마커 추가 (응답 길이: {len(marked_response)})")
                return marked_response
            
            # 그 외의 경우는 일반 처리
            response = await self.router.process(query, context)
            return response
                
        except Exception as e:
            return f"보고서 처리 중 오류가 발생했습니다: {str(e)}"
    
    def get_capabilities(self) -> list:
        """에이전트 기능 목록"""
        return [
            "업무 플래닝 및 추천 업무 제공",
            "일간/주간/월간 보고서 작성",
            "과거 보고서 검색 (RAG)",
            "실적 및 성과 조회",
        ]

