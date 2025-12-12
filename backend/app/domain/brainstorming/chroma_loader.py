"""
브레인스토밍 청크를 ChromaDB에 로드하는 모듈

이 모듈은 임베딩된 청크 데이터를 ChromaDB 벡터 데이터베이스에 저장합니다.
벡터 DB에 저장되면 빠른 유사도 검색이 가능합니다.
"""
import json
import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings


class ChromaDBLoader:
    """ChromaDB에 청크를 로드하는 클래스"""
    
    def __init__(self):
        # .env 파일 로드
        env_path = Path(__file__).parent.parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        # 디렉토리 경로 설정
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.embeddings_dir = self.data_dir / "embeddings"
        
        # ChromaDB 설정 - 브레인스토밍 모듈 전용 경로
        # 다른 팀원과 충돌하지 않도록 모듈 내부에 저장
        self.persist_directory = str(self.data_dir / "chroma")
        # 브레인스토밍 전용 컬렉션 이름
        self.collection_name = "brainstorming_techniques"
        
        print(f"📁 ChromaDB 저장 경로: {self.persist_directory}")
        
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
    def load_embedded_chunks(self, filename: str = "embedded_chunks.json") -> List[Dict]:
        """
        임베딩된 청크 JSON 파일 로드
        
        Args:
            filename: 로드할 파일명
            
        Returns:
            임베딩된 청크 리스트
        """
        file_path = self.embeddings_dir / filename
        
        print(f"📂 파일 로드 중: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        return chunks
    
    def create_or_get_collection(self):
        """
        ChromaDB 컬렉션 생성 또는 가져오기
        
        Returns:
            ChromaDB 컬렉션 객체
        """
        try:
            # 기존 컬렉션이 있으면 삭제 (재생성)
            try:
                self.client.delete_collection(name=self.collection_name)
                print(f"🗑️  기존 컬렉션 '{self.collection_name}' 삭제됨")
            except:
                pass
            
            # 새 컬렉션 생성
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "description": "브레인스토밍 기법 청크 컬렉션",
                    "hnsw:space": "cosine"  # 코사인 유사도 사용
                }
            )
            
            print(f"✅ 새 컬렉션 '{self.collection_name}' 생성됨")
            
            return collection
            
        except Exception as e:
            print(f"❌ 컬렉션 생성 실패: {e}")
            raise
    
    def prepare_data_for_chroma(self, chunks: List[Dict]):
        """
        ChromaDB에 삽입할 수 있는 형태로 데이터 변환
        
        Args:
            chunks: 임베딩된 청크 리스트
            
        Returns:
            (ids, embeddings, metadatas, documents) 튜플
        """
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        # 중복 체크를 위한 카운터
        id_counter = {}
        
        for idx, chunk in enumerate(chunks):
            # embedding 필드가 있는 청크만 처리
            if 'embedding' not in chunk:
                print(f"⚠️  청크 {chunk['chunk_id']}에 임베딩이 없어 스킵됨")
                continue
            
            # ID: 중복 처리 (같은 chunk_id가 있으면 뒤에 번호 추가)
            chunk_id = chunk['chunk_id']
            if chunk_id in id_counter:
                id_counter[chunk_id] += 1
                unique_id = f"chunk_{chunk_id}_{id_counter[chunk_id]}"
                print(f"⚠️  중복된 chunk_id '{chunk_id}' 발견 → '{unique_id}'로 저장")
            else:
                id_counter[chunk_id] = 0
                unique_id = f"chunk_{chunk_id}"
            
            ids.append(unique_id)
            
            # Embedding: 벡터
            embeddings.append(chunk['embedding'])
            
            # Metadata: 검색 결과와 함께 반환될 메타데이터
            metadata = {
                "chunk_id": chunk['chunk_id'],
                "title": chunk['title'],
                "word_count": chunk['metadata'].get('word_count', 0),
                "char_count": chunk['metadata'].get('char_count', 0),
                "source_file": chunk['metadata'].get('source_file', ''),
                "embedding_model": chunk['metadata'].get('embedding_model', ''),
                "original_index": idx  # 원본 인덱스도 저장
            }
            metadatas.append(metadata)
            
            # Document: 실제 텍스트 내용 (검색 시 반환됨)
            documents.append(chunk['content'])
        
        return ids, embeddings, metadatas, documents
    
    def load_to_chromadb(self, chunks: List[Dict]):
        """
        청크들을 ChromaDB에 로드
        
        Args:
            chunks: 임베딩된 청크 리스트
        """
        print("\n🔮 ChromaDB에 데이터 로드 중...")
        
        # 컬렉션 생성
        collection = self.create_or_get_collection()
        
        # 데이터 준비
        print("📦 데이터 변환 중...")
        ids, embeddings, metadatas, documents = self.prepare_data_for_chroma(chunks)
        
        print(f"✅ {len(ids)}개의 청크 준비 완료")
        
        # ChromaDB에 배치 삽입
        print("💾 ChromaDB에 저장 중...")
        
        try:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            
            print(f"✅ {len(ids)}개의 청크가 ChromaDB에 저장되었습니다!")
            
            # 저장 확인
            count = collection.count()
            print(f"📊 컬렉션 '{self.collection_name}'에 총 {count}개의 문서가 있습니다.")
            
            return collection
            
        except Exception as e:
            print(f"❌ ChromaDB 저장 실패: {e}")
            raise
    
    def test_search(self, collection, query_text: str = "팀 협업을 위한 브레인스토밍"):
        """
        테스트 검색 수행
        
        Args:
            collection: ChromaDB 컬렉션
            query_text: 검색 쿼리
        """
        print("\n" + "=" * 60)
        print("🔍 테스트 검색 수행")
        print("=" * 60)
        print(f"Query: '{query_text}'")
        
        # OpenAI로 쿼리 임베딩 생성
        from openai import OpenAI
        
        api_key = os.getenv('OPENAI_API_KEY')
        client = OpenAI(api_key=api_key)
        
        response = client.embeddings.create(
            model=os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large'),
            input=query_text,
            encoding_format="float"
        )
        
        query_embedding = response.data[0].embedding
        
        # ChromaDB에서 유사도 검색 (상위 3개)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
        
        print(f"\n📋 상위 3개 결과:")
        print("-" * 60)
        
        for idx, (doc_id, metadata, document, distance) in enumerate(
            zip(
                results['ids'][0],
                results['metadatas'][0],
                results['documents'][0],
                results['distances'][0]
            ),
            1
        ):
            print(f"\n{idx}. [{metadata['title']}] (유사도: {1 - distance:.4f})")
            print(f"   청크 ID: {metadata['chunk_id']}")
            print(f"   내용 미리보기: {document[:100]}...")
        
        print("\n" + "=" * 60)
    
    def process(self, input_filename: str = "embedded_chunks.json", run_test: bool = True):
        """
        전체 ChromaDB 로드 프로세스 실행
        
        Args:
            input_filename: 입력 파일명 (임베딩된 청크)
            run_test: 테스트 검색 실행 여부
        """
        print("=" * 60)
        print("🚀 ChromaDB 벡터 DB 구축 시작")
        print("=" * 60)
        
        # 1. 임베딩된 청크 로드
        chunks = self.load_embedded_chunks(input_filename)
        print(f"✅ {len(chunks)}개의 청크를 로드했습니다.")
        
        # 2. ChromaDB에 저장
        collection = self.load_to_chromadb(chunks)
        
        # 3. 테스트 검색
        if run_test:
            self.test_search(collection)
        
        print("\n" + "=" * 60)
        print("✅ ChromaDB 벡터 DB 구축 완료!")
        print("=" * 60)
        print(f"📁 저장 위치: {self.persist_directory}")
        print(f"📦 컬렉션 이름: {self.collection_name}")
        print(f"🔢 저장된 문서 수: {collection.count()}")
        print("\n💡 이제 RAG 검색을 사용할 수 있습니다!")
        print("=" * 60)


# 실행
if __name__ == "__main__":
    try:
        loader = ChromaDBLoader()
        loader.process()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print("\n💡 확인사항:")
        print("   1. embedded_chunks.json 파일이 존재하는지 확인")
        print("   2. ChromaDB가 설치되어 있는지 확인 (pip install chromadb)")
        print("   3. 저장 경로에 쓰기 권한이 있는지 확인")

