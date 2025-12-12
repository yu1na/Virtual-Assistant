"""
월간 보고서 생성 체인
새로운 4청크 구조 기반 RAG 프롬프트 사용
"""
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import uuid
import json
from calendar import monthrange

from app.core.config import settings

# 보고서 owner는 상수로 사용 (실제 사용자 이름과 분리)
REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER

from app.domain.report.core.canonical_models import CanonicalReport, CanonicalMonthly
from app.domain.report.weekly.repository import WeeklyReportRepository
from app.domain.report.daily.repository import DailyReportRepository
from app.infrastructure.vector_store_report import get_report_vector_store
from app.domain.report.search.retriever import UnifiedRetriever
from app.llm.client import LLMClient
from app.core.config import settings
from multi_agent.agents.report_main_router import ReportPromptRegistry


def get_month_range(target_date: date) -> tuple[date, date]:
    """
    target_date가 속한 달의 1일~말일 날짜 범위를 계산
    
    Args:
        target_date: 기준 날짜
        
    Returns:
        (first_day, last_day) 튜플
    """
    first_day = target_date.replace(day=1)
    last_day_num = monthrange(target_date.year, target_date.month)[1]
    last_day = target_date.replace(day=last_day_num)
    return (first_day, last_day)


def generate_monthly_report(
    db: Session,
    owner: str,  # 실제 사용자 이름 (display_name용, 더 이상 CanonicalReport.owner에 저장 안 함)
    target_date: date,
    kpi_data: Optional[Dict[str, Any]] = None,
    display_name: Optional[str] = None,  # HTML 보고서에 표시할 이름
    prompt_registry: Optional[ReportPromptRegistry] = None,
) -> CanonicalReport:
    """
    월간 보고서 자동 생성 (새로운 4청크 구조 기반)
    
    Args:
        db: 데이터베이스 세션
        owner: 작성자 (deprecated, 호환성 유지용)
        target_date: 기준 날짜 (해당 월의 아무 날짜)
        kpi_data: PostgreSQL에서 조회한 월간 KPI 숫자 JSON (선택)
        display_name: HTML 보고서에 표시할 이름 (선택, 없으면 owner 사용)
        
    Returns:
        CanonicalReport (monthly, owner는 상수로 설정됨)
    """
    # 1. 해당 월의 1일~말일 날짜 계산
    first_day, last_day = get_month_range(target_date)
    month_str = target_date.strftime("%Y-%m")
    
    # 2. DB에서 해당 월의 모든 주간보고서 조회
    # owner 필터링 제거: 단일 워크스페이스로 동작 (모든 주간보고서 조회)
    # TODO: PostgreSQL 스키마에서 owner 필터링 제거 필요 (현재는 호환성 유지)
    weekly_reports = WeeklyReportRepository.list_by_owner_and_period_range(
        db=db,
        owner=REPORT_OWNER,  # 상수 owner 사용
        period_start=first_day,
        period_end=last_day
    )
    
    print(f"[INFO] 주간보고서 {len(weekly_reports)}개 발견: {first_day}~{last_day}")
    
    # 3. 벡터DB에서 해당 월의 일일보고서 청크 검색
    vector_store = get_report_vector_store()
    collection = vector_store.get_collection()
    retriever = UnifiedRetriever(
        collection=collection,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    
    # 해당 월의 모든 일일보고서 청크 검색
    # owner 필터링 제거: 단일 워크스페이스로 동작
    daily_chunks = retriever.search_daily(
        query="월간 업무",
        owner=None,  # owner 필터링 제거
        period_start=first_day.isoformat(),
        period_end=last_day.isoformat(),
        n_results=500,  # 충분한 데이터 수집
        chunk_types=None  # 모든 청크 타입
    )
    
    print(f"[INFO] 일일보고서 청크 {len(daily_chunks)}개 발견: {first_day}~{last_day}")
    
    # 4. 주간보고서 JSON 변환
    weekly_reports_json = []
    for weekly_report in weekly_reports:
        if weekly_report.report_json:
            weekly_reports_json.append(weekly_report.report_json.get("weekly", {}))
    
    # 5. 일일보고서 청크 변환
    daily_chunks_data = []
    for chunk in daily_chunks:
        daily_chunks_data.append({
            "text": chunk.text,
            "metadata": chunk.metadata
        })
    
    # 6. LLM 프롬프트 구성
    llm_client = LLMClient(model="gpt-4o", temperature=0.7, max_tokens=2000)
    prompt_registry = prompt_registry or ReportPromptRegistry
    weekly_reports_dump = json.dumps(weekly_reports_json, ensure_ascii=False, indent=2)
    daily_chunks_dump = json.dumps(daily_chunks_data, ensure_ascii=False, indent=2)
    kpi_dump = json.dumps(kpi_data or {}, ensure_ascii=False, indent=2)
    user_prompt = prompt_registry.monthly_user(
        weekly_reports_json=weekly_reports_dump,
        daily_chunks_json=daily_chunks_dump,
        kpi_json=kpi_dump,
        month_str=month_str,
    )
    
    # 7. LLM 호출
    try:
        response = llm_client.complete_json(
            system_prompt=prompt_registry.monthly_system(),
            user_prompt=user_prompt,
            temperature=0.7
        )
        
        monthly_data = response if isinstance(response, dict) else json.loads(response)
        
    except Exception as e:
        print(f"[ERROR] 월간보고서 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    # 8. CanonicalMonthly 생성
    # 주의: key_metrics는 LLM이 출력하지 않음 (시스템에서 자동 계산)
    # display_name 결정 (HTML 보고서용)
    actual_display_name = display_name or owner
    header = {
        "월": month_str,  # YYYY-MM 형식 (예: "2025-11")
        "작성일자": last_day.isoformat(),
        "성명": actual_display_name  # HTML 보고서에 표시할 이름
    }
    
    canonical_monthly = CanonicalMonthly(
        header=header,
        weekly_summaries=monthly_data.get("weekly_summaries", {}),
        next_month_plan=monthly_data.get("next_month_plan", "")
    )
    
    # 9. CanonicalReport 생성
    report = CanonicalReport(
        report_id=str(uuid.uuid4()),
        report_type="monthly",
        owner=REPORT_OWNER,  # 상수 owner 사용 (실제 사용자 이름과 분리)
        period_start=first_day,
        period_end=last_day,
        monthly=canonical_monthly
    )
    
    # 10. kpi_data를 report 객체에 임시 저장 (html_renderer에서 사용)
    # LLM은 key_metrics를 출력하지 않으므로, kpi_data를 그대로 사용
    if kpi_data:
        # analysis 필드 제거 (숫자만 표시)
        kpi_data_clean = {
            "new_contracts": kpi_data.get("new_contracts", 0),
            "renewals": kpi_data.get("renewals", 0),
            "consultations": kpi_data.get("consultations", 0),
            "analysis": ""  # 분석 문장 없음 (숫자만 표시)
        }
        setattr(report, '_kpi_data', kpi_data_clean)
        print(f"[INFO] KPI 데이터 저장: new_contracts={kpi_data_clean.get('new_contracts', 0)}, renewals={kpi_data_clean.get('renewals', 0)}, consultations={kpi_data_clean.get('consultations', 0)}")
    else:
        print(f"[WARN] kpi_data가 제공되지 않았습니다.")
    
    return report
