"""
주간 보고서 생성 체인
새로운 4청크 구조 기반 RAG 프롬프트 사용
"""
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import uuid
import json

from app.domain.report.core.canonical_models import CanonicalReport, CanonicalWeekly
from app.infrastructure.vector_store_report import get_report_vector_store
from app.domain.report.search.retriever import UnifiedRetriever
from app.llm.client import LLMClient
from app.core.config import settings
from multi_agent.agents.report_main_router import ReportPromptRegistry

# 보고서 owner는 상수로 사용 (실제 사용자 이름과 분리)
REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER


def get_week_range(target_date: date) -> tuple[date, date]:
    """해당 주의 월요일~금요일 날짜 범위 계산"""
    weekday = target_date.weekday()
    monday = target_date - timedelta(days=weekday)
    friday = monday + timedelta(days=4)
    return (monday, friday)


def generate_weekly_report(
    db: Session,
    owner: str,  # 실제 사용자 이름 (display_name용, 더 이상 CanonicalReport.owner에 저장 안 함)
    target_date: date,
    display_name: Optional[str] = None,  # HTML 보고서에 표시할 이름
    prompt_registry: Optional[ReportPromptRegistry] = None,
) -> CanonicalReport:
    """
    주간 보고서 자동 생성 (새로운 4청크 구조 기반)
    
    Args:
        db: 데이터베이스 세션
        owner: 작성자 (deprecated, 호환성 유지용)
        target_date: 기준 날짜 (해당 주의 아무 날짜)
        display_name: HTML 보고서에 표시할 이름 (선택, 없으면 owner 사용)
        
    Returns:
        CanonicalReport (weekly, owner는 상수로 설정됨)
    """
    # 1. 해당 주의 월~금 날짜 계산
    monday, friday = get_week_range(target_date)
    iso_calendar = monday.isocalendar()
    week_str = f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"
    
    # 2. 벡터DB에서 주간 데이터 검색 (날짜 범위 기반)
    vector_store = get_report_vector_store()
    collection = vector_store.get_collection()
    retriever = UnifiedRetriever(
        collection=collection,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    
    print(f"[DEBUG] 주간 보고서 데이터 검색: range={monday}~{friday}")
    
    # 날짜 범위로 모든 일일보고서 청크 검색 (5일 × 4청크 = 20개 기대)
    # owner 필터링 제거: 단일 워크스페이스로 동작
    all_chunks = retriever.search_daily(
        query="주간 업무",
        owner=None,  # owner 필터링 제거
        date_range=(monday, friday),
        top_k=20,  # 충분히 20개
        chunk_types=None  # 모든 청크 타입
    )
    
    print(f"[INFO] 벡터DB 검색 완료: {len(all_chunks)}개 청크 발견")
    
    if len(all_chunks) == 0:
        raise ValueError(f"해당 주({monday}~{friday})에 일일보고서 데이터를 찾을 수 없습니다.")
    
    # 3. 검색 결과를 프롬프트 형식으로 변환
    search_results = []
    for chunk in all_chunks:
        search_results.append({
            "text": chunk.text,
            "metadata": chunk.metadata
        })
    
    # 4. LLM 프롬프트 구성
    llm_client = LLMClient(model="gpt-4o", temperature=0.7, max_tokens=2000)
    prompt_registry = prompt_registry or ReportPromptRegistry
    search_results_json = json.dumps(search_results, ensure_ascii=False, indent=2)
    user_prompt = prompt_registry.weekly_user(
        search_results_json=search_results_json,
        monday=monday,
        friday=friday,
    )
    
    # 5. LLM 호출
    try:
        system_prompt = prompt_registry.weekly_system(week_number=week_str)
        response = llm_client.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )
        
        weekly_data = response if isinstance(response, dict) else json.loads(response)
        
        # 디버그: LLM 응답 확인
        print(f"[DEBUG] LLM 응답 weekday_tasks 키: {list(weekly_data.get('weekday_tasks', {}).keys())}")
        
    except Exception as e:
        print(f"[ERROR] 주간보고서 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    # 6. CanonicalWeekly 생성
    # display_name 결정 (HTML 보고서용)
    actual_display_name = display_name or owner
    header = {
        "작성일자": target_date.isoformat(),
        "성명": actual_display_name  # HTML 보고서에 표시할 이름
    }
    
    # weekday_tasks 처리: 새로운 구조 (요일명 키 + tasks/notes 객체) 또는 기존 구조 (날짜 키 + 리스트)
    weekday_tasks_raw = weekly_data.get("weekday_tasks", {})
    weekday_tasks_converted = {}
    
    # 요일 한글 이름 매핑 (0=월요일, 4=금요일)
    weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일']
    weekday_short_names = ['월', '화', '수', '목', '금']
    
    # 새로운 구조인지 확인 (요일명 키 사용)
    is_new_structure = False
    if weekday_tasks_raw:
        first_key = list(weekday_tasks_raw.keys())[0]
        if first_key in weekday_short_names:
            is_new_structure = True
    
    # weekday_notes 딕셔너리 초기화 (KPI 집계용)
    weekday_notes = {}
    
    if is_new_structure:
        # 새로운 구조: { "월": { "tasks": [...], "notes": "..." }, ... }
        print(f"[DEBUG] 새로운 구조 감지: 요일명 키 사용")
        for day_idx, short_name in enumerate(weekday_short_names):
            weekday_name = weekday_names[day_idx]
            if short_name in weekday_tasks_raw:
                day_data = weekday_tasks_raw[short_name]
                if isinstance(day_data, dict):
                    # tasks와 notes 추출 - notes는 별도 딕셔너리에 저장
                    tasks = day_data.get("tasks", [])
                    notes = day_data.get("notes", "")
                    weekday_tasks_converted[weekday_name] = tasks
                    weekday_notes[weekday_name] = notes  # notes 정보 보존
                    print(f"[DEBUG] {weekday_name} ({short_name}) 업무 {len(tasks)}개, notes: {notes}")
                else:
                    # dict가 아니면 리스트로 처리 (하위 호환)
                    weekday_tasks_converted[weekday_name] = day_data if isinstance(day_data, list) else []
            else:
                weekday_tasks_converted[weekday_name] = []
                print(f"[WARNING] {weekday_name} ({short_name}) 업무 데이터 없음")
    else:
        # 기존 구조: { "YYYY-MM-DD": [...], ... } 또는 { "월요일": [...], ... }
        print(f"[DEBUG] 기존 구조 감지: 날짜 또는 요일명 키 사용")
        current_date = monday
        for day_idx in range(5):
            weekday_name = weekday_names[day_idx]
            date_str = current_date.isoformat()
            
            # 날짜 키로 업무 찾기
            if date_str in weekday_tasks_raw:
                tasks = weekday_tasks_raw[date_str]
                weekday_tasks_converted[weekday_name] = tasks if isinstance(tasks, list) else []
                print(f"[DEBUG] {weekday_name} ({date_str}) 업무 {len(weekday_tasks_converted[weekday_name])}개 변환 완료")
            elif weekday_name in weekday_tasks_raw:
                # 요일명 키로도 확인 (하위 호환)
                tasks = weekday_tasks_raw[weekday_name]
                weekday_tasks_converted[weekday_name] = tasks if isinstance(tasks, list) else []
                print(f"[DEBUG] {weekday_name} (요일명 키) 업무 {len(weekday_tasks_converted[weekday_name])}개 변환 완료")
            else:
                weekday_tasks_converted[weekday_name] = []
                print(f"[WARNING] {weekday_name} ({date_str}) 업무 데이터 없음")
            
            current_date += timedelta(days=1)
    
    print(f"[DEBUG] 최종 weekday_tasks_converted: {list(weekday_tasks_converted.keys())}")
    
    # weekly_goals는 새로운 구조에서 제거되었으므로 빈 리스트로 처리
    weekly_goals = weekly_data.get("weekly_goals", [])
    if not weekly_goals:
        weekly_goals = []
    
    # notes는 새로운 구조에서 제거되었으므로 빈 문자열로 처리
    notes = weekly_data.get("notes", "")
    if not notes:
        notes = ""
    
    canonical_weekly = CanonicalWeekly(
        header=header,
        weekly_goals=weekly_goals,
        weekday_tasks=weekday_tasks_converted,
        weekday_notes=weekday_notes,  # 요일별 notes 정보 추가
        weekly_highlights=weekly_data.get("weekly_highlights", []),
        notes=notes
    )
    
    # 7. CanonicalReport 생성
    report = CanonicalReport(
        report_id=str(uuid.uuid4()),
        report_type="weekly",
        owner=REPORT_OWNER,  # 상수 owner 사용 (실제 사용자 이름과 분리)
        period_start=monday,
        period_end=friday,
        weekly=canonical_weekly
    )
    
    return report
