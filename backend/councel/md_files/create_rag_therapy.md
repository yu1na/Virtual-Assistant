<!-- 생성일 2025.11.21 12:08 -->
<!-- 완료일 2025.11.21 -->

# Task
- ``rag_therapy.py`` 파일을 참고하여 사용자의 Input에 따라 **답변을 생성**하거나 **상담**해주는 Python 스크립트를 생성한다.

# Input
- Vector DB 경로: ``backend/councel/vector_db``
- Input: 사용자의 입력값
- Output: 답변 또는 상담 결과
- 모델: OpenAI gpt-4o-mini(api키는 프로젝트 루트에 위치한 .env 파일에 저장되어있음)

# Rules
- 사용자의 입력값이 아들러(영어 한글 상관 X)가 포함되어있을 경우 Vecotr DB에서 검색을 진행 후 답변 생성
- 사용자의 입력값이 "나 힘들어", "상담 좀 해줘", "짜증나" 이런식의 감정과 관련이 있거나 상담이 포함되어있을 경우 상담을 진행
- 사용자의 입력값은 다른 언어라 할지라도 영어로 번역 후 Vector DB에 전달, 생성된 답변은 한글로 전달한다.
- 일단은 단기기억으로 구현, 나중에 장기기억으로 수정할 예정

# Output Format
- py파일 저장은 ``backend/councel/sourcecode/persona/rag_therapy.py`` 파일을 수정 후 저장한다.

---

## ✅ 구현 완료 (2025.11.21)

### 주요 변경사항

#### 1. OpenAI API 통합
- ✅ BGE-M3 모델 제거
- ✅ OpenAI `text-embedding-3-small`로 임베딩 생성
- ✅ OpenAI `gpt-4o-mini`로 답변 생성
- ✅ 환경변수 `OPENAI_API_KEY` 로드

#### 2. 입력 분류 시스템
- ✅ `classify_input()` 함수 구현
  - "아들러"/"adler" → adler 모드
  - 감정/상담 키워드 → counseling 모드
  - 기타 → general 모드

#### 3. 번역 기능
- ✅ `translate_to_english()` 함수 구현
- ✅ 모든 입력을 영어로 번역 후 Vector DB 검색
- ✅ 답변은 한국어로 생성

#### 4. RAG 기반 상담 시스템
- ✅ Vector DB에서 관련 자료 검색
- ✅ 검색 결과를 아들러 페르소나로 재구성

#### 5. 새로운 함수들
- `translate_to_english()`: 영어 번역
- `classify_input()`: 입력 분류
- `generate_response_with_persona()`: 페르소나 기반 답변 생성

### 테스트 방법
```bash
cd backend/councel/sourcecode/persona
python rag_therapy.py
```

### 사용 가이드
자세한 사용 방법은 `usage_example.md` 참고

---

## ✅ 페르소나 통합 완료 (2025.11.21)

### 추가 변경사항

#### 1. 임베딩 모델 업그레이드
- ✅ `text-embedding-3-small` → `text-embedding-3-large`
- ✅ 더 높은 정확도의 임베딩 생성

#### 2. 아들러 페르소나 시스템
- ✅ **아들러 페르소나**: 개인심리학 관점, 격려와 용기
- ✅ 모든 모드에서 아들러 페르소나 적용

#### 4. 대화 히스토리 관리
- ✅ 최근 10개 대화 저장 (단기 기억)
- ✅ 최근 2개 대화를 컨텍스트에 포함
- ✅ 자연스러운 대화 흐름 유지

#### 5. 페르소나 기반 답변 생성
- ✅ `generate_response_with_persona()` 함수
- ✅ 모드별 페르소나 프롬프트 적용
- ✅ RAG + 페르소나 통합

#### 6. 개선된 콘솔 인터페이스
- ✅ 페르소나 표시 (🎭 아들러)
- ✅ 처리 단계별 상태 표시
- ✅ 사용자 친화적 메시지

### 최종 파일
- `backend/councel/sourcecode/persona/rag_therapy.py`: 페르소나 통합 완료
- `backend/councel/md_files/persona_rag_guide.md`: 상세 사용 가이드