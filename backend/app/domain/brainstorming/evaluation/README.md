# 브레인스토밍 평가 모듈 (LLM as a Judge)

GPT-5를 Judge로 사용하여 브레인스토밍 결과를 자동 평가하는 모듈입니다.

## 📊 평가 기준 (5가지, 각 20%)

1. **RAG 활용도** (20%)
   - Permanent RAG 기법(SCAMPER 등) 적용 여부
   - Ephemeral RAG 키워드 통합 여부

2. **답변 완성도** (20%)
   - 아이디어 개수 충족
   - SWOT 분석 완전성

3. **질문-답변 연관도** (20%)
   - 질문 의도 정확한 파악
   - 환각 없는 정확성

4. **창의성** (20%)
   - 독창성, 차별화
   - 새로운 접근

5. **실용성** (20%)
   - 현실적 실행 가능성
   - 구체적인 방법 제시

## 🚀 사용법

### 전체 테스트 케이스 실행

```bash
cd /Users/jinmokim/dev/Virtual-Assistant
python -m backend.app.domain.brainstorming.evaluation.runner
```

### 특정 테스트 케이스만 실행

```bash
python -m backend.app.domain.brainstorming.evaluation.runner --case-id tc001
```

## 📁 파일 구조

```
evaluation/
├── __init__.py           # 모듈 초기화
├── models.py             # Pydantic 데이터 모델
├── criteria.py           # 평가 기준 & 가중치
├── prompts.py            # Judge 프롬프트
├── judge.py              # Judge 클래스 (GPT-5)
├── test_cases.py         # 테스트 케이스 정의
├── runner.py             # 자동 실행 스크립트
├── results/              # 평가 결과 JSON 저장
└── README.md             # 이 파일
```

## 📝 테스트 케이스 추가 방법

`test_cases.py`에 새로운 케이스 추가:

```python
TEST_CASE_002 = {
    "id": "tc002",
    "name": "스타트업 마케팅 전략",
    "category": "마케팅",
    "q1_purpose": "소규모 스타트업의 저비용 마케팅 전략",
    "q3_associations": ["스타트업", "마케팅", "저비용", ...],
    "expected": {
        "ideas_count_min": 2,
        "has_swot": True,
    }
}

# ALL_TEST_CASES에 추가
ALL_TEST_CASES = [
    TEST_CASE_001,
    TEST_CASE_002,  # ← 추가
]
```

## 📊 결과 파일

### 개별 테스트 결과
```
results/20251127_143022_tc001_result.json
```

### 전체 요약
```
results/summary_20251127_143500.json
```

## 🔧 설정

### Judge 모델 변경
`judge.py`:
```python
judge = BrainstormingJudge(
    model="gpt-5",      # 변경 가능
    temperature=0.0     # 일관성 위해 0 권장
)
```

### 가중치 변경
`criteria.py`:
```python
WEIGHTS = {
    "rag_utilization": 0.20,
    "completeness": 0.20,
    "relevance": 0.20,
    "creativity": 0.20,
    "practicality": 0.20,
}
```

## ⚠️ 주의사항

1. **실행 전 확인**:
   - OpenAI API Key 설정 (`.env`)
   - 백엔드 서버는 **실행하지 않아도 됨** (스크립트가 직접 실행)

2. **실행 시간**:
   - 1회 실행: 약 1-2분
   - 3회 반복: 약 3-6분
   - GPT-5 호출로 약간 느릴 수 있음

3. **비용**:
   - 1회 평가: 약 $0.01 (Judge GPT-5)
   - 3회 평가: 약 $0.03
   - 100회: 약 $1 (합리적)

## 📈 Before/After 비교 방법

1. **Before 평가 (현재 프롬프트)**:
   ```bash
   python -m backend.app.domain.brainstorming.evaluation.runner
   ```
   결과: `summary_before.json`

2. **프롬프트 개선**:
   - `backend/app/api/v1/endpoints/brainstorming.py` 수정
   - 창의성 향상 전략 적용

3. **After 평가 (개선된 프롬프트)**:
   ```bash
   python -m backend.app.domain.brainstorming.evaluation.runner
   ```
   결과: `summary_after.json`

4. **비교**:
   ```
   Before: 5.9/10
   After:  8.2/10
   개선: +2.3점
   ```

## 🎯 발표 자료 작성

결과 JSON을 읽어서:
- Before/After 점수 비교 차트
- 각 차원별 점수 레이더 차트
- 개선 효과 시각화

---

**문의**: 코드 관련 문의는 프로젝트 관리자에게 문의하세요.

