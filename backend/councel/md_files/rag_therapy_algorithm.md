<!-- 생성일 2025.11.21 -->

# RAG Therapy System 알고리즘 및 구조 설명

## 개요

`rag_therapy.py`는 OpenAI API와 ChromaDB를 활용한 RAG(Retrieval-Augmented Generation) 기반 상담 시스템입니다. 아들러 개인심리학 페르소나를 적용하여 사용자 질문에 맞춤형 답변을 생성합니다.

## 시스템 아키텍처

```
┌─────────────────┐
│  사용자 입력     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  입력 분류       │ (adler/counseling/general)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  영어 번역       │ (OpenAI gpt-4o-mini)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  임베딩 생성     │ (OpenAI text-embedding-3-large)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Vector DB 검색  │ (ChromaDB)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  컨텍스트 구성   │ (상위 3개 청크)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  페르소나 적용   │ (아들러 페르소나)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  답변 생성       │ (OpenAI gpt-4o-mini)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  대화 히스토리   │ (단기 기억)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  한국어 출력     │
└─────────────────┘
```

## 핵심 알고리즘

### 1. 입력 분류 알고리즘 (`classify_input`)

**목적**: 사용자 입력을 분석하여 처리 모드를 결정

**알고리즘**:
```python
1. 입력 텍스트를 소문자로 변환
2. "아들러" 또는 "adler" 키워드 검색
   → 발견 시: "adler" 반환
3. 감정/상담 키워드 목록 순회
   → 발견 시: "counseling" 반환
4. 그 외: "general" 반환
```

**키워드 목록**:
- 한국어: "힘들어", "상담", "짜증", "우울", "불안", "스트레스", "고민", "걱정", "슬프", "외로", "화나", "답답"
- 영어: "counseling", "therapy", "help", "depressed", "anxious"

**시간 복잡도**: O(n) (n = 키워드 개수)

### 2. 번역 알고리즘 (`translate_to_english`)

**목적**: 다국어 입력을 영어로 번역하여 Vector DB 검색 정확도 향상

**알고리즘**:
```python
1. OpenAI API 호출 (gpt-4o-mini)
2. System Prompt: "번역기 역할"
3. User Input: 원문 텍스트
4. 번역 결과 반환
5. 실패 시 원문 반환 (Fallback)
```

**특징**:
- Temperature: 0.3 (일관된 번역)
- Max Tokens: 500
- 에러 처리: 원문 반환으로 시스템 안정성 확보

### 3. 임베딩 생성 알고리즘 (`create_query_embedding`)

**목적**: 텍스트를 고차원 벡터로 변환하여 의미적 유사도 검색 가능하게 함

**알고리즘**:
```python
1. OpenAI Embeddings API 호출
2. Model: text-embedding-3-large
3. Input: 영어로 번역된 텍스트
4. 3072차원 벡터 반환
```

**특징**:
- text-embedding-3-large: 고정밀도 임베딩
- 벡터 차원: 3072
- 코사인 유사도 기반 검색

### 4. Vector DB 검색 알고리즘 (`retrieve_chunks`)

**목적**: 사용자 질문과 유사한 상담 자료를 Vector DB에서 검색

**알고리즘**:
```python
1. 현재 컬렉션 확인
2. 쿼리 임베딩 생성
3. ChromaDB query() 호출
   - query_embeddings: [임베딩 벡터]
   - n_results: 5
4. 결과 포맷팅
   - id, text, metadata, distance
5. 청크 리스트 반환
```

**검색 방식**:
- 코사인 유사도 기반 유사도 검색
- 상위 5개 결과 반환
- 거리(distance) 값으로 유사도 측정

**시간 복잡도**: O(log n) (ChromaDB의 인덱싱 활용)

### 5. 페르소나 기반 답변 생성 알고리즘 (`generate_response_with_persona`)

**목적**: 검색된 자료를 아들러 페르소나 스타일로 재구성하여 답변 생성

**알고리즘**:
```python
1. 검색 결과 확인
   → 없으면: 기본 메시지 반환
2. 컨텍스트 구성
   - 상위 3개 청크 선택
   - 각 청크에 출처 정보 추가
3. 프롬프트 구성
   - System: 아들러 페르소나 프롬프트
   - User: 참고 자료 + 사용자 질문
4. 대화 히스토리 추가
   - 최근 2개 대화만 포함 (컨텍스트 길이 관리)
5. OpenAI API 호출
   - Model: gpt-4o-mini
   - Temperature: 0.7
   - Max Tokens: 1000
6. 답변 반환
```

**페르소나 프롬프트 구조**:
```
1. 역할 정의: 아들러 개인심리학 심리학자
2. 핵심 원칙:
   - 열등감과 보상
   - 사회적 관심
   - 생활양식
   - 목적론적 관점
   - 격려
3. 답변 방식:
   - 열등감을 성장 기회로 재해석
   - 사회적 관심 강조
   - 격려와 용기 제공
4. 말투:
   - 격려적이고 희망적인 표현
   - "~할 수 있습니다", "~의 기회입니다"
```

**컨텍스트 관리**:
- 최근 2개 대화만 포함 (토큰 수 제한)
- 최대 10개 대화 히스토리 저장
- 오래된 대화 자동 제거

