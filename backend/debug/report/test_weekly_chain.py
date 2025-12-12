"""
Weekly Chain 테스트 스크립트

주간 보고서 자동 생성 테스트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from datetime import date
from app.infrastructure.database.session import SessionLocal
from app.domain.report.weekly.chain import generate_weekly_report
from app.domain.report.weekly.repository import WeeklyReportRepository
from app.domain.report.weekly.schemas import WeeklyReportCreate


def test_weekly_chain():
    """주간 보고서 생성 테스트"""
    print("=" * 60)
    print("📊 Weekly Report Chain 테스트 시작")
    print("=" * 60)
    
    # 테스트 파라미터
    owner = "김보험"
    target_date = date(2025, 1, 20)  # 2025년 1월 20일 (월요일)
    
    print(f"\n🔍 테스트 파라미터:")
    print(f"  - 작성자: {owner}")
    print(f"  - 기준 날짜: {target_date}")
    
    # DB 세션
    db = SessionLocal()
    
    try:
        # 1. 주간 보고서 생성
        print(f"\n📝 주간 보고서 생성 중...")
        report = generate_weekly_report(
            db=db,
            owner=owner,
            target_date=target_date
        )
        
        print(f"\n✅ 주간 보고서 생성 완료!")
        print(f"  - Report ID: {report.report_id}")
        print(f"  - Report Type: {report.report_type}")
        print(f"  - Owner: {report.owner}")
        print(f"  - Period: {report.period_start} ~ {report.period_end}")
        print(f"  - Tasks: {len(report.tasks)}개")
        print(f"  - KPIs: {len(report.kpis)}개")
        print(f"  - Issues: {len(report.issues)}개")
        print(f"  - Plans: {len(report.plans)}개")
        print(f"\n📊 Metadata:")
        for key, value in report.metadata.items():
            print(f"  - {key}: {value}")
        
        # 2. DB에 저장
        print(f"\n💾 DB에 저장 중...")
        report_dict = report.model_dump(mode='json')
        report_create = WeeklyReportCreate(
            owner=report.owner,
            period_start=report.period_start,
            period_end=report.period_end,
            report_json=report_dict
        )
        
        db_report, is_created = WeeklyReportRepository.create_or_update(
            db, report_create
        )
        
        action = "생성" if is_created else "업데이트"
        print(f"✅ DB 저장 완료 ({action})")
        print(f"  - DB Record ID: {db_report.id}")
        
        # 3. 저장된 데이터 확인
        print(f"\n🔍 저장된 보고서 조회...")
        saved_reports = WeeklyReportRepository.list_by_owner(db, owner, limit=5)
        print(f"✅ {owner}의 주간 보고서: {len(saved_reports)}개")
        
        for idx, saved_report in enumerate(saved_reports[:3], 1):
            print(f"  {idx}. {saved_report.period_start} ~ {saved_report.period_end}")
        
        print(f"\n{'=' * 60}")
        print(f"✅ 모든 테스트 완료!")
        print(f"{'=' * 60}")
        
    except ValueError as e:
        print(f"\n❌ 에러: {e}")
        print(f"💡 해당 기간에 일일보고서가 없습니다. 먼저 일일보고서를 생성해주세요.")
    
    except Exception as e:
        print(f"\n❌ 예상치 못한 에러: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    test_weekly_chain()

