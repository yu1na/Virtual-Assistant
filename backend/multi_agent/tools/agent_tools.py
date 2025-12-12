"""
Agent Tools

각 전문 에이전트를 LangChain Tool로 래핑합니다.
Supervisor Agent가 이 도구들을 호출하여 작업을 수행합니다.

LangChain 1.1.0 호환
"""

from typing import List, Dict, Any, Optional
from langchain_core.tools import tool, Tool

from ..context import get_session_id, get_user_context
from app.domain.chatbot.memory_manager import MemoryManager

# 전역 에이전트 인스턴스 (Lazy loading)
_chatbot_agent = None
_rag_agent = None
_brainstorming_agent = None
_report_agent = None
_therapy_agent = None
_notion_agent = None
_email_agent = None
_insurance_agent = None

# MemoryManager 초기화
memory_manager = MemoryManager()

# 챗봇 에이전트 호출
def get_chatbot_agent():
    global _chatbot_agent
    if _chatbot_agent is None:
        from multi_agent.agents.chatbot_agent import ChatbotAgent
        _chatbot_agent = ChatbotAgent()
    return _chatbot_agent

# 회사 문서/규정 검색 에이전트 호출
def get_rag_agent():
    global _rag_agent
    if _rag_agent is None:
        from multi_agent.agents.rag_agent import RAGAgent
        _rag_agent = RAGAgent()
    return _rag_agent

# 브레인스토밍 에이전트 호출
def get_brainstorming_agent():
    global _brainstorming_agent
    if _brainstorming_agent is None:
        from multi_agent.agents.brainstorming_agent import BrainstormingAgent
        _brainstorming_agent = BrainstormingAgent()
    return _brainstorming_agent


# 보고서 에이전트
def get_report_agent():
    global _report_agent
    if _report_agent is None:
        from multi_agent.agents.report_agent import ReportAgent
        _report_agent = ReportAgent()
    return _report_agent

# 심리 상담 에이전트 호출
def get_therapy_agent():
    global _therapy_agent
    if _therapy_agent is None:
        from multi_agent.agents.therapy_agent import TherapyAgent
        _therapy_agent = TherapyAgent()
    return _therapy_agent

# Notion 에이전트 호출
def get_notion_agent():
    global _notion_agent
    if _notion_agent is None:
        from backend.multi_agent.agents.notion_agent import NotionAgent
        _notion_agent = NotionAgent()
    return _notion_agent

# Email 에이전트 호출
def get_email_agent():
    global _email_agent
    if _email_agent is None:
        from backend.multi_agent.agents.email_agent import EmailAgent
        _email_agent = EmailAgent()
    return _email_agent

# Insurance RAG 에이전트 호출
def get_insurance_agent():
    global _insurance_agent
    if _insurance_agent is None:
        from backend.multi_agent.agents.insurance_rag_agent import InsuranceRAGAgent
        _insurance_agent = InsuranceRAGAgent()
    return _insurance_agent

def _parse_history_markdown(markdown: str) -> List[Dict[str, Any]]:
    """MemoryManager의 마크다운 히스토리를 파싱하여 리스트로 변환"""
    messages = []
    if not markdown:
        return messages
        
    # 구분자로 분리
    chunks = markdown.split("\n---\n")
    
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
            
        role = "unknown"
        if "## 👤 사용자" in chunk:
            role = "user"
        elif "## 🤖 AI 비서" in chunk:
            role = "assistant"
        else:
            continue # 헤더나 기타 내용
            
        # 내용 추출 (시간 다음 줄부터)
        lines = chunk.split('\n')
        content_start = -1
        for i, line in enumerate(lines):
            if line.startswith("**시간:**"):
                content_start = i + 2 # 빈 줄 건너뛰기
                break
        
        if content_start != -1 and content_start < len(lines):
            content = "\n".join(lines[content_start:]).strip()
            if content:
                messages.append({"role": role, "content": content})
            
    return messages

def get_current_context() -> Dict[str, Any]:
    """현재 컨텍스트(세션, 사용자, 대화 기록)를 반환"""
    session_id = get_session_id()
    user_context = get_user_context()
    
    context = user_context.copy()
    if session_id:
        context["session_id"] = session_id
        
        # 대화 기록 가져오기
        try:
            history_md = memory_manager.get_all_messages(session_id)
            history = _parse_history_markdown(history_md)
            context["conversation_history"] = history
        except Exception as e:
            print(f"[ERROR] History fetch failed: {e}")
            context["conversation_history"] = []
            
    return context

# Tool 정의

# 챗봇 툴 정의
@tool
async def chatbot_tool(query: str) -> str:
    """일반적인 대화와 질문에 답변합니다. 인사말, 잡담, 일상적인 질문을 처리합니다."""
    agent = get_chatbot_agent()
    context = get_current_context()
    return await agent.process(query, context=context)

# 회사 문서, 규정 및 정책을 검색하여 답변(HR)
@tool
async def rag_tool(query: str) -> str:
    """회사 문서, 규정, 정책을 검색하여 답변합니다. HR 규정, 복지 정책, 연차/휴가 규정 등을 처리합니다."""
    agent = get_rag_agent()
    context = get_current_context()
    return await agent.process(query, context=context)

