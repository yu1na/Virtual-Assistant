# Multi-Agent 시스템

LangChain Tool Calling 패턴을 사용한 Multi-Agent 시스템입니다.

## 아키텍처

```
┌─────────────────┐
│   사용자 질문    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Supervisor     │  ← 중앙 조율자
│  Agent          │
└────────┬────────┘
         │
         ├──┬──┬──┬──┬──┬──┐
         ▼  ▼  ▼  ▼  ▼  ▼
    ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐
    │Chat││ RAG││Brn ││Plan││Rpt ││Thpy│
    │bot ││    ││stm ││ner ││    ││    │
    └────┘└────┘└────┘└────┘└────┘└────┘
```

## 구조

```
multi_agent/
├── __init__.py
├── config.py              # 설정
├── schemas.py             # Pydantic 스키마
├── supervisor.py          # Supervisor Agent
├── agents/
│   ├── __init__.py
│   ├── base_agent.py      # 기본 에이전트 클래스
│   ├── chatbot_agent.py   # 일반 대화
│   ├── rag_agent.py       # 문서 검색
│   ├── brainstorming_agent.py  # 브레인스토밍
│   ├── planner_agent.py   # 일정 관리
│   ├── report_agent.py    # 리포트 생성
│   └── therapy_agent.py   # 심리 상담
└── tools/
    ├── __init__.py
    └── agent_tools.py     # Tool 래핑
```

## 전문 에이전트

### 1. Chatbot Agent
- **역할**: 일반 대화, 인사, 잡담
- **키워드**: 안녕, 고마워, 날씨, 기분, 잘 지내, 뭐해, 재미, 좋은 하루
- **예시**: "안녕", "고마워", "오늘 날씨 어때?"

### 2. RAG Agent
- **역할**: 회사 문서, 규정, 정책 검색
- **키워드**: 연차, 휴가, 급여, 복지, 규정, 정책, 문서, 검색, 알려줘, 확인
- **예시**: "연차 규정이 어떻게 돼?", "복지 정책 알려줘"

### 3. Brainstorming Agent
- **역할**: 창의적 아이디어, 브레인스토밍 기법
- **키워드**: 아이디어, 브레인스토밍, 창의적, 혁신, 문제 해결, 전략, 제안
- **예시**: "새로운 마케팅 아이디어", "문제 해결 방법"

### 4. Planner Agent
- **역할**: 일정 관리, 계획 수립
- **키워드**: 일정, 계획, 할 일, 업무, 스케줄, 우선순위, 관리, 정리
- **예시**: "오늘 할 일", "일정 정리"

### 5. Report Agent
- **역할**: 리포트 생성, 실적 분석
- **키워드**: 리포트, 보고서, 실적, 성과, 분석, 통계, 평가, 주간, 월간
- **예시**: "이번 주 리포트", "실적 분석"

### 6. Therapy Agent
- **역할**: 심리 상담, 정신 건강 지원
- **키워드**: 스트레스, 우울, 불안, 걱정, 힘들어, 고민, 상담, 대인관계, 감정, 번아웃, 자존감, 트라우마, 직장 스트레스, 관계 갈등 등 (상세 키워드는 KEYWORDS.md 참조)
- **예시**: "스트레스가 많아", "대인관계 문제", "심리 상담 받고 싶어", "번아웃이 와", "상사가 무서워"

## API 엔드포인트

### POST /api/v1/multi-agent/query
Multi-Agent 질의응답

**요청:**
```json
{
  "query": "연차 규정이 어떻게 돼?",
  "session_id": "optional-session-id",
  "user_id": 1,
  "context": {}
}
```

**응답:**
```json
{
  "query": "연차 규정이 어떻게 돼?",
  "answer": "연차 규정은 다음과 같습니다...",
  "agent_used": "rag_tool",
  "intermediate_steps": [...],
  "processing_time": 1.23,
  "session_id": "session-id"
}
```

### GET /api/v1/multi-agent/agents
사용 가능한 에이전트 목록

**응답:**
```json
[
  {
    "name": "chatbot_tool",
    "description": "일반적인 대화와 질문에 답변합니다."
  },
  ...
]
```

### GET /api/v1/multi-agent/health
헬스 체크

**응답:**
```json
{
  "status": "healthy",
  "service": "multi-agent",
  "version": "1.0.0"
}
```

## 프론트엔드 사용법

```javascript
import { sendMultiAgentMessage, getAvailableAgents } from './chatbotService.js';

// Multi-Agent에 질문하기
const response = await sendMultiAgentMessage("연차 규정 알려줘");
console.log(response.answer);
console.log(`사용된 에이전트: ${response.agent_used}`);

// 사용 가능한 에이전트 목록 조회
const agents = await getAvailableAgents();
console.log(agents);
```

