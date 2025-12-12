"""
Daily Report HTML Generator

일일보고서를 HTML로 생성
템플릿: backend/Data/reports/html/일일보고서.html
"""
from datetime import date
from typing import Optional
from pathlib import Path
import json

from app.reporting.html_generator.base import BaseHTMLGenerator
from app.domain.report.core.schemas import CanonicalReport


class DailyReportHTMLGenerator(BaseHTMLGenerator):
    """일일보고서 HTML 생성기"""
    
    def __init__(self):
        super().__init__("일일보고서.html")
    
    def _convert_to_html_format(self, report: CanonicalReport) -> dict:
        """
        CanonicalReport를 HTML 템플릿이 기대하는 형식으로 변환
        
        HTML 템플릿의 loadFromJSON 함수는 다음 형식을 기대:
        {
            "report_id": "...",
            "report_type": "daily",
            "owner": "...",
            "period_start": "...",
            "period_end": "...",
            "daily": {
                "header": {
                    "작성일자": "...",
                    "성명": "..."
                },
                "summary_tasks": [...],
                "detail_tasks": [
                    {
                        "time_start": "...",
                        "time_end": "...",
                        "text": "...",
                        "note": "..."
                    }
                ],
                "pending": [...],
                "plans": [...],
                "notes": "..."
            }
        }
        """
        if not report.daily:
            raise ValueError("CanonicalReport must have daily data for daily report HTML generation")
        
        daily = report.daily
        
        # 날짜를 문자열로 변환 (YYYY-MM-DD 형식)
        작성일자 = report.period_start.strftime("%Y-%m-%d") if report.period_start else ""
        
        # 헤더 정보
        header = {
            "작성일자": daily.header.get("작성일자", 작성일자),
            "성명": daily.header.get("성명", report.owner)
        }
        
        # 세부 업무 목록 (최대 9개)
        detail_tasks = []
        for task in daily.detail_tasks[:9]:
            detail_tasks.append({
                "time_start": task.time_start or "",
                "time_end": task.time_end or "",
                "text": task.text or "",
                "note": task.note or ""
            })
        
        # HTML 템플릿 형식으로 변환
        html_data = {
            "report_id": report.report_id,
            "report_type": "daily",
            "owner": report.owner,
            "period_start": 작성일자,
            "period_end": 작성일자,
            "daily": {
                "header": header,
                "summary_tasks": daily.todo_tasks or [],  # todo_tasks 사용 (하위 호환성을 위해 키는 summary_tasks 유지)
                "detail_tasks": detail_tasks,
                "pending": daily.pending or [],
                "plans": daily.plans or [],
                "notes": daily.notes or ""
            },
            "weekly": None,
            "monthly": None
        }
        
        return html_data
    
    def generate(
        self,
        report: CanonicalReport,
        output_filename: Optional[str] = None
    ) -> bytes:
        """
        일일보고서 HTML 생성
        
        Args:
            report: CanonicalReport 객체 (daily 타입)
            output_filename: 출력 파일명 (None이면 자동 생성)
            
        Returns:
            HTML 파일 바이트 스트림
        """
        if not report.daily:
            raise ValueError("CanonicalReport must have daily data for daily report HTML generation")
        
        daily = report.daily
        
        print(f"📄 일일보고서 HTML 생성 시작")
        print(f"   Owner: {report.owner}, Date: {report.period_start}")
        print(f"   Detail Tasks: {len(daily.detail_tasks)}개, Pending: {len(daily.pending)}개")
        
        # 템플릿 로드
        html_content = self._load_template()
        
        # CanonicalReport를 HTML 형식으로 변환
        json_data = self._convert_to_html_format(report)
        
        # HTML에 데이터 주입
        html_content = self._inject_data_and_auto_load(html_content, json_data)
        
        # 출력 파일명 생성
        if output_filename is None:
            from app.reporting.pdf_generator.utils import format_korean_date
            작성일자 = format_korean_date(report.period_start) if report.period_start else ""
            output_filename = f"일일보고서_{report.owner}_{작성일자}.html"
        
        # HTML 파일 저장
        output_path = self._save_html(html_content, output_filename, "daily")
        
        print(f"📁 HTML 출력 경로: {output_path}")
        print(f"   템플릿 경로: {self.template_path}")
        
        # 바이트로 읽어서 반환
        with open(output_path, 'rb') as f:
            html_bytes = f.read()
        
        print(f"✅ HTML 생성 완료: {len(html_bytes)} bytes")
        
        return html_bytes


def generate_daily_html_from_json(report_json: dict, output_filename: Optional[str] = None) -> bytes:
    """
    JSON에서 직접 HTML 생성 (편의 함수)
    
    Args:
        report_json: CanonicalReport JSON dict
        output_filename: 출력 파일명
        
    Returns:
        HTML 바이트 스트림
    """
    report = CanonicalReport(**report_json)
    generator = DailyReportHTMLGenerator()
    return generator.generate(report, output_filename)

