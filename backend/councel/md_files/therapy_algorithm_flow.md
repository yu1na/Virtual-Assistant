<!-- 생성일 2025.11.24 -->
<!-- 심리상담 RAG 시스템 전체 알고리즘 플로우 -->

# 심리상담 RAG 시스템 전체 알고리즘 플로우

## 📋 개요
백엔드 Vector DB 생성부터 프론트엔드 사용자 입력, 결과값 출력까지의 전체 프로세스를 단계별로 정리합니다.

---

## 🔄 전체 플로우 다이어그램

```
[1단계] 백엔드 서버 시작
    ↓
[2단계] Vector DB 자동 생성 (automatic_save, 자세한건 algorithm_flow.md 참고)
    ├─ Step 1: 청크 파일 생성
    ├─ Step 2: 임베딩 파일 생성
    └─ Step 3: Vector DB 저장
    ↓
[3단계] TherapyService 초기화(therapy_algorithm_flow.md 174줄 이하 참고)
    ↓
[4단계] 사용자 입력 (프론트엔드, therapy_algorithm_flow.md 196줄 이하 참고)
    ↓
[5단계] 키워드 감지 (chatService.js, therapy_algorithm_flow.md 220줄 이하 참고)
    ↓
[6단계] Therapy API 호출(therapy_algorithm_flow.md 254줄 이하 참고)
    ↓
[7단계] RAG 시스템 처리(therapy_algorithm_flow.md 292줄 이하 참고)
    ├─ 입력 분류
    ├─ 영어 번역
    ├─ Vector DB 검색
    ├─ 페르소나 적용
    └─ 답변 생성
    ↓
[8단계] 응답 반환 및 UI 표시(therapy_algorithm_flow.md 451줄 이하 참고)
```

---

## 🔄 전체 데이터 흐름

```
[원본 PDF]
    ↓
[청크 파일] (JSON)
    ↓
[임베딩 파일] (JSON, 벡터)
    ↓
[Vector DB] (ChromaDB)
    ↓
[사용자 입력] (한국어)
    ↓
[영어 번역]
    ↓
[임베딩 벡터]
    ↓
[Vector DB 검색] (유사도 검색)
    ↓
[관련 청크 5개]
    ↓
[아들러 페르소나 + 컨텍스트]
    ↓
[GPT-4o-mini 답변 생성]
    ↓
[한국어 답변] (2-3문장)
    ↓
[프론트엔드 UI 표시] (🎭 아이콘)
```

---

## 📊 주요 컴포넌트 역할

| 컴포넌트 | 파일 | 역할 |
|---------|------|------|
| **AutomaticSaveManager** | `automatic_save.py` | Vector DB 자동 생성 관리 |
| **RAGTherapySystem** | `rag_therapy.py` | RAG 기반 상담 시스템 핵심 로직 |
| **TherapyService** | `therapy/service.py` | FastAPI와 RAG 시스템 연결 |
| **Therapy Endpoint** | `endpoints/therapy.py` | REST API 엔드포인트 |
| **ChatService** | `chatService.js` | 키워드 감지 및 API 호출 |
| **ChatPanel** | `chatPanel.js` | UI 메시지 표시 |

---

---

## 🎯 핵심 알고리즘 요약

1. **서버 시작** → Vector DB 자동 생성 (청크 → 임베딩 → 저장)
2. **사용자 입력** → 키워드 감지 → Therapy API 호출
3. **입력 처리** → 분류 → 번역 → Vector DB 검색
4. **답변 생성** → 페르소나 적용 → GPT 생성 → 히스토리 업데이트
5. **UI 표시** → 특별한 스타일로 메시지 표시

---

## 📝 상세 알고리즘 순서

### **1단계: 백엔드 서버 시작**

**파일**: `backend/app/main.py`

**실행 순서**:
1. FastAPI 애플리케이션 생성
2. `lifespan` 함수 실행 (서버 시작 시)
3. 데이터베이스 테이블 생성
4. **Vector DB 자동 생성 호출** (`automatic_save()`)

**코드 위치**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 데이터베이스 초기화 ...
    
    # Vector DB 자동 생성
    print("\n🧠 Initializing Therapy Vector DB...")
    success = automatic_save()
