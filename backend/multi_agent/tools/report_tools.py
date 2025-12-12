"""
Report Agent Tools

각 보고서 전문 에이전트를 LangChain Tool로 래핑합니다.
ReportMainRouterAgent가 이 도구들을 호출하여 작업을 수행합니다.
서브 에이전트 호출 전문

LangChain 1.1.0 호환
"""

from typing import List
from langchain_core.tools import tool


# 전역 에이전트 인스턴스 (Lazy loading)
_planning_agent = None
_report_generation_agent = None
_report_rag_agent = None


# 업무 플래닝 에이전트 호출
def get_planning_agent():
    """ReportPlanningAgent 싱글톤 인스턴스 반환"""
    global _planning_agent
    if _planning_agent is None:
        from multi_agent.agents.report_planning_agent import ReportPlanningAgent
        _planning_agent = ReportPlanningAgent()
    return _planning_agent


# 보고서 작성/생성 에이전트 호출
def get_report_generation_agent():
    """ReportGenerationAgent 싱글톤 인스턴스 반환"""
    global _report_generation_agent
    if _report_generation_agent is None:
        from multi_agent.agents.report_generation_agent import ReportGenerationAgent
        _report_generation_agent = ReportGenerationAgent()
    return _report_generation_agent


# RAG 챗봇 에이전트 호출
def get_report_rag_agent():
    """ReportRAGAgent 싱글톤 인스턴스 반환"""
    global _report_rag_agent
    if _report_rag_agent is None:
        from multi_agent.agents.report_rag_agent import ReportRAGAgent
        _report_rag_agent = ReportRAGAgent()
    return _report_rag_agent


# ========================================
# LangChain Tool 정의
# ========================================

@tool
async def planning_tool(query: str) -> str:
    """업무 플래닝과 일정 관리를 도와줍니다. 오늘 할 일 추천, 업무 우선순위 결정 등을 처리합니다."""
    agent = get_planning_agent()
    # Note: context는 ReportMainRouterAgent에서 주입
    return await agent.process(query)


@tool
async def report_tool(query: str) -> str:
    """일일/주간/월간 보고서 작성 및 생성을 도와줍니다. FSM 기반 대화형 보고서 작성, 주간/월간 보고서 자동 생성을 처리합니다."""
    agent = get_report_generation_agent()
    # Note: context는 ReportMainRouterAgent에서 주입
    return await agent.process(query)


@tool
async def rag_tool(query: str) -> str:
    """일일보고서 데이터를 검색하여 질문에 답변합니다. 과거 업무 내역, 고객 상담 기록, 미종결 업무 등을 조회합니다."""
    agent = get_report_rag_agent()
    # Note: context는 ReportMainRouterAgent에서 주입
    return await agent.process(query)


# 모든 에이전트 도구 리스트 반환
def get_all_report_agent_tools() -> List:
    """
    모든 Report Agent Tool 반환
    
    Returns:
        Tool 리스트
    """
    return [
        planning_tool,
        report_tool,
        rag_tool,
    ]

