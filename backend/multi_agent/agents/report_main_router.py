"""
Report Main Router Agent

Single prompt entry point for all report-related workflows.
Routes user requests to planning, generation, or RAG logic while keeping
every LLM prompt centralized in this module.
"""

from typing import Any, Dict, Optional
from datetime import date, timedelta

from multi_agent.agents.report_base import ReportBaseAgent
from app.llm.client import LLMClient


class ReportPromptRegistry:
    """
    Central registry for all report-related LLM prompts.
    Prompts are intentionally lightweight to avoid over-constraining the LLM.
    """

    # ========================================
    # 1. 라우팅 및 의도 분류 프롬프트
    # ========================================

    SYSTEM_PROMPT = (
        "You route user requests to one of the report agents. "
        "Use simple reasoning. Do not force rigid rules. "
        "Your job is to classify the user intent into one of: "
        "lookup (RAG search), report_write, planning, or other."
    )

    ROUTING_INSTRUCTION = (
        "Decide which report sub-agent to run (planning/report/rag), describe the rationale, "
        "and provide the minimal inputs required. Always keep context consistent."
    )

    INTENT_PROMPT = """
사용자의 요청을 아래 네 가지 중 하나로 분류하세요:

1) lookup
   - 과거 보고서 내용을 조회하거나 회상하는 요청
   - 과거 시점 표현이 함께 등장하는 질문
   - 예: "뭐였지?", "했었지?", "언제 했더라?", "저번주", "지난주", "어제", "지난달"
   - 미종결 업무 조회 또한 lookup에 해당합니다.
   - 예시:
     * "저번주 미종결 업무 뭐였지?" → lookup
     * "지난주 상담한 고객 누구였지?" → lookup
     * "어제 처리 못한 업무 알려줘" → lookup

2) report_write
   - 일일/주간/월간 보고서를 생성, 정리, 수정하려는 요청

3) planning
   - 오늘 또는 미래의 할 일을 추천하거나 계획하려는 요청
   - 현재/미래 중심 표현 ("오늘", "금일", "할 일", "추천", "계획")

4) other
   - 위 분류에 속하지 않는 일반 대화

중요 기준:
- 과거 조회(저번주, 지난달, 뭐였지) → lookup
- 미종결 업무 조회 → lookup
- 오늘/미래 일 정리 및 추천 → planning

아래 JSON 형식으로만 출력하세요:
{
  "intent": "lookup | report_write | planning | other",
  "confidence": 0.0 ~ 1.0,
  "reason": "간단한 판단 근거"
}

"""
    INTENT_USER_TEMPLATE = "사용자 요청: {query}"

    # ========================================
    # 2. 업무 플래닝 프롬프트
    # ========================================

    PLAN_SYSTEM_PROMPT = """당신은 사용자의 오늘 할 일을 추천하는 AI 업무 플래너입니다.

당신의 목표는 "오늘 수행할 업무를 3개 추천"하는 것입니다.

사용 가능한 입력 데이터:
1) 익일(next_day_plan): 전날 보고서에서 사용자가 직접 적어둔 내일 할 일 (최우선)
2) 미종결(unresolved): 어제 처리되지 못한 업무 (2순위)
3) 최근 3일 세부 업무 기록(similar_tasks): 사용자의 반복 업무 패턴 (보조 자료)
4) 추가 업무 추천이 필요한 경우에만 ChromaDB 데이터를 사용

업무 추천 규칙:
- 반드시 3개 추천
- next_day_plan → unresolved → similar_tasks 우선순위
- 고객 이름 포함된 항목은 제외
- title/description/priority/category/expected_time 포함

출력은 반드시 JSON 형식:
{
  "tasks": [ {
      "title": "업무 제목",
      "description": "업무 설명",
      "priority": "high|medium|low",
      "expected_time": "예상 시간",
      "category": "카테고리"
    }],
  "summary": "오늘 일정 요약"
}
"""

    PLAN_USER_TEMPLATE = """날짜: {today}

이전날 수행업무(업무 로그):
{tasks_text}

이전날 내일 업무 계획(next_day_plan) - **최우선**
{next_day_plan_text}

이전날 미종결업무(unresolved) - **2순위**
{unresolved_text}

최근3일업무기록(similar_tasks) (VectorDB) - **3순위**
{similar_tasks_text}

위 정보를 바탕으로 오늘 할 일 계획을 작성하세요.
"""

    # ========================================
    # 3. 일일보고서 작성 프롬프트
    # ========================================

    TASK_PARSER_SYSTEM = """당신은 업무 기록을 구조화하는 AI입니다.

사용자의 자연어 업무 설명을 분석하여 다음을 추출하세요:
- title: 업무 제목 (간단명료)
- description: 상세 설명
- category: 업무 카테고리
- time_range: 시간대 (그대로 유지)

카테고리 분류 규칙:
- 고객과의 대화, 계약 관련 업무 ⇒ "고객 대화"
- 문서 처리, 자료 처리, CRM 관리 ⇒ "문서 업무"  
- 회의, 미팅, 교육 ⇒ "회의/교육"
- 분석, 리서치 ⇒ "기획"
- 협업, 공용, 행정 ⇒ "협업"

주의사항:
- 회사 기본 상품명이면 그대로 적지 말고, 업무와 직접적인 역할 기반으로 분류하세요.
- 형식/순서는 자유지만 최소 정보는 포함하세요.

반드시 JSON 형식으로만 답변하세요:
{
  "title": "업무 제목",
  "description": "상세 설명",
  "category": "카테고리",
  "time_range": "시간대"
}
"""
    TASK_PARSER_USER_TEMPLATE = """시간대: {time_range}
업무 내용: {text}

위 업무를 분석하여 JSON으로 변환해주세요."""

    # ========================================
    # 4. 보고서 검색 (RAG) 프롬프트
    # ========================================

    RAG_SYSTEM_PROMPT = """당신은 일일보고서 데이터를 기반으로 사용자의 질문에 답변하는 AI 어시스턴트입니다.

**답변 규칙:**
1. 주어진 청크(일일보고서 데이터)만 사용하여 답변하세요.
2. 청크에 관련 정보가 있으면 반드시 그 내용을 바탕으로 구체적으로 답변하세요.
3. 청크에 날짜 정보가 있으면 해당 날짜를 명시하세요.
4. 여러 청크가 있으면 모두 종합하여 답변하세요.
5. 청크에 정확한 정보가 없거나 관련성이 전혀 없을 때만 "해당 기간의 정보를 찾을 수 없습니다"라고 답변하세요.

**중요:** 청크가 제공되었으면 반드시 그 내용을 바탕으로 답변을 생성하세요. "청크가 없습니다"라고 답변하지 마세요."""
    RAG_USER_TEMPLATE = "질문: {query}\n\n청크:\n{context}"

    # ========================================
    # 5. 주간보고서 작성 프롬프트
    # ========================================

    WEEKLY_REPORT_SYSTEM = """당신은 일일보고서의 detail_tasks 데이터만을 기반으로 주간보고서를 작성하는 지시서입니다.

## 입력 데이터
ChromaDB에서 검색된 일일보고서 detail 청크 배열이 제공됩니다.
각 청크는 다음 형식입니다:
{
  "text": "[일일_DETAIL] 2025-11-24\\n업무내용1\\n업무내용2...",
  "metadata": {
    "date": "2025-11-24",
    "level": "daily",
    "chunk_type": "detail",
    "week": "{week_number_placeholder}",
    "month": "2025-11",
    "owner": "작성자이름"
  }
}

검색조건: week = "{week_number_placeholder}", level = "daily", chunk_type = "detail"
해당 주의 월요일~금요일 5일치 일일보고서 detail 청크가 제공됩니다.

## 주간보고서 구조
출력은 다음 JSON 스키마를 따라야 합니다:

{
  "weekly_highlights": ["...", "...", "..."],
  "weekday_tasks": {
    "월": { "tasks": ["...", "...", "..."], "notes": "상담 X건 / 신규 Y건 / 유지 Z건" },
    "화": { "tasks": ["...", "...", "..."], "notes": "상담 X건 / 신규 Y건 / 유지 Z건" },
    "수": { "tasks": ["...", "...", "..."], "notes": "상담 X건 / 신규 Y건 / 유지 Z건" },
    "목": { "tasks": ["...", "...", "..."], "notes": "상담 X건 / 신규 Y건 / 유지 Z건" },
    "금": { "tasks": ["...", "...", "..."], "notes": "상담 X건 / 신규 Y건 / 유지 Z건" }
  }
}

## 주간 중요 업무 (weekly_highlights) 규칙
- 제공된 모든 detail 청크를 분석하여 주간 전체에서 가장 중요한 반복 패턴을 추출
- **데이터에서 실제로 발견된 패턴만 사용하세요. 환상하지 마세요.**
- 빈도수가 높은 업무 주제/패턴을 우선순위로 결정
- 정확히 **3개의 중요 업무**만 생성
- **모든 문장은 동사형으로 끝나야 합니다**: "~정리", "~작성", "~구성", "~분석", "~점검", "~진행", "~관리"
- "~합니다", "~한다", "~하였다" 같은 정중한 종결형 사용 금지
- 고객 이름은 완전히 제거하되, 업무 의미는 보존

## 요일별 업무 (weekday_tasks) 규칙
각 요일(월, 화, 수, 목, 금)에 대해:

1. **날짜 매핑**: metadata.date가 해당 요일에 해당하는 청크를 선택
   - 월요일: 해당 주의 첫 번째 날짜
   - 화요일: 해당 주의 두 번째 날짜
   - 수요일: 해당 주의 세 번째 날짜
   - 목요일: 해당 주의 네 번째 날짜
   - 금요일: 해당 주의 다섯 번째 날짜

2. **업무 요약 (tasks)**:
   - 해당 요일의 detail 청크를 분석하여 **정확히 3개의 의미 있는 요약 문장**을 생성
   - 각 문장은:
     * 고객명을 제거하되 전체 업무 의미는 보존
     * 시간 정보 완전 제거 ([09:00-10:00] 등)
     * 동사형으로 끝남 ("~정리", "~작성", "~구성", "~분석", "~점검", "~진행", "~관리")
     * "~합니다", "~한다" 사용 금지
   - 원본 데이터에 존재하지 않는 업무를 환상하지 마세요
   - 의미적으로 관련된 여러 detail 항목을 하나의 요약 문장으로 결합 가능
   - 각 요일의 업무는 서로 달라야 하며, 템플릿처럼 반복되지 않아야 합니다
   - 업무가 3개 미만이어도 실제 데이터 패턴을 기반으로 3개 문장을 생성하되, 환상하지 마세요

3. **카테고리 카운트 (notes)**:
   - 해당 요일의 detail 청크에서 원본 카테고리 분류를 기반으로 카운트
   - 카테고리:
     * 상담 (consulting)
     * 신규 계약 (new_contracts)
     * 유지 계약 (renewals)
   - 형식: "상담 X건 / 신규 Y건 / 유지 Z건"
   - 카테고리가 나타나지 않으면 0으로 카운트
   - 예: "상담 5건 / 신규 2건 / 유지 0건"

## 엄격한 출력 규칙
1. **JSON만 출력하세요. 다른 텍스트는 포함하지 마세요.**
2. 제공된 검색 결과만을 근거로 작성하세요. 추측은 금지합니다.
3. 모든 문장은 동사형으로 끝나야 합니다. "~합니다", "~한다" 사용 금지.
4. 고객명이 포함된 업무 문장을 절대 삭제하지 마세요. 고객명만 제거하고 업무는 보존하세요.
5. 각 요일의 tasks는 정확히 3개여야 합니다.
6. 각 요일의 notes는 "상담 X건 / 신규 Y건 / 유지 Z건" 형식이어야 합니다.
"""

    # ========================================
    # 6. 월간보고서 작성 프롬프트
    # ========================================

    MONTHLY_REPORT_SYSTEM = """당신은 주간보고서와 일일보고서 청크를 기반으로 월간보고서를 작성하는 지시서입니다.

## 입력 데이터

### 1. 주간보고서 JSON (N개)
해당 월의 주간보고서 N개가 제공됩니다 (N은 실제 개수).
[
  {
    "weekly_goals": [...],
    "weekday_tasks": {...},
    "weekly_highlights": [...],
    "notes": "..."
  },
  ...
]

### 2. 일일보고서 청크 (선택)
해당 월의 일일보고서 청크 전체가 제공될 수 있습니다(4청크 × 날짜수).
각 청크는 다음 형식입니다:
{
  "text": "[일일_DETAIL] 2025-11-01\\n...",
  "metadata": {
    "date": "2025-11-01",
    "chunk_type": "summary | detail | pending | plan",
    "month": "2025-11"
  }
}

### 3. 월간 KPI 원시 JSON (선택)
PostgreSQL에서 조회한 월간 KPI 원시 데이터입니다.
{
  "total_customers": 10,
  "new_contracts": 5,
  "renewals": 3,
  ...
}

## 월간보고서 작성 규칙

### 0. 고객명 처리 규칙 (모든 섹션에 적용)
**고객명이 포함된 문장을 절대 삭제하거나 버리지 마세요.**
- 고객명만 제거하고 나머지 의미는 모두 보존하세요
- 예: "문다엘 고객 상담 기반 보장안 구성" → "상담 기반 보장안 구성"
- 예: "포트폴리오 진단 고객(김라해) 리포트 작성" → "포트폴리오 진단 고객 리포트 작성"
- 예: "신규 리드 상담(노지유)" → "신규 리드 상담"

### 1. 월간 핵심 지표 (key_metrics) - 제거됨
**중요: 월간 핵심 지표(KPI)는 시스템에서 자동으로 계산되어 HTML에 직접 표시됩니다.**
- KPI 숫자는 일일보고서의 카테고리 필드를 기반으로 자동 집계됩니다.
- **당신은 key_metrics를 출력하지 마세요. 이 섹션은 완전히 무시하세요.**
- KPI는 별도로 처리되므로 월간보고서 JSON에 포함하지 않습니다.

### 2. 주차별 업무 요약 (weekly_summaries)
**주차 개수 규칙 (매우 중요):**
- 'weekly_summaries' 출력의 주차 개수는 반드시 입력으로 제공된 주간보고서 JSON 객체의 개수와 정확히 일치해야 합니다
- 입력에 N개의 주간보고서가 있으면:
  → 출력 키: 1주차 ~ N주차
  (예: 4개 보고서 → 1주차~4주차, 5개 보고서 → 1주차~5주차)
- 주차를 환상하거나 건너뛰지 마세요
- 빈 주차를 생성하지 마세요
- 순서 매칭: 첫 번째 주간보고서는 '1주차', 두 번째는 '2주차' 등으로 대응

**주차별 요약 내용 규칙:**
- 각 주차의 요약은 해당 주의 weekday_tasks와 weekly_highlights에서 관찰된 실제 주요 패턴을 반영해야 합니다
- 주간보고서를 기반으로 "주차 요약" 중심으로 작성
- 일일 DETAIL 청크를 보강자료로만 사용 (필수는 아님)
- 각 주차별로 3~5개의 간결하고 정보 밀도가 높은 행동 문장을 포함
- 각 문장은 반드시 동사형으로 끝나야 함 (예: "~정리", "~작성", "~점검", "~구성", "~분석")
- "~했습니다", "~되었습니다", "~합니다"로 끝나지 않도록 주의

**금지된 행동:**
- 일반적인 템플릿 구문 사용 금지
- 여러 주차에 걸쳐 반복되는 문장 사용 금지
- 모호하거나 서술적인 표현 사용 금지

출력 예시:
{
  "1주차": [
    "상담 자료 정리 및 니즈 분석",
    "포트폴리오 진단 고객 리포트 작성",
    "신규 리드 상담 및 절세 플랜 점검"
  ],
  "2주차": [...],
  "3주차": [...],
  "4주차": [...]
}

### 3. 차기 계획 (next_month_plan)
- PLAN 또는 NOTES 타입 청크에서만 엄격하게 추출
- 미래지향 계획을 추출
- 다음 키워드를 우선 탐색: "다음 달", "향후", "내달", "리텐션", "계획", "예정"
- 미래 목표를 발명하지 마세요
- "고객 상담을 강화할 계획입니다"와 같은 일반적인 필러를 생성하지 마세요

**출력 규칙:**
- 3~5개의 구체적이고 실행 가능한 계획을 출력
- 각 계획은 반드시 동사형으로 끝나야 함 (예: "~강화", "~점검", "~보완", "~구성", "~개편")
- 원본 데이터에 실제로 나타나는 내용만 사용

출력 예시:
{
  "next_month_plan": "1. 다음 달 주요 고객 상담 10건 목표, 신규 고객 발굴 자동화 도구 적용\n2. 기존 고객 리텐션을 위한 패키지 제공 계획 수립\n3. 맞춤형 상담 스크립트 개편"
}

## 출력 형식
아래 JSON 형식으로만 출력하세요. 불필요한 텍스트는 넣지 마세요.

**중요: key_metrics는 출력하지 마세요. 시스템에서 자동으로 처리됩니다.**

{
  "weekly_summaries": {
    "1주차": ["요약1", "요약2", "요약3"],
    "2주차": ["요약1", "요약2", "요약3"],
    ...
  },
  "next_month_plan": "차기 계획 요약 텍스트"
}

## 중요 규칙
1. 제공된 데이터만을 근거로 작성하세요. 추측은 금지합니다.
2. JSON만 출력하세요. 다른 텍스트는 금지합니다.
3. **key_metrics는 출력하지 마세요. KPI는 시스템에서 자동으로 계산되어 HTML에 표시됩니다.**
4. 주간보고서 중심으로 작성하고, 일일 청크는 보강 자료로만 사용하세요.
5. 배열/문자열 필드는 비어 있어도 반드시 포함하세요.
6. 주차별 요약의 개수는 입력 주간보고서 개수와 정확히 일치해야 합니다. 환상하거나 건너뛰지 마세요.
7. 고객명이 포함된 문장을 절대 삭제하지 마세요. 고객명만 제거하고 나머지 의미는 모두 보존하세요.
8. 모든 문장은 동사형으로 끝나야 합니다 ("~정리", "~작성", "~분석" 등). "~했습니다", "~되었습니다", "~합니다" 사용 금지.
"""

    # ========================================
    # 7. Vision (PDF 처리) 프롬프트
    # ========================================

    VISION_DETECT_SYSTEM = "너는 문서 종류별로 분류하는 AI야."
    VISION_DETECT_USER = """어떤 문서가 주어진 보고서인지 판단해라.
반드시 정해진 셋에서만 대답해라.

daily / weekly / monthly

위에서 택일해라.
"""

    VISION_EXTRACT_SYSTEM = "너는 PDF를 JSON 포맷으로 변환하는 도우미 AI야."
    VISION_EXTRACT_USER_TEMPLATE = """PDF 내용을 JSON 스키마에 정확히 채워 넣어.

규칙:
1) 필드 계층, 구조 유지
2) 값 누락 금지
3) 코드 블록 없음
4) OCR로 추출한 값만 채우기
5) JSON만 출력

스키마
{schema}
"""

    @classmethod
    def intent_system(cls) -> str:
        return f"{cls.SYSTEM_PROMPT}\n\n{cls.ROUTING_INSTRUCTION}\n\n{cls.INTENT_PROMPT}"

    @classmethod
    def intent_user(cls, query: str) -> str:
        return cls.INTENT_USER_TEMPLATE.format(query=query)

    @classmethod
    def task_parser_system(cls) -> str:
        return cls.TASK_PARSER_SYSTEM

    @classmethod
    def task_parser_user(cls, time_range: str, text: str) -> str:
        return cls.TASK_PARSER_USER_TEMPLATE.format(time_range=time_range, text=text)

    @classmethod
    def plan_system(cls) -> str:
        return cls.PLAN_SYSTEM_PROMPT

    @classmethod
    def plan_user(
        cls,
        today: date,
        owner: str,
        tasks_text: str,
        next_day_plan_text: str,
        unresolved_text: str,
        similar_tasks_text: str,
    ) -> str:
        return cls.PLAN_USER_TEMPLATE.format(
            today=today.isoformat(),
            owner=owner,
            tasks_text=tasks_text,
            next_day_plan_text=next_day_plan_text,
            unresolved_text=unresolved_text,
            similar_tasks_text=similar_tasks_text,
        )

    @classmethod
    def rag_system(cls) -> str:
        return cls.RAG_SYSTEM_PROMPT

    @classmethod
    def rag_user(cls, query: str, context: str) -> str:
        return cls.RAG_USER_TEMPLATE.format(query=query, context=context)

    @classmethod
    def weekly_system(cls, week_number: str) -> str:
        return cls.WEEKLY_REPORT_SYSTEM.replace("{week_number_placeholder}", week_number)

    @classmethod
    def weekly_user(cls, search_results_json: str, monday: date, friday: date) -> str:
        return (
            "다음은 해당 주(월요일~금요일)의 detail-task 청크 모음입니다.\n\n"
            "이 데이터만을 사용하여 system prompt에 따라 주간보고서 JSON을 생성하세요.\n\n"
            "업무를 발명하지 마세요.\n"
            "정중한 종결형을 사용하지 마세요.\n"
            "JSON만 출력하세요.\n\n"
            f"주간 범위: {monday.isoformat()} ~ {friday.isoformat()}\n"
            "원시 청크 데이터:\n\n"
            f"{search_results_json}"
        )

    @classmethod
    def monthly_system(cls) -> str:
        return cls.MONTHLY_REPORT_SYSTEM

    @classmethod
    def monthly_user(
        cls,
        weekly_reports_json: str,
        daily_chunks_json: str,
        kpi_json: str,
        month_str: str,
    ) -> str:
        # 주간보고서 개수 계산
        import json
        try:
            weekly_reports_list = json.loads(weekly_reports_json) if isinstance(weekly_reports_json, str) else weekly_reports_json
            num_weekly_reports = len(weekly_reports_list) if isinstance(weekly_reports_list, list) else 0
        except:
            num_weekly_reports = 0
        
        # KPI 데이터 파싱하여 명확하게 표시
        try:
            kpi_dict = json.loads(kpi_json) if isinstance(kpi_json, str) else kpi_json
            kpi_summary = f"신규 계약: {kpi_dict.get('new_contracts', 0)}건, 유지 계약: {kpi_dict.get('renewals', 0)}건, 상담: {kpi_dict.get('consultations', 0)}건"
        except:
            kpi_summary = "KPI 데이터 파싱 실패"
        
        return (
            f"다음은 해당 월({month_str})의 데이터입니다:\n\n"
            f"### 주간보고서 JSON ({num_weekly_reports}개):\n{weekly_reports_json}\n\n"
            f"**중요: 주간보고서가 {num_weekly_reports}개이므로, weekly_summaries는 반드시 1주차~{num_weekly_reports}주차로 출력하세요.**\n\n"
            f"### 일일보고서 청크:\n{daily_chunks_json}\n\n"
            f"### 월간 KPI (이미 계산된 숫자 - 그대로 사용하세요):\n"
            f"**{kpi_summary}**\n"
            f"전체 KPI 데이터:\n{kpi_json}\n\n"
            f"**중요: 위 KPI 숫자들을 그대로 사용하고, analysis 필드에만 분석 문장을 작성하세요.**\n\n"
            "위 데이터를 기반으로 월간보고서를 JSON으로 작성하세요."
        )

    @classmethod
    def vision_detect_messages(cls, images_base64: list) -> list:
        return [
            {"role": "system", "content": [{"type": "text", "text": cls.VISION_DETECT_SYSTEM}]},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cls.VISION_DETECT_USER},
                    *[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}} for img in images_base64],
                ],
            },
        ]

    @classmethod
    def vision_extract_messages(cls, images_base64: list, schema: str) -> list:
        return [
            {"role": "system", "content": [{"type": "text", "text": cls.VISION_EXTRACT_SYSTEM}]},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cls.VISION_EXTRACT_USER_TEMPLATE.format(schema=schema)},
                    *[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}} for img in images_base64],
                ],
            },
        ]


