# 프로젝트 개념 완전 정리 문서

> 이 문서는 프로젝트의 모든 핵심 개념을 상세히 정리한 문서입니다. JSON 파일로 변환하기 쉽도록 구조화되어 있습니다.

---

## 1. 전체 시스템 아키텍처

### 1.1 시스템 개요
- **목적**: RAG(Retrieval-Augmented Generation) 기반 심리 상담 시스템 + 멀티 에이전트 시스템
- **핵심 기술**: 
  - Vector Database (ChromaDB)
  - OpenAI Embeddings (text-embedding-3-large)
  - OpenAI GPT (gpt-4o-mini, gpt-4o)
  - LangChain + LangGraph (멀티 에이전트)
- **주요 기능**:
  1. 아들러 개인심리학 기반 심리 상담
  2. 문서 기반 RAG 검색
  3. 멀티 에이전트 시스템 (Supervisor 패턴)

### 1.2 시스템 흐름도
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
SearchEngine (Vector DB 검색)
    ↓
ResponseGenerator (LLM 답변 생성)
    ↓
사용자에게 답변 반환
```

---

## 2. 상담 시스템 (RAG 기반)

### 2.1 RAGTherapySystem (메인 상담 시스템)

#### 2.1.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/persona/rag_therapy.py`
- **역할**: RAG 기반 상담 시스템의 메인 컨트롤러
- **주요 책임**:
  1. Vector DB 연결 및 관리
  2. 상담 세션 관리 (대화 히스토리, 사용자별 세션)
  3. EAP + SFBT 프로토콜 통합 관리
  4. Threshold 기반 분기 처리
  5. Self-learning (Q&A 자동 저장)

#### 2.1.2 초기화 과정
```python
# 초기화 단계
1. Vector DB 경로 확인 및 ChromaDB 클라이언트 생성
2. 컬렉션 로드 ("vector_adler")
3. OpenAI 클라이언트 초기화 (동기 + 비동기)
4. 모듈 초기화:
   - PersonaManager: 페르소나 생성 및 관리
   - TherapyProtocol: EAP + SFBT 프로토콜 관리
   - SearchEngine: Vector DB 검색
   - ResponseGenerator: 답변 생성
5. 대화 히스토리 초기화 (최대 10개 유지)
6. 사용자별 세션 관리 초기화 (user_sessions)
```

#### 2.1.3 Threshold 기반 분기 시스템
- **Threshold 값**: 0.7 (고정)
- **분기 로직**:
  ```
  최고 유사도 >= 0.7
    → LLM 단독 답변 (RAG 없이)
  
  최고 유사도 < 0.7
    → RAG + Self-learning
      - 검색된 청크를 기반으로 답변 생성
      - Q&A를 Vector DB에 자동 저장 (Self-learning)
  ```

#### 2.1.4 Self-learning 메커니즘
- **목적**: 유사도가 낮은 질문-답변 쌍을 Vector DB에 저장하여 시스템 개선
- **동작 방식**:
  1. 유사도 < 0.7인 경우 자동 트리거
  2. 사용자 질문과 LLM 답변을 JSON 형태로 저장
  3. 질문을 임베딩으로 변환하여 Vector DB에 저장
  4. 메타데이터: `source="self_learning"`, `type="qa_pair"`
- **비동기 처리**: `asyncio.create_task()`로 백그라운드 실행

#### 2.1.5 주요 메서드

##### `chat(user_input: str) -> Dict[str, Any]`
- **역할**: 사용자 입력을 받아 상담 답변 생성
- **처리 단계**:
  1. 종료 키워드 확인 ("exit", "고마워", "끝", "종료", "그만", "안녕")
     - 종료 시 세션 초기화 (대화 히스토리 + 프로토콜 세션)
  2. 프로토콜 가이드 생성 (TherapyProtocol.generate_protocol_guidance)
     - 프로토콜 선택 (EAP/SFBT/통합)
     - 심각도 평가
     - SFBT 질문 생성
     - 답변 구조 결정
  3. 입력 분류 (ResponseGenerator.classify_input)
  4. Multi-step 반복 검색 (SearchEngine)
  5. 최고 유사도 계산
  6. Threshold 분기:
     - >= 0.7: LLM 단독 답변 (프로토콜 프롬프트 적용)
     - < 0.7: RAG + Self-learning (프로토콜 프롬프트 적용)
  7. 대화 히스토리에 추가 (최대 10개)
- **반환값**:
  ```json
  {
    "answer": "답변 텍스트",
    "used_chunks": ["청크 요약 리스트"],
    "used_chunks_detailed": [{"chunk_id": "...", "source": "...", ...}],
    "mode": "llm_only" | "counseling" | "adler" | "general",
    "continue_conversation": true,
    "similarity_score": 0.85,
    "search_iterations": 1,
    "search_quality": {"quality_score": 0.75, ...},
    "protocol_info": {
      "protocol_type": "eap|sfbt|integrated",
      "current_stage": "initial_contact|assessment|...",
      "severity_level": "critical|high|medium|low",
      "sfbt_question_type": "scaling|exception|...",
      "sfbt_question": "질문 텍스트"
    }
  }
  ```

---

### 2.2 PersonaManager (페르소나 관리)

#### 2.2.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/persona/persona_manager.py`
- **역할**: 아들러 심리학자 페르소나 생성 및 관리
- **페르소나 생성 방식**:
  1. **기본 페르소나**: 프롬프트 엔지니어링으로 생성 (즉시 사용 가능)
  2. **RAG 페르소나**: Vector DB + 웹 검색으로 생성 (백그라운드)

#### 2.2.2 페르소나 생성 전략

##### 기본 페르소나 (프롬프트 엔지니어링)
- **특징**: 즉시 사용 가능, 안정적
- **내용**:
  - 아들러 개인심리학 핵심 원칙 5가지
  - 3단계 답변 구조 (감정 인정 → 재해석 → 격려)
  - 말투 가이드라인

##### RAG 페르소나 (동적 생성)
- **생성 과정**:
  1. Vector DB에서 아들러 관련 청크 검색 (3개 쿼리)
  2. 웹 검색으로 최신 정보 수집 (LLM 호출)
  3. 검색된 자료를 기반으로 LLM이 페르소나 프롬프트 생성
- **캐싱**: 24시간 유효한 JSON 캐시 파일
- **백그라운드 생성**: 기본 페르소나로 시작 후 백그라운드에서 RAG 페르소나 생성

#### 2.2.3 주요 메서드

##### `generate_persona_with_prompt_engineering() -> str`
- **역할**: 프롬프트 엔지니어링으로 기본 페르소나 생성
- **반환값**: 페르소나 프롬프트 문자열

