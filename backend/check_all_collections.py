"""
ChromaDB의 모든 컬렉션 확인 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from ingestion.chroma_client import get_chroma_service

try:
    print("=" * 70)
    print("📊 ChromaDB 전체 컬렉션 상태 확인")
    print("=" * 70)
    
    # ChromaDB 클라이언트 가져오기
    chroma = get_chroma_service()
    
    # 모든 컬렉션 리스트 가져오기
    collections = chroma.client.list_collections()
    
    print(f"\n📦 총 컬렉션 개수: {len(collections)}개\n")
    
    for idx, collection in enumerate(collections, 1):
        print(f"{'=' * 70}")
        print(f"[{idx}] 컬렉션 이름: {collection.name}")
        print(f"    컬렉션 ID: {collection.id}")
        print(f"    문서 개수: {collection.count()}개")
        
        # 샘플 데이터 확인
        if collection.count() > 0:
            try:
                result = collection.peek(limit=3)
                print(f"\n    📄 샘플 데이터 (최대 3개):")
                for i, doc in enumerate(result["documents"][:3], 1):
                    metadata = result["metadatas"][i-1] if result.get("metadatas") else {}
                    doc_type = metadata.get("doc_type", "N/A")
                    chunk_type = metadata.get("chunk_type", "N/A")
                    date = metadata.get("date", "N/A")
                    owner = metadata.get("owner", "N/A")
                    
                    preview = doc[:60] + "..." if len(doc) > 60 else doc
                    print(f"      [{i}] doc_type={doc_type}, chunk_type={chunk_type}")
                    print(f"          date={date}, owner={owner}")
                    print(f"          text: {preview}")
                    print()
            except Exception as e:
                print(f"      샘플 조회 실패: {e}")
        print()
    
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

