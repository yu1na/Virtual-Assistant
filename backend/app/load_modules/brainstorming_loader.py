"""
브레인스토밍 모듈 초기화

ChromaDB에 브레인스토밍 기법 데이터가 없으면 자동 생성합니다.
이미 있으면 스킵합니다.
"""

from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings


def init_brainstorming() -> bool:
    """
    브레인스토밍 RAG 초기화
    
    - ChromaDB 컬렉션이 비어있으면: embedded_chunks.json으로 생성
    - 이미 데이터가 있으면: 스킵
    
    Returns:
        bool: 성공 여부
    """
    # 경로 설정
    base_dir = Path(__file__).parent.parent / "domain" / "brainstorming"
    data_dir = base_dir / "data"
    chroma_dir = data_dir / "chroma"
    embeddings_dir = data_dir / "embeddings"
    embedded_file = embeddings_dir / "embedded_chunks.json"
    
    collection_name = "brainstorming_techniques"
    
    print("\n🧠 [브레인스토밍] RAG 초기화 체크...")
    
    # 1. embedded_chunks.json 존재 확인
    if not embedded_file.exists():
        print(f"   ⚠️  임베딩 파일 없음: {embedded_file}")
        print("   브레인스토밍 RAG 사용 불가")
        return False
    
    # 2. ChromaDB 클라이언트 초기화
    try:
        # idea_generator.py와 동일한 설정 사용 (충돌 방지)
        client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    except Exception as e:
        print(f"   ❌ ChromaDB 초기화 실패: {e}")
        return False
    
    # 3. 컬렉션 존재 여부 및 데이터 확인
    try:
        collection = client.get_collection(name=collection_name)
        count = collection.count()
        
        if count > 0:
            print(f"   ✅ 이미 존재 ({count}개 문서) - 스킵")
            return True
        else:
            print(f"   ⚠️  컬렉션 비어있음 - 재생성")
            
    except Exception:
        print("   📝 컬렉션 없음 - 생성 시작")
    
    # 4. ChromaDB에 데이터 로드
    try:
        import json
        with open(embedded_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        print(f"   📦 {len(chunks)}개 청크 로드")
        
        # 5. 컬렉션 생성
        try:
            client.delete_collection(name=collection_name)
        except:
            pass
        
        collection = client.create_collection(
            name=collection_name,
            metadata={
                "description": "브레인스토밍 기법 청크 컬렉션",
                "hnsw:space": "cosine"
            }
        )
        
        # 6. 데이터 준비 및 삽입
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        id_counter = {}
        
        for chunk in chunks:
            if 'embedding' not in chunk:
                continue
            
            chunk_id = chunk['chunk_id']
            if chunk_id in id_counter:
                id_counter[chunk_id] += 1
                unique_id = f"chunk_{chunk_id}_{id_counter[chunk_id]}"
            else:
                id_counter[chunk_id] = 0
                unique_id = f"chunk_{chunk_id}"
            
            ids.append(unique_id)
            embeddings.append(chunk['embedding'])
            metadatas.append({
                "chunk_id": chunk['chunk_id'],
                "title": chunk['title'],
                "word_count": chunk['metadata'].get('word_count', 0),
                "char_count": chunk['metadata'].get('char_count', 0),
                "source_file": chunk['metadata'].get('source_file', ''),
                "embedding_model": chunk['metadata'].get('embedding_model', ''),
            })
            documents.append(chunk['content'])
        
        # 7. ChromaDB에 삽입
        if ids:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            
            print(f"   ✅ 초기화 완료! ({len(ids)}개 문서)")
            return True
        else:
            print("   ⚠️  삽입할 데이터 없음")
            return False
            
    except Exception as e:
        print(f"   ❌ 초기화 실패: {e}")
        return False


# 직접 실행 테스트
if __name__ == "__main__":
    success = init_brainstorming()
    print(f"\n결과: {'성공' if success else '실패'}")
