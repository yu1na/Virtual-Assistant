"""
임시 세션 정리 스크립트

삭제되지 않고 남아있는 임시 세션 데이터를 정리합니다.
"""

from session_manager import SessionManager
from ephemeral_rag import EphemeralRAG
from pathlib import Path
import chromadb


def cleanup_all_sessions():
    """모든 임시 세션 정리"""
    
    print("=" * 60)
    print("🧹 임시 세션 정리")
    print("=" * 60)
    
    # 1. Ephemeral 디렉토리의 세션 폴더 확인
    current_file = Path(__file__).resolve()
    module_dir = current_file.parent
    ephemeral_dir = module_dir / "data" / "ephemeral"
    
    if not ephemeral_dir.exists():
        print("\n✅ 정리할 세션이 없습니다.")
        return
    
    session_folders = [f for f in ephemeral_dir.iterdir() if f.is_dir()]
    
    if not session_folders:
        print("\n✅ 정리할 세션이 없습니다.")
        return
    
    print(f"\n📁 발견된 세션 폴더: {len(session_folders)}개\n")
    
    # 2. ChromaDB 클라이언트 초기화
    chroma_dir = module_dir / "data" / "chroma"
    chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
    
    # 3. 각 세션 정리
    for folder in session_folders:
        session_id = folder.name
        print(f"\n🗑️  세션 정리: {session_id}")
        
        # ChromaDB 컬렉션 이름 생성
        collection_name = f"ephemeral_session_{session_id.replace('-', '_')}"
        
        try:
            # ChromaDB 컬렉션 삭제
            chroma_client.delete_collection(name=collection_name)
            print(f"   ✅ ChromaDB 컬렉션 삭제: {collection_name}")
        except Exception as e:
            print(f"   ⚠️  ChromaDB 컬렉션 삭제 실패 (이미 삭제됨?): {e}")
        
        try:
            # 세션 폴더 삭제
            import shutil
            shutil.rmtree(folder)
            print(f"   ✅ 세션 폴더 삭제: {folder}")
        except Exception as e:
            print(f"   ⚠️  세션 폴더 삭제 실패: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 정리 완료!")
    print("=" * 60)


if __name__ == "__main__":
    cleanup_all_sessions()

