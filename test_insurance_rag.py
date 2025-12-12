"""
Insurance RAG 테스트 스크립트
ChromaDB 연결 및 라우팅 테스트
"""
import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

print("=" * 60)
print("Insurance RAG 테스트")
print("=" * 60)

# 1. ChromaDB 컬렉션 확인
print("\n[1] ChromaDB 컬렉션 확인")
try:
    import chromadb
    chroma_path = "backend/app/domain/rag/insurance/chroma_db"
    client = chromadb.PersistentClient(path=chroma_path)
    collections = client.list_collections()
    
    print(f"✅ ChromaDB 경로: {chroma_path}")
    print(f"✅ 발견된 컬렉션 수: {len(collections)}")
    
    for coll in collections:
        count = coll.count()
        print(f"  - {coll.name}: {count} documents")
        
        if count > 0:
            # 샘플 데이터 확인
            sample = coll.peek(limit=1)
            if sample['documents']:
                print(f"    샘플 내용: {sample['documents'][0][:100]}...")
    
except Exception as e:
    print(f"❌ ChromaDB 접속 실패: {e}")

# 2. Insurance Config 확인
print("\n[2] Insurance Config 확인")
try:
    from app.domain.rag.insurance.config import insurance_config
    
    print(f"✅ CHROMA_COLLECTION_NAME: {insurance_config.CHROMA_COLLECTION_NAME}")
    print(f"✅ CHROMA_PERSIST_DIRECTORY: {insurance_config.CHROMA_PERSIST_DIRECTORY}")
    print(f"✅ EMBEDDING_MODEL: {insurance_config.EMBEDDING_MODEL}")
    print(f"✅ RAG_TOP_K: {insurance_config.RAG_TOP_K}")
    
except Exception as e:
    print(f"❌ Config 로드 실패: {e}")

# 3. Insurance RAG Pipeline 초기화 테스트
print("\n[3] Insurance RAG Pipeline 초기화 테스트")
try:
    from app.domain.rag.insurance.services.rag_pipeline import RAGPipeline
    
    print("  RAGPipeline 클래스 로드됨")
    
    # 초기화 시도
    pipeline = RAGPipeline()
    print("✅ RAGPipeline 초기화 성공")
    
    # 파이프라인 정보 출력
    info = pipeline.get_pipeline_info()
    print(f"  Vector Store: {info['vector_store']}")
    print(f"  Collection Info: {info['vector_store_info']}")
    print(f"  Embedding Model: {info['embedding_model']}")
    print(f"  LLM Model: {info['llm_model']}")
    
except Exception as e:
    print(f"❌ RAG Pipeline 초기화 실패: {e}")
    import traceback
    traceback.print_exc()

# 4. Insurance Agent 초기화 테스트
print("\n[4] Insurance Agent 초기화 테스트")
try:
    from multi_agent.agents.insurance_rag_agent import InsuranceRAGAgent
    
    agent = InsuranceRAGAgent()
    print(f"✅ Insurance Agent 초기화 성공")
    print(f"  Name: {agent.name}")
    print(f"  Description: {agent.description}")
    
except Exception as e:
    print(f"❌ Insurance Agent 초기화 실패: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("테스트 완료")
print("=" * 60)
