"""
ChromaDB 컬렉션 관리 스크립트
생성날짜: 2025.11.18
설명: ChromaDB의 컬렉션을 조회, 삭제, 관리하는 유틸리티
"""

import chromadb
from pathlib import Path
import sys

# Vector DB 매니저
class CollectionManager:
    
    # 초기화 함수
    def __init__(self, db_path: str):

        self.db_path = Path(db_path) # DB경로: 매개변수로 전달한 경로 사용
        
        # DB가 존재하지 않으면
        if not self.db_path.exists():
            print(f"[경고] Vector DB 경로가 존재하지 않습니다: {self.db_path}")
            print("Vector DB가 아직 생성되지 않았을 수 있습니다.")
            sys.exit(1)
        
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(path=str(self.db_path)) # PersistentClient 사용
        print(f"ChromaDB 연결 완료: {self.db_path}\n")
    
    # 컬렉션 목록 조회 함수
    def list_collections(self):
        """모든 컬렉션 목록 조회"""
        print("=" * 60)
        print("저장된 컬렉션 목록")
        print("=" * 60)
        
        collections = self.client.list_collections() # 컬렉션 목록 가지고오기
        
        # 컬렉션이 없으면
        if not collections:
            print("저장된 컬렉션이 없습니다.")
            return []
        
        # 컬렉션이 있을 경우
        collection_info = [] # 컬렉션 정보를 저장할 리스트
        for col in collections:
            count = col.count()
            collection_info.append({ # 컬렉션 정보를 저장할 리스트에 이름, 개수, metadata 추가
                'name': col.name,
                'count': count,
                'metadata': col.metadata
            })

            # 컬렉션 정보 출력
            print(f"\n컬렉션 이름: {col.name}")
            print(f"  - 항목 수: {count}개")
            print(f"  - 메타데이터: {col.metadata}")
        
        print("\n" + "=" * 60)
        return collection_info
    
    # 특정 컬렉션의 상세 정보 조회
    def get_collection_details(self, collection_name: str):

        try:
            collection = self.client.get_collection(name=collection_name) # 컬렉션 이름으로 해당 컬렉션 가지고오기
            
            print("=" * 60)
            print(f"컬렉션 '{collection_name}' 상세 정보")
            print("=" * 60)
            
            count = collection.count()
            print(f"총 항목 수: {count}개")
            print(f"메타데이터: {collection.metadata}")
            
            # 샘플 데이터 조회 (처음 3개)
            if count > 0:
                sample = collection.peek(limit=min(3, count)) # 샘플 데이터로 3개의 데이터만 가지고 와서 sample에 저장
                print(f"\n샘플 데이터 (최대 3개):")
                for i, (id, doc, meta) in enumerate(zip(sample['ids'], sample['documents'], sample['metadatas']), 1):
                    print(f"\n  [{i}] ID: {id}")
                    print(f"      텍스트: {doc[:100]}..." if len(doc) > 100 else f"      텍스트: {doc}")
                    print(f"      메타데이터: {meta}")
            
            print("\n" + "=" * 60)
            return collection
        
        # 예외처리
        except Exception as e:
            print(f"[오류] 컬렉션을 찾을 수 없습니다: {collection_name}") # 나중에 삭제 예정
            print(f"상세: {e}") # 예외 추적 결과, 나중에 삭제 예정
            return None
    
    # 특정 컬렉션 삭제
    def delete_collection(self, collection_name: str):

        try:
            # 컬렉션 존재 확인
            collection = self.client.get_collection(name=collection_name)
            count = collection.count()
            
            print(f"\n컬렉션 '{collection_name}' 삭제 예정")
            print(f"  - 항목 수: {count}개")
            
            # 사용자 확인
            confirm = input(f"\n정말로 '{collection_name}' 컬렉션을 삭제하시겠습니까? (y/n): ")
            
            # 사용자가 정말 삭제한다고 하면 삭제 진행
            if confirm.lower() == 'y':
                self.client.delete_collection(name=collection_name) # 해당 컬렉션 삭제
                print(f"[완료] 컬렉션 '{collection_name}' 삭제 완료")
                return True
            else:
                print("[취소] 삭제가 취소되었습니다.")
                return False
        
        # 예외처리
        except Exception as e:
            print(f"[오류] 컬렉션 삭제 실패: {collection_name}") # 나중에 삭제 예정
            print(f"상세: {e}") # 나중에 삭제 예정
            return False
    
    # 모든 컬렉션 삭제
    def delete_all_collections(self):

        collections = self.client.list_collections() # 모든컬렉션 목록 가지고오기
        
        # 컬렉션이 없으면
        if not collections:
            print("삭제할 컬렉션이 없습니다.")
            return
        
        print("\n모든 컬렉션 삭제 예정:")
        for col in collections:
            print(f"  - {col.name} ({col.count()}개 항목)")
        
        # 사용자 확인, 정말로 삭제할건지
        confirm = input(f"\n정말로 모든 컬렉션을 삭제하시겠습니까? (y/n): ")
        
        # 사용자가 삭제한다고 할 경우
        if confirm.lower() == 'y':
            deleted_count = 0
            for col in collections: # 반복문 돌면서 컬렉션 삭제
                try:
                    self.client.delete_collection(name=col.name) # 컬렉션 삭제
                    print(f"[완료] '{col.name}' 삭제됨")
                    deleted_count += 1
                except Exception as e:
                    print(f"[오류] '{col.name}' 삭제 실패: {e}")
            
            print(f"\n총 {deleted_count}개 컬렉션 삭제 완료")
        else:
            print("[취소] 삭제가 취소되었습니다.")
    
    # 컬렉션에서 유사도 검색
    def search_in_collection(self, collection_name: str, query_text: str, n_results: int = 5):

        try:
            collection = self.client.get_collection(name=collection_name)
            
            print(f"\n컬렉션 '{collection_name}'에서 검색 중...")
            print(f"검색어: {query_text}")
            print(f"결과 수: {n_results}개\n")
            
            # 참고: 실제 검색을 위해서는 query_embeddings가 필요하지만,
            # 여기서는 간단히 get으로 데이터를 조회
            results = collection.get(limit=n_results)
            
            print("=" * 60)
            print("검색 결과")
            print("=" * 60)
            
            for i, (id, doc, meta) in enumerate(zip(results['ids'], results['documents'], results['metadatas']), 1):
                print(f"\n[{i}] ID: {id}")
                print(f"    텍스트: {doc[:150]}..." if len(doc) > 150 else f"    텍스트: {doc}")
                print(f"    메타데이터: {meta}")
            
            print("\n" + "=" * 60)
            
        except Exception as e:
            print(f"[오류] 검색 실패: {e}") # 나중에 삭제 예정