## 환경 변수

```env
# OpenAI API
OPENAI_API_KEY=your-api-key

# Supervisor 모델 (더 강력한 모델 권장)
SUPERVISOR_MODEL=gpt-4o

# 에이전트 모델 (비용 효율적인 모델)
AGENT_MODEL=gpt-4o-mini

# LangSmith 추적 (선택)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=multi-agent-system
```

## 작동 원리

1. **사용자 질문 수신**: 사용자가 질문을 입력
2. **Supervisor 분석**: Supervisor Agent가 질문의 의도를 파악
3. **에이전트 선택**: 가장 적합한 전문 에이전트를 선택
4. **Tool 호출**: 선택된 에이전트를 Tool로 호출
5. **응답 생성**: 에이전트의 응답을 사용자에게 전달

---

## 🔄 전체 시스템 흐름도

### 서버 시작부터 답변까지의 상세 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 서버 시작 단계                                               │
└─────────────────────────────────────────────────────────────────┘

[1-1] 서버 시작
  📁 backend/app/main.py
  ├─ FastAPI 앱 생성 (line 66-71)
  ├─ CORS 설정 (line 74-80)
  ├─ API 라우터 등록 (line 84)
  │   └─ api_router → backend/app/api/v1/router.py
  │       └─ multi_agent_router 등록 (line 111-115)
  │           └─ prefix="/multi-agent"
  └─ 서버 실행 (uvicorn)
      └─ 포트: 8000

[1-2] Multi-Agent 라우터 로드
  📁 backend/app/api/v1/endpoints/multi_agent.py
  ├─ SupervisorAgent import (line 17)
  ├─ 라우터 엔드포인트 정의:
  │   ├─ POST /api/v1/multi-agent/query
  │   ├─ GET /api/v1/multi-agent/agents
  │   └─ GET /api/v1/multi-agent/health
  └─ 싱글톤 패턴으로 Supervisor 인스턴스 관리 (line 29-37)

[1-3] Supervisor Agent 초기화 (최초 요청 시)
  📁 backend/multi_agent/supervisor.py
  ├─ __init__() 메서드 실행 (line 33-66)
  │   ├─ LangSmith 설정 (line 32-34)
  │   ├─ LLM 초기화 (line 37-43)
  │   │   └─ ChatOpenAI(model="gpt-4o")
  │   ├─ Agent Tools 가져오기 (line 46)
  │   │   └─ backend/multi_agent/tools/agent_tools.py
  │   │       └─ get_all_agent_tools() 호출
  │   │           └─ [chatbot_tool, rag_tool, brainstorming_tool, ...]
  │   ├─ Supervisor 프롬프트 생성 (line 49)
  │   ├─ Agent 생성 (line 52-56)
  │   │   └─ create_openai_tools_agent()
  │   └─ AgentExecutor 생성 (line 58-64)
  └─ 초기화 완료 (싱글톤으로 재사용)


┌─────────────────────────────────────────────────────────────────┐
│  2. 프론트엔드 요청 단계                                         │
└─────────────────────────────────────────────────────────────────┘

[2-1] 사용자 질문 입력
  📁 renderer/chat/chatPanel.js 또는 chatUI.js
  └─ 사용자가 메시지 입력

[2-2] Multi-Agent API 호출
  📁 renderer/chat/chatbotService.js
  ├─ sendMultiAgentMessage() 함수 호출 (line 207-240)
  ├─ 세션 ID 가져오기/생성 (line 173-199)
  └─ HTTP POST 요청 전송
      └─ URL: http://localhost:8000/api/v1/multi-agent/query
      └─ Body: { query: "사용자 질문", session_id: "..." }


┌─────────────────────────────────────────────────────────────────┐
│  3. API 엔드포인트 처리 단계                                    │
└─────────────────────────────────────────────────────────────────┘

[3-1] FastAPI 라우팅
  📁 backend/app/api/v1/endpoints/multi_agent.py
  ├─ multi_agent_query() 엔드포인트 실행 (line 40-63)
  ├─ MultiAgentRequest 스키마 검증
  │   └─ backend/multi_agent/schemas.py (line 16-22)
  │       └─ query, session_id, user_id, context
  └─ Supervisor Agent 가져오기 (line 43)
      └─ get_supervisor_agent() (싱글톤)


┌─────────────────────────────────────────────────────────────────┐
│  4. Supervisor Agent 처리 단계                                  │
└─────────────────────────────────────────────────────────────────┘

