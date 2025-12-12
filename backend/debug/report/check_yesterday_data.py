"""
전날 데이터 확인 스크립트

DB에 전날 데이터가 있는지 확인하고, 문제를 진단합니다.
"""
import sys
import os
from datetime import date, timedelta
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

from app.infrastructure.database.session import SessionLocal
from app.domain.report.daily.models import DailyReport
from app.domain.report.daily.repository import DailyReportRepository


def main():
    """전날 데이터 확인"""
    db = SessionLocal()
    
    try:
        owner = "김보험"
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        print(f"🔍 전날 데이터 확인")
        print(f"   오늘: {today}")
        print(f"   전날: {yesterday}")
        print(f"   Owner: {owner}")
        print()
        
        # 1. 전날 데이터 확인
        yesterday_report = DailyReportRepository.get_by_owner_and_date(
            db, owner, yesterday
        )
        
        if yesterday_report:
            print(f"✅ 전날({yesterday}) 데이터 발견!")
            print(f"   ID: {yesterday_report.id}")
            print(f"   날짜: {yesterday_report.date}")
            print(f"   Owner: {yesterday_report.owner}")
            
            # report_json 확인
            if yesterday_report.report_json:
                report_json = yesterday_report.report_json
                issues = report_json.get("issues", [])
                metadata = report_json.get("metadata", {})
                next_plan = metadata.get("next_plan", [])
                tasks = report_json.get("tasks", [])
                
                print(f"   미종결 업무: {len(issues)}개")
                for i, issue in enumerate(issues[:3], 1):
                    print(f"     {i}. {issue}")
                
                print(f"   익일 계획: {len(next_plan) if isinstance(next_plan, list) else 1}개")
                if isinstance(next_plan, list):
                    for i, plan in enumerate(next_plan[:3], 1):
                        print(f"     {i}. {plan}")
                elif next_plan:
                    print(f"     {next_plan}")
                
                print(f"   업무: {len(tasks)}개")
        else:
            print(f"❌ 전날({yesterday}) 데이터 없음")
            print()
            
            # 2. 최근 데이터 확인
            print(f"🔍 최근 데이터 확인 (최대 7일 전까지)...")
            recent_reports = DailyReportRepository.list_by_owner(
                db, owner, skip=0, limit=10
            )
            
            if recent_reports:
                print(f"✅ 최근 데이터 {len(recent_reports)}개 발견:")
                for report in recent_reports[:5]:
                    days_ago = (today - report.date).days
                    print(f"   - {report.date} ({days_ago}일 전)")
                
                # 가장 가까운 데이터 찾기
                closest = None
                for report in recent_reports:
                    if report.date < today:
                        if closest is None or report.date > closest.date:
                            closest = report
                
                if closest:
                    print(f"\n✅ 가장 가까운 데이터: {closest.date} ({(today - closest.date).days}일 전)")
                else:
                    print(f"\n❌ 오늘 이전 데이터 없음")
            else:
                print(f"❌ 최근 데이터도 없음")
                print()
                
                # 3. 전체 데이터 확인
                total_count = DailyReportRepository.count_by_owner(db, owner)
                print(f"📊 {owner}의 전체 보고서 개수: {total_count}개")
                
                if total_count == 0:
                    print(f"\n⚠️  {owner}의 보고서가 하나도 없습니다!")
                    print(f"   bulk_daily_ingest.py를 실행하여 데이터를 먼저 저장하세요.")
    
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

