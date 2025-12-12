"""
Daily FSM 테스트

시간대별 일일보고서 입력 FSM 테스트

실행 방법:
    python -m debug.report.test_daily_fsm

Author: AI Assistant
Created: 2025-11-18
"""
import sys
import os
from pathlib import Path
from datetime import date
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.domain.report.daily.fsm_state import DailyFSMContext
from app.domain.report.daily.time_slots import generate_time_slots
from app.domain.report.daily.task_parser import TaskParser
from app.domain.report.daily.daily_fsm import DailyReportFSM
from app.domain.report.daily.daily_builder import build_daily_report
from app.llm.client import get_llm


def print_separator(title: str = ""):
    """구분선"""
    if title:
        print(f"\n{'='*80}")
        print(f" {title}")
        print(f"{'='*80}\n")
    else:
        print(f"{'='*80}\n")


def test_time_slots():
    """시간대 생성 테스트"""
    print_separator("시간대 생성 테스트")
    
    slots = generate_time_slots("09:00", "12:00", 60)
    print(f"생성된 시간대: {len(slots)}개")
    for slot in slots:
        print(f"  - {slot}")
    
    return slots


def test_task_parser():
    """Task Parser 테스트"""
    print_separator("Task Parser 테스트")
    
    llm_client = get_llm()
    parser = TaskParser(llm_client)
    
    # 테스트 케이스
    test_cases = [
        ("암보험 고객 2명 상담했음", "09:00~10:00"),
        ("CRM 시스템 데이터 정리", "10:00~11:00"),
        ("팀 회의 참석", "11:00~12:00")
    ]
    
    results = []
    for text, time_range in test_cases:
        print(f"\n입력: \"{text}\" ({time_range})")
        result = parser.parse_sync(text, time_range)
        print(f"결과:")
        print(f"  title: {result['title']}")
        print(f"  category: {result['category']}")
        print(f"  description: {result['description']}")
        results.append(result)
    
    return results


def test_daily_fsm():
    """Daily FSM 전체 테스트"""
    print_separator("Daily FSM 전체 테스트")
    
    # 1. 금일 진행 업무 (TodayPlan에서 선택된 것)
    main_tasks = [
        {
            "title": "신규 고객 상담",
            "description": "보험 가입 상담 진행",
            "category": "고객 상담",
            "priority": "high"
        },
        {
            "title": "계약서 작성",
            "description": "2건의 계약서 작성",
            "category": "문서 작업",
            "priority": "medium"
        }
    ]
    
    print("금일 진행 업무 (main_tasks):")
    for i, task in enumerate(main_tasks, 1):
        print(f"  [{i}] {task['title']} - {task['category']}")
    print()
    
    # 2. 시간대 생성 (테스트용으로 3개만)
    time_ranges = generate_time_slots("09:00", "12:00", 60)
    print(f"시간대: {time_ranges}")
    print()
    
    # 3. FSM 초기화
    llm_client = get_llm()
    parser = TaskParser(llm_client)
    fsm = DailyReportFSM(parser)
    
    # 4. FSM 컨텍스트 생성
    context = DailyFSMContext(
        owner="김보험",
        target_date=date(2025, 1, 25),
        time_ranges=time_ranges,
        today_main_tasks=main_tasks,
        current_index=0,
        finished=False
    )
    
    # 5. 세션 시작
    result = fsm.start_session(context)
    print(f"[질문 1] {result['question']}")
    
    # 6. 답변 시뮬레이션
    answers = [
        "암보험 고객 2명 상담",
        "CRM 데이터 정리했음",
        "팀 회의 참석"
    ]
    
    current_context = result['state']
    
    for i, answer in enumerate(answers, 1):
        print(f"[답변 {i}] {answer}")
        
        result = fsm.process_answer(current_context, answer)
        current_context = result['state']
        
        if not result['finished']:
            print(f"[질문 {i+1}] {result['question']}")
        else:
            print("\n모든 시간대 입력 완료!")
            break
        print()
    
    # 7. 최종 보고서 생성
    print_separator("최종 보고서 생성")
    
    report = build_daily_report(
        owner=current_context.owner,
        target_date=current_context.target_date,
        main_tasks=current_context.today_main_tasks,
        time_tasks=current_context.time_tasks
    )
    
    print(f"Report ID: {report.report_id}")
    print(f"Owner: {report.owner}")
    print(f"Date: {report.period_start}")
    print(f"Type: {report.report_type}")
    print()
    
    print(f"총 Tasks: {len(report.tasks)}개")
    print(f"  - 금일 진행 업무: {len(main_tasks)}개")
    print(f"  - 시간대별 세부업무: {len(current_context.time_tasks)}개")
    print()
    
    print("Tasks 상세:")
    for i, task in enumerate(report.tasks, 1):
        status_mark = "[완료]" if task.status == "completed" else "[예정]"
        print(f"  {status_mark} {task.title}")
        print(f"      시간: {task.time_start}~{task.time_end}" if task.time_start else "      (시간 미지정)")
        print(f"      설명: {task.description}")
        print(f"      비고: {task.note}")
        print()
    
    return report


def main():
    """메인 테스트"""
    print("\n" + "="*80)
    print(" Daily FSM 시스템 테스트")
    print("="*80)
    
    try:
        # 테스트 1: 시간대 생성
        test_time_slots()
        
        # 테스트 2: Task Parser
        test_task_parser()
        
        # 테스트 3: 전체 FSM
        report = test_daily_fsm()
        
        print_separator("테스트 완료")
        print(f"최종 보고서 생성 완료!")
        print(f"  - Report ID: {report.report_id}")
        print(f"  - 총 Tasks: {len(report.tasks)}개")
        
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

