"""
PDF Export API

pdfkit (wkhtmltopdf)를 사용한 서버 측 PDF 생성 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Literal
from datetime import date as date_type

from app.infrastructure.database.session import get_db
from app.domain.report.daily.repository import DailyReportRepository
from app.domain.report.weekly.repository import WeeklyReportRepository
from app.domain.report.monthly.repository import MonthlyReportRepository
from app.domain.report.core.canonical_models import CanonicalReport
from app.reporting.html_renderer import get_html_renderer
from app.domain.report.monthly.kpi_calculator import calculate_monthly_kpi
# pdfkit (wkhtmltopdf 래퍼) 사용
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False
    pdfkit = None
    print("⚠️ pdfkit이 설치되지 않았습니다. pip install pdfkit를 실행해주세요.")
    print("💡 또한 wkhtmltopdf 바이너리가 시스템에 설치되어 있어야 합니다.")

from io import BytesIO

router = APIRouter(prefix="/reports", tags=["pdf-export"])


@router.get("/daily/pdf")
async def generate_daily_pdf(
    report_id: str = Query(None, description="보고서 ID (UUID)"),
    report_date: str = Query(None, description="보고서 날짜 (YYYY-MM-DD, report_id가 없을 때 사용)"),
    db: Session = Depends(get_db)
):
    """
    일일보고서 PDF 생성
    
    Args:
        report_id: 보고서 UUID (우선 사용)
        date: 보고서 날짜 (report_id가 없을 때 사용)
        db: 데이터베이스 세션
        
    Returns:
        PDF 파일 (application/pdf)
    """
    try:
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        
        # 보고서 조회
        if report_id and report_id != "null":
            # UUID로 조회 시도
            try:
                import uuid
                report_uuid = uuid.UUID(report_id)
                report = DailyReportRepository.get_by_id(db, report_uuid)
            except (ValueError, AttributeError):
                report = None
        else:
            report = None
        
        # report_id로 찾지 못했고 report_date가 있으면 날짜로 조회
        if not report and report_date:
            from datetime import date as date_type
            parsed_date = date_type.fromisoformat(report_date)
            report = DailyReportRepository.get_by_owner_and_date(db, REPORT_OWNER, parsed_date)
        
        if not report or not report.report_json:
            raise HTTPException(
                status_code=404,
                detail=f"일일보고서를 찾을 수 없습니다. (report_id={report_id}, report_date={report_date})"
            )
        
        # CanonicalReport 객체 생성
        canonical_report = CanonicalReport(**report.report_json)
        
        # HTML 렌더링
        renderer = get_html_renderer()
        # display_name 우선 사용, 없으면 daily.header의 성명 사용
        display_name = canonical_report.daily.header.get("성명", "") if canonical_report.daily else ""
        # "default_workspace"나 빈 값이면 None으로 설정 (html_renderer에서 처리)
        if display_name == "default_workspace" or not display_name or display_name.strip() == "":
            display_name = None
        
        context = renderer._convert_daily_to_context(
            canonical_report,
            display_name=display_name  # None이면 html_renderer에서 daily.header.get("성명") 사용
        )
        context["report_id"] = str(report.id)  # report_id 추가
        
        template = renderer.env.get_template("일일보고서.html")
        html_string = template.render(**context)
        
        # pdfkit으로 PDF 생성
        if not PDFKIT_AVAILABLE:
            raise HTTPException(
                status_code=500,
                detail="pdfkit이 설치되지 않았습니다. pip install pdfkit를 실행해주세요."
            )
        
        try:
            # pdfkit 옵션 설정
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None
            }
            
            # HTML 문자열을 PDF로 변환
            pdf_bytes = pdfkit.from_string(html_string, False, options=options)
        except Exception as pdf_error:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ PDF 생성 오류: {str(pdf_error)}")
            print(f"📄 HTML 내용 (처음 500자): {html_string[:500]}")
            print(f"🔍 에러 상세:\n{error_details}")
            
            # wkhtmltopdf 바이너리 관련 오류인 경우
            if "No wkhtmltopdf executable found" in str(pdf_error) or "wkhtmltopdf" in str(pdf_error).lower():
                raise HTTPException(
                    status_code=500,
                    detail="wkhtmltopdf 바이너리가 설치되지 않았습니다. https://wkhtmltopdf.org/downloads.html 에서 다운로드해주세요."
                )
            
            raise HTTPException(
                status_code=500,
                detail=f"PDF 생성 중 오류가 발생했습니다: {str(pdf_error)}"
            )
        
        # 파일명 생성
        report_date = canonical_report.period_start.isoformat() if canonical_report.period_start else "unknown"
        filename = f"일일업무보고서_{report_date}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF 생성 실패: {str(e)}"
        )


@router.get("/weekly/pdf")
async def generate_weekly_pdf(
    report_id: str = Query(None, description="보고서 ID (UUID)"),
    report_date: str = Query(None, description="보고서 날짜 (YYYY-MM-DD, report_id가 없을 때 사용)"),
    db: Session = Depends(get_db)
):
    """
    주간보고서 PDF 생성
    
    Args:
        report_id: 보고서 UUID (우선 사용)
        date: 보고서 날짜 (report_id가 없을 때 사용)
        db: 데이터베이스 세션
        
    Returns:
        PDF 파일 (application/pdf)
    """
    try:
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        
        # 보고서 조회
        if report_id and report_id != "null":
            try:
                import uuid
                report_uuid = uuid.UUID(report_id)
                report = WeeklyReportRepository.get_by_id(db, report_uuid)
            except (ValueError, AttributeError):
                report = None
        else:
            report = None
        
        # report_id로 찾지 못했고 report_date가 있으면 날짜로 조회
        if not report and report_date:
            parsed_date = date.fromisoformat(report_date)
            # 주간보고서는 날짜 범위로 조회해야 함 (간단히 period_start로 조회)
            reports = WeeklyReportRepository.list_by_owner_and_period_range(
                db, REPORT_OWNER, parsed_date, parsed_date
            )
            report = reports[0] if reports else None
        
        if not report or not report.report_json:
            raise HTTPException(
                status_code=404,
                detail=f"주간보고서를 찾을 수 없습니다. (report_id={report_id}, report_date={report_date})"
            )
        
        # CanonicalReport 객체 생성
        canonical_report = CanonicalReport(**report.report_json)
        
        # HTML 렌더링
        renderer = get_html_renderer()
        context = renderer._convert_weekly_to_context(
            canonical_report,
            display_name=canonical_report.weekly.header.get("성명", "")
        )
        context["report_id"] = str(report.id)  # report_id 추가
        
        template = renderer.env.get_template("주간보고서.html")
        html_string = template.render(**context)
        
        # pdfkit으로 PDF 생성
        if not PDFKIT_AVAILABLE:
            raise HTTPException(
                status_code=500,
                detail="pdfkit이 설치되지 않았습니다. pip install pdfkit를 실행해주세요."
            )
        
        try:
            # pdfkit 옵션 설정
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None
            }
            
            # HTML 문자열을 PDF로 변환
            pdf_bytes = pdfkit.from_string(html_string, False, options=options)
        except Exception as pdf_error:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ PDF 생성 오류: {str(pdf_error)}")
            print(f"📄 HTML 내용 (처음 500자): {html_string[:500]}")
            print(f"🔍 에러 상세:\n{error_details}")
            
            # wkhtmltopdf 바이너리 관련 오류인 경우
            if "No wkhtmltopdf executable found" in str(pdf_error) or "wkhtmltopdf" in str(pdf_error).lower():
                raise HTTPException(
                    status_code=500,
                    detail="wkhtmltopdf 바이너리가 설치되지 않았습니다. https://wkhtmltopdf.org/downloads.html 에서 다운로드해주세요."
                )
            
            raise HTTPException(
                status_code=500,
                detail=f"PDF 생성 중 오류가 발생했습니다: {str(pdf_error)}"
            )
        
        # 파일명 생성
        report_date = canonical_report.period_end.isoformat() if canonical_report.period_end else "unknown"
        filename = f"주간업무보고서_{report_date}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF 생성 실패: {str(e)}"
        )


@router.get("/monthly/pdf")
async def generate_monthly_pdf(
    report_id: str = Query(None, description="보고서 ID (UUID)"),
    year: int = Query(None, description="연도 (report_id가 없을 때 사용)"),
    month: int = Query(None, description="월 (report_id가 없을 때 사용)"),
    db: Session = Depends(get_db)
):
    """
    월간보고서 PDF 생성
    
    Args:
        report_id: 보고서 UUID (우선 사용)
        year: 연도 (report_id가 없을 때 사용)
        month: 월 (report_id가 없을 때 사용)
        db: 데이터베이스 세션
        
    Returns:
        PDF 파일 (application/pdf)
    """
    try:
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        
        # 보고서 조회
        if report_id and report_id != "null":
            try:
                import uuid
                report_uuid = uuid.UUID(report_id)
                report = MonthlyReportRepository.get_by_id(db, report_uuid)
            except (ValueError, AttributeError):
                report = None
        else:
            report = None
        
        # report_id로 찾지 못했고 year/month가 있으면 조회
        if not report and year and month:
            from calendar import monthrange
            first_day = date_type(year, month, 1)
            last_day_num = monthrange(year, month)[1]
            last_day = date_type(year, month, last_day_num)
            
            reports = MonthlyReportRepository.list_by_owner_and_period_range(
                db, REPORT_OWNER, first_day, last_day
            )
            report = reports[0] if reports else None
        
        if not report or not report.report_json:
            raise HTTPException(
                status_code=404,
                detail=f"월간보고서를 찾을 수 없습니다. (report_id={report_id}, year={year}, month={month})"
            )
        
        # CanonicalReport 객체 생성
        canonical_report = CanonicalReport(**report.report_json)
        
        # KPI 데이터 계산
        if canonical_report.period_start:
            kpi_data = calculate_monthly_kpi(
                db=db,
                year=canonical_report.period_start.year,
                month=canonical_report.period_start.month
            )
        else:
            kpi_data = None
        
        # HTML 렌더링
        renderer = get_html_renderer()
        context = renderer._convert_monthly_to_context(
            canonical_report,
            display_name=canonical_report.monthly.header.get("성명", ""),
            kpi_data=kpi_data
        )
        context["report_id"] = str(report.id)  # report_id 추가
        
        template = renderer.env.get_template("월간보고서.html")
        html_string = template.render(**context)
        
        # pdfkit으로 PDF 생성
        if not PDFKIT_AVAILABLE:
            raise HTTPException(
                status_code=500,
                detail="pdfkit이 설치되지 않았습니다. pip install pdfkit를 실행해주세요."
            )
        
        try:
            # pdfkit 옵션 설정
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None
            }
            
            # HTML 문자열을 PDF로 변환
            pdf_bytes = pdfkit.from_string(html_string, False, options=options)
        except Exception as pdf_error:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ PDF 생성 오류: {str(pdf_error)}")
            print(f"📄 HTML 내용 (처음 500자): {html_string[:500]}")
            print(f"🔍 에러 상세:\n{error_details}")
            
            # wkhtmltopdf 바이너리 관련 오류인 경우
            if "No wkhtmltopdf executable found" in str(pdf_error) or "wkhtmltopdf" in str(pdf_error).lower():
                raise HTTPException(
                    status_code=500,
                    detail="wkhtmltopdf 바이너리가 설치되지 않았습니다. https://wkhtmltopdf.org/downloads.html 에서 다운로드해주세요."
                )
            
            raise HTTPException(
                status_code=500,
                detail=f"PDF 생성 중 오류가 발생했습니다: {str(pdf_error)}"
            )
        
        # 파일명 생성
        if canonical_report.period_start:
            month_str = f"{canonical_report.period_start.year}-{canonical_report.period_start.month:02d}"
        else:
            month_str = "unknown"
        filename = f"월간업무보고서_{month_str}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF 생성 실패: {str(e)}"
        )

