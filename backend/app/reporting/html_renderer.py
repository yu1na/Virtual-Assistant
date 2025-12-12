"""
HTML Report Renderer

Jinja2 템플릿 엔진을 사용하여 보고서를 HTML로 렌더링
"""
from pathlib import Path
from typing import Literal, Optional, Dict, Any
from datetime import date

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from app.domain.report.core.schemas import CanonicalReport
from app.core.config import settings


class HTMLReportRenderer:
    """HTML 보고서 렌더러"""
    
    # 프로젝트 루트 찾기 (Virtual-Assistant 루트)
    # backend/app/reporting/html_renderer.py -> parent.parent.parent.parent = Virtual-Assistant 루트
    _BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    
    # 템플릿 디렉토리
    TEMPLATE_DIR = _BASE_DIR / "backend" / "Data" / "reports" / "html"
    
    # 출력 디렉토리 (타입별로 분리)
    # main.py와 동일한 경로: Virtual-Assistant/backend/output
    OUTPUT_BASE_DIR = _BASE_DIR / "backend" / "output"
    
    def __init__(self):
        """Jinja2 Environment 초기화"""
        # 출력 디렉토리 생성 (타입별로 분리)
        (self.OUTPUT_BASE_DIR / "daily").mkdir(parents=True, exist_ok=True)
        (self.OUTPUT_BASE_DIR / "weekly").mkdir(parents=True, exist_ok=True)
        (self.OUTPUT_BASE_DIR / "monthly").mkdir(parents=True, exist_ok=True)
        
        # Jinja2 Environment 설정
        self.env = Environment(
            loader=FileSystemLoader(str(self.TEMPLATE_DIR)),
            autoescape=True,  # XSS 방지
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # 템플릿 파일명 매핑
        self.template_map = {
            "daily": "일일보고서.html",
            "weekly": "주간보고서.html",
            "monthly": "월간보고서.html"
        }
    
    def _convert_daily_to_context(self, report: CanonicalReport, display_name: Optional[str] = None) -> Dict[str, Any]:
        """
        일일보고서 CanonicalReport → 템플릿 context 변환
        
        Args:
            report: CanonicalReport 객체
            display_name: HTML 보고서에 표시할 이름 (우선 사용)
        
        Returns:
            템플릿에 전달할 context 딕셔너리
        """
        if not report.daily:
            raise ValueError("CanonicalReport must have daily data for daily report HTML generation")
        
        daily = report.daily
        
        # 날짜를 문자열로 변환 (YYYY-MM-DD 형식)
        작성일자 = report.period_start.strftime("%Y-%m-%d") if report.period_start else ""
        
        # 성명 결정: display_name 우선, 없으면 daily.header의 성명 사용
        # report.owner는 더 이상 사용하지 않음 (상수이므로)
        성명 = display_name or daily.header.get("성명", "")
        
        # 헤더 정보
        header = {
            "작성일자": daily.header.get("작성일자", 작성일자),
            "성명": 성명
        }
        
        # 세부 업무 목록 (새 템플릿 형식: 업무명, 상세내용, 비고)
        detail_tasks = []
        for task in daily.detail_tasks:
            # 카테고리 추출 (note에서 "카테고리: " 제거)
            category = ""
            if task.note:
                # "카테고리: 유지 계약" 형식에서 "유지 계약"만 추출
                if "카테고리:" in task.note:
                    category = task.note.replace("카테고리:", "").strip()
                elif "카테고리 :" in task.note:
                    category = task.note.replace("카테고리 :", "").strip()
                else:
                    # 이미 카테고리만 있는 경우
                    category = task.note.strip()
            
            detail_tasks.append({
                "text": task.text or "",  # 상세내용에 사용
                "category": category,  # 업무명에 카테고리만 표시
                "note": task.note or ""  # 비고 (원본 유지)
            })
        
        # 빈 행 추가 (최소 1개)
        if len(detail_tasks) == 0:
            detail_tasks.append({
                "text": "",
                "note": ""
            })
        
        # 미종결 업무 (리스트를 줄바꿈 문자열로 변환)
        pending_text = "\n".join(daily.pending) if daily.pending else ""
        
        # 익일 계획 (리스트를 줄바꿈 문자열로 변환)
        plans_text = "\n".join(daily.plans) if daily.plans else ""
        
        return {
            "header": header,
            "summary_tasks": daily.todo_tasks or [],  # todo_tasks 사용 (하위 호환성을 위해 키는 summary_tasks 유지)
            "detail_tasks": detail_tasks,
            "pending": pending_text,
            "plans": plans_text,
            "notes": daily.notes or "",
            "report_id": report.report_id or ""  # report_id 추가
        }
    
    def _convert_weekly_to_context(self, report: CanonicalReport, display_name: Optional[str] = None) -> Dict[str, Any]:
        """
        주간보고서 CanonicalReport → 템플릿 context 변환
        
        Args:
            report: CanonicalReport 객체
            display_name: HTML 보고서에 표시할 이름 (우선 사용)
        
        Returns:
            템플릿에 전달할 context 딕셔너리
        """
        if not report.weekly:
            raise ValueError("CanonicalReport must have weekly data for weekly report HTML generation")
        
        weekly = report.weekly
        
        # 날짜를 문자열로 변환 (YYYY-MM-DD 형식)
        작성일자 = report.period_end.strftime("%Y-%m-%d") if report.period_end else ""
        
        # 성명 결정: display_name 우선, 없으면 weekly.header의 성명 사용
        # report.owner는 더 이상 사용하지 않음 (상수이므로)
        성명 = display_name or weekly.header.get("성명", "")
        
        # 헤더 정보
        header = {
            "작성일자": weekly.header.get("작성일자", 작성일자),
            "성명": 성명
        }
        
        # 주간 세부 업무 (새 템플릿 형식: 분류/업무내용/비고)
        # weekday_tasks는 { "월요일": ["업무1", "업무2"], ... } 형식
        # 요일별로 그룹화하여 한 행에 모든 업무를 표시
        weekday_tasks_list = []
        day_name_map = {
            "월요일": "월",
            "화요일": "화",
            "수요일": "수",
            "목요일": "목",
            "금요일": "금"
        }
        
        # 요일 순서 정의
        weekday_order = ["월요일", "화요일", "수요일", "목요일", "금요일"]
        
        # weekday_tasks를 요일 순서대로 처리
        for weekday_name in weekday_order:
            if weekday_name not in weekly.weekday_tasks:
                continue
            
            tasks = weekly.weekday_tasks[weekday_name]
            if not isinstance(tasks, list):
                continue
            
            day_short = day_name_map.get(weekday_name, weekday_name)
            
            # 요일별로 모든 업무를 하나의 문자열로 합치기 (줄바꿈으로 구분)
            # textarea는 HTML을 렌더링하지 않으므로 \n을 사용
            tasks_text = "\n".join(task for task in tasks if task.strip())
            
            # 업무가 있으면 한 행으로 추가
            if tasks_text:
                weekday_tasks_list.append({
                    "category": day_short,  # 분류: 요일명 (월, 화, 수, 목, 금)
                    "content": tasks_text,  # 업무내용: 모든 업무를 줄바꿈으로 구분
                    "note": ""  # 비고
                })
        
        # 빈 행 추가 (최소 1개)
        if len(weekday_tasks_list) == 0:
            weekday_tasks_list.append({
                "category": "",
                "content": "",
                "note": ""
            })
        
        return {
            "header": header,
            "weekly_goals": weekly.weekly_goals or [],
            "weekday_tasks": weekday_tasks_list,  # 리스트 형식으로 변경
            "weekly_highlights": weekly.weekly_highlights or [],
            "notes": weekly.notes or "",
            "report_id": report.report_id or ""  # report_id 추가
        }
    
    def _convert_monthly_to_context(self, report: CanonicalReport, display_name: Optional[str] = None, kpi_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        월간보고서 CanonicalReport → 템플릿 context 변환
        
        Args:
            report: CanonicalReport 객체
            display_name: HTML 보고서에 표시할 이름 (우선 사용)
        
        Returns:
            템플릿에 전달할 context 딕셔너리
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
        
        # 성명 결정: display_name 우선, 없으면 monthly.header의 성명 사용
        # report.owner는 더 이상 사용하지 않음 (상수이므로)
        # fallback 체인: display_name -> monthly.header.성명
        성명 = display_name
        if not 성명 or (isinstance(성명, str) and 성명.strip() == ""):
            성명 = monthly.header.get("성명", "")
        # 최종 fallback: 빈 문자열이면 "사용자" (템플릿에서 빈 값 방지)
        if not 성명 or (isinstance(성명, str) and 성명.strip() == ""):
            성명 = "사용자"
        
        # 헤더 정보
        상단정보 = {
            "월": monthly.header.get("월", 월),
            "작성일자": monthly.header.get("작성일자", 작성일자),
            "성명": 성명
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
        # Jinja2 템플릿에서 쉽게 접근할 수 있도록 리스트로도 제공
        주차별_세부_업무_list = []
        for i in range(1, 6):
            주차 = f"{i}주"
            if 주차 not in 주차별_세부_업무:
                주차별_세부_업무[주차] = {
                    "업무내용": "",
                    "비고": ""
                }
            주차별_세부_업무_list.append({
                "주차": 주차,
                "업무내용": 주차별_세부_업무[주차]["업무내용"],
                "비고": 주차별_세부_업무[주차]["비고"]
            })
        
        # KPI 데이터 처리 (숫자만 표시, analysis 없음)
        key_metrics = {
            "new_contracts": 0,
            "renewals": 0,
            "consultations": 0,
            "analysis": ""  # 비고 필드에 표시하지 않음
        }
        if kpi_data:
            # kpi_data에서 숫자만 추출 (analysis는 사용하지 않음)
            key_metrics["new_contracts"] = kpi_data.get("new_contracts", 0)
            key_metrics["renewals"] = kpi_data.get("renewals", 0)
            key_metrics["consultations"] = kpi_data.get("consultations", 0)
            # analysis는 빈 문자열로 유지 (비고 필드에 표시하지 않음)
        
        return {
            "상단정보": 상단정보,
            "key_metrics": key_metrics,
            "주차별_세부_업무": 주차별_세부_업무,
            "주차별_세부_업무_list": 주차별_세부_업무_list,
            "익월_계획": monthly.next_month_plan or "",
            "report_id": report.report_id or ""  # report_id 추가
        }
    
    def _convert_to_context(
        self,
        report_type: Literal["daily", "weekly", "monthly"],
        report: CanonicalReport,
        display_name: Optional[str] = None,
        kpi_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        CanonicalReport를 템플릿 context로 변환
        
        Args:
            report_type: 보고서 타입
            report: CanonicalReport 객체
            display_name: HTML 보고서에 표시할 이름 (우선 사용)
            
        Returns:
            템플릿에 전달할 context 딕셔너리
        """
        if report_type == "daily":
            return self._convert_daily_to_context(report, display_name)
        elif report_type == "weekly":
            return self._convert_weekly_to_context(report, display_name)
        elif report_type == "monthly":
            return self._convert_monthly_to_context(report, display_name, kpi_data)
        else:
            raise ValueError(f"Unknown report type: {report_type}")
    
    def render_report_html(
        self,
        report_type: Literal["daily", "weekly", "monthly"],
        data: Dict[str, Any],
        output_filename: Optional[str] = None,
        display_name: Optional[str] = None,
        kpi_data: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        보고서를 HTML로 렌더링
        
        Args:
            report_type: 보고서 타입 ("daily", "weekly", "monthly")
            data: CanonicalReport JSON 딕셔너리 또는 CanonicalReport 객체
            output_filename: 출력 파일명 (None이면 자동 생성)
            
        Returns:
            생성된 HTML 파일 경로
            
        Raises:
            ValueError: 잘못된 report_type 또는 데이터 형식
            TemplateNotFound: 템플릿 파일을 찾을 수 없음
        """
        # CanonicalReport 객체로 변환
        if isinstance(data, dict):
            report = CanonicalReport(**data)
        elif isinstance(data, CanonicalReport):
            report = data
        else:
            raise ValueError(f"data must be dict or CanonicalReport, got {type(data)}")
        
        # 템플릿 파일명 확인
        template_filename = self.template_map.get(report_type)
        if not template_filename:
            raise ValueError(f"Unknown report type: {report_type}")
        
        # 템플릿 로드
        try:
            template = self.env.get_template(template_filename)
        except TemplateNotFound:
            raise TemplateNotFound(
                f"Template not found: {template_filename} in {self.TEMPLATE_DIR}"
            )
        
        # CanonicalReport → context 변환 (display_name, kpi_data 전달)
        context = self._convert_to_context(report_type, report, display_name, kpi_data)
        
        # report_id를 context에 추가 (이미 _convert_*_to_context에서 추가되지만, 없을 경우를 대비)
        if "report_id" not in context:
            context["report_id"] = str(report.report_id) if report.report_id else ""
        
        # HTML 렌더링
        html_content = template.render(**context)
        
        # 출력 파일명 생성
        if output_filename is None:
            if report_type == "daily":
                date_str = report.period_start.isoformat() if report.period_start else ""
                output_filename = f"일일보고서_{report.owner}_{date_str}.html"
            elif report_type == "weekly":
                date_str = report.period_end.isoformat() if report.period_end else ""
                output_filename = f"주간보고서_{report.owner}_{date_str}.html"
            elif report_type == "monthly":
                month_str = f"{report.period_start.year}-{report.period_start.month:02d}" if report.period_start else ""
                output_filename = f"월간보고서_{report.owner}_{month_str}.html"
        
        # 파일명에서 특수문자 제거 (URL 안전하게)
        import re
        output_filename = re.sub(r'[<>:"/\\|?*]', '_', output_filename)
        
        # 타입별 출력 디렉토리 선택
        if report_type == "daily":
            output_dir = self.OUTPUT_BASE_DIR / "daily"
        elif report_type == "weekly":
            output_dir = self.OUTPUT_BASE_DIR / "weekly"
        elif report_type == "monthly":
            output_dir = self.OUTPUT_BASE_DIR / "monthly"
        else:
            output_dir = self.OUTPUT_BASE_DIR  # 기본값
        
        # HTML 파일 저장
        output_path = output_dir / output_filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ HTML 생성 완료: {output_path}")
        
        return output_path


# 전역 렌더러 인스턴스 (싱글톤)
_renderer: Optional[HTMLReportRenderer] = None


def get_html_renderer() -> HTMLReportRenderer:
    """HTML 렌더러 싱글톤 인스턴스 반환"""
    global _renderer
    if _renderer is None:
        _renderer = HTMLReportRenderer()
    return _renderer


def render_report_html(
    report_type: Literal["daily", "weekly", "monthly"],
    data: Dict[str, Any],
    output_filename: Optional[str] = None,
    display_name: Optional[str] = None,
    kpi_data: Optional[Dict[str, Any]] = None
) -> Path:
    """
    보고서를 HTML로 렌더링 (편의 함수)
    
    Args:
        report_type: 보고서 타입
        data: CanonicalReport JSON 딕셔너리
        output_filename: 출력 파일명
        display_name: HTML 보고서에 표시할 이름 (우선 사용)
        
    Returns:
        생성된 HTML 파일 경로
    """
    renderer = get_html_renderer()
    return renderer.render_report_html(report_type, data, output_filename, display_name, kpi_data)

