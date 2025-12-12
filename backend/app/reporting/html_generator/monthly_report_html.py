"""
Monthly Report HTML Generator

월간보고서를 HTML로 생성
템플릿: backend/Data/reports/html/월간보고서.html
"""
from datetime import date
from typing import Optional
from pathlib import Path
import json

from app.reporting.html_generator.base import BaseHTMLGenerator
from app.domain.report.core.schemas import CanonicalReport


class MonthlyReportHTMLGenerator(BaseHTMLGenerator):
    """월간보고서 HTML 생성기"""
    
    def __init__(self):
        super().__init__("월간보고서.html")
    
    def _convert_to_html_format(self, report: CanonicalReport) -> dict:
        """
        CanonicalReport를 HTML 템플릿이 기대하는 형식으로 변환
        
        HTML 템플릿의 loadFromJSON 함수는 다음 형식을 기대:
        {
            "상단정보": {
                "월": "...",
                "작성일자": "...",
                "성명": "..."
            },
            "월간_핵심_지표": {
                "신규_계약_건수": {
                    "건수": "...",
                    "비고": "..."
                },
                "유지_계약_건수": {
                    "유지": "...",
                    "갱신": "...",
                    "미납_방지": "...",
                    "비고": "..."
                },
                "상담_진행_건수": {
                    "전화": "...",
                    "방문": "...",
                    "온라인": "...",
                    "비고": "..."
                }
            },
            "주차별_세부_업무": {
                "1주": {
                    "업무내용": "...",
                    "비고": "..."
                },
                ...
            },
            "익월_계획": "..."
        }
        """
        if not report.monthly:
            raise ValueError("CanonicalReport must have monthly data for monthly report HTML generation")
        
        monthly = report.monthly
        
        # 날짜를 문자열로 변환
        월 = ""
        작성일자 = ""
        if report.period_start:
            월 = f"{report.period_start.year}-{report.period_start.month:02d}"
            작성일자 = report.period_start.strftime("%Y-%m-%d")
        
        # 헤더 정보
        상단정보 = {
            "월": monthly.header.get("월", 월),
            "작성일자": monthly.header.get("작성일자", 작성일자),
            "성명": monthly.header.get("성명", report.owner)
        }
        
        # 주차별 세부 업무 변환
        # CanonicalReport: { "1주차": ["업무1", "업무2"], ... }
        # HTML 템플릿: { "1주": { "업무내용": "...", "비고": "..." }, ... }
        주차별_세부_업무 = {}
        for 주차_key, 업무_list in monthly.weekly_summaries.items():
            # "1주차" -> "1주" 변환
            if "주차" in 주차_key:
                주차 = 주차_key.replace("주차", "주")
            else:
                주차 = 주차_key
            
            # 리스트를 하나의 문자열로 합치기
            업무내용 = "\n".join(업무_list) if isinstance(업무_list, list) else str(업무_list)
            
            주차별_세부_업무[주차] = {
                "업무내용": 업무내용,
                "비고": ""
            }
        
        # 1주~5주까지 모두 채우기 (없으면 빈 값)
        for i in range(1, 6):
            주차 = f"{i}주"
            if 주차 not in 주차별_세부_업무:
                주차별_세부_업무[주차] = {
                    "업무내용": "",
                    "비고": ""
                }
        
        # HTML 템플릿 형식으로 변환
        html_data = {
            "상단정보": 상단정보,
            "월간_핵심_지표": {
                "신규_계약_건수": {
                    "건수": "",
                    "비고": ""
                },
                "유지_계약_건수": {
                    "유지": "",
                    "갱신": "",
                    "미납_방지": "",
                    "비고": ""
                },
                "상담_진행_건수": {
                    "전화": "",
                    "방문": "",
                    "온라인": "",
                    "비고": ""
                }
            },
            "주차별_세부_업무": 주차별_세부_업무,
            "익월_계획": monthly.next_month_plan or ""
        }
        
        return html_data
    
    def generate(
        self,
        report: CanonicalReport,
        output_filename: Optional[str] = None
    ) -> bytes:
        """
        월간보고서 HTML 생성
        
        Args:
            report: CanonicalReport 객체 (monthly 타입)
            output_filename: 출력 파일명 (None이면 자동 생성)
            
        Returns:
            HTML 파일 바이트 스트림
        """
        if not report.monthly:
            raise ValueError("CanonicalReport must have monthly data for monthly report HTML generation")
        
        monthly = report.monthly
        
        print(f"📄 월간보고서 HTML 생성 시작")
        print(f"   Owner: {report.owner}, Period: {report.period_start}~{report.period_end}")
        print(f"   Weekly summaries: {len(monthly.weekly_summaries)}개 주차")
        
        # 템플릿 로드
        html_content = self._load_template()
        
        # CanonicalReport를 HTML 형식으로 변환
        json_data = self._convert_to_html_format(report)
        
        # HTML에 데이터 주입
        html_content = self._inject_data_and_auto_load(html_content, json_data)
        
        # 출력 파일명 생성
        if output_filename is None:
            월 = f"{report.period_start.month}" if report.period_start else ""
            output_filename = f"월간보고서_{report.owner}_{월}월.html"
        
        # HTML 파일 저장
        output_path = self._save_html(html_content, output_filename, "monthly")
        
        print(f"📁 HTML 출력 경로: {output_path}")
        print(f"   템플릿 경로: {self.template_path}")
        
        # 바이트로 읽어서 반환
        with open(output_path, 'rb') as f:
            html_bytes = f.read()
        
        print(f"✅ HTML 생성 완료: {len(html_bytes)} bytes")
        
        return html_bytes


def generate_monthly_html_from_json(report_json: dict, output_filename: Optional[str] = None) -> bytes:
    """
    JSON에서 직접 HTML 생성 (편의 함수)
    
    Args:
        report_json: CanonicalReport JSON dict
        output_filename: 출력 파일명
        
    Returns:
        HTML 바이트 스트림
    """
    report = CanonicalReport(**report_json)
    generator = MonthlyReportHTMLGenerator()
    return generator.generate(report, output_filename)