##### `generate_persona_with_rag() -> str`
- **역할**: RAG 기반 페르소나 생성
- **처리 과정**:
  1. Vector DB 검색 (3개 쿼리)
  2. 웹 검색 (LLM 호출)
  3. LLM으로 페르소나 프롬프트 생성
- **캐싱**: 생성된 페르소나를 JSON 파일로 저장

##### `_load_cached_persona() -> Optional[str]`
- **역할**: 캐시된 페르소나 로드
- **캐시 유효성**: 24시간 (86400초)

---

### 2.3 SearchEngine (검색 엔진)

#### 2.3.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/persona/search_engine.py`
- **역할**: Vector DB 검색 및 유사도 계산
- **주요 기능**:
  1. 임베딩 생성 (동기/비동기)
  2. Vector DB 검색
  3. Re-ranker (검색 결과 재정렬)
  4. Multi-step 반복 검색
  5. 감정 키워드 가중치 적용

#### 2.3.2 검색 전략

##### 기본 검색 (`retrieve_chunks_async`)
- **과정**:
  1. 사용자 질문을 임베딩으로 변환
  2. ChromaDB에서 유사도 검색 (L2 distance)
  3. Distance를 유사도로 변환: `1 / (1 + distance)`
  4. 조건부 Re-ranker 적용 (최고 유사도 < 0.55일 때만)

##### Re-ranker (재정렬)
- **목적**: 검색 결과의 관련성 향상
- **동작 방식**:
  1. LLM에게 청크들의 관련성 평가 요청
  2. LLM이 관련성 순서대로 번호 반환
  3. 번호 순서대로 청크 재정렬
- **조건**: 최고 유사도 < 0.55일 때만 실행 (비용 절감)

##### Multi-step 반복 검색
- **목적**: 검색 품질이 낮을 때 자동으로 개선
- **동작 방식**:
  1. 초기 검색 실행
  2. 품질 평가 (평균 유사도, 다양성 점수)
  3. 품질이 낮으면 (`needs_improvement=True`):
     - 쿼리 확장 (키워드 기반 또는 LLM 기반)
     - 확장된 쿼리로 재검색 (병렬 처리)
     - 중복 제거 후 재평가
  4. 최종 Re-ranker 적용
- **조기 종료 조건**:
  - 품질 점수 >= 0.7
  - 평균 유사도 >= 0.6

##### 감정 키워드 가중치
- **목적**: 감정 관련 질문의 검색 정확도 향상
- **동작 방식**:
  1. 사용자 입력에서 감정 키워드 추출 (set 연산)
  2. 청크 텍스트에서 매칭되는 키워드 개수 계산
  3. 매칭 비율에 따라 보너스 계산 (최대 0.2)
  4. 최종 유사도 = 기본 유사도 + 감정 보너스

#### 2.3.3 주요 메서드

##### `create_query_embedding_async(query_text: str) -> List[float]`
- **역할**: 질문을 임베딩 벡터로 변환 (비동기)
- **모델**: text-embedding-3-large

##### `retrieve_chunks_async(user_input: str, n_results: int = 5) -> List[Dict]`
- **역할**: Vector DB에서 관련 청크 검색
- **반환값**: 청크 리스트 (id, text, metadata, distance 포함)

##### `rerank_chunks(user_input: str, chunks: List[Dict]) -> List[Dict]`
- **역할**: LLM을 사용하여 청크 재정렬
- **조건**: 최고 유사도 < 0.55일 때만 실행

##### `_iterative_search_with_query_expansion_async(...) -> Dict`
- **역할**: Multi-step 반복 검색
- **반환값**:
  ```json
  {
    "chunks": [...],
    "quality_info": {
      "avg_similarity": 0.65,
      "diversity_score": 0.8,
      "quality_score": 0.68,
      "needs_improvement": false
    },
    "iterations_used": 1,
    "total_chunks_found": 15
  }
  ```

##### `_calculate_emotion_boost(user_input: str, chunk_text: str) -> float`
- **역할**: 감정 키워드 매칭 보너스 계산
- **최대 보너스**: 0.2

##### `get_distance_to_similarity(distance: float) -> float`
- **역할**: L2 distance를 유사도 점수로 변환
- **공식**: `1 / (1 + distance)`

---

### 2.4 ResponseGenerator (답변 생성기)

#### 2.4.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/persona/response_generator.py`
- **역할**: LLM을 사용하여 상담 답변 생성
- **주요 기능**:
  1. 입력 분류 (adler/counseling/general)
  2. LLM 단독 답변 생성
  3. RAG 기반 답변 생성 (페르소나 + 청크)

#### 2.4.2 입력 분류 시스템
- **분류 기준**:
  - **adler**: "아들러" 또는 "adler" 키워드 포함
  - **counseling**: 감정/상담 키워드 포함 (set 연산으로 최적화)
  - **general**: 그 외
- **최적화**: 키워드 리스트를 set으로 변환하여 O(1) 조회

#### 2.4.3 답변 생성 전략

##### LLM 단독 답변 (`_generate_llm_only_response`)
- **사용 조건**: 유사도 >= 0.7 (Threshold 분기)
- **특징**:
  - RAG 없이 페르소나만 사용
  - 대화 히스토리 최근 2개만 포함 (컨텍스트 최적화)
  - 감정 맥락 파악 (최근 대화에서 감정 키워드 추출)
  - 2~3문장으로 적절한 길이로 작성
- **모델**: gpt-4o-mini
- **Temperature**: 0.3 (일관된 답변)
- **Max Tokens**: 180 (2~3문장)

##### RAG 기반 답변 (`generate_response_with_persona`)
- **사용 조건**: 유사도 < 0.7
- **특징**:
  - 검색된 청크 상위 3개 사용
  - 페르소나 프롬프트 + 청크 컨텍스트
  - 대화 히스토리 최근 5개 포함
  - 감정 키워드 자동 감지 및 프롬프트에 반영
  - 참고 자료를 바탕으로 상세하고 구체적인 답변 생성 (4~7문장)
- **모델**: gpt-4o-mini
- **Temperature**: 0.3
- **Max Tokens**: 400 (RAG 사용 시 상세하게 4~7문장)

#### 2.4.4 답변 구조

##### LLM 단독 답변 구조 (2~3문장)
1. **감정 인정 및 공감** (1문장, 필수)
   - 사용자의 감정을 있는 그대로 인정
   - 예: "~하셨군요", "~느끼시는 마음이 충분히 이해됩니다"
   - 금지: "하지만", "그래도"로 시작

2. **자연스러운 질문 또는 공감문** (1~2문장)
   - 사용자의 상황에 맞게 자연스럽게 질문
   - 상담을 계속 이어가도록 하는 질문 포함

