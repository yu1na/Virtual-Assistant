"""
Vector DB 저장 스크립트
생성날짜: 2025.11.21
리팩토링: 2025.11.25 - 1차 코드 리팩토링(쓸데 없는 print문 제거 및 코드 정리)
수정날짜: 2025.11.28 - Parent-Child Chunking 지원
설명: adler/embeddings 폴더의 OpenAI 임베딩 파일들을 ChromaDB에 저장
      Parent와 Child 청크를 같은 컬렉션에 저장하며 chunk_type 메타데이터로 구분
"""

import os
import json
import sys
import shutil
import gc
import logging
import warnings
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings

# ChromaDB의 경고 메시지 억제 (Add of existing embedding ID 등)
logging.getLogger("chromadb").setLevel(logging.ERROR)
# ChromaDB 내부 모듈들의 로깅도 억제
logging.getLogger("chromadb.db").setLevel(logging.ERROR)
logging.getLogger("chromadb.segment").setLevel(logging.ERROR)
# warnings 모듈로도 경고 억제
warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")
# stderr 출력 억제를 위한 설정
import io
from contextlib import redirect_stderr

# Vector DB 매니저
class VectorDBManager:

    def __init__(self, db_path: str):

        # 경로 설정
        self.db_path = Path(db_path)
        
        # ChromaDB 클라이언트 초기화
        self.client = None
        self._initialize_client()
    
    # Chroma DB 클라이언트 초기화
    def _initialize_client(self):

        try:
            # DB 폴더 생성
            self.db_path.mkdir(parents=True, exist_ok=True)
            
            # ChromaDB 클라이언트 생성
            self.client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
        except Exception as e:
            raise Exception(f"ChromaDB 초기화 실패: {e}") # 예외처리 print문은 배포 전 삭제 예정
    
    # 임베딩 파일 로드 함수
    # 예외처리 print문은 배포 전 삭제 예정
    def load_embedding_file(self, filepath: Path) -> List[Dict[str, Any]]:

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)
            return data
        except FileNotFoundError:
            print(f"파일을 찾을 수 없습니다")
            raise
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            raise
        except Exception as e:
            print(f"파일 로드 오류: {e}")
            raise
    
    # 컬렉션 생성 또는 이미 존재할 경우 가져오기
    # print문은 배포 전 삭제 예정
    def create_or_get_collection(self, collection_name: str):

        try:
            # 기존 컬렉션이 있는지 확인
            collection = self.client.get_collection(name=collection_name)
            return collection
            
        except Exception:
            # 컬렉션이 없으면 새로 생성
            try:
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}  # 코사인 유사도 사용
                )
                return collection
                
            except Exception as e:
                print(f"컬렉션 생성 오류: {e}")
                raise
    
    # 데이터를 컬렉션에 배치 단위로 저장하는 함수
    # collection_name: 컬렉션 이름
    # data: 저장할 데이터 리스트
    # batch_size: 배치 크기
    def save_to_collection(self, collection_name: str, data: List[Dict[str, Any]], 
                          batch_size: int = 1000) -> int:

        try:
            # 컬렉션 생성 또는 기존 컬렉션 가져오기
            collection = self.create_or_get_collection(collection_name)
            
            # 기존 데이터 개수 확인
            existing_count = collection.count()

            # 기존 ID 목록 가져오기 (중복 방지) - 스트리밍 방식으로 ID만 조회
            # 메모리 최적화: include=["ids"]로 ID만 로드 (embeddings, documents, metadatas 제외)
            existing_ids = set()
            if existing_count > 0:
                try:
                    # ID만 가져오기 (메모리 최적화: include=["ids"]로 ID만 로드)
                    # ChromaDB는 offset을 지원하지 않으므로 전체 ID를 한 번에 가져오되,
                    # ID만 로드하므로 메모리 사용량이 크게 감소함
                    existing_data = collection.get(
                        include=["ids"]  # ID만 가져오기 (메모리 최적화)
                    )
                    if existing_data and existing_data.get('ids'):
                        existing_ids = set(existing_data['ids'])
                            
                except Exception as e:
                    # 기존 ID 확인 실패 시 조용히 넘어감 (ChromaDB 버전 차이로 인한 오류일 수 있음)
                    pass
            
            # 데이터 준비
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            skipped_count = 0
            
            for item in data:
                # 이미 존재하는 ID는 건너뛰기
                if item['id'] in existing_ids:
                    skipped_count += 1
                    continue
                
                ids.append(item['id'])
                embeddings.append(item['embedding'])
                documents.append(item['text'])
                
                # 메타데이터 처리 (ChromaDB는 list를 지원하지 않으므로 변환)
                metadata = item['metadata'].copy()
                if 'tags' in metadata and isinstance(metadata['tags'], list):
                    metadata['tags'] = ', '.join(metadata['tags'])
                metadatas.append(metadata)
            
            if not ids:
                return 0
            
            # 배치로 저장 (스트리밍 방식)
            total_items = len(ids)
            
            successful_batches = 0
            failed_batches = 0
            
            for i in range(0, total_items, batch_size):
                end_idx = min(i + batch_size, total_items)
                
                try:
                    # 컬렉션에 데이터 추가 (ChromaDB 경고 메시지 억제)
                    # stderr를 임시로 리다이렉트하여 "Add of existing embedding ID" 메시지 억제
                    with redirect_stderr(io.StringIO()):
                        collection.add(
                            ids=ids[i:end_idx],
                            embeddings=embeddings[i:end_idx],
                            documents=documents[i:end_idx],
                            metadatas=metadatas[i:end_idx]
                        )
                    successful_batches += 1
                    
                    # 배치 처리 후 메모리 해제를 위한 힌트 (실제 해제는 루프 종료 후)
                    
                except Exception as e:
                    # ChromaDB의 중복 에러는 무시 (이미 존재하는 경우)
                    error_msg = str(e).lower()
                    if "existing" in error_msg or "duplicate" in error_msg or "already exists" in error_msg:
                        # 중복 에러는 조용히 건너뛰기
                        successful_batches += 1
                        continue
                    print(f"\n배치 저장 실패: {e}") # 예외처리 print문은 배포 전 삭제 예정
                    failed_batches += 1
            
            # 메모리 해제를 위한 정리
            del ids, embeddings, documents, metadatas
            gc.collect()
            
            return total_items
        
        except Exception as e:
            print(f"데이터 저장 오류: {e}")
            raise
    
    # 컬렉션 검증 함수
    def verify_collection(self, collection_name: str) -> Dict[str, Any]:

        try:
            collection = self.client.get_collection(name=collection_name) # 컬렉션 가져오기
            count = collection.count() # 컬렉션 개수
            
            result = {
                'name': collection_name,
                'count': count,
                'metadata': collection.metadata
            }
            
            # 샘플 데이터 조회
            if count > 0:
                sample = collection.peek(limit=1)
                if sample['ids']:
                    result['sample_id'] = sample['ids'][0]
            
            return result
        
        except Exception as e:
            print(f"컬렉션 검증 오류: {e}")
            raise

