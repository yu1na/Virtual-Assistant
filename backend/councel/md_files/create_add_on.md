<!-- 생성일 2025.12.01 11:55 -->

# Task
- 이 프로젝트는 Threshold 기반 Retrieval-Augmented Generation(RAG) + Self-learning RAG 시스템을 구현하는 것입니다.
- 사용자의 질문을 임베딩하고, 유사도 점수에 따라 다른 응답 전략을 적용합니다.

# Input
- 사용자 입력(question)
- Vector DB
- 임베딩 모델
- LLM 모델
- Threshold 값 (0.75)

# Rules
1. 임베딩 & 유사도 계산
- 사용자 입력(question)을 임베딩합니다.
- Vector DB에서 관련 문서를 검색하고 코사인 유사도를 계산합니다.

2. Threshold 분기 로직
- Case A: 유사도 ≥ 0.75
  - RAG를 사용하지 않고 LLM 단독으로 답변 생성합니다.

- Case B: 유사도 < 0.75
  - Vector DB에서 검색된 내용을 컨텍스트로 포함합니다.
  - 동시에 Self-learning RAG(자가학습)를 수행합니다:
  - 사용자 질문 + LLM의 답변을 하나의 문서로 생성하고 문서를 임베딩하여 Vector DB에 자동 저장
  - 이후 LLM에게 Vector DB의 내용 + 신규 자가학습 문서를 기반으로 답변을 생성하게 합니다.

3. Self-learning RAG 상세 규칙
- 문서 형태는 JSON 또는 Text로 정규화합니다.
- 저장할 데이터 포맷 예시:

```json
{
  "user_query": "...",
  "llm_response": "...",
  "timestamp": "...",
}

- 임베딩 생성 후 Vector DB에 저장합니다.
- 저장 시 duplicate 체크는 선택 사항입니다.

# Output Format
- 파일은 backend/councel/sourcecode/persona/rag_therapy.py 파일에 추가합니다.
