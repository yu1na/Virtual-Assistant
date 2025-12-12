# 7일 완성 프로젝트 개념 학습 계획

> 이 문서는 프로젝트의 모든 핵심 개념을 7일 안에 체계적으로 학습할 수 있도록 구성되었습니다.
> 매일 필수 암기 사항을 중심으로 학습하세요.

---

## 📅 전체 학습 일정

| 날짜 | 주제 | 핵심 키워드 |
|------|------|------------|
| Day 1 | 시스템 개요 및 기본 개념 | RAG, Vector DB, 멀티 에이전트, 시스템 흐름 |
| Day 2 | RAG 시스템 기초 | RAGTherapySystem, Threshold, Self-learning |
| Day 3 | 검색 엔진 및 최적화 | SearchEngine, Re-ranker, Multi-step 검색 |
| Day 4 | 답변 생성 및 프로토콜 | ResponseGenerator, TherapyProtocol, EAP, SFBT |
| Day 5 | 데이터 파이프라인 | ChunkCreator, 임베딩, VectorDB 저장 |
| Day 6 | 멀티 에이전트 시스템 | SupervisorAgent, BaseAgent, Context 관리 |
| Day 7 | 통합 복습 및 핵심 정리 | 전체 시스템 통합 이해 |

---

# Day 1: 시스템 개요 및 기본 개념

## 🎯 학습 목표
- 전체 시스템 아키텍처 이해
- 핵심 기술 스택 파악
- 시스템 흐름도 암기

## ⭐ 필수 암기 사항 (반드시 외우기!)

### 1. 시스템 목적
```
RAG(Retrieval-Augmented Generation) 기반 심리 상담 시스템 + 멀티 에이전트 시스템
```

### 2. 핵심 기술 스택 (5가지)
1. **Vector Database**: ChromaDB
2. **OpenAI Embeddings**: text-embedding-3-large
3. **OpenAI GPT**: gpt-4o-mini, gpt-4o
4. **LangChain + LangGraph**: 멀티 에이전트
5. **아들러 개인심리학**: 상담 기반 이론

### 3. 주요 기능 (3가지)
1. 아들러 개인심리학 기반 심리 상담
2. 문서 기반 RAG 검색
3. 멀티 에이전트 시스템 (Supervisor 패턴)

### 4. 시스템 흐름도 (암기 필수!)
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

### 5. 핵심 개념 정의

#### RAG (Retrieval-Augmented Generation)
- **정의**: 검색 기반 생성 모델
- **동작 방식**:
  1. 사용자 질문을 임베딩으로 변환
  2. Vector DB에서 유사한 문서 검색
  3. 검색된 문서를 컨텍스트로 LLM에 전달
  4. LLM이 컨텍스트를 바탕으로 답변 생성
- **장점**: 최신 정보 반영, 도메인 특화, 환각 감소

#### 멀티 에이전트 시스템
- **패턴**: Supervisor Pattern
- **구조**: Supervisor Agent (중앙 관리자) + 전문 에이전트들
- **통신**: LangChain Tool Calling

## 📚 학습 내용 요약

### 1.1 시스템 개요
- RAG 기반 심리 상담 시스템
- 멀티 에이전트 아키텍처
- 아들러 개인심리학 적용

### 1.2 시스템 흐름도
- 사용자 질문 → Supervisor → 전문 에이전트 → RAGTherapySystem → SearchEngine → ResponseGenerator → 답변

## ✅ 복습 체크리스트
- [ ] 시스템 목적을 한 문장으로 설명할 수 있는가?
- [ ] 핵심 기술 스택 5가지를 모두 외웠는가?
- [ ] 시스템 흐름도를 그릴 수 있는가?
- [ ] RAG의 동작 방식을 4단계로 설명할 수 있는가?
- [ ] 멀티 에이전트 시스템의 패턴을 말할 수 있는가?

---

# Day 2: RAG 시스템 기초

## 🎯 학습 목표
- RAGTherapySystem의 역할과 책임 이해
- Threshold 기반 분기 시스템 암기
- Self-learning 메커니즘 이해
- PersonaManager의 페르소나 생성 전략 파악

## ⭐ 필수 암기 사항 (반드시 외우기!)

### 1. RAGTherapySystem 주요 책임 (5가지)
1. Vector DB 연결 및 관리
2. 상담 세션 관리 (대화 히스토리, 사용자별 세션)
3. EAP + SFBT 프로토콜 통합 관리
4. Threshold 기반 분기 처리
5. Self-learning (Q&A 자동 저장)

### 2. Threshold 기반 분기 시스템 (암기 필수!)
- **Threshold 값**: **0.7** (고정)
- **분기 로직**:
  ```
  최고 유사도 >= 0.7
    → LLM 단독 답변 (RAG 없이)
  
  최고 유사도 < 0.7
    → RAG + Self-learning
      - 검색된 청크를 기반으로 답변 생성
      - Q&A를 Vector DB에 자동 저장 (Self-learning)
  ```