[4-1] 질문 분석 및 에이전트 선택
  📁 backend/multi_agent/supervisor.py
  ├─ process() 메서드 실행 (line 144-210)
  │   ├─ 처리 시작 시간 기록 (line 154)
  │   └─ AgentExecutor 실행 (line 158-161)
  │       └─ LangChain Agent Executor
  │
  ├─ AgentExecutor 내부 동작:
  │   ├─ [4-1-1] 질문을 Supervisor LLM에 전달
  │   │   └─ 프롬프트: system_message (line 75-135)
  │   │       ├─ 에이전트 목록과 키워드 설명
  │   │       ├─ 에이전트 선택 가이드
  │   │       └─ 사용자 질문
  │   │
  │   ├─ [4-1-2] Supervisor LLM이 질문 분석
  │   │   └─ 키워드 매칭
  │   │   └─ 적절한 Tool(에이전트) 선택
  │   │       예: "연차 규정" → rag_tool 선택
  │   │
  │   └─ [4-1-3] 선택된 Tool 호출
  │       └─ LangChain Tool 실행


┌─────────────────────────────────────────────────────────────────┐
│  5. Tool (에이전트) 실행 단계                                   │
└─────────────────────────────────────────────────────────────────┘

[5-1] Tool 함수 실행
  📁 backend/multi_agent/tools/agent_tools.py
  ├─ 선택된 Tool 함수 실행
  │   예: rag_tool(query: str) (line 87-105)
  │
  └─ Tool 함수 내부:
      ├─ [5-1-1] 해당 에이전트 인스턴스 가져오기
      │   └─ get_rag_agent() (싱글톤, line 29-35)
      │       └─ backend/multi_agent/agents/rag_agent.py
      │           └─ RAGAgent 클래스 인스턴스 반환
      │
      └─ [5-1-2] 에이전트의 process() 메서드 호출
          └─ await agent.process(query)


┌─────────────────────────────────────────────────────────────────┐
│  6. 전문 에이전트 처리 단계                                      │
└─────────────────────────────────────────────────────────────────┘

[6-1] 에이전트별 처리 (예: RAG Agent)
  📁 backend/multi_agent/agents/rag_agent.py
  ├─ process() 메서드 실행 (line 35-54)
  │   ├─ [6-1-1] RAGRetriever 인스턴스 가져오기 (lazy loading)
  │   │   └─ property: rag_retriever (line 29-34)
  │   │       └─ backend/app/domain/rag/HR/retriever.py
  │   │
  │   ├─ [6-1-2] QueryRequest 생성
  │   │   └─ backend/app/domain/rag/HR/schemas.py
  │   │
  │   └─ [6-1-3] RAG 검색 및 답변 생성
  │       └─ rag_retriever.query(request)
  │           ├─ Vector DB 검색
  │           ├─ 관련 문서 청크 검색
  │           └─ LLM으로 답변 생성
  │
  └─ 답변 반환 (str)


[6-2] 다른 에이전트 예시들:

  • ChatbotAgent:
    📁 backend/multi_agent/agents/chatbot_agent.py
    └─ ChatService 사용
        └─ backend/app/domain/chatbot/service.py

  • BrainstormingAgent:
    📁 backend/multi_agent/agents/brainstorming_agent.py
    └─ BrainstormingService 사용
        └─ backend/app/domain/brainstorming/service.py

  • TherapyAgent:
    📁 backend/multi_agent/agents/therapy_agent.py
    └─ TherapyService 사용
        └─ backend/app/domain/therapy/service.py


┌─────────────────────────────────────────────────────────────────┐
│  7. 응답 반환 단계                                               │
└─────────────────────────────────────────────────────────────────┘

[7-1] Tool → Supervisor
  📁 backend/multi_agent/tools/agent_tools.py
  └─ Tool 함수 반환 (str)
      └─ Supervisor로 전달

[7-2] Supervisor → API
  📁 backend/multi_agent/supervisor.py
  ├─ AgentExecutor 결과 받기 (line 158-161)
  ├─ 결과 추출 (line 164)
  │   └─ answer = result.get("output")
  │
  ├─ MultiAgentResponse 생성 (line 177-186)
  │   ├─ query: 원본 질문
  │   ├─ answer: 최종 답변
  │   ├─ agent_used: 사용된 에이전트
  │   ├─ intermediate_steps: 중간 단계
  │   ├─ processing_time: 처리 시간
  │   └─ session_id: 세션 ID
  │
  └─ 반환 (line 187)

