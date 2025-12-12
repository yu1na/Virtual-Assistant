"""
Today Plan Chain 테스트

오늘의 추천 일정 생성 체인을 테스트합니다.

실행 방법:
    python -m debug.report.test_today_plan_chain

Author: AI Assistant
Created: 2025-11-18
"""
import sys
import os
from pathlib import Path
from datetime import date, datetime
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트 path 추가
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.vector_store_report import get_report_vector_store
from app.domain.report.search.retriever import UnifiedRetriever
from app.domain.report.planner.tools import YesterdayReportTool
from app.domain.report.planner.schemas import TodayPlanRequest
from app.domain.report.planner.today_plan_chain import TodayPlanGenerator
from app.llm.client import get_llm


def print_separator(title: str = ""):
    """구분선 출력"""
    if title:
        print(f"\n{'='*80}")
        print(f" {title}")
        print(f"{'='*80}\n")
    else:
        print(f"{'='*80}\n")


def test_yesterday_report_tool():
    """Step 1: 전날 보고서 검색 테스트"""
    print_separator("Step 1: 전날 보고서 검색")
    
    # 초기화
    collection = get_report_vector_store().get_collection()
    retriever = UnifiedRetriever(collection)
    tool = YesterdayReportTool(retriever)
    
    # 테스트 파라미터
    owner = ""  # 빈 문자열로 검색 (owner 필터 없음)
    target_date = date(2025, 1, 25)  # 2025-01-25 (오늘) - 데이터가 있는 날짜
    
    print(f"Owner: {owner}")
    print(f"Target Date (오늘): {target_date}")
    print(f"전날 날짜: {target_date.replace(day=target_date.day-1)}")
    print()
    
    # 전날 보고서 가져오기
    result = tool.get_yesterday_report(owner, target_date)
    
    print(f"발견 여부: {result['found']}")
    print(f"검색 날짜: {result['search_date']}")
    print()
    
    print(f"미종결 업무 (unresolved): {len(result['unresolved'])}개")
    for i, item in enumerate(result['unresolved'][:3], 1):
        print(f"  [{i}] {item}")
    print()
    
    print(f"익일 계획 (next_day_plan): {len(result['next_day_plan'])}개")
    for i, item in enumerate(result['next_day_plan'][:3], 1):
        print(f"  [{i}] {item}")
    print()
    
    print(f"전날 작업 (tasks): {len(result.get('tasks', []))}개")
    for i, item in enumerate(result.get('tasks', [])[:3], 1):
        print(f"  [{i}] {item}")
    print()
    
    print(f"전체 청크 수: {len(result['raw_chunks'])}개")
    
    return result


def test_today_plan_generation():
    """Step 2: 오늘 일정 생성 테스트"""
    print_separator("Step 2: 오늘 일정 생성")
    
    # 초기화
    collection = get_report_vector_store().get_collection()
    retriever = UnifiedRetriever(collection)
    tool = YesterdayReportTool(retriever)
    llm_client = get_llm(model="gpt-4o", temperature=0.7, max_tokens=2000)
    
    generator = TodayPlanGenerator(tool, llm_client)
    
    # 요청 생성
    request = TodayPlanRequest(
        owner="",  # 빈 문자열
        target_date=date(2025, 1, 25)  # 데이터가 있는 날짜
    )
    
    print(f"Owner: {request.owner}")
    print(f"Date: {request.target_date}")
    print()
    
    print("LLM 호출 중...")
    
    # 일정 생성 (동기)
    response = generator.generate_sync(request)
    
    print()
    print_separator("생성된 오늘 일정")
    
    print(f"Owner: {response.owner}")
    print(f"Source Date (전날): {response.source_date}")
    print(f"Summary: {response.summary}")
    print()
    
    print(f"Tasks: {len(response.tasks)}개")
    print("-" * 80)
    
    for i, task in enumerate(response.tasks, 1):
        print(f"\n[Task {i}]")
        print(f"  Title: {task.title}")
        print(f"  Description: {task.description}")
        print(f"  Priority: {task.priority}")
        print(f"  Expected Time: {task.expected_time}")
        print(f"  Category: {task.category}")
    
    return response


def main():
    """메인 테스트 함수"""
    print("\n" + "="*80)
    print(" Today Plan Chain 테스트")
    print("="*80)
    
    try:
        # Step 1: 전날 보고서 검색
        yesterday_result = test_yesterday_report_tool()
        
        # Step 2: 오늘 일정 생성
        if yesterday_result['found']:
            today_plan = test_today_plan_generation()
            
            print_separator("테스트 완료")
            print("전날 보고서 기반 오늘 일정 생성 성공!")
        else:
            print_separator("테스트 결과")
            print("전날 데이터가 없어 기본 일정이 생성될 것입니다.")
            
            # 그래도 생성 테스트
            today_plan = test_today_plan_generation()
    
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