### 3. Self-learning 메커니즘
- **목적**: 유사도가 낮은 질문-답변 쌍을 Vector DB에 저장하여 시스템 개선
- **트리거 조건**: 유사도 < 0.7
- **동작**: 
  1. 사용자 질문과 LLM 답변을 JSON 형태로 저장
  2. 질문을 임베딩으로 변환하여 Vector DB에 저장
  3. 메타데이터: `source="self_learning"`, `type="qa_pair"`
- **처리 방식**: 비동기 (`asyncio.create_task()`)

### 4. RAGTherapySystem.chat() 처리 단계 (7단계)
1. 종료 키워드 확인 ("exit", "고마워", "끝", "종료", "그만", "안녕")
2. 프로토콜 가이드 생성 (TherapyProtocol.generate_protocol_guidance)
3. 입력 분류 (ResponseGenerator.classify_input)
4. Multi-step 반복 검색 (SearchEngine)
5. 최고 유사도 계산
6. Threshold 분기 (>= 0.7: LLM 단독, < 0.7: RAG + Self-learning)
7. 대화 히스토리에 추가 (최대 10개)

### 5. PersonaManager 페르소나 생성 방식 (2가지)
1. **기본 페르소나**: 프롬프트 엔지니어링 (즉시 사용 가능, 안정적)
2. **RAG 페르소나**: Vector DB + 웹 검색 (백그라운드 생성, 24시간 캐시)

### 6. 초기화 과정 (6단계)
1. Vector DB 경로 확인 및 ChromaDB 클라이언트 생성
2. 컬렉션 로드 ("vector_adler")
3. OpenAI 클라이언트 초기화 (동기 + 비동기)
4. 모듈 초기화 (PersonaManager, TherapyProtocol, SearchEngine, ResponseGenerator)
5. 대화 히스토리 초기화 (최대 10개 유지)
6. 사용자별 세션 관리 초기화 (user_sessions)

## 📚 학습 내용 요약

### 2.1 RAGTherapySystem
- 메인 상담 시스템 컨트롤러
- 파일 위치: `backend/councel/sourcecode/persona/rag_therapy.py`
- Threshold 0.7 기준으로 분기 처리

### 2.2 PersonaManager
- 아들러 심리학자 페르소나 생성 및 관리
- 파일 위치: `backend/councel/sourcecode/persona/persona_manager.py`
- 기본 페르소나 + RAG 페르소나 이중 전략

## ✅ 복습 체크리스트
- [ ] Threshold 값 0.7을 외웠는가?
- [ ] Threshold 분기 로직을 설명할 수 있는가?
- [ ] Self-learning의 트리거 조건과 동작 방식을 설명할 수 있는가?
- [ ] chat() 메서드의 7단계 처리 과정을 외웠는가?
- [ ] PersonaManager의 2가지 페르소나 생성 방식을 구분할 수 있는가?

---

# Day 3: 검색 엔진 및 최적화

## 🎯 학습 목표
- SearchEngine의 검색 전략 이해
- Re-ranker 동작 방식 암기
- Multi-step 반복 검색 메커니즘 파악
- 감정 키워드 가중치 시스템 이해

## ⭐ 필수 암기 사항 (반드시 외우기!)

### 1. SearchEngine 주요 기능 (5가지)
1. 임베딩 생성 (동기/비동기)
2. Vector DB 검색
3. Re-ranker (검색 결과 재정렬)
4. Multi-step 반복 검색
5. 감정 키워드 가중치 적용

### 2. 기본 검색 과정 (4단계)
1. 사용자 질문을 임베딩으로 변환
2. ChromaDB에서 유사도 검색 (L2 distance)
3. Distance를 유사도로 변환: **`1 / (1 + distance)`**
4. 조건부 Re-ranker 적용 (최고 유사도 < 0.55일 때만)

### 3. Re-ranker (재정렬)
- **목적**: 검색 결과의 관련성 향상
- **동작 방식**:
  1. LLM에게 청크들의 관련성 평가 요청
  2. LLM이 관련성 순서대로 번호 반환
  3. 번호 순서대로 청크 재정렬
- **실행 조건**: **최고 유사도 < 0.55일 때만** (비용 절감)

### 4. Multi-step 반복 검색
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

### 5. 감정 키워드 가중치
- **목적**: 감정 관련 질문의 검색 정확도 향상
- **동작 방식**:
  1. 사용자 입력에서 감정 키워드 추출 (set 연산)
  2. 청크 텍스트에서 매칭되는 키워드 개수 계산
  3. 매칭 비율에 따라 보너스 계산
  4. 최종 유사도 = 기본 유사도 + 감정 보너스
- **최대 보너스**: **0.2**

### 6. Distance → Similarity 변환 공식
```
similarity = 1 / (1 + distance)
```

### 7. 주요 메서드
- `create_query_embedding_async()`: 질문을 임베딩 벡터로 변환 (text-embedding-3-large)
- `retrieve_chunks_async()`: Vector DB에서 관련 청크 검색
- `rerank_chunks()`: LLM을 사용하여 청크 재정렬 (조건: 최고 유사도 < 0.55)
- `_iterative_search_with_query_expansion_async()`: Multi-step 반복 검색
- `_calculate_emotion_boost()`: 감정 키워드 매칭 보너스 계산 (최대 0.2)

