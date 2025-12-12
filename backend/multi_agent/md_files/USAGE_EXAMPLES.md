# Multi-Agent 시스템 사용 예시

## 목차
1. [기본 사용법](#기본-사용법)
2. [프론트엔드 통합](#프론트엔드-통합)
3. [Python에서 직접 사용](#python에서-직접-사용)
4. [API 호출 예시](#api-호출-예시)
5. [고급 사용법](#고급-사용법)

---

## 기본 사용법

### 1. 서버 시작

```bash
# backend 폴더에서
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. API 테스트

```bash
# 헬스 체크
curl http://localhost:8000/api/v1/multi-agent/health

# 질문하기
curl -X POST http://localhost:8000/api/v1/multi-agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "안녕하세요!"}'

# 에이전트 목록 조회
curl http://localhost:8000/api/v1/multi-agent/agents
```

---

## 프론트엔드 통합

### JavaScript에서 사용

```javascript
import { 
  sendMultiAgentMessage, 
  getAvailableAgents,
  checkMultiAgentHealth 
} from './renderer/chat/chatbotService.js';

// 1. 헬스 체크
const health = await checkMultiAgentHealth();
console.log('시스템 상태:', health.status);

// 2. 질문하기
const response = await sendMultiAgentMessage("연차 규정 알려줘");
console.log('답변:', response.answer);
console.log('사용된 에이전트:', response.agent_used);
console.log('처리 시간:', response.processing_time);

// 3. 에이전트 목록 조회
const agents = await getAvailableAgents();
agents.forEach(agent => {
  console.log(`${agent.name}: ${agent.description}`);
});
```

### 채팅 UI에 통합

```javascript
// chatPanel.js 또는 chatUI.js에서

async function handleUserMessage(message) {
  try {
    // 로딩 표시
    showLoading();
    
    // Multi-Agent에 질문
    const response = await sendMultiAgentMessage(message);
    
    // 응답 표시
    displayMessage('assistant', response.answer);
    
    // 메타데이터 표시 (선택)
    displayMetadata({
      agent: response.agent_used,
      time: response.processing_time
    });
    
  } catch (error) {
    displayError('오류가 발생했습니다: ' + error.message);
  } finally {
    hideLoading();
  }
}
```

---

## Python에서 직접 사용

### 기본 예시

```python
import asyncio
from multi_agent.supervisor import SupervisorAgent
from multi_agent.schemas import MultiAgentRequest

async def main():
    # Supervisor 초기화
    supervisor = SupervisorAgent()
    
    # 질문 생성
    request = MultiAgentRequest(
        query="연차 규정이 어떻게 돼?",
        session_id="my-session-123"
    )
    
    # 처리
    response = await supervisor.process(request)
    
    # 결과 출력
    print(f"답변: {response.answer}")
    print(f"사용된 에이전트: {response.agent_used}")
    print(f"처리 시간: {response.processing_time}초")

asyncio.run(main())
```

### 배치 처리

```python
async def batch_process(queries):
    """여러 질문을 순차적으로 처리"""
    supervisor = SupervisorAgent()
    results = []
    
    for query in queries:
        request = MultiAgentRequest(query=query)
        response = await supervisor.process(request)
        results.append({
            'query': query,
            'answer': response.answer,
            'agent': response.agent_used
        })
    
    return results

# 사용
queries = [
    "안녕하세요",
    "연차 규정 알려줘",
    "새로운 아이디어가 필요해"
]
results = asyncio.run(batch_process(queries))
```

---

## API 호출 예시

### 1. Chatbot Agent (일반 대화)

```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "안녕하세요! 오늘 날씨가 좋네요",
    "session_id": "session-123"
  }'
```

**예상 응답:**
```json
{
  "query": "안녕하세요! 오늘 날씨가 좋네요",
  "answer": "안녕하세요! 네, 정말 좋은 날씨네요. 😊 무엇을 도와드릴까요?",
  "agent_used": "chatbot_tool",
  "processing_time": 1.23,
  "session_id": "session-123"
}
```

### 2. RAG Agent (문서 검색)

```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "연차 규정이 어떻게 되나요?",
    "session_id": "session-123"
  }'
```

**예상 응답:**
```json
{
  "query": "연차 규정이 어떻게 되나요?",
  "answer": "연차 규정은 다음과 같습니다:\n\n1. 입사 1년 후 15일의 연차가 부여됩니다.\n2. 2년 이상 근속 시 매년 1일씩 추가됩니다...\n\n출처: 연차규정.txt",
  "agent_used": "rag_tool",
  "processing_time": 2.45,
  "session_id": "session-123"
}
```

### 3. Brainstorming Agent (아이디어 제안)

```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "팀 협업을 개선할 수 있는 방법을 제안해줘",
    "session_id": "session-123"
  }'
```

### 4. Planner Agent (일정 관리)

```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "오늘 할 일을 정리해줘",
    "session_id": "session-123"
  }'
```

### 5. Report Agent (리포트 생성)

```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "이번 주 실적을 분석해줘",
    "session_id": "session-123"
  }'