##### RAG 기반 답변 구조 (4~7문장)
1. **감정 인정 및 공감** (1~2문장, 필수)
   - 사용자의 감정을 있는 그대로 인정
   - 예: "~하셨군요", "~느끼시는 마음이 충분히 이해됩니다"
   - 금지: "하지만", "그래도"로 시작

2. **참고 자료 기반 통찰 또는 조언** (2~3문장)
   - 검색된 자료의 내용을 바탕으로 구체적이고 실용적인 조언 제공
   - 아들러 심리학의 원칙을 자연스럽게 통합하여 설명
   - 사용자의 상황에 맞게 자료의 내용을 적용하여 설명

3. **자연스러운 질문 또는 다음 단계 제안** (1~2문장)
   - 사용자의 상황에 맞게 자연스럽게 질문
   - 상담을 계속 이어가도록 하는 질문 포함

#### 2.4.5 주요 메서드

##### `classify_input(user_input: str) -> str`
- **역할**: 사용자 입력 분류
- **반환값**: "adler" | "counseling" | "general"

##### `is_therapy_related(user_input: str) -> bool`
- **역할**: 심리 상담 관련 질문인지 확인

##### `_generate_llm_only_response(...) -> Dict`
- **역할**: RAG 없이 LLM만으로 답변 생성
- **반환값**: 답변 딕셔너리 (mode="llm_only")

##### `generate_response_with_persona(...) -> Dict`
- **역할**: RAG 기반 답변 생성
- **반환값**: 답변 딕셔너리 (mode="counseling" | "adler" | "general")

---

### 2.5 TherapyProtocol (EAP + SFBT 통합 프로토콜)

#### 2.5.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/persona/therapy_protocol.py`
- **역할**: EAP(Employee Assistance Program)와 SFBT(Solution-Focused Brief Therapy)를 통합한 상담 프로토콜 관리
- **생성날짜**: 2025.12.05
- **주요 책임**:
  1. 프로토콜 선택 (EAP/SFBT/통합)
  2. 심각도 평가 (critical/high/medium/low)
  3. 답변 구조 결정 (감정만 vs 감정+상황)
  4. SFBT 질문 생성 및 순서 관리
  5. 세션 상태 추적 및 관리

#### 2.5.2 프로토콜 유형

##### EAP (Employee Assistance Program)
- **목적**: 직장인 정신건강 지원 프로그램
- **단계**:
  1. **INITIAL_CONTACT**: 초기 접촉 및 문제 파악
  2. **ASSESSMENT**: 평가 (심각도, 긴급성)
  3. **SHORT_TERM_INTERVENTION**: 단기 개입
  4. **FOLLOW_UP**: 후속 조치

##### SFBT (Solution-Focused Brief Therapy)
- **목적**: 해결중심 단기 치료
- **질문 유형**:
  1. **SCALING**: 척도 질문 (0~10점)
  2. **EXCEPTION**: 예외 탐색 질문
  3. **COPING**: 대처 질문
  4. **MIRACLE**: 기적 질문
  5. **RELATIONSHIP**: 관계 질문

##### 통합 프로토콜 (INTEGRATED)
- **목적**: EAP와 SFBT를 상황에 맞게 통합 사용
- **선택 기준**: 사용자 입력 내용과 대화 단계에 따라 자동 선택

#### 2.5.3 키워드 기반 판단 시스템

##### 프로토콜 선택 (`select_protocol`)
- **위기 키워드**: ['죽고 싶', '자살', '자해', '끝내고 싶', '포기', '절망']
  - 감지 시 → EAP 프로토콜 우선 적용
- **해결책 키워드**: ['어떻게', '방법', '해결', '개선', '나아지', '변화']
  - 감지 시 → SFBT 프로토콜 우선 적용
- **기본**: 통합 프로토콜 사용
- **처리 시간**: ~2ms

##### 심각도 평가 (`assess_severity`)
- **Critical**: ['죽고 싶', '자살', '자해', '끝내고 싶']
- **High**: ['견딜 수 없', '미치겠', '한계', '더 이상 못', '불가능']
- **Medium**: ['힘들', '어렵', '괴롭', '고통', '스트레스']
- **Low**: 그 외
- **처리 시간**: ~2ms

##### 답변 구조 결정 (`has_situation_context`)
- **감정 키워드** (23개): 힘들, 어렵, 괴롭, 슬프, 화나, 우울, 불안, 답답, 스트레스, 고통, 절망, 무기력, 초조, 걱정, 두려움, 짜증, 분노, 상처, 아픔, 외로움, 허탈, 실망
- **상황 키워드** (40개+): 직장, 회사, 동료, 상사, 가족, 부모, 문제, 상황, 일어났, 발생했, 때문에, 해서 등
- **판단 로직**:
  - 감정 + 상황 모두 있음 → 1~3단계 답변 구조 (공감 + 재해석 + 실천 방안 + 질문)
  - 감정만 있음 → 공감 + 척도 질문만 (1~2문장)
- **처리 시간**: ~3ms
- **현재 한계**: 부정문 처리 미흡 (예: "힘들지 않아요" → 오탐 가능)

#### 2.5.4 SFBT 질문 순서 관리

##### 대화 단계별 질문 유형
- **0회차 (첫 대화)**: SCALING (척도 질문)
  - "지금 그런 힘든 마음은 0~10점 중 몇 점인 것 같으세요?"
- **1회차**: EXCEPTION (예외 탐색)
- **2회차**: COPING (대처 질문)
- **3회차**: MIRACLE (기적 질문)
- **4회차 이상**: RELATIONSHIP (관계 질문)

##### 질문 템플릿
- 각 질문 유형마다 3개의 템플릿 제공
- 첫 대화에서는 항상 첫 번째 템플릿 사용 (일관성 보장)
- 그 외에는 랜덤 선택

#### 2.5.5 세션 상태 관리

##### TherapySession 클래스
- **상태 추적 항목**:
  - `current_stage`: 현재 EAP 단계
  - `protocol_type`: 사용 중인 프로토콜 유형
  - `conversation_count`: 대화 횟수
  - `severity_level`: 심각도 수준
  - `scaling_scores`: 척도 질문 응답 저장
  - `identified_issues`: 식별된 문제 목록
  - `goals`: 목표 목록
  - `exceptions_found`: 발견된 예외 상황
  - `coping_strategies`: 대처 전략 목록

##### 세션 초기화
- **자동 초기화**: 종료 키워드 감지 시 ("exit", "고마워", "끝", "종료", "그만", "안녕")
- **수동 초기화**: `reset_session()` 메서드 호출
- **초기화 내용**: 모든 세션 상태를 초기값으로 리셋

#### 2.5.6 통합 답변 구조

