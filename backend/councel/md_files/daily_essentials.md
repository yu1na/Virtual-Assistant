# 매일 필수 암기 사항 (Daily Essentials)

> 이 문서는 매일 아침/저녁에 빠르게 복습할 수 있도록 핵심 정리만 모았습니다.
> 하루 5분씩만 투자해서 외우세요!

---

## 🔢 핵심 숫자 정리 (암기 필수!)

### Threshold 및 유사도
- **Threshold**: **0.7**
- **Re-ranker 실행 조건**: 최고 유사도 < **0.55**
- **감정 키워드 최대 보너스**: **0.2**
- **Multi-step 조기 종료**: 품질 점수 >= **0.7** 또는 평균 유사도 >= **0.6**

### Chunking
- **Parent 크기**: **1000 tokens**
- **Child 크기**: **500 tokens**
- **Overlap**: **0.2 (20%)**

### 임베딩 및 배치
- **임베딩 모델**: **text-embedding-3-large**
- **임베딩 차원**: **3072**
- **임베딩 배치 크기**: **100**
- **Vector DB 배치 크기**: **1000**

### 대화 히스토리
- **최대 대화 히스토리**: **10개**
- **LLM 단독 답변 히스토리**: 최근 **2개**
- **RAG 기반 답변 히스토리**: 최근 **5개**

### 성능
- **키워드 기반 처리 시간**: **~9ms**
- **LLM 대비 속도**: 약 **125배** 빠름 (12ms vs 1,500ms)
- **키워드 기반 처리 비용**: **무료**

### 모델 설정
- **Supervisor 모델**: **gpt-4o**
- **Agent 모델**: **gpt-4o-mini**
- **Supervisor Temperature**: **0.3**
- **Agent Temperature**: **0.7**
- **LLM 답변 Temperature**: **0.3**
- **LLM 단독 Max Tokens**: **180** (2~3문장)
- **RAG 기반 Max Tokens**: **400** (4~7문장)

### 세션
- **세션 타임아웃**: **3600초 (1시간)**
- **페르소나 캐시 유효성**: **24시간 (86400초)**

---

## 🔄 시스템 흐름도 (암기 필수!)

```
사용자 질문
    ↓
Supervisor Agent (의도 분석)
    ↓
전문 에이전트 선택 (Therapy/RAG/Chatbot 등)
    ↓
[Therapy Agent의 경우]
    ↓
RAGTherapySystem
    ↓
TherapyProtocol.generate_protocol_guidance()
    ↓
SearchEngine (Vector DB 검색)
    ↓
Threshold 분기 (0.7)
    ↓
ResponseGenerator (LLM 답변 생성)
    ↓
사용자에게 답변 반환
```

---

## 📋 Threshold 기반 분기 (암기 필수!)

```
최고 유사도 >= 0.7
    → LLM 단독 답변 (RAG 없이)

최고 유사도 < 0.7
    → RAG + Self-learning
      - 검색된 청크를 기반으로 답변 생성
      - Q&A를 Vector DB에 자동 저장 (Self-learning)
```

---

## 📝 답변 구조 (암기 필수!)

### LLM 단독 답변 구조 (2~3문장)

1. **감정 인정 및 공감** (1문장) - 필수
   - 사용자의 감정을 있는 그대로 인정
   - 예: "~하셨군요", "~느끼시는 마음이 충분히 이해됩니다"
   - 금지: "하지만", "그래도"로 시작

2. **자연스러운 질문 또는 공감문** (1~2문장) - 필수
   - 사용자의 상황에 맞게 자연스럽게 질문
   - 상담을 계속 이어가도록 하는 질문 포함

### RAG 기반 답변 구조 (4~7문장)

1. **감정 인정 및 공감** (1~2문장) - 필수
   - 사용자의 감정을 있는 그대로 인정
   - 예: "~하셨군요", "~느끼시는 마음이 충분히 이해됩니다"
   - 금지: "하지만", "그래도"로 시작

2. **참고 자료 기반 통찰 또는 조언** (2~3문장) - 필수
   - 검색된 자료의 내용을 바탕으로 구체적이고 실용적인 조언 제공
   - 아들러 심리학의 원칙을 자연스럽게 통합하여 설명
   - 사용자의 상황에 맞게 자료의 내용을 적용하여 설명

