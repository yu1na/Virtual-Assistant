"""
Weekly Report HTML Generator

주간보고서를 HTML로 생성
템플릿: backend/Data/reports/html/주간보고서.html
"""
from datetime import date
from typing import Optional
from pathlib import Path
import json

from app.reporting.html_generator.base import BaseHTMLGenerator
from app.domain.report.core.schemas import CanonicalReport


class WeeklyReportHTMLGenerator(BaseHTMLGenerator):
    """주간보고서 HTML 생성기"""
    
    def __init__(self):
        super().__init__("주간보고서.html")
    
    def _convert_to_html_format(self, report: CanonicalReport) -> dict:
        """
        CanonicalReport를 HTML 템플릿이 기대하는 형식으로 변환
        
        HTML 템플릿의 loadFromJSON 함수는 다음 형식을 기대:
        {
            "report_id": "...",
            "report_type": "weekly",
            "owner": "...",
            "period_start": "...",
            "period_end": "...",
            "weekly": {
                "header": {
                    "작성일자": "...",
                    "성명": "..."
                },
                "weekly_goals": [...],
                "weekday_tasks": {
                    "YYYY-MM-DD": [...],
                    ...
                },
                "weekly_highlights": [...],
                "notes": "..."
            }
        }
        """
        if not report.weekly:
            raise ValueError("CanonicalReport must have weekly data for weekly report HTML generation")
        
        weekly = report.weekly
        
        # 날짜를 문자열로 변환 (YYYY-MM-DD 형식)
        작성일자 = report.period_end.strftime("%Y-%m-%d") if report.period_end else ""
        
        # 헤더 정보
        header = {
            "작성일자": weekly.header.get("작성일자", 작성일자),
            "성명": weekly.header.get("성명", report.owner)
        }
        
        # HTML 템플릿 형식으로 변환
        html_data = {
            "report_id": report.report_id,
            "report_type": "weekly",
            "owner": report.owner,
            "period_start": report.period_start.strftime("%Y-%m-%d") if report.period_start else "",
            "period_end": report.period_end.strftime("%Y-%m-%d") if report.period_end else "",
            "daily": None,
            "weekly": {
                "header": header,
                "weekly_goals": weekly.weekly_goals or [],
                "weekday_tasks": weekly.weekday_tasks or {},
                "weekly_highlights": weekly.weekly_highlights or [],
                "notes": weekly.notes or ""
            },
            "monthly": None
        }
        
        return html_data
    
    def generate(
        self,
        report: CanonicalReport,
        output_filename: Optional[str] = None
    ) -> bytes:
        """
        주간보고서 HTML 생성
        
        Args:
            report: CanonicalReport 객체 (weekly 타입)
            output_filename: 출력 파일명 (None이면 자동 생성)
            
        Returns:
            HTML 파일 바이트 스트림
        """
        if not report.weekly:
            raise ValueError("CanonicalReport must have weekly data for weekly report HTML generation")
        
        weekly = report.weekly
        
        print(f"📄 주간보고서 HTML 생성 시작")
        print(f"   Owner: {report.owner}, Period: {report.period_start}~{report.period_end}")
        print(f"   Weekly Goals: {len(weekly.weekly_goals)}개, Highlights: {len(weekly.weekly_highlights)}개")
        
        # 템플릿 로드
        html_content = self._load_template()
        
        # CanonicalReport를 HTML 형식으로 변환
        json_data = self._convert_to_html_format(report)
        
        # HTML에 데이터 주입
        html_content = self._inject_data_and_auto_load(html_content, json_data)
        
        # 출력 파일명 생성
        if output_filename is None:
            from app.reporting.pdf_generator.utils import format_korean_date
            작성일자 = format_korean_date(report.period_end) if report.period_end else ""
            output_filename = f"주간보고서_{report.owner}_{작성일자}.html"
        
        # HTML 파일 저장
        output_path = self._save_html(html_content, output_filename, "weekly")
        
        print(f"📁 HTML 출력 경로: {output_path}")
        print(f"   템플릿 경로: {self.template_path}")
        
        # 바이트로 읽어서 반환
        with open(output_path, 'rb') as f:
            html_bytes = f.read()
        
        print(f"✅ HTML 생성 완료: {len(html_bytes)} bytes")
        
        return html_bytes


def generate_weekly_html_from_json(report_json: dict, output_filename: Optional[str] = None) -> bytes:
    """
    JSON에서 직접 HTML 생성 (편의 함수)
    
    Args:
        report_json: CanonicalReport JSON dict
        output_filename: 출력 파일명
        
    Returns:
        HTML 바이트 스트림
    """
    report = CanonicalReport(**report_json)
    generator = WeeklyReportHTMLGenerator()
    return generator.generate(report, output_filename)

