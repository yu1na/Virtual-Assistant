"""간단한 ChromaDB 확인 스크립트"""
import chromadb

try:
    chroma_path = r"backend\app\domain\rag\insurance\chroma_db"
    print(f"ChromaDB 경로: {chroma_path}")
    
    client = chromadb.PersistentClient(path=chroma_path)
    collections = client.list_collections()
    
    print(f"\n발견된 컬렉션: {len(collections)}개")
    
    for coll in collections:
        print(f"\n컬렉션명: {coll.name}")
        print(f"문서 수: {coll.count()}")
        
        if coll.count() > 0:
            sample = coll.peek(limit=2)
            print(f"샘플 문서:")
            for i, doc in enumerate(sample['documents'][:2]):
                print(f"  [{i+1}] {doc[:150]}...")
        
except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
