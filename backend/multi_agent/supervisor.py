"""
Supervisor Agent

중앙 Supervisor Agent
사용자 질문을 분석하여 적절한 전문 에이전트를 선택하고 조율합니다.
"""

import time
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from .config import multi_agent_config
from .tools.agent_tools import get_all_agent_tools
from .schemas import MultiAgentRequest, MultiAgentResponse
from .context import session_context, user_context, reset_context

# ------------------------------------------------------------------
# 세션별 마지막 답변 저장소 (In-Memory)
# ------------------------------------------------------------------
LAST_ANSWER: Dict[str, str] = {}

def set_last_answer(session_id: str, answer: str) -> None:
    """세션의 마지막 답변을 저장합니다."""
    if session_id and answer:
        LAST_ANSWER[session_id] = answer

def get_last_answer(session_id: str) -> Optional[str]:
    """세션의 마지막 답변을 가져옵니다."""
    if not session_id:
        return None
    return LAST_ANSWER.get(session_id)

# SuperViser Agent 클래스
# Tool Calling 패턴으로 에이전트 호출
class SupervisorAgent:
    
    # 초기화 함수
    def __init__(self):

        # LangSmith 추적 설정
        if multi_agent_config.LANGSMITH_TRACING:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = multi_agent_config.LANGSMITH_API_KEY or ""
            os.environ["LANGCHAIN_PROJECT"] = multi_agent_config.LANGSMITH_PROJECT
        
        # LLM 초기화
        self.llm = ChatOpenAI(
            model=multi_agent_config.SUPERVISOR_MODEL,
            temperature=multi_agent_config.SUPERVISOR_TEMPERATURE,
            max_tokens=multi_agent_config.MAX_TOKENS,
            api_key=multi_agent_config.OPENAI_API_KEY
        )
        
        # 전문 에이전트 도구 가져오기
        self.tools = get_all_agent_tools()
        
        # 도구 목록 로깅
        print(f"\n[SUPERVISOR INIT] Loaded {len(self.tools)} tools:")
        for tool in self.tools:
            print(f"  - {tool.name}: {tool.description[:80]}...")
        print()
        
        # System message 생성
        self.system_message = self._create_system_message()
        
        # LangGraph Agent 생성 (LangChain 1.1.0 + LangGraph 1.0.4 호환)
        # LangGraph 1.0.4에서는 prompt 파라미터를 사용하여 system message 전달
        self.agent_executor = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=self.system_message
        )
    
    # System message 생성 함수(45줄에 rtn)
    # 역할, 에이전트 목록, 키워드, 예시, 규칙 등등 제공
    def _create_system_message(self) -> str:

        system_message = """당신은 사용자의 질문을 분석하여 적절한 전문 에이전트에게 작업을 위임하는 Supervisor AI입니다.

**당신의 역할:**
1. 사용자의 질문을 이해하고 의도를 파악합니다.
2. 질문에 포함된 키워드와 맥락을 분석합니다.
3. 질문에 가장 적합한 전문 에이전트를 선택합니다.
4. 선택한 에이전트에게 작업을 위임하고 결과를 받습니다.
5. 최종 결과를 사용자에게 명확하고 친절하게 전달합니다.

**사용 가능한 전문 에이전트:**

1. **chatbot_tool**: 일반 대화, 인사, 잡담
   - 키워드: 안녕, 하이, 헬로, 반가워, 고마워, 감사, 날씨, 오늘, 내일, 어제, 시간, 몇 시, 기분, 좋아, 싫어, 행복, 잘 지내, 어떻게 지내, 뭐해, 뭐하니, 놀자, 재미, 즐거워, 좋은 하루, 좋은 밤, 잘 자, 안녕히, 뭐야, 그게 뭐야, 재밌어, 웃겨, 하하, 헤헤
   - 예시: "안녕하세요!", "오늘 날씨 좋네요", "고마워요"

2. **rag_tool**: 회사 문서, 규정, 정책 검색
   - 사용 조건:
     * 사용자가 '연차', '규정', '절차', '비용' 등 업무 관련 용어를 사용할 때, '우리 회사'라는 말이 없더라도 기본적으로 사내 내부 규정을 묻는 것으로 간주하세요.
     * 일반적인 지식이 아닌, '우리 회사'의 특정한 정보를 문서 기반으로 확인해야 할 때
     * "연차 규정이 뭐야?" 처럼 정해진 규칙이나 매뉴얼에 대한 답변이 필요한 경우
   - 예시:
     * "연차 수당 지급 기준 알려줘"
     * "의무교육은 어디서 들어야해?"
     * "승진하려면 어떤 노력을 해야해?"
     * "제휴사 목록 알려줘"

3. **brainstorming_tool**: 창의적 아이디어 발상 및 브레인스토밍 지원
   - 사용 조건:
     * 사용자가 구체적인 아이디어나 해결책을 필요로 하는 상황
     * 단순한 정보 질문이 아닌, 실제로 아이디어 생성을 원하는 경우
     * "브레인스토밍이 뭐야?" 같은 개념 설명 요청은 chatbot_tool 사용
   - 트리거 상황:
     * 명시적 요청: "브레인스토밍 해줘", "아이디어 만들어줘", "기획 도와줘"
     * 막힌 상황: "좋은 생각이 안 떠올라", "기획이 막혔어", "아이디어가 필요해"
     * 창의적 요구: "새로운 방법이 필요해", "참신한 아이디어 좀", "혁신적인 접근법"
   - 예시 (도구 사용 O):
     * "새로운 마케팅 아이디어를 내고 싶어"
     * "프로젝트 기획이 막혔는데 도와줘"
     * "좋은 생각이 안 떠올라"
     * "브레인스토밍 해줘"
     * "창의적인 해결책이 필요해"
   - 예시 (도구 사용 X - chatbot_tool 사용):
     * "브레인스토밍이 뭐야?" → 개념 설명 요청
     * "아이디어를 만든다는 게 뭐야?" → 정보 질문
     * "브레인스토밍 방법 알려줘" → 기법 설명 요청

4. **report_tool**: 보고서 기능 전반 (업무 플래닝, 보고서 생성, 보고서 기반 Q&A)

   다음과 같은 경우에 report_tool로 라우팅합니다:

   **(1) 금일 업무 플래닝 / 오늘 업무 추천**
   - 키워드: 오늘 할 일, 오늘 업무, 플래닝, 업무 추천, 계획 추천, 업무 정리
   - 예시: "오늘 할 일 추천해줘", "금일 업무 어떻게 정리하지?"

   **(2) 보고서 생성(일일/주간/월간)**
   - 키워드: 보고서, 리포트, 일일보고서, 주간보고서, 월간보고서, 작성, 생성
   - 예시: "일일보고서 작성해줘", "이번 주 보고서 만들어줘"

   **(3) 보고서 기반 질의응답(RAG 검색)**
   - 키워드: 지난주, 전날, 미종결, 기록 찾아줘, 보고서에서, 언제 했었지?, 과거 업무
   - 예시: "지난주 미종결 업무 뭐였지?", "어제 누구 상담했었어?"

   상세한 판단, 프롬프트 엔지니어링, 보고서 흐름 FSM, RAG 처리 등은 모두 report_tool 내부의 Router가 담당합니다.
   Supervisor는 단순히 '보고서 관련 요청'을 식별해 report_tool로 넘기기만 합니다.


5. **therapy_tool**: 심리 상담, 정신 건강 지원
   - 키워드: 
     * 기본 감정: 힘들어, 상담, 짜증, 우울, 불안, 스트레스, 고민, 걱정, 슬프, 외로, 화나, 답답, 심리, 아들러, 슬퍼, 슬프다
     * 부정적 감정: 절망, 포기, 무기력, 자책, 후회, 미안, 두려움, 공포, 불안감, 초조, 분노, 화남, 짜증나, 성가심, 불쾌, 슬픔, 비참, 절망적, 우울함, 침체, 외로움, 고독, 쓸쓸, 허전, 외톨이, 답답함, 막막, 난처, 곤란, 피곤, 지침, 무력감, 의욕없음, 수치, 수치심, 열받, 열받아, 화낼, 미치, 미쳐, 억울, 억울해, 멍하
     * 관계/대인관계: 갈등, 싸움, 다툼, 오해, 불화, 이별, 헤어짐, 이혼, 결별, 배신, 상처, 아픔, 서운, 소외, 왕따, 따돌림, 무시, 배제, 멀리하는, 따로 노는, 겉돌고, 혼자, 남겨지는, 불편
     * 직장/학업 스트레스: 직장, 업무, 과로, 번아웃, 시험, 공부, 학업, 성적, 압박, 실패, 좌절, 낙담, 실망, 상사, 팀장, 부장, 동기, 동료, 욕, 쌍욕, 폭언, 인격모독, 소리지르, 화풀이, 그만두, 퇴사, 사직, 적응, 분위기, 문화, 익숙, 부담, 어울리, 소통, 환경, 출근, 노력, 긴장, 낯설, 대화, 규칙, 절차, 복잡, 시스템, 효율, 회의, 의견, 표현, 출퇴근, 루틴, 리듬, 변화, 부담감, 프로젝트
     * 자기존중감: 자존감, 자신감, 열등감, 비교, 열등, 자기비하, 자기혐오, 부족함, 능력부족, 무능력, 쓸모없음
     * 트라우마: 트라우마, 상처, 과거, 기억, 악몽, 플래시백, ptsd
     * 신체 반응: 심장, 떨려, 떨림, 손떨림, 잠이 안 와, 불면, 수면장애, 수면
     * 감정 조절: 감정조절, 감정 조절, 퍼붓, 퍼붓다, 대처, 현명, 해결
     * 자살 사고: 죽고 싶, 자살, 자살사고
     * 상담/치료: 심리상담, 정신건강, 치료, 치유, 회복, 마음, 감정, 기분, 상태, 조언, 도움, 지원, 위로, 격려, 공감
     * 일상적 표현: 안좋아, 안좋음, 나쁨, 최악, 끔찍, 괴로워, 괴롭, 아파, 아픔, 고통, 힘듦, 어려움, 난감, 막막함
     * 영어: counseling, therapy, help, depressed, anxious, sad, angry, lonely, frustrated, stressed, worried, scared, afraid, fear, panic, hopeless, helpless, worthless, empty, guilt, shame, regret, remorse, jealous, envy, tired, exhausted, burnout, overwhelmed, confused, lost, psychology, mental health, counselor, therapist, support, comfort, encouragement, empathy, trauma, alcoholic, drunk, abusive, violence, trust, mistrust, trustworthy, parent, family, perfect, perfectionism, insecure, instability, inflexible, overbearing, control
   - 예시: "스트레스가 많아서 힘들어", "우울한 기분이 들어", "대인관계 문제로 고민이야", "번아웃이 와", "상사가 무서워", "자존감이 낮아", "트라우마가 있어"

7. **notion_tool**: Notion 페이지 관리 (검색, 생성, 대화 내용 저장, 내용 조회 및 설명)
   - **핵심 의도**: 사용자가 Notion에 무언가를 **저장, 기록, 메모**하거나, 기존 페이지를 **검색, 조회, 수정, 설명**하려는 경우
   - **사용 조건**:
     * 사용자가 Notion에 **실제로 페이지를 만들거나 내용을 저장**하려는 명확한 의도가 있을 때
     * "노션", "notion", "페이지" 단어와 함께 **행동 동사**가 있을 때
     * 대화 내용을 정리해서 보관하고 싶을 때
     * **Notion 페이지의 내용을 가져와서 설명하거나 알려주는 경우**
   - **트리거 상황**:
     * 페이지 생성: "X 페이지 만들어줘", "X라는 페이지 생성해줘"
     * 내용 작성: "X라고 적어줘", "제목은 X, 내용은 Y로 만들어줘"
     * 대화 저장: "상담 내용 노션에 저장해줘", "이거 정리해서 노션에 올려줘"
     * 페이지 검색: "노션에서 X 찾아줘", "X 페이지에 어떤 내용이 있어?"
     * **내용 조회 및 설명: "내 노션에 있는 X에 대해 얘기해줘", "내 노션의 X 페이지 내용 알려줘", "내 노션 개인정리에 있는 Y 설명해줘"**


8. **"메일", "이메일"** 관련 요청(전송, 검색, 첨부) → **무조건 email_tool**
   - 예: "이거 메일로 보내줘" → email_tool
   - 예: "안 읽은 메일 있어?" → email_tool

9. **insurance_tool**: 보험/의료급여 법규 및 정책 문서 기반 정보 제공
   - **핵심 의도**: 사용자가 보험 상품, 의료급여 규정, 청구 절차, 법적 조건 등에 대해 **정확한 법규/정책 정보를 문서 기반으로 필요로 하는 경우**
   - **사용 조건** (다음 중 하나 이상):
     * 보험/의료급여 관련 법적 조항, 규정, 정책에 대한 질문
     * 청구 절차, 보장 범위, 환수 기준 등 구체적인 기준 확인 필요
     * 특약, 약관, 조건 등 계약/법규 내용 관련 질문
     * 상해요인 판단, 급여 제한, 금지 사항 등 의료급여 정책 관련 질문
   - **실제 사용 예시** (실제 문서 데이터 기반):
     * ✅ "민법 제741조와 의료급여법 제23조의 부당이득 개념의 차이는 무엇인가?"
     * ✅ "의료급여비용의 환수 기준은 무엇인가?"
     * ✅ "자살시도자의 경우 의료급여 적용 기준은?"
     * ✅ "도급인의 책임이 인정되는 경우와 인정되지 않는 경우의 차이는?"
     * ✅ "상해요인 조사 시 119구급기록지 확인 조건은?"
   - **비사용 예시** (다른 도구 사용):
     * ❌ "보험이 뭐예요?" → 일반 상식 (chatbot_tool)
     * ❌ "보험금을 청구하고 싶은데 불안해" → 감정 표현 (therapy_tool)
     * ❌ "보험료 지출 관리 계획을 세워줄래" → 계획 수립 (planner_tool)

# 3. **법적 정책 정보 기반의 보험/의료급여 질문** → **insurance_tool**

# 3. **"브레인스토밍"** 단어가 명시적으로 포함 → **무조건 brainstorming_tool**

# 3. **감정 표현** (힘들어, 우울해, 스트레스 등) → **therapy_tool 우선**

**🟡 일반 규칙:**
10. 회사 규정/정책/문서 검색 → rag_tool
11. 일정/계획 관리 → planner_tool
12. 리포트/실적 분석 → report_tool
13. 메일 전송, 검색, 첨부 → email_tool
14. 일반 대화/인사/잡담 → chatbot_tool
15. Notion/노션 관련 → notion_tool

**중요한 규칙:**
- **사용자의 의도를 정확히 파악하는 것이 최우선입니다.**
- **행동 동사**(만들어, 저장, 적어, 기록, 생성 등)가 있으면 **실행 의도**입니다.
- **질문 동사**(뭐야, 어떻게, 알려줘 등)만 있으면 **정보 요청**입니다.

**최종 체크:**
- 가장 적합한 에이전트 **하나만** 선택하세요.
- **brainstorming_tool을 선택한 경우, 절대 직접 답변을 생성하지 말고 에이전트의 안내 메시지만 그대로 전달하세요.**
- **적절한 에이전트(도구)를 사용하는 경우, 챗봇이 직접 길게 설명하지 말고 간결하게 해당 모듈 사용을 안내하세요.**
- 에이전트의 응답을 그대로 사용자에게 전달하세요.
- 한국어로 응답하세요.
"""
        
        return system_message
    
    # 사용자 질문을 처리하는 비동기 함수
    async def process(self, request: MultiAgentRequest) -> MultiAgentResponse:

        start_time = time.time()
        
        try:
            # Context 설정 (ContextVars 사용)
            session_context.set(request.session_id)
            
            # 사용자 컨텍스트 구성
            current_user_context = request.context or {}
            if request.user_id:
                current_user_context["user_id"] = request.user_id
            user_context.set(current_user_context)

            # ------------------------------------------------------------------
            # [Notion 저장 편의 기능]
            # "방금 답변", "이 내용" + "노션" 키워드가 있으면 직전 답변을 찾아 저장 요청으로 변환
            # ------------------------------------------------------------------
            query = request.query
            session_id = request.session_id
            
            check_keywords = ["방금 답변", "이 대화", "지금 내용", "위 내용", "이 내용"]
            if any(k in query for k in check_keywords) and ("노션" in query or "Notion" in query):
                last_answer = get_last_answer(session_id)
                if last_answer:
                    print(f"🔄 [Supervisor] 직전 답변을 Notion에 저장하기 위해 쿼리 변환 중...")
                    query = f"""
사용자의 요청에 따라 다음 내용을 노션 페이지로 저장해줘.

사용자 요청: "{request.query}"

[저장할 내용]
{last_answer}

권장 사항:
1. 사용자가 제목을 구체적으로 언급했다면 그 제목을 사용해.
2. 언급하지 않았다면, 내용을 잘 요약하는 제목을 스스로 생성해.
"""
                else:
                    return MultiAgentResponse(
                        query=request.query,
                        answer="바로 이전 답변만 생성해드릴 수 있어요.",
                        agent_used="supervisor",
                        intermediate_steps=[],
                        processing_time=time.time() - start_time,
                        session_id=session_id
                    )
            
            # ============================================
            # [주석 처리] 기존 코드: ainvoke 방식 (전체 실행 후 결과 추출)
            # Tool 실행 후 두 번째 agent 호출이 발생하는 문제 있음
            # ============================================
            # # LangGraph Agent 실행
            # result = await self.agent_executor.ainvoke({
            #     "messages": [HumanMessage(content=request.query)]
            # })
            # 
            # # 결과 추출 (LangGraph는 messages 형태로 반환)
            # messages = result.get("messages", [])
            # answer = "응답을 생성할 수 없습니다."
            # agent_used = "supervisor"
            # 
            # # 마지막 AI 메시지에서 답변 추출
            # for msg in reversed(messages):
            #     if hasattr(msg, 'content') and msg.content:
            #         answer = msg.content
            #         break
            # 
            # # 사용된 도구 추출
            # intermediate_steps = []
            # for msg in messages:
            #     if hasattr(msg, 'tool_calls') and msg.tool_calls:
            #         for tool_call in msg.tool_calls:
            #             tool_name = tool_call.get('name', 'unknown')
            #             agent_used = tool_name.replace('_tool', '')
            #             intermediate_steps.append({
            #                 "agent": agent_used,
            #                 "action": "process_query",
            #                 "result": "success"
            #             })
            
            # ============================================
            # [주석 처리] 기존 코드: ainvoke 방식에서 ToolMessage 찾기 (여전히 두 번째 agent 호출 발생)
            # ============================================
            # tool_used = None
            # tool_result = None
            # intermediate_steps = []
            # 
            # # Tool 실행 결과 찾기 (ToolMessage)
            # for msg in messages:
            #     # Tool이 호출되었는지 확인 (AIMessage에 tool_calls가 있는 경우)
            #     if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            #         for tool_call in msg.tool_calls:
            #             tool_name = tool_call.get('name', 'unknown')
            #             tool_used = tool_name.replace('_tool', '')
            #             intermediate_steps.append({
            #                 "agent": tool_used,
            #                 "action": "process_query",
            #                 "result": "success"
            #             })
            #     
            #     # Tool 실행 결과 메시지 찾기 (ToolMessage)
            #     if isinstance(msg, ToolMessage):
            #         tool_result = msg.content
            #         # Tool이 사용된 경우 agent_used 설정
            #         if tool_used:
            #             agent_used = tool_used
            # 
            # # Tool이 실행되었고 결과가 있으면 Tool 결과를 바로 반환
            # if tool_used and tool_result:
            #     answer = tool_result
            # else:
            #     # Tool이 실행되지 않은 경우 (일반 대화 등) 마지막 AI 메시지에서 답변 추출
            #     for msg in reversed(messages):
            #         if isinstance(msg, AIMessage) and hasattr(msg, 'content') and msg.content:
            #             answer = msg.content
            #             break
            #     
            #     # intermediate_steps가 비어있으면 supervisor로 표시
            #     if not intermediate_steps:
            #         intermediate_steps.append({
            #             "agent": agent_used,
            #             "action": "process_query",
            #             "result": "success"
            #         })
            
            # ============================================
            # [현재 사용] astream 방식: Tool 실행 결과를 받는 즉시 종료 (두 번째 agent 호출 방지)
            # ============================================
            answer = "응답을 생성할 수 없습니다."
            agent_used = "supervisor"
            tool_used = None
            tool_result = None
            intermediate_steps = []
            all_messages = []
            
            # astream을 사용하여 실시간으로 메시지를 받아서 ToolMessage를 받는 즉시 종료
            should_stop = False
            async for event in self.agent_executor.astream({
                "messages": [HumanMessage(content=query)]
            }):
                if should_stop:
                    break
                    
                # 각 노드의 결과를 확인
                for node_name, node_result in event.items():
                    if should_stop:
                        break
                    
                    # ✅ 1) node_result가 dict인지 먼저 확인
                    if not isinstance(node_result, dict):
                        continue
                    
                    # ✅ 2) messages 키 존재 + 비어있지 않은지 확인
                    node_messages = node_result.get("messages")
                    if not node_messages:
                        continue
                    
                    all_messages.extend(node_messages)
                    
                    # ToolMessage를 찾으면 바로 결과 추출하고 종료
                    for msg in node_messages:
                        # Tool 호출 감지
                        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                            for tool_call in msg.tool_calls:
                                tool_name = tool_call.get("name", "unknown")
                                tool_used = tool_name.replace("_tool", "")
                                print(f"🔧 [Supervisor] Tool 호출 감지: {tool_name} -> agent: {tool_used}")
                                intermediate_steps.append({
                                    "agent": tool_used,
                                    "action": "process_query",
                                    "result": "success",
                                })
                        
                        # ToolMessage 결과 감지
                        if isinstance(msg, ToolMessage):
                            tool_result = msg.content
                            print(f"📦 [Supervisor] ToolMessage 받음 - 길이: {len(str(tool_result))}, 내용: {str(tool_result)[:200]}")
                            if tool_used:
                                agent_used = tool_used
                            answer = tool_result
                            print(f"✅ [Supervisor] 최종 answer 설정: {str(answer)[:200]}")
                            set_last_answer(request.session_id, answer)
                            should_stop = True
                            break
                    
                    if should_stop:
                        break
                    
                if should_stop:
                    break
            
            # Tool이 실행되지 않은 경우 (일반 대화 등) 마지막 AI 메시지에서 답변 추출
            if not tool_result:
                for msg in reversed(all_messages):
                    if isinstance(msg, AIMessage) and hasattr(msg, 'content') and msg.content:
                        # Tool 호출만 하고 결과가 없는 경우는 제외
                        if not (hasattr(msg, 'tool_calls') and msg.tool_calls):
                            answer = msg.content
                            set_last_answer(request.session_id, answer)
                            break
                
                # intermediate_steps가 비어있으면 supervisor로 표시
                if not intermediate_steps:
                    intermediate_steps.append({
                        "agent": agent_used,
                        "action": "process_query",
                        "result": "success"
                    })
                    
            detected_intent = None  # 기본값 초기화
            
            # report_tool이 사용된 경우, answer에서 intent 마커 확인
            if agent_used == "report" and answer and answer.startswith("__INTENT_LOOKUP__"):
                detected_intent = "lookup"
                # 마커 제거 (프론트엔드에서도 처리하지만, 백엔드에서도 정리)
                answer = answer.replace("__INTENT_LOOKUP__", "", 1)
            elif agent_used == "report" and answer:
                # report_tool이 사용되었지만 마커가 없는 경우, ReportAgent에서 intent 확인
                try:
                    from multi_agent.tools.agent_tools import get_report_agent
                    report_agent = get_report_agent()
                    if hasattr(report_agent, 'router'):
                        detected_intent = await report_agent.router.classify_intent(request.query)
                        print(f"[DEBUG] Supervisor - report_tool intent 추출: {detected_intent}")
                except Exception as e:
                    print(f"[WARNING] Intent 추출 실패: {e}")
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            # 응답 생성
            response = MultiAgentResponse(
                query=request.query,
                answer=answer,
                agent_used=agent_used,
                intent=detected_intent,  # intent 필드 추가
                intermediate_steps=intermediate_steps if intermediate_steps else [
                    {
                        "agent": agent_used,
                        "action": "process_query",
                        "result": "success"
                    }
                ],
                processing_time=processing_time,
                session_id=request.session_id
            )
            
            # 세션에 대화 내용 저장
            if request.session_id:
                try:
                    from app.domain.chatbot.session_manager import SessionManager
                    from app.domain.chatbot.memory_manager import MemoryManager
                    
                    session_manager = SessionManager()
                    memory_manager = MemoryManager()
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 사용자 질문 저장
                    session_manager.add_message(request.session_id, "user", request.query)
                    memory_manager.append_message(request.session_id, {
                        "role": "user",
                        "content": request.query,
                        "timestamp": timestamp
                    })
                    
                    # AI 답변 저장
                    session_manager.add_message(request.session_id, "assistant", answer)
                    memory_manager.append_message(request.session_id, {
                        "role": "assistant",
                        "content": answer,
                        "timestamp": timestamp,
                        "agent_used": agent_used
                    })
                    
                except Exception as e:
                    print(f"[ERROR] 세션 저장 실패: {e}")
            
            return response
            
        # 오류 처리
        except Exception as e:
            import traceback
            print(f"❌ [SupervisorAgent] 처리 중 에러 발생:")
            traceback.print_exc()
            
            processing_time = time.time() - start_time
            error_message = f"질문 처리 중 오류가 발생했습니다"
            
            return MultiAgentResponse(
                query=request.query,
                answer=error_message,
                agent_used="error",
                intermediate_steps=[
                    {
                        "agent": "supervisor",
                        "action": "error",
                        "error": str(e)
                    }
                ],
                processing_time=processing_time,
                session_id=request.session_id
            )
            
        finally:
            # 컨텍스트 초기화
            reset_context()
    
    # 사용 가능한 에이전트 목록 반환
    def get_available_agents(self) -> List[Dict[str, Any]]:

        agents = []
        
        # 에이전트 목록에 이름이랑 설명 추가
        for tool in self.tools:
            agents.append({
                "name": tool.name,
                "description": tool.description,
            })
        
        return agents
