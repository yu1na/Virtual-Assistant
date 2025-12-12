"""
Judge 프롬프트 템플릿 (GPT-5용)
"""

from typing import Dict, List


def build_judge_prompt(
    question: str,
    answer: str,
    permanent_rag_docs: List[str],
    ephemeral_keywords: List[str]
) -> str:
    """
    Judge 평가 프롬프트 생성
    
    Args:
        question: 사용자 질문 (Q1 목적)
        answer: AI 답변 (생성된 아이디어)
        permanent_rag_docs: Permanent RAG 문서 리스트
        ephemeral_keywords: Ephemeral RAG 키워드 리스트
    
    Returns:
        str: Judge 프롬프트
    """
    
    # RAG 컨텍스트 포맷팅
    permanent_rag_text = "\n".join([f"- {doc[:200]}..." for doc in permanent_rag_docs]) if permanent_rag_docs else "(없음)"
    ephemeral_keywords_text = ", ".join(ephemeral_keywords) if ephemeral_keywords else "(없음)"
    
    prompt = f"""당신은 브레인스토밍 전문 평가자입니다.
아래 AI의 답변을 **객관적으로 평가**하세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 📋 사용자 질문:
{question}

### 🤖 AI 답변:
{answer}

### 📚 AI가 사용한 RAG 컨텍스트:

**Permanent RAG (브레인스토밍 기법):**
{permanent_rag_text}

**Ephemeral RAG (사용자 연상 키워드):**
{ephemeral_keywords_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 📊 평가 기준 (각 1-10점):

**1. RAG 활용도 (1-10)**
- RAG 컨텍스트를 답변에 명확히 반영했나?
- Permanent RAG 기법(SCAMPER, Mind Mapping 등)을 적용했나?
- Ephemeral RAG 키워드를 아이디어에 통합했나?

채점 기준:
- 10점: 기법 명시 + 키워드 자연스럽게 통합
- 7-9점: 암묵적 반영 (명시는 없음)
- 4-6점: 표면적으로만 반영
- 1-3점: RAG 거의 사용 안 함

---

**2. 답변 완성도 (1-10)**
- 요청한 아이디어 개수를 충족했나?
- SWOT 분석이 완전한가? (4개 항목 모두)
- 각 아이디어가 충분히 구체적인가?

채점 기준:
- 10점: 5개 아이디어 + 상세 SWOT + 실행 단계
- 7-9점: 3개 아이디어 + 완전한 SWOT
- 4-6점: 2-3개 아이디어 + 불완전한 SWOT
- 1-3점: 1-2개만 또는 SWOT 없음

---

**3. 질문-답변 연관도 (1-10)**
- 질문 의도를 정확히 파악했나?
- 질문의 맥락(목적, 제약 조건)을 반영했나?
- 환각(hallucination) 없이 정확한가?

채점 기준:
- 10점: 모든 요소 완벽 반영
- 7-9점: 핵심 의도 파악, 일부 세부 요소 누락
- 4-6점: 관련은 있으나 방향 빗나감
- 1-3점: 의도 잘못 이해, 엉뚱한 답변

---

**4. 창의성 (1-10)**
- 브레인스토밍 기법을 활용한 창의적 사고 과정이 보이는가?
- 다양한 관점에서 접근했는가? (조합, 변형, 확장, 역발상 등)
- 발상의 다양성과 풍부함이 느껴지는가?
- **참고**: 결과가 기존 시장에 있는 아이디어여도, 창의적 기법으로 도출했다면 높은 점수

채점 기준:
- 10점: 여러 기법 명확히 활용 + 다양한 방향성 탐색
- 7-9점: 창의적 사고 과정이 보임 (기법 암묵적 사용)
- 4-6점: 단순 나열, 기법 활용 미흡
- 1-3점: 창의적 사고 없이 단순 정리만

---

**5. 실용성 (1-10)**
- 현실적으로 실행 가능한가?
- 구체적인 실행 방법이 제시되었나?
- 비용/시간이 현실적인가?

채점 기준:
- 10점: 즉시 실행 가능, 낮은 진입 장벽
- 7-9점: 며칠~몇 주 내 가능
- 4-6점: 준비 기간/비용 필요
- 1-3점: 비현실적 또는 방법 불명확

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### ✅ 출력 형식 (JSON만 출력):

반드시 아래 JSON 형식으로만 출력하세요. 다른 설명이나 텍스트는 포함하지 마세요.

```json
{{
  "rag_utilization": 7,
  "completeness": 8,
  "relevance": 9,
  "creativity": 5,
  "practicality": 8,
  "reasoning": "RAG 기법이 답변에 명시되지 않았지만 암묵적으로 반영됨. 아이디어 3개가 완전한 SWOT과 함께 제공되어 완성도가 높음. 질문 의도를 정확히 파악했으나 창의성은 다소 부족함. 실행 방법이 구체적이어서 실용성은 우수함."
}}
```

**중요:**
- 점수는 반드시 1-10 사이의 정수
- reasoning은 2-3줄로 간결하게 작성
- JSON 형식을 정확히 지킬 것
"""
    
    return prompt


# System 프롬프트
JUDGE_SYSTEM_PROMPT = """당신은 엄격하고 공정한 브레인스토밍 평가 전문가입니다.

평가 원칙:
1. 객관적이고 일관된 기준 적용
2. 근거를 명확히 제시
3. 후한 점수보다 정확한 평가 우선
4. JSON 형식 엄수
"""

