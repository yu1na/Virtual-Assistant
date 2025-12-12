"""
RAG 시스템 디버깅 유틸리티

RAG 시스템이 제대로 작동하는지 확인하는 스크립트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .vector_store import VectorStore
from .retriever import RAGRetriever
from .config import rag_config
from .utils import get_logger

logger = get_logger(__name__)


def check_vector_store():
    """벡터 저장소 상태 확인"""
    print("=" * 60)
    print("벡터 저장소 상태 확인")
    print("=" * 60)
    
    try:
        vector_store = VectorStore()
        
        # 문서 수 확인
        doc_count = vector_store.count_documents()
        print(f"✓ 저장된 문서 청크 수: {doc_count}개")
        
        if doc_count == 0:
            print("⚠ 경고: 저장된 문서가 없습니다!")
            print("   먼저 파일을 업로드하세요:")
            print("   python -m app.domain.rag.HR.cli upload <파일경로>")
            return False
        
        # 테스트 검색
        print("\n테스트 검색 실행 중...")
        test_query = "연차"
        results = vector_store.search(test_query, top_k=3)
        
        if results and results.get('documents') and results['documents'][0]:
            print(f"✓ 검색 성공: {len(results['documents'][0])}개 결과")
            for i, doc in enumerate(results['documents'][0][:3], 1):
                distance = results['distances'][0][i-1] if results.get('distances') and results['distances'][0] else None
                print(f"  {i}. 거리: {distance:.4f if distance else 'N/A'}, 길이: {len(doc)}자")
        else:
            print("✗ 검색 결과가 없습니다.")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_rag_query():
    """RAG 질의응답 테스트"""
    print("\n" + "=" * 60)
    print("RAG 질의응답 테스트")
    print("=" * 60)
    
    try:
        retriever = RAGRetriever()
        
        # 테스트 질문
        test_queries = [
            "연차 규정은 어떻게 되나요?",
            "안녕하세요"
        ]
        
        for query in test_queries:
            print(f"\n질문: {query}")
            print("-" * 60)
            
            from .schemas import QueryRequest
            request = QueryRequest(query=query)
            response = retriever.query(request)
            
            print(f"답변: {response.answer[:200]}...")
            print(f"검색된 청크: {len(response.retrieved_chunks)}개")
            print(f"처리 시간: {response.processing_time:.2f}초")
            
            if response.retrieved_chunks:
                print("참고 문서:")
                for i, chunk in enumerate(response.retrieved_chunks, 1):
                    print(f"  {i}. {chunk.metadata.get('filename', 'Unknown')} "
                          f"(유사도: {chunk.score:.3f})")
        
        return True
        
    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("RAG 시스템 디버깅")
    print("=" * 60)
    print(f"ChromaDB 경로: {rag_config.CHROMA_PERSIST_DIRECTORY}")
    print(f"컬렉션 이름: {rag_config.CHROMA_COLLECTION_NAME}")
    print(f"임베딩 모델: {rag_config.KOREAN_EMBEDDING_MODEL}")
    print(f"Threshold: {rag_config.RAG_SIMILARITY_THRESHOLD}")
    print()
    
    # 1. 벡터 저장소 확인
    vector_store_ok = check_vector_store()
    
    if not vector_store_ok:
        print("\n⚠ 벡터 저장소에 문제가 있습니다. 파일을 먼저 업로드하세요.")
        return
    
    # 2. RAG 질의응답 테스트
    rag_ok = check_rag_query()
    
    print("\n" + "=" * 60)
    if vector_store_ok and rag_ok:
        print("✓ 모든 테스트 통과!")
    else:
        print("✗ 일부 테스트 실패")
    print("=" * 60)


if __name__ == "__main__":
    main()