[7-3] API → 프론트엔드
  📁 backend/app/api/v1/endpoints/multi_agent.py
  ├─ HTTP 응답 생성 (line 58)
  │   └─ MultiAgentResponse (JSON)
  │
  └─ FastAPI가 JSON으로 직렬화하여 전송


[7-4] 프론트엔드 수신
  📁 renderer/chat/chatbotService.js
  ├─ sendMultiAgentMessage() 응답 받기 (line 228)
  ├─ JSON 파싱
  └─ 반환 (line 240)

[7-5] UI 표시
  📁 renderer/chat/chatPanel.js 또는 chatUI.js
  └─ 답변을 채팅 UI에 표시
```

---

## 📂 파일별 역할 상세 설명

### 1. 서버 시작 관련

#### `backend/app/main.py`
- **역할**: FastAPI 애플리케이션의 진입점
- **주요 기능**:
  - FastAPI 앱 생성 및 설정
  - CORS 미들웨어 설정
  - API 라우터 등록
  - 서버 실행 (uvicorn)
- **라인**: 66-177

#### `backend/app/api/v1/router.py`
- **역할**: 모든 API 엔드포인트 라우터 통합
- **주요 기능**:
  - 각 도메인별 라우터 통합
  - Multi-Agent 라우터 등록 (`/multi-agent`)
- **라인**: 111-115

### 2. API 엔드포인트

#### `backend/app/api/v1/endpoints/multi_agent.py`
- **역할**: Multi-Agent 시스템의 HTTP API 엔드포인트
- **주요 기능**:
  - `POST /api/v1/multi-agent/query`: 질의응답
  - `GET /api/v1/multi-agent/agents`: 에이전트 목록
  - `GET /api/v1/multi-agent/health`: 헬스 체크
- **주요 메서드**:
  - `multi_agent_query()`: 질의응답 처리 (line 40-63)
  - `get_supervisor_agent()`: Supervisor 싱글톤 관리 (line 32-37)

### 3. Supervisor Agent

#### `backend/multi_agent/supervisor.py`
- **역할**: 중앙 조율자, 적절한 에이전트 선택 및 실행
- **주요 구성**:
  - `__init__()`: 초기화 (LLM, Tools, Agent Executor 생성)
  - `_create_supervisor_prompt()`: Supervisor 프롬프트 생성
  - `process()`: 질문 처리 및 응답 생성
- **핵심 로직**:
  1. 사용자 질문을 LangChain Agent Executor에 전달
  2. Agent Executor가 Supervisor LLM으로 질문 분석
  3. Supervisor가 적절한 Tool(에이전트) 선택
  4. Tool 실행 및 결과 수신
  5. 최종 응답 생성

### 4. Tools (에이전트 래퍼)

#### `backend/multi_agent/tools/agent_tools.py`
- **역할**: 각 에이전트를 LangChain Tool로 래핑
- **주요 함수**:
  - `chatbot_tool()`: ChatbotAgent Tool
  - `rag_tool()`: RAGAgent Tool
  - `brainstorming_tool()`: BrainstormingAgent Tool
  - `planner_tool()`: PlannerAgent Tool
  - `report_tool()`: ReportAgent Tool
  - `therapy_tool()`: TherapyAgent Tool
  - `get_all_agent_tools()`: 모든 Tool 목록 반환
- **동작 방식**:
  1. Tool 함수가 호출되면 해당 에이전트 인스턴스 가져오기 (싱글톤)
  2. 에이전트의 `process()` 메서드 호출
  3. 결과 반환

### 5. 전문 에이전트들

#### `backend/multi_agent/agents/base_agent.py`
- **역할**: 모든 에이전트의 기본 클래스
- **추상 메서드**: `process(query, context)`

#### 각 에이전트 파일들:
- `chatbot_agent.py`: 일반 대화 처리
- `rag_agent.py`: 문서 검색
- `brainstorming_agent.py`: 브레인스토밍
- `planner_agent.py`: 일정 관리
- `report_agent.py`: 리포트 생성
- `therapy_agent.py`: 심리 상담

**공통 구조**:
```python
class XxxAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="...", description="...")
        self._service = None  # Lazy loading
    
    async def process(self, query, context=None):
        # 기존 서비스 활용
        return await self.service.method(query)
