"""
금일 진행 업무 선택 Flow 테스트

전체 플로우:
1. TodayPlan Chain으로 추천 업무 생성
2. 사용자가 선택한 업무를 /select_main_tasks로 저장
3. /daily/start 호출 시 자동으로 main_tasks 불러오기

Author: AI Assistant
Created: 2025-11-19
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import date
from app.domain.report.daily.main_tasks_store import get_main_tasks_store
from app.domain.report.planner.today_plan_chain import TodayPlanGenerator
from app.domain.report.planner.tools import YesterdayReportTool
from app.domain.report.planner.schemas import TodayPlanRequest
from app.domain.report.search.retriever import UnifiedRetriever
from app.infrastructure.vector_store_report import get_report_vector_store
from app.llm.client import get_llm


def test_main_tasks_flow():
    """금일 진행 업무 선택 Flow 전체 테스트"""
    print("=" * 60)
    print("금일 진행 업무 선택 Flow 테스트")
    print("=" * 60)
    
    owner = "김보험"
    today = date.today()
    
    # Step 1: TodayPlan Chain으로 추천 업무 생성
    print("\n[Step 1] TodayPlan Chain 실행")
    print("-" * 60)
    
    try:
        collection = get_report_vector_store().get_collection()
        retriever = UnifiedRetriever(collection)
        retriever_tool = YesterdayReportTool(retriever)
        llm_client = get_llm(model="gpt-4o", temperature=0.7, max_tokens=2000)
        
        generator = TodayPlanGenerator(retriever_tool, llm_client)
        
        request = TodayPlanRequest(
            owner=owner,
            target_date=today
        )
        
        result = generator.generate_sync(request)
        
        print(f"✅ 추천 업무 생성 성공!")
        print(f"   요약: {result.summary}")
        print(f"   추천 업무 수: {len(result.tasks)}")
        
        for i, task in enumerate(result.tasks, 1):
            print(f"\n   [{i}] {task.title}")
            print(f"       설명: {task.description}")
            print(f"       우선순위: {task.priority}")
            print(f"       예상 시간: {task.expected_time}")
            print(f"       카테고리: {task.category}")
    
    except Exception as e:
        print(f"❌ TodayPlan Chain 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: 사용자가 선택한 업무를 저장소에 저장
    print("\n[Step 2] 선택한 업무 저장")
    print("-" * 60)
    
    # 첫 3개 업무를 선택했다고 가정
    selected_tasks = []
    for task in result.tasks[:3]:
        selected_tasks.append({
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "expected_time": task.expected_time,
            "category": task.category
        })
    
    try:
        store = get_main_tasks_store()
        store.save(
            owner=owner,
            target_date=today,
            main_tasks=selected_tasks
        )
        
        print(f"✅ {len(selected_tasks)}개 업무 저장 성공!")
        for i, task in enumerate(selected_tasks, 1):
            print(f"   [{i}] {task['title']}")
    
    except Exception as e:
        print(f"❌ 업무 저장 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: 저장소에서 불러오기 테스트
    print("\n[Step 3] 저장된 업무 불러오기")
    print("-" * 60)
    
    try:
        store = get_main_tasks_store()
        loaded_tasks = store.get(owner=owner, target_date=today)
        
        if loaded_tasks:
            print(f"✅ {len(loaded_tasks)}개 업무 불러오기 성공!")
            for i, task in enumerate(loaded_tasks, 1):
                print(f"   [{i}] {task['title']}")
            
            # 원본과 동일한지 확인
            if len(loaded_tasks) == len(selected_tasks):
                print("\n✅ 저장된 업무와 불러온 업무가 일치합니다!")
            else:
                print("\n⚠️  저장된 업무와 불러온 업무 수가 다릅니다!")
        else:
            print("❌ 저장된 업무를 찾을 수 없습니다!")
    
    except Exception as e:
        print(f"❌ 업무 불러오기 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("✅ 전체 Flow 테스트 완료!")
    print("=" * 60)


def test_main_tasks_store():
    """MainTasksStore 단독 테스트"""
    print("\n" + "=" * 60)
    print("MainTasksStore 단독 테스트")
    print("=" * 60)
    
    store = get_main_tasks_store()
    
    owner = "테스트사용자"
    test_date = date(2025, 11, 19)
    
    test_tasks = [
        {
            "title": "테스트 업무 1",
            "description": "테스트 설명 1",
            "priority": "high",
            "expected_time": "30분",
            "category": "테스트"
        },
        {
            "title": "테스트 업무 2",
            "description": "테스트 설명 2",
            "priority": "medium",
            "expected_time": "1시간",
            "category": "테스트"
        }
    ]
    
    # 저장 테스트
    print("\n[저장 테스트]")
    store.save(owner, test_date, test_tasks)
    print(f"✅ {len(test_tasks)}개 업무 저장")
    
    # 조회 테스트
    print("\n[조회 테스트]")
    loaded = store.get(owner, test_date)
    if loaded:
        print(f"✅ {len(loaded)}개 업무 조회")
        for task in loaded:
            print(f"   - {task['title']}")
    else:
        print("❌ 조회 실패")
    
    # 삭제 테스트
    print("\n[삭제 테스트]")
    success = store.delete(owner, test_date)
    if success:
        print("✅ 삭제 성공")
    else:
        print("❌ 삭제 실패")
    
    # 삭제 후 조회
    print("\n[삭제 후 조회 테스트]")
    loaded = store.get(owner, test_date)
    if loaded is None:
        print("✅ 삭제 확인됨 (None 반환)")
    else:
        print("❌ 삭제 실패 (데이터가 여전히 존재)")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # MainTasksStore 단독 테스트
    test_main_tasks_store()
    
    # 전체 Flow 테스트 (LLM API 필요)
    print("\n\n")
    test_main_tasks_flow()