# 메인 함수
# 예외처리 print문 및 쓸데없는 print문은 배포 전 삭제 예정
def main():
    
    # 경로 설정 (sourcecode/automatic_save 기준)
    base_dir = Path(__file__).parent.parent.parent
    embedding_dir = base_dir / "dataset" / "adler" / "embeddings"
    vector_db_dir = base_dir / "vector_db"
    
    # 컬렉션 이름
    collection_name = "vector_adler"
    
    # 입력 디렉토리 확인
    if not embedding_dir.exists():
        print(f"오류: 입력 디렉토리가 존재하지 않습니다")
        sys.exit(1)
    
    # 임베딩 파일 목록 가져오기
    embedding_files = sorted(embedding_dir.glob("*_embeddings.json"))
    
    if not embedding_files:
        print(f"오류: 임베딩 파일을 찾을 수 없습니다")
        sys.exit(1)

    try:
        # Vector DB 매니저 초기화
        db_manager = VectorDBManager(str(vector_db_dir))
        
        # 스트리밍 처리: 파일별로 순차 처리하고 각 파일 처리 후 메모리 해제
        total_saved = 0
        file_stats = []
        
        for emb_file in embedding_files:
            try:
                # 파일별로 데이터 로드
                data = db_manager.load_embedding_file(emb_file)
                
                if not data:
                    file_stats.append({
                        'file': emb_file.name,
                        'count': 0,
                        'status': '경고: 데이터 없음'
                    })
                    continue
                
                # 즉시 Vector DB에 저장 (스트리밍 처리)
                saved_count = db_manager.save_to_collection(
                    collection_name=collection_name,
                    data=data,
                    batch_size=1000
                )
                
                total_saved += saved_count
                file_stats.append({
                    'file': emb_file.name,
                    'count': len(data),
                    'saved': saved_count,
                    'status': '성공'
                })
                
                # 메모리 해제
                del data
                gc.collect()
                
            except Exception as e:
                file_stats.append({
                    'file': emb_file.name,
                    'count': 0,
                    'status': f'실패: {e}'
                })
                print(f"로드 실패: {emb_file.name} - {e}")
        
        # 처리 결과 확인
        if total_saved == 0:
            print("경고: 저장된 데이터가 없습니다.")
        
    except KeyboardInterrupt:
        print("\n\n작업이 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n치명적 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# 메인 호출
if __name__ == "__main__":
    main()