3. **자연스러운 질문 또는 다음 단계 제안** (1~2문장) - 필수
   - 사용자의 상황에 맞게 자연스럽게 질문
   - 상담을 계속 이어가도록 하는 질문 포함

---

## 🏥 EAP 프로토콜 4단계 (암기 필수!)

1. **INITIAL_CONTACT**: 초기 접촉 및 문제 파악
2. **ASSESSMENT**: 평가 (심각도, 긴급성)
3. **SHORT_TERM_INTERVENTION**: 단기 개입
4. **FOLLOW_UP**: 후속 조치

---

## 💬 SFBT 질문 유형 5가지 (암기 필수!)

1. **SCALING**: 척도 질문 (0~10점)
2. **EXCEPTION**: 예외 탐색 질문
3. **COPING**: 대처 질문
4. **MIRACLE**: 기적 질문
5. **RELATIONSHIP**: 관계 질문

---

## 📅 SFBT 질문 순서 (대화 단계별)

- **0회차 (첫 대화)**: SCALING (척도 질문)
- **1회차**: EXCEPTION (예외 탐색)
- **2회차**: COPING (대처 질문)
- **3회차**: MIRACLE (기적 질문)
- **4회차 이상**: RELATIONSHIP (관계 질문)

---

## 🔑 키워드 기반 판단

### 프로토콜 선택
- **위기 키워드**: ['죽고 싶', '자살', '자해', '끝내고 싶', '포기', '절망']
  - 감지 시 → **EAP 프로토콜** 우선 적용
- **해결책 키워드**: ['어떻게', '방법', '해결', '개선', '나아지', '변화']
  - 감지 시 → **SFBT 프로토콜** 우선 적용
- **기본**: 통합 프로토콜 사용

### 심각도 평가
- **Critical**: ['죽고 싶', '자살', '자해', '끝내고 싶']
- **High**: ['견딜 수 없', '미치겠', '한계', '더 이상 못', '불가능']
- **Medium**: ['힘들', '어렵', '괴롭', '고통', '스트레스']
- **Low**: 그 외

### 답변 구조 결정
- **감정 + 상황 모두 있음** → 1~3단계 답변 구조 (공감 + 재해석 + 실천 방안 + 질문)
- **감정만 있음** → 공감 + 척도 질문만 (1~2문장)

---

## 🆘 위기 개입 전화번호 (암기 필수!)

- **자살예방상담전화**: **1393**
- **정신건강위기상담**: **1577-0199**

---

## 🔄 RAGTherapySystem.chat() 처리 단계 (7단계)

1. 종료 키워드 확인 ("exit", "고마워", "끝", "종료", "그만", "안녕")
2. 프로토콜 가이드 생성 (TherapyProtocol.generate_protocol_guidance)
3. 입력 분류 (ResponseGenerator.classify_input)
4. Multi-step 반복 검색 (SearchEngine)
5. 최고 유사도 계산
6. Threshold 분기 (>= 0.7: LLM 단독, < 0.7: RAG + Self-learning)
7. 대화 히스토리에 추가 (최대 10개)

---

## 🔍 기본 검색 과정 (4단계)

1. 사용자 질문을 임베딩으로 변환
2. ChromaDB에서 유사도 검색 (L2 distance)
3. Distance를 유사도로 변환: **`1 / (1 + distance)`**
4. 조건부 Re-ranker 적용 (최고 유사도 < 0.55일 때만)

---

## 📊 데이터 파이프라인 (3단계)

1. **Step 1: 청크 파일 생성**
   - 스크립트: `create_chunk_files.py`
   - 입력: PDF 파일들
   - 출력: JSON 청크 파일들 (*_chunks.json)

2. **Step 2: 임베딩 파일 생성**
   - 스크립트: `create_openai_embeddings.py`
   - 입력: 청크 파일들 (*_chunks.json)
   - 출력: 임베딩 파일들 (*_embeddings.json)

3. **Step 3: Vector DB 저장**
   - 스크립트: `save_to_vectordb.py`
   - 입력: 임베딩 파일들 (*_embeddings.json)
   - 출력: ChromaDB 컬렉션 ("vector_adler")