# 브레인스토밍 기법 제안 -> 아이디어 도출
@tool
async def brainstorming_tool(query: str) -> str:
    """창의적인 아이디어와 브레인스토밍 기법을 제안합니다. 새로운 아이디어, 문제 해결 방법을 제공합니다."""
    agent = get_brainstorming_agent()
    context = get_current_context()
    return await agent.process(query, context=context)

# 일정 관리와 계획 수립을 도와줌
# 주의: planner_tool은 report_tool로 통합되었습니다.
# report_tool이 업무 플래닝을 처리하므로, planner_tool은 report_tool로 리다이렉트합니다.
@tool
async def planner_tool(query: str) -> str:
    """일정 관리와 계획 수립을 도와줍니다. 오늘의 할 일, 업무 일정 관리, 시간 관리 조언을 제공합니다."""
    # report_tool로 리다이렉트 (업무 플래닝은 report_tool이 처리)
    return await report_tool(query)

# 업무 플래닝, 보고서 작성, 보고서 검색/대화를 수행
@tool
async def report_tool(query: str) -> str:
    """
    업무 플래닝, 보고서 작성, 보고서 검색을 수행합니다.
    - 금일 추천 업무 및 업무 플래닝
    - 일일/주간/월간 보고서 작성 및 HTML 생성
    - 과거 보고서 검색 및 실적 조회 (RAG 기반 대화)
    """
    agent = get_report_agent()
    context = get_current_context()
    response = await agent.process(query, context=context)
    
    # intent 정보는 ReportAgent.process에서 마커로 포함되거나
    # supervisor에서 answer를 분석하여 추출하므로 여기서는 처리하지 않음
    return response

# 심리 상담 제공
@tool
async def therapy_tool(query: str) -> str:
    """심리 상담과 정신 건강 지원을 제공합니다. 감정적 지원, 스트레스 관리, 대인관계 조언을 제공합니다."""
    agent = get_therapy_agent()
    context = get_current_context()
    return await agent.process(query, context=context)

# Notion 페이지 관리
@tool
async def notion_tool(query: str) -> str:
    """Notion 페이지를 관리합니다. 페이지 검색, 생성, 대화 내용 저장 등을 처리합니다."""
    try:
        print(f"🔧 [notion_tool] 호출됨 - query: {query}")
        agent = get_notion_agent()
        context = get_current_context()
        
        # user_id 추출 (context에서, 문자열로 변환)
        user_id_raw = context.get("user_id")
        if user_id_raw is None:
            user_id = "default_user"
            print(f"⚠️ [notion_tool] user_id가 없어서 default_user 사용")
        else:
            # 숫자일 수도 있으므로 문자열로 변환
            user_id = str(user_id_raw)
            print(f"✅ [notion_tool] user_id: {user_id}")
        
        # session_id 추출 (context에서, 없으면 기본값 사용)
        session_id = context.get("session_id", "default_session")
        print(f"✅ [notion_tool] session_id: {session_id}")
        
        result = await agent.process(query, user_id, session_id, context)
        print(f"📦 [notion_tool] agent.process 결과: {type(result)}, {result}")
        
        # 결과가 dict 형태면 answer 추출
        if isinstance(result, dict):
            answer = result.get("answer", str(result))
            print(f"✅ [notion_tool] 최종 반환값: {answer[:100] if len(str(answer)) > 100 else answer}")
            return answer
        print(f"✅ [notion_tool] 최종 반환값 (str): {str(result)[:100] if len(str(result)) > 100 else str(result)}")
        return str(result)
    except Exception as e:
        import traceback
        print(f"❌ [notion_tool] 에러 발생:")
        traceback.print_exc()
        return f"Notion 도구 실행 중 오류가 발생했습니다: {str(e)}"

# 이메일 전송 및 검색
@tool
async def email_tool(query: str = "is:unread") -> str:
    """이메일을 전송하거나 검색합니다. 메일 보내기, 첨부파일 전송, 안 읽은 메일 확인 등을 처리합니다.

    query를 비우면 기본값으로 'is:unread'를 사용합니다.
    """
    agent = get_email_agent()
    context = get_current_context()
    
    # user_id 추출 (context에서)
    user_id = context.get("user_id", "default_user")
    
    result = await agent.process(query, context)
    
    # 결과가 dict 형태면 answer 추출
    if isinstance(result, dict):
        return result.get("answer", str(result))
    return str(result)

# 보험/의료급여 관련 문서 검색 및 답변
@tool
async def insurance_tool(query: str) -> str:
    """보험 상품, 의료급여 법규, 청구 절차, 보장 범위 등 보험 관련 정보를 제공합니다. 의료급여법, 보험약관, 특약 조건 등을 검색하여 답변합니다."""
    agent = get_insurance_agent()
    context = get_current_context()
    return await agent.process(query, context=context)


# 모든 에이전트를 도구로 해서 도구 리스트 리턴
def get_all_agent_tools() -> List[Tool]:
    return [
        chatbot_tool,
        rag_tool,
        brainstorming_tool,
        report_tool,
        therapy_tool,
        notion_tool,
        email_tool,
        insurance_tool,
    ]