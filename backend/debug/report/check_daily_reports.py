"""
일일 보고서 데이터 검증 및 디버깅 스크립트

1. 로컬 txt 파일들의 작성일자 최소/최대 날짜 계산
2. Chroma Cloud daily_reports 컬렉션에서 2025-10-01 이후 데이터 확인
3. ingestion 스크립트 처리 경로 확인

사용법:
    python -m debug.report.check_daily_reports
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# .env 파일 로드
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass
except Exception:
    pass

from ingestion.chroma_client import get_chroma_service


# ========================================
# 설정
# ========================================
DATA_DIR = project_root / "Data" / "mock_reports" / "daily"
COLLECTION_NAME = "daily_reports"


# ========================================
# JSON 파싱 함수 (ingest_daily_reports.py와 동일)
# ========================================
def parse_multi_json_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    txt 파일에서 여러 개의 JSON 객체를 파싱
    
    Args:
        file_path: txt 파일 경로
        
    Returns:
        파싱된 JSON 객체 리스트
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 정규식으로 JSON 객체 블록 추출
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    json_strings = re.findall(json_pattern, content, re.DOTALL)
    
    parsed_objects = []
    
    for idx, json_str in enumerate(json_strings):
        try:
            obj = json.loads(json_str)
            parsed_objects.append(obj)
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 파싱 오류 (인덱스 {idx}): {e}")
            continue
    
    return parsed_objects


# ========================================
# 1. 로컬 파일 날짜 분석
# ========================================
def analyze_local_dates() -> Dict[str, Any]:
    """
    로컬 txt 파일들을 스캔하여 작성일자 최소/최대 날짜 계산
    
    Returns:
        {
            "min_date": "YYYY-MM-DD",
            "max_date": "YYYY-MM-DD",
            "total_days": int,
            "total_reports": int,
            "date_set": set of date strings,
            "files_processed": int
        }
    """
    print("=" * 80)
    print("📊 1. 로컬 txt 파일 날짜 분석")
    print("=" * 80)
    print()
    
    if not DATA_DIR.exists():
        print(f"❌ 경로가 존재하지 않습니다: {DATA_DIR}")
        return {}
    
    # 모든 txt 파일 찾기
    txt_files = list(DATA_DIR.rglob("*.txt"))
    print(f"📁 발견된 txt 파일 수: {len(txt_files)}개")
    print()
    
    dates = []
    date_set = set()
    total_reports = 0
    files_processed = 0
    
    # 각 파일 처리
    for txt_file in sorted(txt_files):
        relative_path = txt_file.relative_to(DATA_DIR)
        month_folder = relative_path.parts[0] if len(relative_path.parts) > 1 else ""
        
        try:
            json_objects = parse_multi_json_file(txt_file)
            
            if not json_objects:
                continue
            
            files_processed += 1
            total_reports += len(json_objects)
            
            # 각 JSON 객체에서 작성일자 추출
            for obj in json_objects:
                try:
                    # 상단정보.작성일자 추출
                    상단정보 = obj.get("상단정보", {})
                    작성일자_str = 상단정보.get("작성일자", "")
                    
                    if 작성일자_str:
                        # 날짜 파싱
                        try:
                            date_obj = datetime.strptime(작성일자_str, "%Y-%m-%d").date()
                            dates.append(date_obj)
                            date_set.add(작성일자_str)
                        except ValueError:
                            print(f"⚠️  날짜 파싱 실패: {작성일자_str} (파일: {relative_path})")
                except Exception as e:
                    print(f"⚠️  JSON 객체 처리 오류 (파일: {relative_path}): {e}")
        
        except Exception as e:
            print(f"❌ 파일 처리 오류 ({relative_path}): {e}")
    
    if not dates:
        print("❌ 날짜 데이터를 찾을 수 없습니다.")
        return {}
    
    min_date = min(dates)
    max_date = max(dates)
    total_days = len(date_set)
    
    result = {
        "min_date": min_date.isoformat(),
        "max_date": max_date.isoformat(),
        "total_days": total_days,
        "total_reports": total_reports,
        "date_set": date_set,
        "files_processed": files_processed
    }
    
    print(f"✅ 처리 완료")
    print(f"   - 처리된 파일 수: {files_processed}개")
    print(f"   - 총 보고서 수: {total_reports}개")
    print(f"   - 최소 날짜: {result['min_date']}")
    print(f"   - 최대 날짜: {result['max_date']}")
    print(f"   - 고유 날짜 수: {total_days}일")
    print()
    
    return result


# ========================================
# 2. Chroma Cloud 데이터 확인
# ========================================
def check_chroma_data(cutoff_date: str = "2025-10-01") -> Dict[str, Any]:
    """
    Chroma Cloud daily_reports 컬렉션에서 특정 날짜 이후 데이터 확인
    
    Args:
        cutoff_date: 기준 날짜 (YYYY-MM-DD)
        
    Returns:
        {
            "found": bool,
            "count": int,
            "samples": List[Dict]
        }
    """
    print("=" * 80)
    print(f"📊 2. Chroma Cloud 데이터 확인 (date >= {cutoff_date})")
    print("=" * 80)
    print()
    
    try:
        chroma_service = get_chroma_service()
        collection = chroma_service.get_or_create_collection(name=COLLECTION_NAME)
        
        print(f"✅ 컬렉션 '{COLLECTION_NAME}' 연결 완료")
        print(f"📦 현재 문서 수: {collection.count()}개")
        print()
        
        # Chroma는 문자열 날짜 비교를 지원하지 않으므로, 
        # 데이터를 가져와서 Python에서 필터링
        print(f"🔍 날짜 >= {cutoff_date} 조건으로 데이터 조회 중...")
        print(f"   (Chroma는 문자열 날짜 비교를 지원하지 않아 모든 데이터를 가져온 후 필터링합니다)")
        
        try:
            total_count = collection.count()
            print(f"   전체 문서 수: {total_count}개")
            
            # 전체 데이터 가져오기 (날짜 필터링을 위해)
            # 배치로 가져오는 것이 더 효율적이지만, 디버깅 목적으로는 전체를 가져옴
            print(f"   전체 데이터 조회 중... (시간이 걸릴 수 있습니다)")
            results = collection.get()
            
            # Python에서 날짜 필터링 및 최대 날짜 찾기
            ids = results.get("ids", [])
            metadatas = results.get("metadatas", [])
            documents = results.get("documents", [])
            
            filtered_indices = []
            all_dates = []
            
            for i, metadata in enumerate(metadatas):
                date_str = metadata.get("date", "")
                if date_str:
                    all_dates.append(date_str)
                    if date_str >= cutoff_date:
                        filtered_indices.append(i)
            
            # 최대/최소 날짜 계산
            max_date = max(all_dates) if all_dates else None
            min_date = min(all_dates) if all_dates else None
            
            # 샘플 5개만 선택
            sample_indices = filtered_indices[:5]
            count = len(filtered_indices)
            
            result = {
                "found": count > 0,
                "count": count,
                "total_checked": total_count,
                "max_date": max_date,
                "min_date": min_date,
                "samples": []
            }
            
            print(f"   Chroma 데이터 날짜 범위: {min_date} ~ {max_date}")
            print()
            
            if count > 0:
                print(f"✅ {count}개 문서 발견 (전체 {total_count}개 중)")
                print()
                
                # 샘플 데이터 출력
                for idx, i in enumerate(sample_indices):
                    print(f"📄 샘플 {idx + 1}:")
                    print(f"   - ID: {ids[i]}")
                    if metadatas and i < len(metadatas):
                        metadata = metadatas[i]
                        print(f"   - 날짜: {metadata.get('date', 'N/A')}")
                        print(f"   - 월: {metadata.get('month', 'N/A')}")
                        print(f"   - 소스 파일: {metadata.get('source_file', 'N/A')}")
                    
                    result["samples"].append({
                        "id": ids[i],
                        "metadata": metadatas[i] if metadatas and i < len(metadatas) else {},
                        "document_preview": documents[i][:100] + "..." if documents and i < len(documents) else ""
                    })
                    print()
                
                if count > 5:
                    print(f"   ... 외 {count - 5}개 더 있음")
                    print()
            else:
                print(f"❌ 조건에 맞는 문서가 없습니다. (전체 {total_count}개 확인)")
                print()
            
            return result
            
        except Exception as e:
            print(f"❌ 쿼리 오류: {e}")
            print()
            return {"found": False, "count": 0, "samples": [], "error": str(e)}
    
    except Exception as e:
        print(f"❌ Chroma Cloud 연결 오류: {e}")
        print()
        return {"found": False, "count": 0, "samples": [], "error": str(e)}


# ========================================
# 3. Ingestion 스크립트 경로 확인
# ========================================
def check_ingestion_paths() -> Dict[str, Any]:
    """
    ingestion 스크립트가 처리하는 파일 경로 확인
    
    Returns:
        {
            "total_files": int,
            "folders": List[str],
            "sample_files": List[str]
        }
    """
    print("=" * 80)
    print("📊 3. Ingestion 스크립트 처리 경로 확인")
    print("=" * 80)
    print()
    
    if not DATA_DIR.exists():
        print(f"❌ 경로가 존재하지 않습니다: {DATA_DIR}")
        return {}
    
    # 모든 txt 파일 찾기 (ingest_daily_reports.py와 동일한 방식)
    txt_files = list(DATA_DIR.rglob("*.txt"))
    
    # 폴더별로 그룹화
    folders = {}
    for txt_file in sorted(txt_files):
        relative_path = txt_file.relative_to(DATA_DIR)
        month_folder = relative_path.parts[0] if len(relative_path.parts) > 1 else ""
        
        if month_folder not in folders:
            folders[month_folder] = []
        folders[month_folder].append(str(relative_path))
    
    result = {
        "total_files": len(txt_files),
        "folders": sorted(folders.keys()),
        "sample_files": []
    }
    
    print(f"✅ 총 {len(txt_files)}개 파일 발견")
    print(f"📁 폴더 수: {len(folders)}개")
    print()
    print("📂 폴더별 파일 목록:")
    for folder in sorted(folders.keys()):
        files = folders[folder]
        print(f"   - {folder}: {len(files)}개 파일")
        result["sample_files"].extend(files[:3])  # 각 폴더에서 최대 3개만 샘플로 저장
    
    print()
    
    # 9월 이후 폴더 확인
    print("🔍 9월 이후 폴더 확인:")
    september_folders = []
    for folder in sorted(folders.keys()):
        # "2025년 9월" 이후인지 확인
        if "2025년 9월" in folder or "2025년 10월" in folder or "2025년 11월" in folder or "2025년 12월" in folder:
            # 숫자로 비교
            try:
                # "2025년 9월" -> 202509
                year_month = folder.replace("년", "").replace("월", "").replace(" ", "")
                if "2025" in year_month:
                    month_num = int(year_month.replace("2025", ""))
                    if month_num >= 9:
                        september_folders.append(folder)
                        print(f"   ✅ {folder}: {len(folders[folder])}개 파일")
            except:
                pass
    
    if not september_folders:
        print("   ⚠️  9월 이후 폴더를 찾을 수 없습니다.")
    
    print()
    
    return result


# ========================================
# 메인 함수
# ========================================
def main():
    """메인 실행 함수"""
    print()
    print("=" * 80)
    print("🔍 일일 보고서 데이터 검증 및 디버깅")
    print("=" * 80)
    print()
    
    # 1. 로컬 파일 날짜 분석
    local_result = analyze_local_dates()
    
    # 2. Chroma Cloud 데이터 확인
    chroma_result = check_chroma_data(cutoff_date="2025-10-01")
    
    # 3. Ingestion 경로 확인
    path_result = check_ingestion_paths()
    
    # 4. 종합 분석
    print("=" * 80)
    print("📊 종합 분석 결과")
    print("=" * 80)
    print()
    
    if local_result:
        print(f"📅 로컬 데이터:")
        print(f"   - 최소 날짜: {local_result['min_date']}")
        print(f"   - 최대 날짜: {local_result['max_date']}")
        print(f"   - 고유 날짜 수: {local_result['total_days']}일")
        print()
    
    if chroma_result:
        print(f"☁️  Chroma Cloud 데이터:")
        if chroma_result.get("max_date"):
            print(f"   - 최소 날짜: {chroma_result.get('min_date', 'N/A')}")
            print(f"   - 최대 날짜: {chroma_result.get('max_date', 'N/A')}")
        if chroma_result.get("found"):
            print(f"   - 2025-10-01 이후 데이터: {chroma_result['count']}개 발견")
        else:
            print(f"   - 2025-10-01 이후 데이터: 없음")
        print()
    
    # 날짜 비교
    if local_result and chroma_result:
        local_max = local_result.get("max_date", "")
        chroma_max = chroma_result.get("max_date", "")
        chroma_found = chroma_result.get("found", False)
        
        if local_max and chroma_max:
            if local_max > chroma_max:
                print("⚠️  경고:")
                print(f"   - 로컬 데이터 최대 날짜: {local_max}")
                print(f"   - Chroma 데이터 최대 날짜: {chroma_max}")
                print(f"   - 로컬에 더 최신 데이터가 있습니다.")
                print(f"   - 데이터 동기화가 필요할 수 있습니다.")
                print()
            elif not chroma_found and local_max >= "2025-10-01":
                print("⚠️  경고:")
                print(f"   - 로컬 데이터 최대 날짜: {local_max}")
                print(f"   - Chroma에는 2025-10-01 이후 데이터가 없음")
                print(f"   - 데이터 동기화가 필요할 수 있습니다.")
                print()
    
    print("=" * 80)
    print("✅ 검증 완료")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()