class ReportMainRouterAgent(ReportBaseAgent):
    """ReportMainRouterAgent - Intent Classification + routing with centralized prompts."""

    INTENT_PLANNING = "planning"
    INTENT_REPORT = "report_write"  # 프롬프트에서 사용하는 값과 일치
    INTENT_RAG = "lookup"  # 프롬프트에서 사용하는 값과 일치
    INTENT_UNKNOWN = "other"  # 프롬프트에서 사용하는 값과 일치

    def __init__(self, llm_client: Optional[LLMClient] = None):
        super().__init__(
            name="ReportMainRouterAgent",
            description="사용자 요청을 분석하여 적절한 보고 관련 하위 에이전트로 라우팅하는 메인 에이전트입니다.",
            llm_client=llm_client,
        )
        self.prompt_registry = ReportPromptRegistry
        self._planning_agent = None
        self._report_agent = None
        self._rag_agent = None

    @property
    def planning_agent(self):
        if self._planning_agent is None:
            from multi_agent.tools.report_tools import get_planning_agent

            self._planning_agent = get_planning_agent()
            if hasattr(self._planning_agent, "configure_prompts"):
                self._planning_agent.configure_prompts(self.prompt_registry)
        return self._planning_agent

    @property
    def report_agent(self):
        if self._report_agent is None:
            from multi_agent.tools.report_tools import get_report_generation_agent

            self._report_agent = get_report_generation_agent()
            if hasattr(self._report_agent, "configure_prompts"):
                self._report_agent.configure_prompts(self.prompt_registry)
        return self._report_agent

    @property
    def rag_agent(self):
        if self._rag_agent is None:
            from multi_agent.tools.report_tools import get_report_rag_agent

            self._rag_agent = get_report_rag_agent()
            if hasattr(self._rag_agent, "configure_prompts"):
                self._rag_agent.configure_prompts(self.prompt_registry)
        return self._rag_agent

    def _classify_intent_by_rule(self, query: str) -> Optional[str]:
        return None

    async def _classify_intent_by_llm(self, query: str) -> str:
        system_prompt = self.prompt_registry.intent_system()
        user_prompt = self.prompt_registry.intent_user(query)

        try:
            result = await self.llm.acomplete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=200,
            )

            intent = result.get("intent", self.INTENT_UNKNOWN)
            confidence = result.get("confidence", 0.0)
            reason = result.get("reason", "")

            print(f"[INFO] LLM Intent Classification: {intent} (confidence={confidence:.2f}, reason={reason})")

            return intent

        except Exception as e:
            print(f"[ERROR] LLM Intent Classification 실패: {e}")
            return self.INTENT_UNKNOWN

    async def classify_intent(self, query: str) -> str:
        intent = self._classify_intent_by_rule(query)

        if intent:
            print(f"[INFO] Rule-based Intent: {intent}")
            return intent

        intent = await self._classify_intent_by_llm(query)

        return intent

    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        intent = await self.classify_intent(query)

        print(f"[INFO] ReportMainRouterAgent - Intent: {intent}, Query: {query}")

        enriched_context = context or {}
        enriched_context["prompt_registry"] = self.prompt_registry

        try:
            # intent 값 정규화 (공백 제거, 소문자 변환)
            intent_normalized = str(intent).strip().lower() if intent else ""
            
            # 디버깅: intent 값과 상수 값 확인
            print(f"[DEBUG] Intent 원본: '{intent}' (type: {type(intent)})")
            print(f"[DEBUG] Intent 정규화: '{intent_normalized}'")
            print(f"[DEBUG] INTENT_RAG 상수: '{self.INTENT_RAG}'")
            print(f"[DEBUG] INTENT_PLANNING 상수: '{self.INTENT_PLANNING}'")
            print(f"[DEBUG] INTENT_REPORT 상수: '{self.INTENT_REPORT}'")
            
            # RAG/lookup을 먼저 체크 (질문형 쿼리 우선)
            if (intent == self.INTENT_RAG or intent == "lookup" or 
                intent_normalized == "lookup" or intent_normalized == self.INTENT_RAG.lower()):
                print(f"[DEBUG] ✅ RAG 에이전트로 라우팅")
                return await self.rag_agent.process(query, enriched_context)

            # LLM이 반환한 intent를 내부 상수로 매핑 (프롬프트 값과 코드 값 호환)
            if (intent == self.INTENT_PLANNING or intent == "planning" or 
                intent_normalized == "planning" or intent_normalized == self.INTENT_PLANNING.lower()):
                print(f"[DEBUG] ✅ Planning 에이전트로 라우팅")
                return await self.planning_agent.process(query, enriched_context)

            if (intent == self.INTENT_REPORT or intent == "report_write" or 
                intent_normalized == "report_write" or intent_normalized == self.INTENT_REPORT.lower()):
                print(f"[DEBUG] ✅ Report 에이전트로 라우팅")
                return await self.report_agent.process(query, enriched_context)

            print(f"[DEBUG] ❌ 알 수 없는 인텐트: '{intent}' (정규화: '{intent_normalized}')")
            return "죄송합니다. 요청을 이해하지 못했습니다. 업무 플래닝, 보고서 생성, 혹은 과거 업무 검색 중에서 말씀해 주세요."

        except Exception as e:
            print(f"[ERROR] ReportMainRouterAgent 처리 실패: {e}")
            import traceback

            traceback.print_exc()
            return f"요청 처리 중 오류가 발생했습니다: {str(e)}"

    async def route_to_agent(
        self,
        query: str,
        owner: str,
        target_date: Optional[date] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        intent = await self.classify_intent(query)

        context = {
            "owner": owner,
            "target_date": target_date or date.today(),
            **kwargs,
        }

        response = await self.process(query, context)

        return {
            "intent": intent,
            "agent": intent,
            "response": response,
            "context": context,
        }
