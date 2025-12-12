"""
Bulk Daily Report Ingestion Script

backend/Data/mock_reports/daily 폴더의 모든 txt 파일을 읽어서
PostgreSQL의 daily_reports 테이블에 저장하는 스크립트

Usage:
    python backend/tools/bulk_daily_ingest.py
"""
import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# 프로젝트 루트를 Python path에 추가
backend_dir = Path(__file__).resolve().parent.parent  # backend/
project_root = backend_dir.parent  # Virtual-Assistant 루트
sys.path.insert(0, str(project_root))  # tools 모듈 import를 위해 프로젝트 루트 추가
sys.path.insert(0, str(backend_dir))  # app 모듈 import를 위해 backend 추가

# 환경 변수 로드 (config 설정을 위해 필요)
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")
report_env = backend_dir / ".env.report"
if report_env.exists():
    load_dotenv(report_env, override=False)

from app.infrastructure.database.session import SessionLocal
from app.domain.report.daily.repository import DailyReportRepository
from app.domain.report.daily.schemas import DailyReportCreate
from app.domain.report.core.canonical_models import CanonicalReport, CanonicalDaily, DetailTask
import uuid


def parse_time_range(time_str: str) -> tuple[Optional[str], Optional[str]]:
    """
    시간 범위 문자열을 파싱하여 (start, end) 튜플 반환
    
    예: "09:00 - 10:00" -> ("09:00", "10:00")
    
    Args:
        time_str: 시간 범위 문자열
        
    Returns:
        (time_start, time_end) 튜플
    """
    if not time_str or time_str.strip() == "":
        return (None, None)
    
    # "09:00 - 10:00" 패턴 매칭
    match = re.match(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', time_str.strip())
    if match:
        return (match.group(1), match.group(2))
    
    # 단일 시간만 있는 경우 (예: "09:00")
    match = re.match(r'(\d{1,2}:\d{2})', time_str.strip())
    if match:
        return (match.group(1), None)
    
    return (None, None)


def parse_date(date_str: str) -> date:
    """
    날짜 문자열을 date 객체로 변환
    
    예: "2025-01-02" -> date(2025, 1, 2)
    
    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD)
        
    Returns:
        date 객체
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"날짜 형식 오류: {date_str}. YYYY-MM-DD 형식이어야 합니다. ({e})")


def convert_to_canonical_report(raw_json: Dict[str, Any], owner: str) -> CanonicalReport:
    """
    Raw JSON을 CanonicalReport로 변환
    
    Args:
        raw_json: 원본 JSON 딕셔너리
        owner: 호출 컨텍스트에서 전달된 owner (문서에서 읽지 않음)
        
    Returns:
        CanonicalReport 객체
    """
    owner = (owner or "").strip()
    if not owner:
        raise ValueError("owner is required for ingestion (cannot be read from document).")

    # 1. 기본 정보 추출
    작성일자 = raw_json["상단정보"]["작성일자"]
    
    period_date = parse_date(작성일자)
    
    # 2. 헤더 정보
    header = {
        "작성일자": 작성일자,
        "성명": owner
    }
    
    # 3. todo_tasks (금일_진행_업무)
    todo_tasks = []
    금일진행업무 = raw_json.get("금일_진행_업무", "")
    if 금일진행업무:
        if isinstance(금일진행업무, list):
            todo_tasks = 금일진행업무
        else:
            todo_tasks = [금일진행업무] if 금일진행업무.strip() else []
    
    # 4. detail_tasks (세부업무)
    detail_tasks = []
    세부업무 = raw_json.get("세부업무", [])
    for task_data in 세부업무:
        업무내용 = task_data.get("업무내용", "")
        if not 업무내용 or not 업무내용.strip():
            continue
        
        time_str = task_data.get("시간", "")
        time_start, time_end = parse_time_range(time_str)
        
        detail_task = DetailTask(
            time_start=time_start,
            time_end=time_end,
            text=업무내용,
            note=task_data.get("비고", "")
        )
        detail_tasks.append(detail_task)
    
    # 5. pending (미종결_업무사항)
    pending = []
    미종결 = raw_json.get("미종결_업무사항", "")
    if 미종결:
        if isinstance(미종결, list):
            pending = 미종결
        else:
            pending = [미종결] if 미종결.strip() else []
    
    # 6. plans (익일_업무계획)
    plans = []
    익일계획 = raw_json.get("익일_업무계획", "")
    if 익일계획:
        if isinstance(익일계획, list):
            plans = 익일계획
        else:
            plans = [익일계획] if 익일계획.strip() else []
    
    # 7. notes (특이사항) - notes와 summary 모두 설정
    notes = raw_json.get("특이사항", "") or ""
    summary = raw_json.get("특이사항", "") or ""  # 특이사항을 summary로도 사용
    
    # 8. CanonicalDaily 생성
    canonical_daily = CanonicalDaily(
        header=header,
        todo_tasks=todo_tasks,
        detail_tasks=detail_tasks,
        pending=pending,
        plans=plans,
        notes=notes,
        summary=summary
    )
    
    # 9. CanonicalReport 생성
    report = CanonicalReport(
        report_id=str(uuid.uuid4()),
        report_type="daily",
        owner=owner,  # owner 파라미터 사용
        period_start=period_date,
        period_end=period_date,
        daily=canonical_daily
    )
    
    return report


def read_json_objects_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    txt 파일에서 여러 JSON 객체를 읽어서 리스트로 반환
    
    각 JSON 객체는 빈 줄로 구분됨
    
    Args:
        file_path: txt 파일 경로
        
    Returns:
        JSON 객체 리스트
    """
    json_objects = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 빈 줄로 분리된 JSON 객체들을 추출
        # 중괄호로 시작하고 끝나는 패턴 찾기
        json_texts = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        
        for json_text in json_texts:
            try:
                obj = json.loads(json_text)
                json_objects.append(obj)
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 파싱 오류 ({file_path.name}): {e}")
                continue
    
    except Exception as e:
        print(f"❌ 파일 읽기 오류 ({file_path}): {e}")
    
    return json_objects


def find_all_txt_files(base_dir: Path, year: Optional[int] = None, month: Optional[int] = None) -> List[Path]:
    """
    base_dir 하위의 txt 파일 찾기 (날짜 필터링 옵션)
    
    Args:
        base_dir: 기본 디렉토리
        year: 필터링할 연도 (None이면 모든 연도)
        month: 필터링할 월 (None이면 모든 월, 예: 11 = 11월)
        
    Returns:
        txt 파일 경로 리스트
    """
    all_files = list(base_dir.rglob("*.txt"))
    
    # 날짜 필터링이 없으면 모든 파일 반환
    if year is None and month is None:
        return sorted(all_files)
    
    # 날짜 필터링
    filtered_files = []
    for file_path in all_files:
        filename = file_path.stem  # 확장자 제거
        
        try:
            # YYYY-MM-DD 형식 파싱
            parts = filename.split('-')
            if len(parts) >= 3:
                file_year = int(parts[0])
                file_month = int(parts[1])
                
                # 필터링 조건 확인
                if year is not None and file_year != year:
                    continue
                if month is not None and file_month != month:
                    continue
                
                filtered_files.append(file_path)
        except (ValueError, IndexError):
            # 날짜 파싱 실패한 파일은 제외
            continue
    
    return sorted(filtered_files)


def preview_files(year: Optional[int] = None, month: Optional[int] = None):
    """
    파일 미리보기 (DB 저장 없이)
    
    Args:
        year: 필터링할 연도 (None이면 모든 연도)
        month: 필터링할 월 (None이면 모든 월, 예: 11 = 11월)
    """
    print("=" * 70)
    print("👀 Daily Report 파일 미리보기")
    if year or month:
        filter_msg = []
        if year:
            filter_msg.append(f"{year}년")
        if month:
            filter_msg.append(f"{month}월")
        print(f"필터: {' '.join(filter_msg)}")
    print("=" * 70)
    
    # 1. 기본 경로 설정
    base_dir = backend_dir / "Data" / "mock_reports" / "daily"
    
    if not base_dir.exists():
        print(f"❌ 디렉토리가 존재하지 않습니다: {base_dir}")
        return
    
    print(f"\n📁 대상 디렉토리: {base_dir}")
    
    # 2. 모든 txt 파일 찾기
    txt_files = find_all_txt_files(base_dir, year=year, month=month)
    print(f"📄 발견된 txt 파일: {len(txt_files)}개\n")
    
    if not txt_files:
        print("⚠️  txt 파일이 없습니다.")
        return
    
    # 3. 각 폴더별 파일 통계
    folder_stats = {}
    total_json_count = 0
    
    for file_path in txt_files:
        folder_name = file_path.parent.name
        
        # JSON 객체 수 확인
        json_objects = read_json_objects_from_file(file_path)
        json_count = len(json_objects)
        total_json_count += json_count
        
        if folder_name not in folder_stats:
            folder_stats[folder_name] = {
                "files": [],
                "total_json": 0
            }
        
        folder_stats[folder_name]["files"].append({
            "name": file_path.name,
            "json_count": json_count
        })
        folder_stats[folder_name]["total_json"] += json_count
    
    # 4. 폴더별 출력
    print("📂 폴더별 파일 목록:\n")
    
    for folder_name in sorted(folder_stats.keys()):
        stats = folder_stats[folder_name]
        print(f"📁 {folder_name}")
        print(f"   ├─ 파일 수: {len(stats['files'])}개")
        print(f"   ├─ 보고서 수: {stats['total_json']}개")
        print(f"   └─ 파일 목록:")
        
        for file_info in stats["files"]:
            print(f"      ├─ {file_info['name']} ({file_info['json_count']}개)")
        
        print()
    
    # 5. 전체 통계
    print("=" * 70)
    print("📊 전체 통계:")
    print(f"   ├─ 폴더 수: {len(folder_stats)}개")
    print(f"   ├─ 파일 수: {len(txt_files)}개")
    print(f"   └─ 총 보고서 수: {total_json_count}개")
    print("=" * 70)
    
    # 6. 샘플 미리보기
    print("\n📖 첫 번째 파일 샘플 미리보기:\n")
    
    if txt_files:
        first_file = txt_files[0]
        json_objects = read_json_objects_from_file(first_file)
        
        if json_objects:
            first_json = json_objects[0]
            print(f"파일: {first_file.name}")
            print(f"작성일자: {first_json.get('상단정보', {}).get('작성일자', 'N/A')}")
            print(f"성명: {first_json.get('상단정보', {}).get('성명', 'N/A')}")
            print(f"세부업무 수: {len(first_json.get('세부업무', []))}개")
            print(f"금일 진행 업무: {first_json.get('금일_진행_업무', 'N/A')[:50]}...")
    
    print("\n" + "=" * 70)
    print("✅ 미리보기 완료!")
    print("\n실행하려면:")
    print("  python backend/tools/bulk_daily_ingest.py")
    print("=" * 70)


def bulk_ingest_daily_reports(year: Optional[int] = None, month: Optional[int] = None, owner: Optional[str] = None):
    """
    메인 함수: 일일보고서를 DB에 저장
    
    Args:
        year: 필터링할 연도 (None이면 모든 연도)
        month: 필터링할 월 (None이면 모든 월, 예: 11 = 11월)
    """
    print("=" * 70)
    print("📊 일일보고서 Bulk Ingestion 시작")
    if year or month:
        filter_msg = []
        if year:
            filter_msg.append(f"{year}년")
        if month:
            filter_msg.append(f"{month}월")
        print(f"필터: {' '.join(filter_msg)}")
    print("=" * 70)

    owner = (owner or os.getenv("REPORT_OWNER") or "").strip()
    if not owner:
        raise ValueError("owner is required (set --owner or REPORT_OWNER env).")
    
    # 1. 기본 경로 설정
    base_dir = backend_dir / "Data" / "mock_reports" / "daily"
    
    if not base_dir.exists():
        print(f"❌ 디렉토리가 존재하지 않습니다: {base_dir}")
        return
    
    print(f"\n📁 대상 디렉토리: {base_dir}")
    
    # 2. txt 파일 찾기 (날짜 필터링 적용)
    txt_files = find_all_txt_files(base_dir, year=year, month=month)
    print(f"📄 발견된 txt 파일: {len(txt_files)}개")
    if year or month:
        print(f"   (필터: {year or '모든 연도'}년 {month or '모든 월'}월)")
    
    if not txt_files:
        print("⚠️  txt 파일이 없습니다.")
        return
    
    # 3. DB 세션 생성
    db = SessionLocal()
    
    # 통계
    total_reports = 0
    created_count = 0
    updated_count = 0
    error_count = 0
    
    try:
        # 4. 각 파일 처리 (진행률 표시)
        total_files = len(txt_files)
        print(f"   📄 총 {total_files}개 파일 처리 중...", end="", flush=True)
        
        for file_idx, file_path in enumerate(txt_files, 1):
            # 4-1. 파일에서 JSON 객체들 읽기
            json_objects = read_json_objects_from_file(file_path)
            
            # 4-2. 각 JSON 객체를 CanonicalReport로 변환 후 DB 저장
            for json_obj in json_objects:
                try:
                    # CanonicalReport 변환
                    canonical_report = convert_to_canonical_report(json_obj, owner=owner)
                    
                    # DB 저장 (UPSERT)
                    report_dict = canonical_report.model_dump(mode='json')
                    report_create = DailyReportCreate(
                        owner=canonical_report.owner,
                        report_date=canonical_report.period_start,
                        report_json=report_dict
                    )
                    
                    db_report, is_created = DailyReportRepository.create_or_update(
                        db, report_create
                    )
                    
                    total_reports += 1
                    if is_created:
                        created_count += 1
                    else:
                        updated_count += 1
                
                except Exception as e:
                    error_count += 1
                    continue
            
            # 진행률 표시 (10% 단위)
            if file_idx % max(1, total_files // 10) == 0 or file_idx == total_files:
                progress = int((file_idx / total_files) * 100)
                print(f"\r   📄 진행률: {progress}% ({file_idx}/{total_files})", end="", flush=True)
        
        print()  # 줄바꿈
        
        # 5. 결과 출력 (간략하게)
        if error_count > 0:
            print(f"   📊 결과: 생성 {created_count}개, 업데이트 {updated_count}개, 에러 {error_count}개")
        else:
            print(f"   📊 결과: 생성 {created_count}개, 업데이트 {updated_count}개")
        
    except Exception as e:
        print(f"\n❌ 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="일일보고서 Bulk Ingestion 스크립트")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="미리보기 모드 (DB 저장하지 않음)"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="필터링할 연도 (예: 2025)"
    )
    parser.add_argument(
        "--month",
        type=int,
        help="필터링할 월 (예: 11)"
    )
    parser.add_argument(
        "--owner",
        type=str,
        help="ingestion 시 사용할 owner (미지정 시 REPORT_OWNER 환경변수 사용)"
    )
    
    args = parser.parse_args()
    
    if args.preview:
        # 미리보기 모드
        preview_files(year=args.year, month=args.month)
    else:
        # 실제 저장 모드
        bulk_ingest_daily_reports(year=args.year, month=args.month, owner=args.owner)