##### 감정 + 상황 설명이 모두 있는 경우
```
1단계 - 감정 인정 및 공감 (1문장) [필수]
2단계 - 재해석 (1문장, 선택적) [아들러]
3단계 - 격려 및 실천 방안 (1문장, 선택적) [EAP + SFBT]
4단계 - 대화형 질문 제시 (필수)
```
- **총 문장 수**: 2~4문장
- **특징**: 재해석과 실천 방안은 선택적이지만, 상세한 입력의 경우 포함 권장

##### 감정만 표현된 경우
```
1단계 - 감정 인정 및 공감 (1문장) [필수]
2단계 - 척도 질문 제시 (필수)
```
- **총 문장 수**: 1~2문장
- **특징**: 재해석과 실천 방안 생략 (척도 질문과 자연스럽게 연결)

#### 2.5.7 주요 메서드

##### `generate_protocol_guidance(user_input, chat_history, adler_persona) -> Dict`
- **역할**: 프로토콜 기반 상담 가이드 생성
- **처리 과정**:
  1. 세션 상태 업데이트
  2. 프로토콜 선택 (키워드 기반)
  3. 심각도 평가 (키워드 기반)
  4. SFBT 질문 생성 (대화 단계 기반)
  5. 답변 구조 결정 (키워드 기반)
  6. 통합 프롬프트 생성
- **반환값**:
  ```json
  {
    "protocol_prompt": "통합 프롬프트 문자열",
    "protocol_type": "eap|sfbt|integrated",
    "current_stage": "initial_contact|assessment|...",
    "severity_level": "critical|high|medium|low",
    "sfbt_question_type": "scaling|exception|...",
    "sfbt_question": "질문 텍스트",
    "session_state": {...}
  }
  ```

##### `select_protocol(user_input, chat_history) -> ProtocolType`
- **역할**: 사용자 상황에 따라 적절한 프로토콜 선택
- **선택 기준**: 키워드 기반 (위기/해결책 키워드 감지)
- **반환값**: ProtocolType.EAP | SFBT | INTEGRATED

##### `assess_severity(user_input, chat_history) -> str`
- **역할**: 문제의 심각도 평가
- **반환값**: "critical" | "high" | "medium" | "low"

##### `has_situation_context(user_input) -> bool`
- **역할**: 감정 + 상황 설명이 있는지 판단
- **반환값**: True (1~3단계 구조) | False (공감+척도만)

##### `should_ask_sfbt_question(chat_history) -> Optional[SFBTQuestionType]`
- **역할**: 대화 단계에 따라 SFBT 질문 유형 결정
- **반환값**: 질문 유형 또는 None

##### `reset_session()`
- **역할**: 세션 상태 초기화
- **사용 시점**: 종료 키워드 감지 시 또는 수동 호출

#### 2.5.8 위기 개입 프로토콜

##### Critical/High 심각도 감지 시
- **즉각 대응**: 안전 확보 최우선
- **전문 기관 연계 안내**:
  - 자살예방상담전화: 1393
  - 정신건강위기상담: 1577-0199
- **안전 계획 제시**: 구체적이고 실천 가능한 계획

#### 2.5.9 성능 특성

##### 키워드 기반 처리
- **처리 시간**: ~9ms (총합)
  - `classify_input()`: ~2ms
  - `select_protocol()`: ~2ms
  - `assess_severity()`: ~2ms
  - `has_situation_context()`: ~3ms (2회 호출)
- **비용**: 무료 (로컬 처리)
- **정확도**: 명시적 표현에서 90%+, 부정문 처리 한계

##### LLM 대비 장점
- **속도**: 약 125배 빠름 (12ms vs 1,500ms)
- **비용**: 무료 vs 월 $45 (1,000 요청/일 기준)
- **확장성**: 무제한 동시 처리 가능

#### 2.5.10 통합 흐름

##### RAGTherapySystem과의 통합
1. `RAGTherapySystem.chat()` 호출
2. `TherapyProtocol.generate_protocol_guidance()` 실행
3. 프로토콜 프롬프트를 `ResponseGenerator`에 전달
4. LLM이 프로토콜 프롬프트를 기반으로 답변 생성

##### 프로토콜 프롬프트 구조
```
[아들러 페르소나]
+ [EAP 프로토콜 가이드]
+ [SFBT 질문 지시]
+ [통합 답변 구조 가이드]
```

---

## 3. 데이터 처리 파이프라인

### 3.1 AutomaticSaveManager (자동 저장 관리자)

#### 3.1.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/automatic_save.py`
- **역할**: 청크 생성 → 임베딩 생성 → Vector DB 저장을 순차적으로 실행
- **주요 기능**:
  1. 각 단계별 파일 존재 확인 (건너뛰기 지원)
  2. 폴더 자동 생성
  3. 에러 발생 시 롤백

#### 3.1.2 처리 단계