# 메뉴 보여주는 함수
def show_menu():

    # 메뉴 출력
    print("\n" + "=" * 60)
    print("ChromaDB 컬렉션 관리")
    print("=" * 60)
    print("1. 모든 컬렉션 목록 보기")
    print("2. 특정 컬렉션 상세 정보 보기")
    print("3. 특정 컬렉션 삭제")
    print("4. 모든 컬렉션 삭제")
    print("5. 컬렉션에서 데이터 조회")
    print("0. 종료")
    print("=" * 60)

# 메인
def main():

    # 경로 설정 (sourcecode/manage_chromadb 기준)
    base_dir = Path(__file__).parent.parent.parent # councel 폴더
    vector_db_dir = base_dir / "vector_db"
    
    print("=" * 60)
    print("ChromaDB 컬렉션 관리 도구")
    print("=" * 60)
    print(f"Vector DB 경로: {vector_db_dir}\n")
    
    try:
        
        # Vector DB 매니저 초기화
        manager = CollectionManager(str(vector_db_dir))
        
        while True:
            show_menu()
            choice = input("\n선택: ").strip()
            
            if choice == '1':
                # 모든 컬렉션 목록
                manager.list_collections()
            
            elif choice == '2':
                # 특정 컬렉션 상세 정보
                collection_name = input("\n컬렉션 이름 입력: ").strip()
                if collection_name:
                    manager.get_collection_details(collection_name)
            
            elif choice == '3':
                # 특정 컬렉션 삭제
                collection_name = input("\n삭제할 컬렉션 이름 입력: ").strip()
                if collection_name:
                    manager.delete_collection(collection_name)
            
            elif choice == '4':
                # 모든 컬렉션 삭제
                manager.delete_all_collections()
            
            elif choice == '5':
                # 데이터 조회
                collection_name = input("\n컬렉션 이름 입력: ").strip()
                if collection_name:
                    n_results = input("조회할 항목 수 (기본 5): ").strip()
                    n_results = int(n_results) if n_results.isdigit() else 5
                    
                    collection = manager.client.get_collection(name=collection_name)
                    results = collection.get(limit=n_results)
                    
                    print("\n" + "=" * 60)
                    print(f"컬렉션 '{collection_name}' 데이터 조회")
                    print("=" * 60)
                    
                    for i, (id, doc, meta) in enumerate(zip(results['ids'], results['documents'], results['metadatas']), 1):
                        print(f"\n[{i}] ID: {id}")
                        print(f"    텍스트: {doc[:150]}..." if len(doc) > 150 else f"    텍스트: {doc}")
                        print(f"    메타데이터: {meta}")
                    
                    print("\n" + "=" * 60)
            
            elif choice == '0':
                print("\n프로그램을 종료합니다.")
                break
            
            else:
                print("\n[오류] 잘못된 선택입니다. 다시 선택해주세요.")
    
    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다.") 
    
    except Exception as e: 
        print(f"\n[오류] 예상치 못한 오류 발생: {e}") # 나중에 삭제 예정
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