## 📚 학습 내용 요약

### 3.1 검색 전략
- 기본 검색 → Re-ranker (조건부) → Multi-step 반복 검색 → 감정 가중치 적용

### 3.2 최적화 기법
- Set 연산으로 키워드 매칭 O(1) 최적화
- 조건부 Re-ranker로 비용 절감
- 조기 종료로 불필요한 반복 방지

## ✅ 복습 체크리스트
- [ ] Distance → Similarity 변환 공식을 외웠는가?
- [ ] Re-ranker의 실행 조건 (최고 유사도 < 0.55)을 외웠는가?
- [ ] Multi-step 반복 검색의 조기 종료 조건을 외웠는가?
- [ ] 감정 키워드 가중치의 최대 보너스 값 (0.2)을 외웠는가?
- [ ] 기본 검색의 4단계 과정을 설명할 수 있는가?

---

# Day 4: 답변 생성 및 프로토콜

## 🎯 학습 목표
- ResponseGenerator의 답변 생성 전략 이해
- 3단계 답변 구조 암기
- TherapyProtocol의 EAP + SFBT 통합 프로토콜 파악
- 키워드 기반 판단 시스템 이해

## ⭐ 필수 암기 사항 (반드시 외우기!)

### 1. ResponseGenerator 입력 분류 (3가지)
- **adler**: "아들러" 또는 "adler" 키워드 포함
- **counseling**: 감정/상담 키워드 포함 (set 연산으로 최적화)
- **general**: 그 외

### 2. 답변 생성 전략

#### LLM 단독 답변 (`_generate_llm_only_response`)
- **사용 조건**: 유사도 >= 0.7 (Threshold 분기)
- **특징**:
  - RAG 없이 페르소나만 사용
  - 대화 히스토리 최근 2개만 포함
  - 감정 맥락 파악
  - 2~3문장으로 적절한 길이로 작성
- **모델**: gpt-4o-mini
- **Temperature**: 0.3
- **Max Tokens**: 180 (2~3문장)

#### RAG 기반 답변 (`generate_response_with_persona`)
- **사용 조건**: 유사도 < 0.7
- **특징**:
  - 검색된 청크 상위 3개 사용
  - 페르소나 프롬프트 + 청크 컨텍스트
  - 대화 히스토리 최근 5개 포함
  - 감정 키워드 자동 감지
  - 참고 자료를 바탕으로 상세하고 구체적인 답변 생성 (4~7문장)
- **모델**: gpt-4o-mini
- **Temperature**: 0.3
- **Max Tokens**: 400 (RAG 사용 시 상세하게 4~7문장)

### 3. 답변 구조 (암기 필수!)

#### LLM 단독 답변 구조 (2~3문장)
1. **감정 인정 및 공감** (1문장, 필수)
   - 사용자의 감정을 있는 그대로 인정
   - 예: "~하셨군요", "~느끼시는 마음이 충분히 이해됩니다"
   - 금지: "하지만", "그래도"로 시작

2. **자연스러운 질문 또는 공감문** (1~2문장)
   - 사용자의 상황에 맞게 자연스럽게 질문
   - 상담을 계속 이어가도록 하는 질문 포함

#### RAG 기반 답변 구조 (4~7문장)
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

### 4. EAP 프로토콜 (4단계)
1. **INITIAL_CONTACT**: 초기 접촉 및 문제 파악
2. **ASSESSMENT**: 평가 (심각도, 긴급성)
3. **SHORT_TERM_INTERVENTION**: 단기 개입
4. **FOLLOW_UP**: 후속 조치

### 5. SFBT 질문 유형 (5가지)
1. **SCALING**: 척도 질문 (0~10점)
2. **EXCEPTION**: 예외 탐색 질문
3. **COPING**: 대처 질문
4. **MIRACLE**: 기적 질문
5. **RELATIONSHIP**: 관계 질문

### 6. SFBT 질문 순서 (대화 단계별)
- **0회차 (첫 대화)**: SCALING (척도 질문)
- **1회차**: EXCEPTION (예외 탐색)
- **2회차**: COPING (대처 질문)
- **3회차**: MIRACLE (기적 질문)
- **4회차 이상**: RELATIONSHIP (관계 질문)

### 7. 키워드 기반 판단 시스템

#### 프로토콜 선택 (`select_protocol`)
- **위기 키워드**: ['죽고 싶', '자살', '자해', '끝내고 싶', '포기', '절망']
  - 감지 시 → **EAP 프로토콜** 우선 적용
- **해결책 키워드**: ['어떻게', '방법', '해결', '개선', '나아지', '변화']
  - 감지 시 → **SFBT 프로토콜** 우선 적용
- **기본**: 통합 프로토콜 사용
- **처리 시간**: ~2ms

#### 심각도 평가 (`assess_severity`)
- **Critical**: ['죽고 싶', '자살', '자해', '끝내고 싶']
- **High**: ['견딜 수 없', '미치겠', '한계', '더 이상 못', '불가능']
- **Medium**: ['힘들', '어렵', '괴롭', '고통', '스트레스']
- **Low**: 그 외
- **처리 시간**: ~2ms

