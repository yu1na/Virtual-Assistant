"""
보고서 모듈 초기화

ChromaDB에 보고서 데이터가 없으면 자동으로 목업 데이터를 로드합니다.
이미 있으면 스킵합니다.
"""

import os
import subprocess
import sys
from pathlib import Path

# 프로젝트 루트 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/


def check_chromadb_has_data() -> bool:
    """
    ChromaDB reports 컬렉션에 데이터가 있는지 확인
    
    Returns:
        bool: 데이터가 있으면 True, 없거나 확인 실패하면 False
    """
    try:
        from app.infrastructure.vector_store_report import get_report_vector_store
        
        vector_store = get_report_vector_store()
        collection = vector_store.get_collection()
        count = collection.count()
        
        return count > 0
    except Exception as e:
        print(f"   ⚠️  ChromaDB 확인 실패: {e}")
        return False


def run_ingestion() -> bool:
    """
    ingestion 모듈 실행 (ChromaDB + PostgreSQL)
    
    Returns:
        bool: 성공 여부
    """
    try:
        # REPORT_OWNER 환경변수 설정 (기본값: "김준경")
        env = os.environ.copy()
        if "REPORT_OWNER" not in env or not env["REPORT_OWNER"]:
            env["REPORT_OWNER"] = "김준경"
        
        # Python 실행 경로
        python_exe = sys.executable
        project_root = BASE_DIR.parent  # Virtual-Assistant 루트
        env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
        
        # 1. ChromaDB ingestion
        print("   🔄 ChromaDB 로드 중...", end="", flush=True)
        result1 = subprocess.run(
            [python_exe, "-m", "ingestion.ingest_mock_reports"],
            cwd=str(BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        
        if result1.returncode != 0:
            print(" ❌ 실패")
            if result1.stderr:
                # 에러만 간단히 표시
                error_lines = [line.strip() for line in result1.stderr.strip().split('\n') if line.strip()]
                if error_lines:
                    print(f"      오류: {error_lines[-1]}")
            return False
        
        # 성공 메시지에서 문서 수 추출
        if result1.stdout:
            lines = result1.stdout.strip().split('\n')
            doc_count = "?"
            for line in lines:
                if "Collection now has" in line:
                    # "Collection now has 1377 documents." 형식에서 숫자 추출
                    import re
                    match = re.search(r'(\d+) documents', line)
                    if match:
                        doc_count = match.group(1)
                    break
            print(f" ✅ 완료 ({doc_count}개 문서)")
        else:
            print(" ✅ 완료")
        
        # 2. PostgreSQL ingestion
        print("   🔄 PostgreSQL 로드 중...", end="", flush=True)
        bulk_ingest_script = BASE_DIR / "tools" / "bulk_daily_ingest.py"
        
        result2 = subprocess.run(
            [python_exe, str(bulk_ingest_script)],
            cwd=str(project_root),  # 프로젝트 루트에서 실행
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        
        if result2.returncode != 0:
            print(" ⚠️  실패")
            if result2.stderr:
                error_lines = [line.strip() for line in result2.stderr.strip().split('\n') if line.strip()]
                if error_lines:
                    print(f"      오류: {error_lines[-1]}")
            # ChromaDB는 성공했으므로 부분 성공으로 처리
            return True
        
        # 성공 메시지에서 결과 추출
        if result2.stdout:
            lines = result2.stdout.strip().split('\n')
            created = "?"
            updated = "?"
            errors = "0"
            for line in lines:
                if "생성:" in line:
                    import re
                    match = re.search(r'생성:\s*(\d+)', line)
                    if match:
                        created = match.group(1)
                if "업데이트:" in line:
                    import re
                    match = re.search(r'업데이트:\s*(\d+)', line)
                    if match:
                        updated = match.group(1)
                if "에러:" in line:
                    import re
                    match = re.search(r'에러:\s*(\d+)', line)
                    if match:
                        errors = match.group(1)
            
            if errors != "0":
                print(f" ✅ 완료 (생성: {created}, 업데이트: {updated}, 에러: {errors})")
            else:
                print(f" ✅ 완료 (생성: {created}, 업데이트: {updated})")
        else:
            print(" ✅ 완료")
        
        return True
            
    except Exception as e:
        print(f"   ❌ Ingestion 실행 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def init_reports() -> bool:
    """
    보고서 RAG 초기화
    
    - ChromaDB 컬렉션이 비어있으면: ingestion 실행
    - 이미 데이터가 있으면: 스킵
    
    Returns:
        bool: 성공 여부
    """
    print("\n📊 [보고서] RAG 초기화 체크...")
    
    # 1. ChromaDB 데이터 확인
    try:
        has_data = check_chromadb_has_data()
        
        if has_data:
            print("   ✅ 이미 데이터 존재 - 스킵")
            return True
        else:
            print("   📝 데이터 없음 - Ingestion 시작")
    except Exception as e:
        print(f"   ⚠️  ChromaDB 확인 실패, Ingestion 실행: {e}")
        # 확인 실패 시에도 ingestion 실행 (fallback)
    
    # 2. Ingestion 실행
    print("   🔄 목업 데이터 로드 중...")
    success = run_ingestion()
    
    if success:
        print("   ✅ 보고서 RAG 초기화 완료")
        return True
    else:
        print("   ⚠️  보고서 RAG 초기화 실패")
        return False


# 직접 실행 테스트
if __name__ == "__main__":
    success = init_reports()
    print(f"\n결과: {'성공' if success else '실패'}")