```

---

### **2단계: Vector DB 자동 생성**

**파일**: `backend/councel/sourcecode/automatic_save.py`

**실행 순서**:

#### **2-1. Step 1: 청크 파일 생성**
- **입력**: `backend/councel/dataset/adler/*.pdf` (원본 PDF 파일들)
- **처리**: 
  - `create_chunk_files.py` 실행
  - PDF 파일을 텍스트로 변환
  - 의미 단위로 청크 분할
- **출력**: `backend/councel/dataset/adler/chunkfiles/*_chunks.json`
- **검증**: 파일이 이미 존재하면 건너뛰기

#### **2-2. Step 2: 임베딩 파일 생성**
- **입력**: `chunkfiles/*_chunks.json`
- **처리**:
  - `create_openai_embeddings.py` 실행
  - OpenAI `text-embedding-3-large` 모델 사용
  - 각 청크를 벡터로 변환
- **출력**: `backend/councel/dataset/adler/embeddings/*_embeddings.json`
- **검증**: 파일이 이미 존재하면 건너뛰기

#### **2-3. Step 3: Vector DB 저장**
- **입력**: `embeddings/*_embeddings.json`
- **처리**:
  - `save_to_vectordb.py` 실행
  - ChromaDB PersistentClient 사용
  - 컬렉션 이름: `vector_adler`
  - 임베딩 벡터와 메타데이터 저장
- **출력**: `backend/councel/vector_db/` (ChromaDB SQLite 파일)
- **검증**: 컬렉션이 이미 존재하고 데이터가 있으면 건너뛰기

**알고리즘**:
```python
def run(self) -> bool:
    if not self.step1_create_chunks():      # 청크 생성
        raise Exception("청크 파일 생성 실패")
    
    if not self.step2_create_embeddings():   # 임베딩 생성
        raise Exception("임베딩 파일 생성 실패")
    
    if not self.step3_save_to_vectordb():   # Vector DB 저장
        raise Exception("Vector DB 저장 실패")
    
    return True
```

---

### **3단계: TherapyService 초기화**

**파일**: `backend/app/domain/therapy/service.py`

**실행 순서**:
1. 싱글톤 패턴으로 인스턴스 생성
2. Vector DB 경로 설정: `backend/councel/vector_db`
3. `RAGTherapySystem` 초기화
   - ChromaDB 클라이언트 연결
   - 컬렉션 `vector_adler` 로드
   - OpenAI 클라이언트 초기화
   - 아들러 페르소나 프롬프트 설정

**알고리즘**:
```python
def __init__(self):
    vector_db_dir = base_dir / "councel" / "vector_db"
    self._rag_system = RAGTherapySystem(str(vector_db_dir))
```

---

### **4단계: 사용자 입력 (프론트엔드)**

**파일**: `renderer/chat/chatPanel.js`

**실행 순서**:
1. 사용자가 채팅창에 메시지 입력
2. `handleSendMessage()` 함수 호출
3. 입력창 초기화
4. `callChatModule(userText)` 호출

**알고리즘**:
```javascript
async function handleSendMessage() {
  const text = chatInput.value.trim();
  addMessage('user', text);
  chatInput.value = '';
  
  const response = await callChatModule(text);
  // 응답 처리...
}
```

---

### **5단계: 키워드 감지 및 라우팅**

**파일**: `renderer/chat/chatService.js`

**실행 순서**:
1. `isTherapyRelated(userText)` 함수로 키워드 검사
2. 심리 상담 키워드 감지 시 → `sendTherapyMessage()` 호출
3. 일반 키워드 → `sendChatbotMessage()` 호출

**심리 상담 키워드 목록**:
```javascript
[
  '힘들어', '상담', '짜증', '우울', '불안', '스트레스',
  '고민', '걱정', '슬프', '외로', '화나', '답답',
  '아들러', 'adler', 'counseling', 'therapy', 'help',
  'depressed', 'anxious', '심리'
]
```

**알고리즘**:
```javascript
export async function callChatModule(userText) {
  // 심리 상담 키워드 감지
  if (isTherapyRelated(userText)) {
    return await sendTherapyMessage(userText);  // Therapy API 호출
  }
  
  // 일반 챗봇 API 호출
  return await sendChatbotMessage(userText);
}
```

---

### **6단계: Therapy API 호출**

**파일**: 
- 프론트엔드: `renderer/chat/chatService.js`
- 백엔드: `backend/app/api/v1/endpoints/therapy.py`

**실행 순서**:

#### **6-1. 프론트엔드 → 백엔드 요청**
```javascript
POST http://localhost:8000/api/v1/therapy/chat
Content-Type: application/json

{
  "message": "요즘 너무 힘들어요"
}
```

#### **6-2. 백엔드 엔드포인트 처리**
1. `TherapyRequest` 모델로 요청 검증
2. `TherapyService.chat(user_input)` 호출
3. 응답을 `TherapyResponse` 모델로 변환

**알고리즘**:
```python
@router.post("/chat", response_model=TherapyResponse)
async def chat_therapy(request: TherapyRequest):
    response = therapy_service.chat(request.message)
    return TherapyResponse(
        answer=response["answer"],
        mode=response["mode"],
        used_chunks=response.get("used_chunks", []),
        continue_conversation=response.get("continue_conversation", True)
    )
```

---

### **7단계: RAG 시스템 처리**

**파일**: `backend/councel/sourcecode/persona/rag_therapy.py`

**실행 순서**:

#### **7-1. 입력 분류 (`classify_input`)**
- **입력**: 사용자 메시지 (한국어/영어)
- **처리**:
  - "아들러" 또는 "adler" 키워드 → `"adler"` 모드
  - 감정/상담 키워드 → `"counseling"` 모드
  - 기타 → `"general"` 모드
- **출력**: `input_type` (adler/counseling/general)

**알고리즘**:
```python
def classify_input(self, user_input: str) -> str:
    if "아들러" in user_input or "adler" in user_input.lower():
        return "adler"
    
    for keyword in self.counseling_keywords:
        if keyword in user_input.lower():
            return "counseling"
    
    return "general"
```

#### **7-2. 영어 번역 (`translate_to_english`)**
- **입력**: 사용자 메시지 (한국어)
- **처리**:
  - OpenAI GPT-4o-mini 모델 사용
  - 한국어 → 영어 번역
- **출력**: 영어 번역된 텍스트
- **이유**: Vector DB의 임베딩이 영어로 생성되었기 때문

**알고리즘**:
```python
def translate_to_english(self, text: str) -> str:
    response = self.openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a translator..."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()
```

#### **7-3. Vector DB 검색 (`retrieve_chunks`)**
- **입력**: 영어로 번역된 질문
- **처리**:
  1. 질문을 임베딩 벡터로 변환 (`text-embedding-3-large`)
  2. ChromaDB에서 유사도 검색 (`n_results=5`)
  3. 상위 5개 관련 청크 반환
- **출력**: 관련 청크 리스트 (텍스트 + 메타데이터)

**알고리즘**:
```python
def retrieve_chunks(self, user_input: str, n_results: int = 5):
    # 1. 임베딩 생성
    query_embedding = self.create_query_embedding(user_input)
    
    # 2. Vector DB 검색
    results = self.collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    
    # 3. 결과 포맷팅
    retrieved_chunks = []
    for i in range(len(results['ids'][0])):
        chunk = {
            'id': results['ids'][0][i],
            'text': results['documents'][0][i],
            'metadata': results['metadatas'][0][i],
            'distance': results['distances'][0][i]
        }
        retrieved_chunks.append(chunk)
    
    return retrieved_chunks
```

#### **7-4. 페르소나 적용 및 답변 생성 (`generate_response_with_persona`)**
- **입력**: 
  - 사용자 메시지 (원문, 한국어)
  - 검색된 청크 리스트
  - 모드 (adler/counseling/general)
- **처리**:
  1. 상위 3개 청크를 컨텍스트로 구성
  2. 아들러 페르소나 프롬프트 적용
  3. 대화 히스토리 추가 (최근 2개)
  4. OpenAI GPT-4o-mini로 답변 생성
  5. 답변 길이 제한 (max_tokens=200, 2-3문장)
- **출력**: 아들러 개인심리학 기반 상담 답변

**아들러 페르소나 핵심 원칙**:
- 열등감과 보상: 열등감을 성장의 기회로 재해석
- 사회적 관심: 공동체 감각 강조
- 생활양식: 개인의 독특한 생활양식 인정
- 목적론적 관점: 미래 목표 중심
- 격려: 용기를 북돋우는 톤

**알고리즘**:
```python
def generate_response_with_persona(self, user_input, retrieved_chunks, mode):
    # 1. 컨텍스트 구성
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks[:3], 1):
        context_parts.append(f"[자료 {i}]\n{chunk['text']}\n(출처: {chunk['metadata']['source']})")
    
    context = "\n\n".join(context_parts)
    
    # 2. 메시지 구성
    messages = [{"role": "system", "content": self.adler_persona}]
    
    # 3. 대화 히스토리 추가 (최근 2개)
    for history in self.chat_history[-2:]:
        messages.append({"role": "user", "content": history["user"]})
        messages.append({"role": "assistant", "content": history["assistant"]})
    
    # 4. 현재 질문 추가
    user_message = f"""참고 자료:
{context}

사용자 질문: {user_input}

위 자료를 바탕으로 아들러 개인심리학 관점에서 답변해주세요.
**중요: 답변은 2-3문장 이내로 간결하게 작성해주세요.**"""
    
    messages.append({"role": "user", "content": user_message})
    
    # 5. OpenAI API 호출
    response = self.openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=200
    )
    
    answer = response.choices[0].message.content.strip()
    
    # 6. 대화 히스토리 업데이트 (최대 10개 유지)
    self.chat_history.append({
        "user": user_input,
        "assistant": answer
    })
    if len(self.chat_history) > 10:
        self.chat_history = self.chat_history[-10:]
    
    return {
        "answer": answer,
        "used_chunks": used_chunks,
        "mode": mode,
        "continue_conversation": True
    }
```

---

### **8단계: 응답 반환 및 UI 표시**

**파일**: 
- 백엔드: `backend/app/api/v1/endpoints/therapy.py`
- 프론트엔드: `renderer/chat/chatPanel.js`, `renderer/styles/chat.css`

**실행 순서**:

#### **8-1. 백엔드 → 프론트엔드 응답**
```json
{
  "answer": "당신의 어려움을 이해합니다. 이러한 상황은...",
  "mode": "counseling",
  "used_chunks": ["adler_01.pdf: 열등감은...", "adler_02.pdf: 사회적 관심은..."],
  "continue_conversation": true
}
```

#### **8-2. 프론트엔드 UI 표시**
1. `chatPanel.js`의 `addTherapyMessage()` 함수 호출
2. 🎭 아이콘과 함께 특별한 스타일로 메시지 표시
3. CSS 애니메이션 적용 (펄스 효과)

**알고리즘**:
```javascript
// chatPanel.js
if (response.type === 'therapy') {
    addTherapyMessage(response.data, response.mode);
}

function addTherapyMessage(text, mode) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant therapy';
    
    // 🎭 아이콘 추가
    const icon = document.createElement('div');
    icon.className = 'therapy-icon';
    icon.textContent = '🎭';
    
    // 메시지 버블
    const bubble = document.createElement('div');
    bubble.className = 'bubble therapy-bubble';
    bubble.textContent = text;
    
    messageDiv.appendChild(icon);
    messageDiv.appendChild(bubble);
    messagesContainer.appendChild(messageDiv);
}
```

**CSS 스타일**:
```css
.message.therapy {
    align-items: flex-start;
}

.therapy-icon {
    font-size: 24px;
    animation: pulse 2s ease-in-out infinite;
}

.therapy-bubble {
    background: linear-gradient(135deg, rgba(255, 230, 200, 0.9), rgba(255, 240, 220, 0.9));
    border-left: 4px solid rgba(200, 150, 100, 0.6);
    font-style: italic;
}
```


## ⚙️ 설정 및 파라미터

### Vector DB 검색
- **검색 결과 수**: `n_results=5` (상위 5개 청크)
- **사용 청크 수**: 상위 3개만 답변 생성에 사용
- **임베딩 모델**: `text-embedding-3-large`

### 답변 생성
- **LLM 모델**: `gpt-4o-mini`
- **Temperature**: `0.7` (창의성과 일관성 균형)
- **Max Tokens**: `200` (2-3문장 제한)
- **대화 히스토리**: 최근 10개 유지 (답변 생성 시 최근 2개만 사용)

### 페르소나
- **이름**: 아들러 개인심리학 기반 상담사
- **톤**: 격려적, 희망적, 실용적
- **답변 스타일**: 간결함 (2-3문장)

---

## 📝 참고사항

- Vector DB는 서버 시작 시 한 번만 생성 (이미 존재하면 건너뛰기)
- 대화 히스토리는 메모리에만 저장 (세션별로 관리되지 않음)
- 모든 모드(adler/counseling/general)에서 아들러 페르소나 적용
- 다국어 지원: 한국어 입력 → 영어 번역 → Vector DB 검색 → 한국어 답변