---

## 🤖 사용 가능한 에이전트 목록 (7가지)

1. **chatbot_tool**: 일반 대화, 인사, 잡담
2. **rag_tool**: 회사 문서, 규정, 정책 검색
3. **brainstorming_tool**: 창의적 아이디어 발상
4. **planner_tool**: 일정 관리, 계획 수립
5. **report_tool**: 리포트 생성, 실적 분석
6. **therapy_tool**: 심리 상담, 정신 건강 지원
7. **notion_tool**: Notion 페이지 관리

---

## 🎯 에이전트 선택 가이드

### 절대 우선순위
1. "노션", "notion", "페이지" 포함 → **notion_tool**
2. "브레인스토밍" 명시 → **brainstorming_tool**
3. 감정 표현 → **therapy_tool** 우선

### 일반 규칙
- 회사 규정/정책 검색 → rag_tool
- 일정/계획 관리 → planner_tool
- 리포트/실적 분석 → report_tool
- 일반 대화 → chatbot_tool

---

## 📁 주요 파일 위치

- RAGTherapySystem: `backend/councel/sourcecode/persona/rag_therapy.py`
- PersonaManager: `backend/councel/sourcecode/persona/persona_manager.py`
- SearchEngine: `backend/councel/sourcecode/persona/search_engine.py`
- ResponseGenerator: `backend/councel/sourcecode/persona/response_generator.py`
- TherapyProtocol: `backend/councel/sourcecode/persona/therapy_protocol.py`
- BaseAgent: `backend/multi_agent/agents/base_agent.py`
- SupervisorAgent: `backend/multi_agent/supervisor.py`
- Context: `backend/multi_agent/context.py`
- Agent Tools: `backend/multi_agent/tools/agent_tools.py`

---

## 🗂️ 컬렉션 이름

- **"vector_adler"**

---

## 🚪 종료 키워드

- "exit", "고마워", "끝", "종료", "그만", "안녕"

---

## 💡 핵심 개념 정의

### RAG (Retrieval-Augmented Generation)
- 검색 기반 생성 모델
- 4단계: 질문 임베딩 → Vector DB 검색 → 컨텍스트 전달 → LLM 답변 생성

### Threshold 기반 분기
- Threshold: 0.7
- >= 0.7: LLM 단독 답변
- < 0.7: RAG + Self-learning

### Self-learning
- 목적: 시스템 자동 개선
- 트리거: 유사도 < 0.7
- 동작: Q&A를 Vector DB에 자동 저장

### Parent-Child Chunking
- Parent: 1000 tokens (큰 맥락)
- Child: 500 tokens (세부 정보)
- 목적: 다양한 검색 시나리오 지원

### Multi-step 반복 검색
- 목적: 검색 품질 자동 개선
- 동작: 초기 검색 → 품질 평가 → 쿼리 확장 → 재검색

### Re-ranker
- 목적: 검색 결과 관련성 향상
- 방식: LLM을 사용하여 청크 재정렬
- 조건: 최고 유사도 < 0.55일 때만 실행

### 멀티 에이전트 시스템
- 패턴: Supervisor Pattern
- 구조: Supervisor Agent + 전문 에이전트들
- 통신: LangChain Tool Calling

### EAP + SFBT 통합 프로토콜
- EAP: 4단계
- SFBT: 5가지 질문 유형
- 키워드 기반 판단: ~9ms, 무료

---

## ✅ 매일 체크리스트

### 아침 복습 (5분)
- [ ] 핵심 숫자 정리 확인
- [ ] 시스템 흐름도 그려보기
- [ ] Threshold 분기 로직 확인
- [ ] LLM 단독 답변 구조 (2~3문장) 확인
- [ ] RAG 기반 답변 구조 (4~7문장) 확인

### 저녁 복습 (5분)
- [ ] 당일 학습한 내용의 핵심 정리 확인
- [ ] 체크리스트 항목 확인
- [ ] 모르는 부분 다시 학습

---

**매일 5분씩만 투자하면 7일 안에 모든 개념을 마스터할 수 있습니다! 🚀**