#### 답변 구조 결정 (`has_situation_context`)
- **감정 키워드** (23개): 힘들, 어렵, 괴롭, 슬프, 화나, 우울, 불안, 답답, 스트레스, 고통, 절망, 무기력, 초조, 걱정, 두려움, 짜증, 분노, 상처, 아픔, 외로움, 허탈, 실망
- **상황 키워드** (40개+): 직장, 회사, 동료, 상사, 가족, 부모, 문제, 상황, 일어났, 발생했, 때문에, 해서 등
- **판단 로직**:
  - 감정 + 상황 모두 있음 → 1~3단계 답변 구조 (공감 + 재해석 + 실천 방안 + 질문)
  - 감정만 있음 → 공감 + 척도 질문만 (1~2문장)
- **처리 시간**: ~3ms

### 8. 키워드 기반 처리 성능
- **처리 시간**: ~9ms (총합)
- **비용**: 무료 (로컬 처리)
- **정확도**: 명시적 표현에서 90%+
- **LLM 대비**: 약 125배 빠름 (12ms vs 1,500ms)

### 9. 위기 개입 프로토콜
- **Critical/High 심각도 감지 시**:
  - 즉각 대응: 안전 확보 최우선
  - 전문 기관 연계 안내:
    - 자살예방상담전화: **1393**
    - 정신건강위기상담: **1577-0199**
  - 안전 계획 제시

### 10. 통합 답변 구조

#### 감정 + 상황 설명이 모두 있는 경우
```
1단계 - 감정 인정 및 공감 (1문장) [필수]
2단계 - 재해석 (1문장, 선택적) [아들러]
3단계 - 격려 및 실천 방안 (1문장, 선택적) [EAP + SFBT]
4단계 - 대화형 질문 제시 (필수)
```
- **총 문장 수**: 2~4문장

#### 감정만 표현된 경우
```
1단계 - 감정 인정 및 공감 (1문장) [필수]
2단계 - 척도 질문 제시 (필수)
```
- **총 문장 수**: 1~2문장

## 📚 학습 내용 요약

### 4.1 ResponseGenerator
- 입력 분류 (adler/counseling/general)
- LLM 단독 답변 vs RAG 기반 답변
- 3단계 답변 구조 강제

### 4.2 TherapyProtocol
- EAP 4단계 프로토콜
- SFBT 5가지 질문 유형
- 키워드 기반 판단 시스템 (~9ms, 무료)
- 동적 답변 구조 (감정만 vs 감정+상황)

## ✅ 복습 체크리스트
- [ ] LLM 단독 답변 구조 (2~3문장)를 외웠는가?
- [ ] RAG 기반 답변 구조 (4~7문장)를 외웠는가?
- [ ] EAP 프로토콜 4단계를 외웠는가?
- [ ] SFBT 질문 유형 5가지를 외웠는가?
- [ ] SFBT 질문 순서를 대화 단계별로 외웠는가?
- [ ] 위기 키워드와 해결책 키워드를 구분할 수 있는가?
- [ ] 심각도 평가 4단계를 외웠는가?
- [ ] 위기 개입 전화번호를 외웠는가? (1393, 1577-0199)
- [ ] 키워드 기반 처리 시간 (~9ms)과 비용(무료)을 외웠는가?

---

# Day 5: 데이터 파이프라인

## 🎯 학습 목표
- AutomaticSaveManager의 처리 단계 이해
- Parent-Child Chunking 전략 암기
- 임베딩 생성 과정 파악
- VectorDB 저장 최적화 기법 이해

## ⭐ 필수 암기 사항 (반드시 외우기!)