### 6. 대화 히스토리 관리 알고리즘

**목적**: 단기 기억을 통해 자연스러운 대화 흐름 유지

**데이터 구조**:
```python
chat_history = [
    {
        "user": "사용자 입력",
        "assistant": "상담사 답변"
    },
    ...
]
```

**관리 알고리즘**:
```python
1. 새 대화 추가
2. 히스토리 길이 확인
3. 길이가 10 초과 시
   → 가장 오래된 항목 제거
   → 최근 10개만 유지
```

**사용 방식**:
- 답변 생성 시 최근 2개 대화만 컨텍스트에 포함
- 토큰 수 제한으로 비용 관리
- 자연스러운 대화 맥락 유지

## 주요 데이터 구조

### 1. RAGTherapySystem 클래스

```python
class RAGTherapySystem:
    # 초기화
    - db_path: Vector DB 경로
    - client: ChromaDB 클라이언트
    - openai_client: OpenAI 클라이언트
    - current_collection: 현재 선택된 컬렉션
    - counseling_keywords: 감정 키워드 목록
    - chat_history: 대화 히스토리 (최대 10개)
    - adler_persona: 아들러 페르소나 프롬프트
```

### 2. 청크 데이터 구조

```python
chunk = {
    'id': str,              # 청크 고유 ID
    'text': str,            # 청크 텍스트 내용
    'metadata': dict,       # 메타데이터 (source, psychologist 등)
    'distance': float       # 유사도 거리 (낮을수록 유사)
}
```

### 3. 응답 데이터 구조

```python
response = {
    'answer': str,                    # 생성된 답변
    'used_chunks': List[str],         # 사용된 청크 요약
    'mode': str,                      # 처리 모드 (adler/counseling/general)
    'continue_conversation': bool     # 대화 계속 여부
}
```

## 처리 플로우 상세

### 전체 처리 흐름

```
1. 사용자 입력 수신
   ↓
2. exit 체크
   → exit이면: 종료 메시지 반환
   ↓
3. 입력 분류 (classify_input)
   → adler / counseling / general
   ↓
4. 영어 번역 (translate_to_english)
   → OpenAI API 호출
   ↓
5. 임베딩 생성 (create_query_embedding)
   → text-embedding-3-large
   ↓
6. Vector DB 검색 (retrieve_chunks)
   → ChromaDB query
   → 상위 5개 결과
   ↓
7. 답변 생성 (generate_response_with_persona)
   → 컨텍스트 구성 (상위 3개)
   → 페르소나 프롬프트 적용
   → 대화 히스토리 추가
   → OpenAI API 호출
   ↓
8. 대화 히스토리 업데이트
   → 새 대화 추가
   → 길이 관리 (최대 10개)
   ↓
9. 답변 반환
```

### 에러 처리

1. **번역 실패**: 원문 반환 (Fallback)
2. **임베딩 생성 실패**: 예외 발생 (시스템 중단)
3. **Vector DB 검색 실패**: 빈 리스트 반환
4. **답변 생성 실패**: 기본 오류 메시지 반환

## 성능 최적화

### 1. 임베딩 캐싱
- 현재는 매번 생성 (향후 캐싱 가능)
- 동일 입력에 대한 중복 생성 방지 가능

### 2. 컨텍스트 길이 관리
- 최근 2개 대화만 포함
- 토큰 수 제한으로 비용 절감
- max_tokens: 1000

### 3. 검색 결과 제한
- 상위 5개 검색
- 상위 3개만 답변에 사용
- 불필요한 정보 제거

### 4. 대화 히스토리 관리
- 최대 10개 저장
- 자동 정리로 메모리 효율성

## 비용 분석

### API 호출 횟수 (1회 대화당)

1. **번역**: 1회 (gpt-4o-mini)
   - Input: ~50 tokens
   - Output: ~50 tokens
   - 비용: ~$0.0001

2. **임베딩**: 1회 (text-embedding-3-large)
   - Input: ~50 tokens
   - 비용: ~$0.0001

3. **답변 생성**: 1회 (gpt-4o-mini)
   - Input: ~500 tokens (프롬프트 + 컨텍스트 + 히스토리)
   - Output: ~200 tokens
   - 비용: ~$0.0005

**총 비용**: 약 $0.0007 per 대화

## 확장 가능성

### 1. 장기 기억 시스템
- 데이터베이스 연동
- 사용자별 세션 관리
- 대화 히스토리 영구 저장

### 2. 추가 페르소나
- 다른 심리학 이론 적용
- 사용자 선택 가능한 페르소나
- 동적 페르소나 전환

### 3. 감정 분석 강화
- 감정 점수 추적
- 감정 변화 모니터링
- 맞춤형 상담 전략

### 4. 멀티모달 지원
- 이미지 입력
- 음성 입출력
- 비디오 분석

## 참고 자료

- **RAG**: Retrieval-Augmented Generation
- **ChromaDB**: 벡터 데이터베이스
- **OpenAI API**: GPT 및 임베딩 모델
- **아들러 개인심리학**: Alfred Adler의 심리학 이론