```

### 6. Therapy Agent (심리 상담)

```bash
curl -X POST http://localhost:8000/api/v1/multi-agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "스트레스가 많아서 힘들어",
    "session_id": "session-123"
  }'
```

**예상 응답:**
```json
{
  "query": "스트레스가 많아서 힘들어",
  "answer": "스트레스를 느끼시는군요. 이런 감정은 자연스러운 것입니다...",
  "agent_used": "therapy_tool",
  "processing_time": 2.15,
  "session_id": "session-123"
}
```

---

## 고급 사용법

### 1. 컨텍스트 전달

```python
request = MultiAgentRequest(
    query="오늘 일정 알려줘",
    session_id="session-123",
    user_id=42,
    context={
        "date": "2025-12-02",
        "timezone": "Asia/Seoul",
        "preferences": {
            "detail_level": "high"
        }
    }
)
```

### 2. 커스텀 에이전트 추가

```python
# agents/custom_agent.py
from .base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="custom",
            description="커스텀 기능을 수행합니다"
        )
    
    async def process(self, query: str, context=None) -> str:
        # 커스텀 로직
        return f"커스텀 응답: {query}"

# tools/agent_tools.py에 추가
@tool
async def custom_tool(query: str) -> str:
    """커스텀 기능을 수행합니다."""
    agent = get_custom_agent()
    return await agent.process(query)
```

### 3. 에이전트 응답 후처리

```python
async def process_with_postprocessing(query: str):
    supervisor = SupervisorAgent()
    request = MultiAgentRequest(query=query)
    response = await supervisor.process(request)
    
    # 후처리
    if response.agent_used == "rag_tool":
        # RAG 응답에 대한 추가 처리
        response.answer = format_rag_response(response.answer)
    
    return response
```

### 4. 에러 핸들링

```python
async def safe_process(query: str, max_retries=3):
    supervisor = SupervisorAgent()
    
    for attempt in range(max_retries):
        try:
            request = MultiAgentRequest(query=query)
            response = await supervisor.process(request)
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"재시도 {attempt + 1}/{max_retries}")
            await asyncio.sleep(1)
```

### 5. 스트리밍 응답 (향후 구현)

```python
# 향후 구현 예정
async def stream_response(query: str):
    supervisor = SupervisorAgent()
    
    async for chunk in supervisor.stream(query):
        print(chunk, end='', flush=True)
```

---

## 디버깅

### LangSmith 추적 활성화

```bash
# .env 파일에 추가
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=multi-agent-system
```

### 로그 레벨 설정

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("multi_agent")
```

### Verbose 모드

Supervisor Agent는 기본적으로 verbose=True로 설정되어 있어,
콘솔에 상세한 실행 로그가 출력됩니다.

---

## 성능 최적화

### 1. 에이전트 캐싱

에이전트 인스턴스는 싱글톤으로 관리되어 재사용됩니다.

### 2. Lazy Loading

각 에이전트는 실제 사용 시에만 초기화됩니다.

### 3. 병렬 처리 (향후)

```python
# 향후 구현 예정
async def parallel_process(queries):
    supervisor = SupervisorAgent()
    tasks = [supervisor.process(MultiAgentRequest(query=q)) for q in queries]
    results = await asyncio.gather(*tasks)
    return results
```

---

## 문제 해결

### Q: "ImportError: No module named 'multi_agent'"
**A:** PYTHONPATH를 설정하세요:
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/Virtual-Assistant/backend"
```

### Q: "OpenAI API key not found"
**A:** .env 파일에 OPENAI_API_KEY를 설정하세요.

### Q: 에이전트가 잘못 선택됨
**A:** Supervisor 프롬프트를 조정하거나, 더 강력한 모델(gpt-4o)을 사용하세요.

### Q: 응답이 느림
**A:** 
- 더 빠른 모델(gpt-4o-mini) 사용
- 캐싱 활성화
- RAG top_k 값 줄이기

---

## 추가 리소스

- [LangChain 문서](https://docs.langchain.com/)
- [Multi-Agent 패턴 가이드](https://docs.langchain.com/oss/python/langchain/multi-agent)
- [프로젝트 README](./README.md)