```

### 6. 스키마

#### `backend/multi_agent/schemas.py`
- **역할**: 요청/응답 데이터 구조 정의
- **주요 클래스**:
  - `MultiAgentRequest`: API 요청 스키마
  - `MultiAgentResponse`: API 응답 스키마
  - `AgentInfo`: 에이전트 정보 스키마

### 7. 프론트엔드

#### `renderer/chat/chatbotService.js`
- **역할**: Multi-Agent API와 통신하는 JavaScript 서비스
- **주요 함수**:
  - `sendMultiAgentMessage()`: 질의응답
  - `getAvailableAgents()`: 에이전트 목록 조회
  - `getOrCreateMultiAgentSession()`: 세션 관리

---

## 🔍 단계별 상세 흐름 예시

### 예시: "연차 규정이 어떻게 돼?" 질문 처리

```
[Step 1] 사용자 입력
  renderer/chat/chatPanel.js
  └─ "연차 규정이 어떻게 돼?" 입력

[Step 2] API 호출
  renderer/chat/chatbotService.js
  └─ sendMultiAgentMessage("연차 규정이 어떻게 돼?")
      └─ POST http://localhost:8000/api/v1/multi-agent/query

[Step 3] API 라우팅
  backend/app/api/v1/endpoints/multi_agent.py
  └─ multi_agent_query() 실행
      └─ request.query = "연차 규정이 어떻게 돼?"

[Step 4] Supervisor 분석
  backend/multi_agent/supervisor.py
  └─ supervisor.process(request) 실행
      └─ AgentExecutor에 질문 전달
          └─ Supervisor LLM이 프롬프트 분석
              └─ 키워드: "연차", "규정"
              └─ 선택: rag_tool ✅

[Step 5] Tool 실행
  backend/multi_agent/tools/agent_tools.py
  └─ rag_tool("연차 규정이 어떻게 돼?") 실행
      └─ get_rag_agent() → RAGAgent 인스턴스

[Step 6] RAG Agent 처리
  backend/multi_agent/agents/rag_agent.py
  └─ rag_agent.process("연차 규정이 어떻게 돼?")
      └─ RAGRetriever.query(request)
          ├─ Vector DB 검색
          ├─ 관련 문서 청크 찾기
          └─ LLM으로 답변 생성
              └─ "연차 규정은 다음과 같습니다..."

[Step 7] 응답 반환
  RAGAgent → Tool → Supervisor → API → Frontend
  └─ JSON 응답:
      {
        "query": "연차 규정이 어떻게 돼?",
        "answer": "연차 규정은 다음과 같습니다...",
        "agent_used": "rag_tool",
        "processing_time": 1.23
      }

[Step 8] UI 표시
  renderer/chat/chatPanel.js
  └─ 답변을 채팅창에 표시
```

---

## 🎯 핵심 포인트

1. **싱글톤 패턴**: Supervisor와 각 에이전트는 싱글톤으로 관리되어 재사용됩니다.
2. **Lazy Loading**: 에이전트의 내부 서비스는 실제 사용 시에만 초기화됩니다.
3. **LangChain Agent Executor**: Supervisor가 Tool Calling을 통해 에이전트를 선택하고 실행합니다.
4. **독립성**: 각 에이전트는 기존 서비스를 재사용하지만, 독립적으로 작동합니다.
5. **확장성**: 새로운 에이전트는 BaseAgent를 상속받아 쉽게 추가할 수 있습니다.

## 확장 방법

### 새로운 에이전트 추가

1. `agents/` 폴더에 새 에이전트 클래스 생성
2. `BaseAgent`를 상속받아 `process()` 메서드 구현
3. `tools/agent_tools.py`에 Tool 함수 추가
4. `agents/__init__.py`와 `tools/__init__.py`에 export 추가

예시:
```python
# agents/custom_agent.py
from .base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="custom",
            description="커스텀 기능을 수행하는 에이전트"
        )
    
    async def process(self, query: str, context=None) -> str:
        # 커스텀 로직 구현
        return "커스텀 응답"

# tools/agent_tools.py
@tool
async def custom_tool(query: str) -> str:
    """커스텀 기능을 수행합니다."""
    agent = get_custom_agent()
    return await agent.process(query)
```

## 주의사항

- Supervisor는 강력한 모델(gpt-4o)을 사용하는 것이 좋습니다
- 각 에이전트는 독립적으로 작동하므로 기존 코드에 영향을 주지 않습니다
- LangSmith를 활성화하면 디버깅이 쉬워집니다
- 세션 관리는 선택 사항입니다

## 문제 해결

### ImportError 발생 시
```bash
# 경로 문제일 수 있으므로 PYTHONPATH 확인
export PYTHONPATH="${PYTHONPATH}:/path/to/Virtual-Assistant/backend"
```

### Agent 초기화 실패 시
- OpenAI API 키가 올바른지 확인
- 필요한 패키지가 모두 설치되었는지 확인
- 기존 서비스(ChatService, RAGRetriever 등)가 정상 작동하는지 확인

## 라이선스

MIT License

