"""
월간 KPI 계산기

카테고리 기반 KPI 계산
주간보고서의 notes 데이터에서 KPI를 추출하여 합산합니다.
"""
from typing import Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from calendar import monthrange
import re

from app.domain.report.weekly.repository import WeeklyReportRepository
from app.core.config import settings

REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER


def _parse_weekly_notes(notes: str) -> tuple[int, int, int]:
    """
    주간보고서 notes에서 KPI 추출
    
    Args:
        notes: "상담 3건 / 신규 1건 / 유지 0건" 형식의 문자열
        
    Returns:
        (new_contracts, renewals, consultations) 튜플
    """
    if not notes:
        return (0, 0, 0)
    
    new_contracts = 0
    renewals = 0
    consultations = 0
    
    # "상담 3건" 패턴 추출
    consult_match = re.search(r'상담\s*(\d+)건', notes)
    if consult_match:
        consultations = int(consult_match.group(1))
    
    # "신규 1건" 패턴 추출
    new_match = re.search(r'신규\s*(\d+)건', notes)
    if new_match:
        new_contracts = int(new_match.group(1))
    
    # "유지 0건" 패턴 추출
    renew_match = re.search(r'유지\s*(\d+)건', notes)
    if renew_match:
        renewals = int(renew_match.group(1))
    
    return (new_contracts, renewals, consultations)


def calculate_monthly_kpi(
    db: Session,
    year: int,
    month: int
) -> Dict[str, Any]:
    """
    월간 KPI 계산 (주간보고서 notes 기반)
    
    해당 월의 모든 주간보고서에서 weekday_tasks의 notes 데이터를 추출하여 합산합니다.
    주간보고서의 각 요일별 notes에는 "상담 3건 / 신규 1건 / 유지 0건" 형식으로 저장되어 있습니다.
    
    Args:
        db: 데이터베이스 세션
        year: 연도
        month: 월 (1~12)
        
    Returns:
        {
            "new_contracts": int,      # 신규 계약 건수
            "renewals": int,           # 유지 계약 건수
            "consultations": int,      # 상담 건수
            "analysis": str            # 분석 문장 (빈 문자열)
        }
    """
    # 해당 월의 첫날과 마지막날 계산
    first_day = date(year, month, 1)
    last_day_num = monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)
    
    # 해당 월의 모든 주간보고서 조회
    weekly_reports = WeeklyReportRepository.list_by_owner_and_period_range(
        db=db,
        owner=REPORT_OWNER,
        period_start=first_day,
        period_end=last_day
    )
    
    print(f"[INFO] 월간 KPI 계산: {year}년 {month}월, 주간보고서 {len(weekly_reports)}개 조회")
    
    # 카테고리별 카운트 초기화
    new_contracts = 0
    renewals = 0
    consultations = 0
    
    # 모든 주간보고서의 weekday_notes 순회
    for idx, report in enumerate(weekly_reports):
        if not report.report_json:
            continue
        
        weekly_data = report.report_json.get("weekly", {})
        weekday_notes = weekly_data.get("weekday_notes", {})  # 새로 추가된 weekday_notes 필드 사용
        
        # 디버깅: 주간보고서 전체 구조 출력
        print(f"\n[DEBUG] === 주간보고서 #{idx+1} ===")
        print(f"[DEBUG] weekly_data 키: {list(weekly_data.keys())}")
        print(f"[DEBUG] weekday_notes 키: {list(weekday_notes.keys())}")
        print(f"[DEBUG] weekday_notes 내용: {weekday_notes}")
        print(f"[DEBUG] ================\n")
        
        # weekday_notes에서 각 요일의 KPI 집계
        for weekday_name, notes in weekday_notes.items():
            if not notes:
                continue
            
            # notes에서 KPI 추출 ("상담 3건 / 신규 1건 / 유지 0건" 형식)
            new_cnt, renew_cnt, consult_cnt = _parse_weekly_notes(notes)
            new_contracts += new_cnt
            renewals += renew_cnt
            consultations += consult_cnt
            
            if new_cnt > 0 or renew_cnt > 0 or consult_cnt > 0:
                print(f"[DEBUG] {weekday_name} KPI 집계: notes='{notes}' -> new={new_cnt}, renew={renew_cnt}, consult={consult_cnt}")
    
    print(f"[INFO] 최종 KPI: 신규 계약 {new_contracts}건, 유지 계약 {renewals}건, 상담 {consultations}건")
    
    # 분석 문장은 빈 문자열 (숫자만 표시)
    analysis = ""
    
    return {
        "new_contracts": new_contracts,
        "renewals": renewals,
        "consultations": consultations,
        "analysis": analysis
    }

