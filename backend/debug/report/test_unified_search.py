"""
Unified Search 테스트 스크립트

통합 검색 시스템의 동작을 테스트합니다.

실행 방법:
    python -m debug.report.test_unified_search

Author: AI Assistant
Created: 2025-11-18
"""
import sys
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.infrastructure.vector_store_report import get_report_vector_store
from app.domain.report.search.retriever import UnifiedRetriever
from app.domain.report.search.intent_router import IntentRouter
from app.domain.report.search.service import UnifiedSearchService


def print_separator(title: str = ""):
    """구분선 출력"""
    if title:
        print(f"\n{'='*80}")
        print(f" {title}")
        print(f"{'='*80}\n")
    else:
        print(f"{'='*80}\n")


def print_result(result: dict):
    """검색 결과 출력"""
    print(f"쿼리: {result['query']}")
    print(f"Intent: {result['intent']}")
    print(f"판단 근거: {result['reason']}")
    print(f"필터: {result['filters']}")
    print(f"결과 개수: {result['count']}개\n")
    
    if result['count'] > 0:
        print("상위 결과 (최대 3개):")
        print("-" * 80)
        
        for i, item in enumerate(result['results'][:3], 1):
            print(f"\n[{i}] chunk_id: {item.chunk_id}")
            print(f"    doc_type: {item.doc_type}")
            print(f"    chunk_type: {item.chunk_type}")
            print(f"    score: {item.score:.4f}")
            print(f"    owner: {item.metadata.get('owner', 'N/A')}")
            print(f"    date: {item.metadata.get('date', 'N/A')}")
            
            # 텍스트 미리보기 (처음 200자)
            preview = item.text[:200] + "..." if len(item.text) > 200 else item.text
            print(f"    text: {preview}")
    else:
        print("검색 결과가 없습니다.")


def test_scenario_1():
    """시나리오 1: 일일 보고서 검색"""
    print_separator("시나리오 1: 일일 보고서 검색")
    
    query = "신규 고객 상담 업무 내용 알려줘"
    
    # 서비스 초기화
    collection = get_report_vector_store().get_collection()
    retriever = UnifiedRetriever(collection)
    router = IntentRouter()
    service = UnifiedSearchService(retriever, router)
    
    # 검색 실행
    result = service.search_sync(query=query, n_results=5)
    
    # 결과 출력
    print_result(result)
    
    return result


def test_scenario_2():
    """시나리오 2: KPI 검색"""
    print_separator("시나리오 2: KPI 검색")
    
    query = "암보험 실적 KPI 정리해줘"
    
    # 서비스 초기화
    collection = get_report_vector_store().get_collection()
    retriever = UnifiedRetriever(collection)
    router = IntentRouter()
    service = UnifiedSearchService(retriever, router)
    
    # 검색 실행
    result = service.search_sync(query=query, n_results=5)
    
    # 결과 출력
    print_result(result)
    
    return result


def test_scenario_3():
    """시나리오 3: 템플릿 검색"""
    print_separator("시나리오 3: 템플릿 검색")
    
    query = "월간 업무 보고서 양식 다시 보여줘"
    
    # 서비스 초기화
    collection = get_report_vector_store().get_collection()
    retriever = UnifiedRetriever(collection)
    router = IntentRouter()
    service = UnifiedSearchService(retriever, router)
    
    # 검색 실행
    result = service.search_sync(query=query, n_results=5)
    
    # 결과 출력
    print_result(result)
    
    return result


def test_all_scenarios():
    """모든 시나리오 테스트"""
    print("\n" + "="*80)
    print(" Unified Search 시스템 테스트")
    print("="*80)
    
    try:
        # 시나리오 1
        result1 = test_scenario_1()
        
        # 시나리오 2
        result2 = test_scenario_2()
        
        # 시나리오 3
        result3 = test_scenario_3()
        
        # 요약
        print_separator("테스트 요약")
        print(f"시나리오 1: Intent={result1['intent']}, 결과={result1['count']}개")
        print(f"시나리오 2: Intent={result2['intent']}, 결과={result2['count']}개")
        print(f"시나리오 3: Intent={result3['intent']}, 결과={result3['count']}개")
        
        print("\n테스트 완료!")
        
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()


def main():
    """메인 함수"""
    test_all_scenarios()


if __name__ == "__main__":
    main()