### 1. AutomaticSaveManager 처리 단계 (3단계)
1. **Step 1: 청크 파일 생성**
   - 스크립트: `create_chunk_files.py`
   - 입력: PDF 파일들 (dataset/adler/{category}/*.pdf)
   - 출력: JSON 청크 파일들 (*_chunks.json)
   - 건너뛰기 조건: chunkfiles 폴더에 *_chunks.json 파일이 존재하면

2. **Step 2: 임베딩 파일 생성**
   - 스크립트: `create_openai_embeddings.py`
   - 입력: 청크 파일들 (*_chunks.json)
   - 출력: 임베딩 파일들 (*_embeddings.json)
   - 건너뛰기 조건: embeddings 폴더에 *_embeddings.json 파일이 존재하면

3. **Step 3: Vector DB 저장**
   - 스크립트: `save_to_vectordb.py`
   - 입력: 임베딩 파일들 (*_embeddings.json)
   - 출력: ChromaDB 컬렉션 ("vector_adler")
   - 건너뛰기 조건: 컬렉션이 존재하고 데이터가 있으면

### 2. Parent-Child Chunking 전략 (암기 필수!)
- **Parent**: **1000 tokens** (큰 섹션)
- **Child**: **500 tokens** (세부 청크)
- **Overlap**: **0.2 (20%)**
- **목적**: 다양한 검색 시나리오 지원
  - 큰 맥락 검색 (Parent)
  - 세부 정보 검색 (Child)

### 3. PDF 처리 과정 (5단계)
1. **텍스트 추출**: PyMuPDF (fitz) 사용, 페이지별로 추출 후 결합
2. **텍스트 정제화**: 10단계 규칙 (페이지 번호 제거, 표/그래프 특수문자 제거, 참고문헌 제거, URL/이메일 제거, 한글 제거, 반복 특수문자 제거, 공백 정리 등)
3. **Parent-Child 청킹**: 
   - Parent: 문단 단위로 분할, 1000 tokens 기준
   - Child: Parent를 500 tokens 기준으로 분할
4. **메타데이터 추출**: 파일명 기반 (카테고리: case, theory, interventions, qna, tone)
5. **청크 객체 생성**: ID 형식
   - Parent: `{base_id}_p{parent_idx:03d}`
   - Child: `{base_id}_p{parent_idx:03d}_c{child_idx:03d}`

### 4. 청크 메타데이터 구조
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

### 5. 임베딩 생성 (OpenAI)
- **모델**: text-embedding-3-large
- **특징**: 비동기 배치 처리
- **배치 크기**: 100
- **동시 배치 수**: 10 (Semaphore로 제한)
- **최적화**: 비동기 처리로 60-70% 시간 단축

### 6. VectorDB 저장 과정 (4단계)
1. **컬렉션 생성/가져오기**: 기존 컬렉션이 있으면 가져오기, 없으면 생성 (hnsw:space="cosine")
2. **중복 방지**: 기존 ID 목록 가져오기 (include=["ids"]로 메모리 최적화), 이미 존재하는 ID는 저장하지 않음
3. **배치 저장**: 배치 크기 1000, 스트리밍 처리 (파일별로 순차 처리 후 메모리 해제)
4. **메타데이터 변환**: 리스트 → 문자열 (ChromaDB는 리스트를 지원하지 않으므로 tags를 문자열로 변환)

### 7. 최적화 기법

#### 청크 생성 최적화
- **정규식 캐싱**: 패턴 컴파일 및 재사용
- **병렬 처리**: ProcessPoolExecutor 사용 (CPU 코어 수만큼 워커)
- **효과**: 70-80% 시간 단축

#### 임베딩 생성 최적화
- **비동기 배치 처리**: AsyncOpenAI 사용
- **Semaphore**: 동시 배치 수 제한 (Rate Limit 고려)
- **병렬 파일 처리**: 여러 파일 동시 처리
- **효과**: 60-70% 시간 단축

#### Vector DB 최적화
- **스트리밍 저장**: 파일별로 순차 처리 후 메모리 해제
- **ID만 로드**: 중복 확인 시 include=["ids"] 사용
- **배치 저장**: 1000개씩 배치로 저장
- **GC 호출**: 배치 처리 후 명시적 가비지 컬렉션

### 8. 컬렉션 이름
- **컬렉션 이름**: **"vector_adler"**

### 9. 임베딩 차원
- **text-embedding-3-large**: **3072차원 벡터**

## 📚 학습 내용 요약

### 5.1 데이터 파이프라인
PDF → 청크 생성 → 임베딩 생성 → Vector DB 저장

### 5.2 Parent-Child Chunking
- Parent: 1000 tokens (큰 맥락)
- Child: 500 tokens (세부 정보)
- 다양한 검색 시나리오 지원

### 5.3 최적화
- 병렬 처리 (청크 생성)
- 비동기 배치 처리 (임베딩 생성)
- 스트리밍 저장 (Vector DB)

## ✅ 복습 체크리스트
- [ ] AutomaticSaveManager의 3단계 처리 과정을 외웠는가?
- [ ] Parent-Child Chunking의 크기 (Parent: 1000, Child: 500)를 외웠는가?
- [ ] Overlap 비율 (0.2, 20%)을 외웠는가?
- [ ] 청크 ID 형식을 외웠는가? (Parent: `{base_id}_p{parent_idx:03d}`, Child: `{base_id}_p{parent_idx:03d}_c{child_idx:03d}`)
- [ ] 컬렉션 이름 ("vector_adler")을 외웠는가?
- [ ] 임베딩 차원 (3072)을 외웠는가?
- [ ] 배치 크기 (임베딩: 100, Vector DB: 1000)를 외웠는가?

---

# Day 6: 멀티 에이전트 시스템

## 🎯 학습 목표
- BaseAgent의 추상 클래스 구조 이해
- SupervisorAgent의 역할과 동작 방식 암기
- Context 관리 (ContextVars) 파악
- Agent Tools의 Lazy Loading 전략 이해

## ⭐ 필수 암기 사항 (반드시 외우기!)

### 1. BaseAgent (추상 클래스)
- **파일 위치**: `backend/multi_agent/agents/base_agent.py`
- **설계 패턴**: Template Method Pattern
- **추상 메서드**: `process(query: str, context: Optional[Dict[str, Any]] = None) -> str`
- **주요 메서드**:
  - `get_name() -> str`
  - `get_description() -> str`
  - `get_capabilities() -> list`

### 2. SupervisorAgent 초기화 과정 (5단계)
1. LangSmith 추적 설정 (선택)
2. LLM 초기화 (ChatOpenAI, gpt-4o)
3. 전문 에이전트 도구 가져오기 (get_all_agent_tools)
4. System message 생성
5. LangGraph Agent 생성 (create_react_agent)

### 3. SupervisorAgent 역할 (5가지)
1. 사용자 질문 이해 및 의도 파악
2. 키워드 및 맥락 분석
3. 적절한 전문 에이전트 선택
4. 작업 위임 및 결과 수신
5. 최종 결과 전달

### 4. 사용 가능한 에이전트 목록 (7가지)
1. **chatbot_tool**: 일반 대화, 인사, 잡담
2. **rag_tool**: 회사 문서, 규정, 정책 검색
3. **brainstorming_tool**: 창의적 아이디어 발상
4. **planner_tool**: 일정 관리, 계획 수립
5. **report_tool**: 리포트 생성, 실적 분석
6. **therapy_tool**: 심리 상담, 정신 건강 지원
7. **notion_tool**: Notion 페이지 관리

### 5. 에이전트 선택 가이드

#### 절대 우선순위
1. "노션", "notion", "페이지" 포함 → **notion_tool**
2. "브레인스토밍" 명시 → **brainstorming_tool**
3. 감정 표현 → **therapy_tool** 우선

#### 일반 규칙
- 회사 규정/정책 검색 → rag_tool
- 일정/계획 관리 → planner_tool
- 리포트/실적 분석 → report_tool
- 일반 대화 → chatbot_tool

### 6. SupervisorAgent.process() 처리 과정 (6단계)
1. Context 설정 (ContextVars)
2. LangGraph Agent 실행
3. 결과 추출 (messages에서 답변 추출)
4. 사용된 도구 추출
5. 세션에 대화 내용 저장
6. MultiAgentResponse 생성

### 7. ContextVars (컨텍스트 관리)
- **파일 위치**: `backend/multi_agent/context.py`
- **목적**: 비동기 요청 간의 컨텍스트 안전하게 관리
- **컨텍스트 종류**:
  1. **session_context**: 세션 ID
  2. **user_context**: 사용자 정보 (user_id 등)
- **특징**: 각 비동기 태스크마다 독립적인 컨텍스트
- **주요 함수**:
  - `get_session_id() -> Optional[str]`
  - `get_user_context() -> Dict[str, Any]`
  - `reset_context()`

### 8. Agent Tools (Lazy Loading)
- **파일 위치**: `backend/multi_agent/tools/agent_tools.py`
- **역할**: 각 전문 에이전트를 LangChain Tool로 래핑
- **Lazy Loading 전략**: 전역 변수로 저장, 첫 호출 시에만 에이전트 인스턴스 생성

### 9. TherapyAgent 특징
- **Lazy Loading**: `_therapy_service = None`으로 시작, `therapy_service` 프로퍼티로 필요 시 로드
- **기능 목록**:
  - 심리 상담
  - 감정적 지원
  - 스트레스 관리 조언
  - 대인관계 조언
  - 정신 건강 지원
  - 아들러 개인심리학 기반 상담

### 10. MultiAgentRequest 구조
```json
{
  "query": "사용자 질문",
  "session_id": "session_123",
  "user_id": 1,
  "context": {}
}
```

### 11. MultiAgentResponse 구조
```json
{
  "query": "사용자 질문",
  "answer": "최종 답변",
  "agent_used": "therapy|rag|chatbot|...",
  "intermediate_steps": [...],
  "processing_time": 1.23,
  "session_id": "session_123"
}
```

### 12. Config 설정
- **SUPERVISOR_MODEL**: "gpt-4o"
- **AGENT_MODEL**: "gpt-4o-mini"
- **SUPERVISOR_TEMPERATURE**: 0.3 (결정적)
- **AGENT_TEMPERATURE**: 0.7 (창의적)
- **MAX_TOKENS**: 2000
- **SESSION_TIMEOUT**: 3600 (1시간)

## 📚 학습 내용 요약

### 6.1 멀티 에이전트 아키텍처
- Supervisor Pattern
- BaseAgent 추상 클래스
- 전문 에이전트들 (7가지)

### 6.2 SupervisorAgent
- 중앙 관리자 역할
- 에이전트 선택 및 조율
- LangGraph Agent 사용

### 6.3 Context 관리
- ContextVars로 비동기 컨텍스트 안전하게 관리
- 세션 ID, 사용자 정보 관리

### 6.4 Lazy Loading
- TherapyAgent, Agent Tools에서 사용
- 메모리 및 초기화 시간 최적화

## ✅ 복습 체크리스트
- [ ] BaseAgent의 추상 메서드 이름을 외웠는가? (process)
- [ ] SupervisorAgent의 5가지 역할을 외웠는가?
- [ ] 사용 가능한 에이전트 7가지를 외웠는가?
- [ ] 에이전트 선택 가이드의 절대 우선순위 3가지를 외웠는가?
- [ ] ContextVars의 컨텍스트 종류 2가지를 외웠는가?
- [ ] Supervisor 모델 (gpt-4o)과 Agent 모델 (gpt-4o-mini)을 구분할 수 있는가?
- [ ] Temperature 설정 (Supervisor: 0.3, Agent: 0.7)을 외웠는가?

---

# Day 7: 통합 복습 및 핵심 정리

## 🎯 학습 목표
- 전체 시스템 통합 이해
- 핵심 개념 최종 정리
- 데이터 구조 암기
- 성능 최적화 기법 종합

## ⭐ 필수 암기 사항 (최종 정리!)

### 1. 전체 시스템 흐름도 (암기 필수!)
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

### 2. 핵심 숫자 정리 (암기 필수!)

#### Threshold 및 유사도
- **Threshold**: 0.7
- **Re-ranker 실행 조건**: 최고 유사도 < 0.55
- **감정 키워드 최대 보너스**: 0.2
- **Multi-step 조기 종료**: 품질 점수 >= 0.7 또는 평균 유사도 >= 0.6

#### Chunking
- **Parent 크기**: 1000 tokens
- **Child 크기**: 500 tokens
- **Overlap**: 0.2 (20%)

#### 임베딩 및 배치
- **임베딩 모델**: text-embedding-3-large
- **임베딩 차원**: 3072
- **임베딩 배치 크기**: 100
- **Vector DB 배치 크기**: 1000

#### 대화 히스토리
- **최대 대화 히스토리**: 10개
- **LLM 단독 답변 히스토리**: 최근 2개
- **RAG 기반 답변 히스토리**: 최근 5개

#### 성능
- **키워드 기반 처리 시간**: ~9ms
- **LLM 대비 속도**: 약 125배 빠름 (12ms vs 1,500ms)
- **키워드 기반 처리 비용**: 무료

#### 모델 설정
- **Supervisor 모델**: gpt-4o
- **Agent 모델**: gpt-4o-mini
- **Supervisor Temperature**: 0.3
- **Agent Temperature**: 0.7
- **LLM 답변 Temperature**: 0.3
- **LLM 단독 Max Tokens**: 180 (2~3문장)
- **RAG 기반 Max Tokens**: 400 (4~7문장)

#### 세션
- **세션 타임아웃**: 3600초 (1시간)
- **페르소나 캐시 유효성**: 24시간 (86400초)

### 3. 핵심 개념 정의 (암기 필수!)

#### RAG (Retrieval-Augmented Generation)
- 검색 기반 생성 모델
- 4단계: 질문 임베딩 → Vector DB 검색 → 컨텍스트 전달 → LLM 답변 생성

#### Threshold 기반 분기
- Threshold: 0.7
- >= 0.7: LLM 단독 답변
- < 0.7: RAG + Self-learning

#### Self-learning
- 목적: 시스템 자동 개선
- 트리거: 유사도 < 0.7
- 동작: Q&A를 Vector DB에 자동 저장

#### Parent-Child Chunking
- Parent: 1000 tokens (큰 맥락)
- Child: 500 tokens (세부 정보)
- 목적: 다양한 검색 시나리오 지원

#### Multi-step 반복 검색
- 목적: 검색 품질 자동 개선
- 동작: 초기 검색 → 품질 평가 → 쿼리 확장 → 재검색

#### Re-ranker
- 목적: 검색 결과 관련성 향상
- 방식: LLM을 사용하여 청크 재정렬
- 조건: 최고 유사도 < 0.55일 때만 실행

#### 멀티 에이전트 시스템
- 패턴: Supervisor Pattern
- 구조: Supervisor Agent + 전문 에이전트들
- 통신: LangChain Tool Calling

#### EAP + SFBT 통합 프로토콜
- EAP: 4단계 (INITIAL_CONTACT, ASSESSMENT, SHORT_TERM_INTERVENTION, FOLLOW_UP)
- SFBT: 5가지 질문 유형 (SCALING, EXCEPTION, COPING, MIRACLE, RELATIONSHIP)
- 키워드 기반 판단: ~9ms, 무료

### 4. 답변 구조 (암기 필수!)

#### LLM 단독 답변 (2~3문장)
1. **감정 인정 및 공감** (1문장) - 필수
2. **자연스러운 질문 또는 공감문** (1~2문장) - 필수

#### RAG 기반 답변 (4~7문장)
1. **감정 인정 및 공감** (1~2문장) - 필수
2. **참고 자료 기반 통찰 또는 조언** (2~3문장) - 필수
3. **자연스러운 질문 또는 다음 단계 제안** (1~2문장) - 필수

### 5. EAP 프로토콜 4단계 (암기 필수!)
1. INITIAL_CONTACT (초기 접촉 및 문제 파악)
2. ASSESSMENT (평가)
3. SHORT_TERM_INTERVENTION (단기 개입)
4. FOLLOW_UP (후속 조치)

### 6. SFBT 질문 유형 5가지 (암기 필수!)
1. SCALING (척도 질문)
2. EXCEPTION (예외 탐색)
3. COPING (대처 질문)
4. MIRACLE (기적 질문)
5. RELATIONSHIP (관계 질문)

### 7. SFBT 질문 순서 (대화 단계별)
- 0회차: SCALING
- 1회차: EXCEPTION
- 2회차: COPING
- 3회차: MIRACLE
- 4회차 이상: RELATIONSHIP

### 8. 키워드 기반 판단

#### 프로토콜 선택
- 위기 키워드 → EAP 프로토콜
- 해결책 키워드 → SFBT 프로토콜
- 기본: 통합 프로토콜

#### 심각도 평가
- Critical: 죽고 싶, 자살, 자해, 끝내고 싶
- High: 견딜 수 없, 미치겠, 한계, 더 이상 못, 불가능
- Medium: 힘들, 어렵, 괴롭, 고통, 스트레스
- Low: 그 외

#### 답변 구조 결정
- 감정 + 상황 → 1~3단계 구조
- 감정만 → 공감 + 척도 질문만

### 9. 위기 개입 전화번호 (암기 필수!)
- 자살예방상담전화: **1393**
- 정신건강위기상담: **1577-0199**

### 10. 파일 위치 정리
- RAGTherapySystem: `backend/councel/sourcecode/persona/rag_therapy.py`
- PersonaManager: `backend/councel/sourcecode/persona/persona_manager.py`
- SearchEngine: `backend/councel/sourcecode/persona/search_engine.py`
- ResponseGenerator: `backend/councel/sourcecode/persona/response_generator.py`
- TherapyProtocol: `backend/councel/sourcecode/persona/therapy_protocol.py`
- BaseAgent: `backend/multi_agent/agents/base_agent.py`
- SupervisorAgent: `backend/multi_agent/supervisor.py`
- Context: `backend/multi_agent/context.py`
- Agent Tools: `backend/multi_agent/tools/agent_tools.py`

### 11. 컬렉션 이름
- **"vector_adler"**

### 12. 종료 키워드
- "exit", "고마워", "끝", "종료", "그만", "안녕"

## 📚 최종 통합 정리

### 전체 시스템 아키텍처
1. 멀티 에이전트 시스템 (Supervisor Pattern)
2. RAG 기반 상담 시스템
3. 데이터 파이프라인 (PDF → 청크 → 임베딩 → Vector DB)

### 핵심 흐름
1. 사용자 질문 → Supervisor Agent
2. 에이전트 선택 → RAGTherapySystem
3. 프로토콜 가이드 생성 → SearchEngine 검색
4. Threshold 분기 → ResponseGenerator 답변 생성

### 최적화 기법
1. Threshold 기반 분기 (0.7)
2. 조건부 Re-ranker (< 0.55)
3. Multi-step 반복 검색
4. 감정 키워드 가중치 (최대 0.2)
5. 키워드 기반 판단 (~9ms, 무료)
6. Lazy Loading
7. 병렬/비동기 처리

## ✅ 최종 복습 체크리스트
- [ ] 전체 시스템 흐름도를 그릴 수 있는가?
- [ ] 핵심 숫자들을 모두 외웠는가? (Threshold 0.7, Parent 1000, Child 500 등)
- [ ] LLM 단독 답변 구조 (2~3문장)를 외웠는가?
- [ ] RAG 기반 답변 구조 (4~7문장)를 외웠는가?
- [ ] EAP 프로토콜 4단계를 외웠는가?
- [ ] SFBT 질문 유형 5가지를 외웠는가?
- [ ] SFBT 질문 순서를 대화 단계별로 외웠는가?
- [ ] 위기 개입 전화번호를 외웠는가?
- [ ] 키워드 기반 판단의 성능 특성을 설명할 수 있는가?
- [ ] 주요 파일 위치를 외웠는가?
- [ ] 핵심 개념들을 정의할 수 있는가?

---

## 📝 학습 팁

### 암기 방법
1. **매일 아침**: 전날 학습한 핵심 정리 복습
2. **매일 저녁**: 당일 학습한 필수 암기 사항 다시 확인
3. **주말**: 전체 복습 및 통합 정리

### 실습 방법
1. 각 컴포넌트의 코드를 직접 읽어보기
2. 시스템 흐름도를 그려보기
3. 핵심 숫자와 키워드를 플래시카드로 만들기

### 체크리스트 활용
- 각 Day의 체크리스트를 매일 확인
- 체크되지 않은 항목은 다시 학습
- Day 7의 최종 체크리스트로 전체 점검

---

## 🎯 학습 성공 기준

다음 질문들에 모두 답할 수 있으면 학습 성공!

1. Threshold 값은 무엇이고, 어떻게 사용되는가?
2. RAG의 동작 방식을 4단계로 설명하라.
3. Parent-Child Chunking의 크기는?
4. LLM 단독 답변 구조와 RAG 기반 답변 구조는?
5. EAP 프로토콜 4단계는?
6. SFBT 질문 유형 5가지는?
7. 키워드 기반 판단의 성능 특성은?
8. 전체 시스템 흐름도를 설명하라.
9. Self-learning의 트리거 조건과 동작 방식은?
10. 멀티 에이전트 시스템의 패턴과 구조는?

---

**화이팅! 7일 안에 모든 개념을 마스터하세요! 🚀**

