"""
Insurance RAG Loader
보험/의료급여 문서를 임베딩하여 ChromaDB에 저장
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from tqdm import tqdm

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "backend"))


def init_insurance_rag() -> bool:
    """
    Insurance RAG ChromaDB 초기화
    
    - JSON 파일에서 텍스트 청크 로드
    - Insurance embedder로 임베딩 생성
    - Insurance/chroma_db에 저장
    
    Returns:
        bool: 성공 여부
    """
    print("\n🏥 [Insurance] RAG 초기화 체크...")
    
    try:
        # 1. 경로 설정
        base_dir = Path(__file__).parent.parent / "domain" / "rag" / "Insurance"
        chroma_dir = base_dir / "chroma_db"
        json_file = base_dir / "documents" / "proceeds" / "chunks_insurance_manual.json"
        
        print(f"   📂 ChromaDB 경로: {chroma_dir}")
        print(f"   📄 JSON 파일: {json_file}")
        
        # ChromaDB 디렉토리 생성
        chroma_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. ChromaDB 클라이언트 초기화
        client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # 3. 컬렉션 가져오기 또는 생성
        collection_name = "insurance_documents"
        
        try:
            # 임베딩 함수 없이 컬렉션 가져오기 (이미 임베딩된 벡터 사용)
            collection = client.get_collection(collection_name)
            print(f"   📋 컬렉션 '{collection_name}' 발견")
        except Exception:
            print(f"   📋 컬렉션 '{collection_name}' 생성 중...")
            # 임베딩 함수 없이 컬렉션 생성 (수동으로 임베딩 제공)
            collection = client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        
        # 4. 이미 데이터가 있는지 확인
        current_count = collection.count()
        if current_count > 0:
            print(f"   ✅ 이미 존재 ({current_count}개 문서) - 스킵")
            return True
        
        # 5. JSON 파일 확인
        if not json_file.exists():
            print(f"   ❌ JSON 파일 없음: {json_file}")
            return False
        
        print(f"   ⚠️  컬렉션 비어있음 - 데이터 로드 시작")
        
        # 6. JSON 데이터 로드
        print(f"   📖 JSON 파일 읽는 중...")
        with open(json_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        print(f"   📦 {len(chunks)}개 청크 로드 완료")
        
        # 7. Insurance Embedder 초기화
        print(f"   🔧 Insurance Embedder 초기화 중...")
        from app.domain.rag.Insurance.services.providers import SimpleEmbeddingProvider
        from app.domain.rag.Insurance.config import insurance_config
        
        embedder = SimpleEmbeddingProvider(
            model=insurance_config.OPENAI_EMBEDDING_MODEL
        )
        print(f"   ✅ Embedder 준비: {insurance_config.OPENAI_EMBEDDING_MODEL}")
        
        # 8. 텍스트만 추출
        texts = [chunk["content"] for chunk in chunks]
        
        # 9. 임베딩 생성 (배치 처리)
        print(f"   � 임베딩 생성 중...")
        batch_size = 100
        all_embeddings = []
        
        for i in tqdm(range(0, len(texts), batch_size), desc="   임베딩 진행"):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = embedder.embed_batch(batch_texts)
            all_embeddings.extend(batch_embeddings)
        
        print(f"   ✅ 임베딩 생성 완료: {len(all_embeddings)}개")
        
        # 10. ChromaDB에 삽입
        print(f"   💾 ChromaDB에 삽입 중...")
        
        ids: List[str] = []
        documents: List[str] = []
        embeddings: List[List[float]] = []
        metadatas: List[Dict[str, Any]] = []
        
        # ID 중복 방지
        id_counter: Dict[str, int] = {}
        
        for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings)):
            base_id = chunk.get("chunk_id", f"ins_chunk_{idx}")
            
            # 고유 ID 생성
            if base_id in id_counter:
                id_counter[base_id] += 1
                unique_id = f"{base_id}_{id_counter[base_id]}"
            else:
                id_counter[base_id] = 0
                unique_id = base_id
            
            ids.append(unique_id)
            documents.append(chunk["content"])
            embeddings.append(embedding)
            
            # 메타데이터
            metadata = {
                "tokens": chunk.get("tokens", 0),
                "source_pages": str(chunk.get("source_pages", [])),
                "chunk_id": base_id
            }
            metadatas.append(metadata)
        
        # 배치 삽입
        insert_batch_size = 100
        for i in tqdm(range(0, len(ids), insert_batch_size), desc="   저장 진행"):
            end_idx = min(i + insert_batch_size, len(ids))
            
            collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )
        
        # 11. 검증
        final_count = collection.count()
        print(f"   ✅ 초기화 완료! ({final_count}개 문서)")
        
        if final_count != len(chunks):
            print(f"   ⚠️  경고: 예상({len(chunks)})과 실제({final_count}) 문서 수 불일치")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Insurance RAG 로더 - 독립 실행")
    print("=" * 60)
    
    result = init_insurance_rag()
    
    print("\n" + "=" * 60)
    print(f"결과: {'✅ 성공' if result else '❌ 실패'}")
    print("=" * 60)