##### Step 1: 청크 파일 생성
- **스크립트**: `create_chunk_files.py`
- **입력**: PDF 파일들 (dataset/adler/{category}/*.pdf)
- **출력**: JSON 청크 파일들 (dataset/adler/chunkfiles/*_chunks.json)
- **건너뛰기 조건**: chunkfiles 폴더에 *_chunks.json 파일이 존재하면

##### Step 2: 임베딩 파일 생성
- **스크립트**: `create_openai_embeddings.py`
- **입력**: 청크 파일들 (*_chunks.json)
- **출력**: 임베딩 파일들 (*_embeddings.json)
- **건너뛰기 조건**: embeddings 폴더에 *_embeddings.json 파일이 존재하면

##### Step 3: Vector DB 저장
- **스크립트**: `save_to_vectordb.py`
- **입력**: 임베딩 파일들 (*_embeddings.json)
- **출력**: ChromaDB 컬렉션 ("vector_adler")
- **건너뛰기 조건**: 컬렉션이 존재하고 데이터가 있으면

#### 3.1.3 주요 메서드

##### `run() -> bool`
- **역할**: 전체 프로세스 실행
- **에러 처리**: 실패 시 롤백 (생성된 폴더 삭제)

---

### 3.2 ChunkCreator (청크 생성기)

#### 3.2.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/automatic_save/create_chunk_files.py`
- **역할**: PDF 파일을 Parent-Child 구조로 청킹
- **청킹 전략**: Parent-Child Chunking
  - **Parent**: 1000 tokens (큰 섹션)
  - **Child**: 500 tokens (세부 청크)
  - **Overlap**: 0.2 (20%)

#### 3.2.2 PDF 처리 과정

##### 1. 텍스트 추출
- **라이브러리**: PyMuPDF (fitz)
- **처리**: 페이지별로 텍스트 추출 후 결합

##### 2. 텍스트 정제화
- **정제 규칙**:
  1. 페이지 번호 제거 (정규식 패턴 4종)
  2. 표/그래프 특수문자 제거 (str.maketrans 사용)
  3. 참고문헌 섹션 제거 (정규식 패턴 5종)
  4. URL, 이메일 제거
  5. 한글 제거 (영문 문서만 처리)
  6. 반복되는 특수문자 제거
  7. 과도한 공백 정리 (줄바꿈, 공백, 탭)
- **최적화**: 정규식 패턴 컴파일 및 캐싱

##### 3. Parent-Child 청킹
- **Parent 청크 생성**:
  - 문단 단위로 분할 (빈 줄 기준)
  - parent_max_tokens (1000) 기준으로 분할
  - 단일 문단이 초과하면 줄 단위로 분할

- **Child 청크 생성**:
  - Parent를 max_tokens (500) 기준으로 분할
  - 문단 단위 우선, 필요시 줄 단위

##### 4. 메타데이터 추출
- **파일명 기반**: `adler_{category}_{number}.pdf`
- **카테고리**: case, theory, interventions, qna, tone
- **메타데이터 구조**:
  ```json
  {
    "author": "Adler",
    "source": "파일명",
    "category": "case|theory|interventions|qna|tone",
    "topic": "individual psychology",
    "tags": ["아들러", "카테고리별 태그"],
    "chunk_type": "parent|child",
    "parent_id": "...",  // Child인 경우
    "parent_index": 1,
    "child_index": 1,    // Child인 경우
    "total_parents": 5,
    "total_children": 3
  }
  ```

##### 5. 청크 객체 생성
- **ID 형식**:
  - Parent: `{base_id}_p{parent_idx:03d}`
  - Child: `{base_id}_p{parent_idx:03d}_c{child_idx:03d}`

#### 3.2.3 병렬 처리 최적화
- **방식**: ProcessPoolExecutor 사용
- **워커 수**: CPU 코어 수
- **효과**: 70-80% 시간 단축

#### 3.2.4 주요 메서드

##### `extract_text_from_pdf(pdf_path: Path) -> str`
- **역할**: PDF에서 텍스트 추출

##### `clean_pdf_text(text: str) -> str`
- **역할**: 텍스트 정제화 (10단계 규칙)

##### `split_into_parents(section_content: str) -> List[str]`
- **역할**: Parent 청크 생성 (1000 tokens 기준)

##### `split_parent_into_children(parent_content: str) -> List[str]`
- **역할**: Child 청크 생성 (500 tokens 기준)

##### `process_single_file(filepath: Path, output_dir: Path) -> Tuple[bool, str, int]`
- **역할**: 단일 파일 처리하여 개별 JSON 파일로 저장
- **반환값**: (성공 여부, 파일명, 청크 개수)

---

### 3.3 임베딩 생성

#### 3.3.1 OpenAI 임베딩 생성기

##### 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/automatic_save/create_openai_embeddings.py`
- **모델**: text-embedding-3-large
- **특징**: 비동기 배치 처리

##### 처리 과정
1. 청크 파일 로드 (*_chunks.json)
2. 비동기 배치 처리:
   - 배치 크기: 100
   - 동시 배치 수: 10 (Semaphore로 제한)
   - AsyncOpenAI 사용
3. 임베딩 파일 저장 (*_embeddings.json)

##### 최적화
- **비동기 처리**: 60-70% 시간 단축
- **병렬 파일 처리**: 여러 청크 파일 동시 처리

#### 3.3.2 BAAI/bge-m3 임베딩 생성기 (참고용)

##### 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/automatic_save/create_embeddings.py`
- **모델**: BAAI/bge-m3
- **특징**: 로컬 모델 (GPU/CPU)

##### 처리 과정
1. 모델 및 토크나이저 로드
2. 배치 처리 (배치 크기: 32)
3. Mean Pooling으로 임베딩 추출
4. NumPy 배열로 변환 후 저장

---

### 3.4 VectorDBManager (Vector DB 저장)

#### 3.4.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/automatic_save/save_to_vectordb.py`
- **역할**: 임베딩 파일들을 ChromaDB에 저장
- **컬렉션 이름**: "vector_adler"

#### 3.4.2 저장 과정

##### 1. 컬렉션 생성/가져오기
- **존재 확인**: 기존 컬렉션이 있으면 가져오기
- **생성**: 없으면 새로 생성 (hnsw:space="cosine")

##### 2. 중복 방지
- **ID 확인**: 기존 ID 목록 가져오기 (include=["ids"]로 메모리 최적화)
- **건너뛰기**: 이미 존재하는 ID는 저장하지 않음

##### 3. 배치 저장
- **배치 크기**: 1000
- **스트리밍 처리**: 파일별로 순차 처리 후 메모리 해제
- **에러 처리**: 중복 에러는 무시

##### 4. 메타데이터 변환
- **리스트 → 문자열**: ChromaDB는 리스트를 지원하지 않으므로 tags를 문자열로 변환

#### 3.4.3 메모리 최적화
- **스트리밍**: 파일별로 처리 후 즉시 메모리 해제
- **ID만 로드**: 기존 ID 확인 시 include=["ids"] 사용
- **GC 호출**: 배치 처리 후 명시적 가비지 컬렉션

#### 3.4.4 주요 메서드

##### `save_to_collection(collection_name: str, data: List[Dict], batch_size: int = 1000) -> int`
- **역할**: 데이터를 배치 단위로 컬렉션에 저장
- **반환값**: 저장된 항목 수

---

### 3.5 CollectionManager (컬렉션 관리)

#### 3.5.1 클래스 개요
- **파일 위치**: `backend/councel/sourcecode/manage_chromadb/manage_collections.py`
- **역할**: ChromaDB 컬렉션 조회, 삭제, 관리

#### 3.5.2 주요 기능

##### 컬렉션 목록 조회
- 모든 컬렉션의 이름, 항목 수, 메타데이터 출력

##### 컬렉션 상세 정보
- 항목 수, 메타데이터, 샘플 데이터 (최대 3개) 조회

##### 컬렉션 삭제
- 특정 컬렉션 삭제 (사용자 확인 필요)
- 모든 컬렉션 삭제 (사용자 확인 필요)

##### 데이터 조회
- 컬렉션에서 데이터 조회 (limit 지정)

---

## 4. 멀티 에이전트 시스템

### 4.1 BaseAgent (기본 에이전트)

#### 4.1.1 클래스 개요
- **파일 위치**: `backend/multi_agent/agents/base_agent.py`
- **역할**: 모든 전문 에이전트의 기본 클래스 (추상 클래스)
- **설계 패턴**: Template Method Pattern

#### 4.1.2 추상 메서드

##### `process(query: str, context: Optional[Dict[str, Any]] = None) -> str`
- **역할**: 질문 처리 (추상 메서드)
- **구현**: 각 에이전트에서 구현 필수

#### 4.1.3 주요 메서드

##### `get_name() -> str`
- **역할**: 에이전트 이름 반환

##### `get_description() -> str`
- **역할**: 에이전트 설명 반환

##### `get_capabilities() -> list`
- **역할**: 에이전트 기능 목록 반환 (기본값: 빈 리스트)

---

### 4.2 TherapyAgent (심리 상담 에이전트)

#### 4.2.1 클래스 개요
- **파일 위치**: `backend/multi_agent/agents/therapy_agent.py`
- **역할**: 멀티 에이전트 시스템에서 심리 상담 제공
- **특징**: Lazy Loading (실제 사용 시에만 TherapyService 로드)

#### 4.2.2 초기화
- **Lazy Loading**: `_therapy_service = None`으로 시작
- **Property**: `therapy_service` 프로퍼티로 필요 시 로드

#### 4.2.3 주요 메서드

##### `process(query: str, context: Optional[Dict[str, Any]] = None) -> str`
- **역할**: 심리 상담 처리
- **처리 과정**:
  1. TherapyService 사용 가능 여부 확인
  2. 컨텍스트에서 enable_scoring 추출 (기본값: True)
  3. TherapyService.chat() 호출
  4. 답변 반환
- **에러 처리**: 예외 발생 시 에러 메시지 반환

##### `get_capabilities() -> list`
- **반환값**: 기능 목록
  - 심리 상담
  - 감정적 지원
  - 스트레스 관리 조언
  - 대인관계 조언
  - 정신 건강 지원
  - 아들러 개인심리학 기반 상담

---

### 4.3 SupervisorAgent (중앙 관리자)

#### 4.3.1 클래스 개요
- **파일 위치**: `backend/multi_agent/supervisor.py`
- **역할**: 사용자 질문을 분석하여 적절한 전문 에이전트 선택 및 조율
- **설계 패턴**: Supervisor Pattern (Tool Calling)

#### 4.3.2 초기화 과정
1. LangSmith 추적 설정 (선택)
2. LLM 초기화 (ChatOpenAI, gpt-4o)
3. 전문 에이전트 도구 가져오기 (get_all_agent_tools)
4. System message 생성
5. LangGraph Agent 생성 (create_react_agent)

#### 4.3.3 System Message 구조

##### 역할 정의
- 사용자 질문 이해 및 의도 파악
- 키워드 및 맥락 분석
- 적절한 전문 에이전트 선택
- 작업 위임 및 결과 수신
- 최종 결과 전달

##### 사용 가능한 에이전트 목록
1. **chatbot_tool**: 일반 대화, 인사, 잡담
2. **rag_tool**: 회사 문서, 규정, 정책 검색
3. **brainstorming_tool**: 창의적 아이디어 발상
4. **planner_tool**: 일정 관리, 계획 수립
5. **report_tool**: 리포트 생성, 실적 분석
6. **therapy_tool**: 심리 상담, 정신 건강 지원
7. **notion_tool**: Notion 페이지 관리

##### 에이전트 선택 가이드
- **절대 우선순위**:
  1. "노션", "notion", "페이지" 포함 → notion_tool
  2. "브레인스토밍" 명시 → brainstorming_tool
  3. 감정 표현 → therapy_tool 우선
- **일반 규칙**:
  - 회사 규정/정책 검색 → rag_tool
  - 일정/계획 관리 → planner_tool
  - 리포트/실적 분석 → report_tool
  - 일반 대화 → chatbot_tool

#### 4.3.4 주요 메서드

##### `process(request: MultiAgentRequest) -> MultiAgentResponse`
- **역할**: 사용자 질문 처리
- **처리 과정**:
  1. Context 설정 (ContextVars)
  2. LangGraph Agent 실행
  3. 결과 추출 (messages에서 답변 추출)
  4. 사용된 도구 추출
  5. 세션에 대화 내용 저장
  6. MultiAgentResponse 생성
- **반환값**:
  ```json
  {
    "query": "사용자 질문",
    "answer": "최종 답변",
    "agent_used": "therapy|rag|chatbot|...",
    "intermediate_steps": [...],
    "processing_time": 1.23,
    "session_id": "..."
  }
  ```

##### `get_available_agents() -> List[Dict[str, Any]]`
- **역할**: 사용 가능한 에이전트 목록 반환

---

### 4.4 Context 관리

#### 4.4.1 ContextVars 사용
- **파일 위치**: `backend/multi_agent/context.py`
- **목적**: 비동기 요청 간의 컨텍스트 안전하게 관리
- **컨텍스트 종류**:
  1. **session_context**: 세션 ID
  2. **user_context**: 사용자 정보 (user_id 등)

#### 4.4.2 주요 함수

##### `get_session_id() -> Optional[str]`
- **역할**: 현재 컨텍스트의 세션 ID 반환

##### `get_user_context() -> Dict[str, Any]`
- **역할**: 현재 컨텍스트의 사용자 정보 반환

##### `reset_context()`
- **역할**: 컨텍스트 초기화

---

### 4.5 Agent Tools (도구 래핑)

#### 4.5.1 클래스 개요
- **파일 위치**: `backend/multi_agent/tools/agent_tools.py`
- **역할**: 각 전문 에이전트를 LangChain Tool로 래핑

#### 4.5.2 Lazy Loading 전략
- **전역 변수**: 각 에이전트를 전역 변수로 저장
- **초기화**: 첫 호출 시에만 에이전트 인스턴스 생성

#### 4.5.3 Tool 정의

##### `chatbot_tool(query: str) -> str`
- **역할**: 일반 대화 처리
- **에이전트**: ChatbotAgent

##### `rag_tool(query: str) -> str`
- **역할**: 회사 문서 검색
- **에이전트**: RAGAgent

##### `brainstorming_tool(query: str) -> str`
- **역할**: 브레인스토밍 지원
- **에이전트**: BrainstormingAgent

##### `planner_tool(query: str) -> str`
- **역할**: 일정 관리
- **에이전트**: PlannerAgent

##### `report_tool(query: str) -> str`
- **역할**: 리포트 생성
- **에이전트**: ReportAgent

##### `therapy_tool(query: str) -> str`
- **역할**: 심리 상담
- **에이전트**: TherapyAgent

##### `notion_tool(query: str) -> str`
- **역할**: Notion 페이지 관리
- **에이전트**: NotionAgent

#### 4.5.4 컨텍스트 관리

##### `get_current_context() -> Dict[str, Any]`
- **역할**: 현재 컨텍스트 반환
- **포함 정보**:
  - session_id
  - user_id
  - conversation_history (대화 기록)

---

### 4.6 Schemas (스키마)

#### 4.6.1 클래스 개요
- **파일 위치**: `backend/multi_agent/schemas.py`
- **역할**: Pydantic 모델 정의

#### 4.6.2 주요 모델

##### `MultiAgentRequest`
- **필드**:
  - query: str (사용자 질문)
  - session_id: Optional[str]
  - user_id: Optional[int]
  - context: Optional[Dict[str, Any]]

##### `MultiAgentResponse`
- **필드**:
  - query: str (원본 질문)
  - answer: str (최종 답변)
  - agent_used: str (사용된 에이전트)
  - intermediate_steps: Optional[List[Dict]]
  - processing_time: float
  - session_id: Optional[str]

##### `AgentInfo`
- **필드**:
  - name: str
  - description: str
  - capabilities: List[str]

---

### 4.7 Config (설정)

#### 4.7.1 클래스 개요
- **파일 위치**: `backend/multi_agent/config.py`
- **역할**: 멀티 에이전트 시스템 설정 관리

#### 4.7.2 주요 설정

##### OpenAI 설정
- OPENAI_API_KEY
- SUPERVISOR_MODEL: "gpt-4o"
- AGENT_MODEL: "gpt-4o-mini"

##### Temperature 설정
- SUPERVISOR_TEMPERATURE: 0.3 (결정적)
- AGENT_TEMPERATURE: 0.7 (창의적)

##### 기타 설정
- MAX_TOKENS: 2000
- SESSION_TIMEOUT: 3600 (1시간)
- LangSmith 추적 설정

---

## 5. 핵심 개념 정리

### 5.1 RAG (Retrieval-Augmented Generation)
- **정의**: 검색 기반 생성 모델
- **동작 방식**:
  1. 사용자 질문을 임베딩으로 변환
  2. Vector DB에서 유사한 문서 검색
  3. 검색된 문서를 컨텍스트로 LLM에 전달
  4. LLM이 컨텍스트를 바탕으로 답변 생성
- **장점**: 
  - 최신 정보 반영 가능
  - 도메인 특화 지식 활용
  - 환각(Hallucination) 감소

### 5.2 Threshold 기반 분기
- **목적**: 검색 품질에 따라 답변 전략 변경
- **Threshold**: 0.7
- **분기**:
  - 높은 유사도 (>= 0.7): LLM 단독 답변 (빠르고 효율적)
  - 낮은 유사도 (< 0.7): RAG + Self-learning (정확도 향상)

### 5.3 Self-learning
- **목적**: 시스템 자동 개선
- **동작**: 유사도가 낮은 Q&A를 Vector DB에 저장
- **효과**: 시간이 지날수록 답변 품질 향상

### 5.4 Parent-Child Chunking
- **목적**: 다양한 검색 시나리오 지원
- **구조**:
  - Parent: 큰 맥락 (1000 tokens)
  - Child: 세부 정보 (500 tokens)
- **장점**: 
  - 큰 맥락 검색 (Parent)
  - 세부 정보 검색 (Child)

### 5.5 Multi-step 반복 검색
- **목적**: 검색 품질 자동 개선
- **동작**:
  1. 초기 검색
  2. 품질 평가
  3. 품질이 낮으면 쿼리 확장 후 재검색
  4. 반복 (최대 max_iterations)

### 5.6 Re-ranker
- **목적**: 검색 결과 관련성 향상
- **방식**: LLM을 사용하여 청크 재정렬
- **조건**: 최고 유사도 < 0.55일 때만 실행

### 5.7 감정 키워드 가중치
- **목적**: 감정 관련 질문의 검색 정확도 향상
- **방식**: 사용자 입력과 청크에서 감정 키워드 매칭
- **보너스**: 최대 0.2

### 5.8 멀티 에이전트 시스템
- **패턴**: Supervisor Pattern
- **구조**:
  - Supervisor Agent: 중앙 관리자
  - 전문 에이전트들: 각 도메인별 전문가
- **통신**: LangChain Tool Calling

### 5.9 Lazy Loading
- **목적**: 메모리 및 초기화 시간 최적화
- **방식**: 실제 사용 시에만 인스턴스 생성
- **적용**: TherapyAgent, Agent Tools

### 5.10 ContextVars
- **목적**: 비동기 요청 간 컨텍스트 안전하게 관리
- **특징**: 각 비동기 태스크마다 독립적인 컨텍스트
- **사용**: 세션 ID, 사용자 정보 관리

### 5.11 EAP + SFBT 통합 프로토콜
- **목적**: 체계적이고 전문적인 상담 프로세스 제공
- **EAP**: 직장인 정신건강 지원 프로그램 (4단계)
- **SFBT**: 해결중심 단기 치료 (5가지 질문 유형)
- **통합 방식**: 상황에 맞게 자동 선택 및 통합
- **키워드 기반 판단**: 빠른 처리 (~9ms), 무료
- **동적 답변 구조**: 감정만 vs 감정+상황에 따라 구조 변경
- **세션 관리**: 대화 단계별 자동 진행 및 상태 추적

### 5.12 키워드 기반 판단 시스템
- **목적**: 빠르고 비용 효율적인 전처리 및 분류
- **사용 위치**: 
  - 프로토콜 선택 (위기/해결책 키워드)
  - 심각도 평가 (critical/high/medium 키워드)
  - 답변 구조 결정 (감정/상황 키워드)
- **장점**: 속도 (~9ms), 비용 무료, 확장성
- **단점**: 부정문 처리 한계, 동의어/은유 인식 어려움
- **개선 방안**: 부정 패턴 감지 추가 (정규식 기반)

---

## 6. 데이터 구조

### 6.1 청크 객체 구조
```json
{
  "id": "adler_theory_1_p001_c001",
  "text": "청크 텍스트 내용...",
  "metadata": {
    "author": "Adler",
    "source": "adler_theory_1.pdf",
    "category": "theory",
    "topic": "individual psychology",
    "tags": ["아들러", "이론", "개인심리학"],
    "chunk_type": "child",
    "parent_id": "adler_theory_1_p001",
    "parent_index": 1,
    "child_index": 1,
    "total_parents": 5,
    "total_children": 3
  }
}
```

### 6.2 임베딩 파일 구조
```json
{
  "id": "adler_theory_1_p001_c001",
  "text": "청크 텍스트 내용...",
  "metadata": {...},
  "embedding": [0.123, -0.456, ...]  // 3072차원 벡터 (text-embedding-3-large)
}
```

### 6.3 상담 응답 구조
```json
{
  "answer": "답변 텍스트",
  "used_chunks": ["청크 요약 리스트"],
  "used_chunks_detailed": [
    {
      "chunk_id": "...",
      "source": "...",
      "metadata": {...},
      "summary_kr": "...",
      "distance": 0.45,
      "similarity": 0.69
    }
  ],
  "mode": "counseling",
  "continue_conversation": true,
  "similarity_score": 0.75,
  "search_iterations": 1,
  "search_quality": {
    "avg_similarity": 0.68,
    "diversity_score": 0.8,
    "quality_score": 0.71,
    "needs_improvement": false
  }
}
```

### 6.4 멀티 에이전트 요청/응답 구조
```json
// 요청
{
  "query": "사용자 질문",
  "session_id": "session_123",
  "user_id": 1,
  "context": {}
}

// 응답
{
  "query": "사용자 질문",
  "answer": "최종 답변",
  "agent_used": "therapy",
  "intermediate_steps": [
    {
      "agent": "therapy",
      "action": "process_query",
      "result": "success"
    }
  ],
  "processing_time": 1.23,
  "session_id": "session_123"
}
```

### 6.5 프로토콜 세션 상태 구조
```json
{
  "current_stage": "initial_contact|assessment|short_term_intervention|follow_up",
  "protocol_type": "eap|sfbt|integrated",
  "conversation_count": 3,
  "identified_issues": ["문제1", "문제2"],
  "severity_level": "critical|high|medium|low",
  "goals": ["목표1", "목표2"],
  "scaling_scores": {
    "첫_대화": 5,
    "두_번째_대화": 6
  },
  "exceptions_found": ["예외 상황1"],
  "coping_strategies": ["대처 전략1"]
}
```

### 6.6 프로토콜 가이드 반환 구조
```json
{
  "protocol_prompt": "통합 프롬프트 문자열 (아들러 + EAP + SFBT)",
  "protocol_type": "eap|sfbt|integrated",
  "current_stage": "initial_contact|assessment|...",
  "severity_level": "critical|high|medium|low",
  "sfbt_question_type": "scaling|exception|coping|miracle|relationship",
  "sfbt_question": "지금 그런 힘든 마음은 0~10점 중 몇 점인 것 같으세요?",
  "session_state": {
    "current_stage": "...",
    "protocol_type": "...",
    "conversation_count": 0,
    "severity_level": "...",
    "scaling_scores": {},
    "identified_issues": [],
    "goals": [],
    "exceptions_found": [],
    "coping_strategies": []
  }
}
```

---

## 7. 성능 최적화 기법

### 7.1 검색 최적화
- **Set 연산**: 키워드 매칭을 O(1)로 최적화
- **조건부 Re-ranker**: 필요할 때만 실행 (비용 절감)
- **조기 종료**: 품질이 충분하면 반복 검색 중단

### 7.2 임베딩 생성 최적화
- **비동기 배치 처리**: AsyncOpenAI 사용
- **Semaphore**: 동시 배치 수 제한 (Rate Limit 고려)
- **병렬 파일 처리**: 여러 파일 동시 처리

### 7.3 청크 생성 최적화
- **정규식 캐싱**: 패턴 컴파일 및 재사용
- **병렬 처리**: ProcessPoolExecutor 사용
- **스트리밍**: 파일별로 처리 후 메모리 해제

### 7.4 Vector DB 최적화
- **스트리밍 저장**: 파일별로 순차 처리
- **ID만 로드**: 중복 확인 시 include=["ids"] 사용
- **배치 저장**: 1000개씩 배치로 저장

### 7.5 컨텍스트 최적화
- **대화 히스토리 제한**: 최근 2-5개만 포함
- **토큰 수 제한**: max_tokens 최적화 (180-200)

---

## 8. 에러 처리 및 예외 상황

### 8.1 Vector DB 연결 실패
- **처리**: FileNotFoundError 발생
- **대응**: 경로 확인 및 컬렉션 생성

### 8.2 OpenAI API 실패
- **처리**: 예외 발생 시 기본 메시지 반환
- **대응**: 재시도 로직 (필요 시)

### 8.3 검색 결과 없음
- **처리**: 빈 리스트 반환
- **대응**: "관련 자료를 찾을 수 없습니다" 메시지

### 8.4 Self-learning 저장 실패
- **처리**: 예외 무시 (답변은 계속 진행)
- **대응**: 백그라운드 태스크이므로 사용자 경험에 영향 없음

---

## 9. 확장 가능성

### 9.1 새로운 에이전트 추가
1. BaseAgent 상속
2. process() 메서드 구현
3. agent_tools.py에 Tool 추가
4. Supervisor의 System Message에 설명 추가

### 9.2 새로운 검색 전략 추가
- SearchEngine에 새로운 메서드 추가
- RAGTherapySystem에서 호출

### 9.3 새로운 페르소나 추가
- PersonaManager에 새로운 생성 메서드 추가
- 캐싱 전략 유지

---

## 10. JSON 변환 가이드

이 문서는 다음과 같은 구조로 JSON으로 변환할 수 있습니다:

```json
{
  "system_architecture": {
    "overview": "...",
    "flow": "..."
  },
  "therapy_system": {
    "rag_therapy_system": {...},
    "persona_manager": {...},
    "search_engine": {...},
    "response_generator": {...}
  },
  "data_pipeline": {
    "automatic_save": {...},
    "chunk_creator": {...},
    "embedding_generation": {...},
    "vector_db_manager": {...}
  },
  "multi_agent_system": {
    "base_agent": {...},
    "therapy_agent": {...},
    "supervisor_agent": {...},
    "context_management": {...},
    "agent_tools": {...},
    "schemas": {...},
    "config": {...}
  },
  "core_concepts": {...},
  "data_structures": {...},
  "performance_optimizations": {...},
  "error_handling": {...},
  "extensibility": {...}
}
```

각 섹션을 더 세분화하여 JSON 객체로 변환하면 됩니다.

---

## 결론

이 문서는 프로젝트의 모든 핵심 개념을 상세히 정리한 문서입니다. 각 컴포넌트의 역할, 동작 방식, 최적화 기법 등을 이해하면 프로젝트를 완벽히 이해할 수 있습니다.

**주요 포인트**:
1. RAG 기반 상담 시스템의 Threshold 분기 전략
2. EAP + SFBT 통합 프로토콜을 통한 체계적 상담 프로세스
3. 키워드 기반 판단 시스템의 빠른 처리 (~9ms, 무료)
4. 동적 답변 구조 (감정만 vs 감정+상황에 따른 구조 변경)
5. Self-learning을 통한 자동 개선
6. Parent-Child Chunking으로 다양한 검색 시나리오 지원
7. 멀티 에이전트 시스템의 Supervisor Pattern
8. 성능 최적화를 위한 다양한 기법

이 문서를 기반으로 JSON 파일을 생성하거나, 추가 문서화를 진행할 수 있습니다.

