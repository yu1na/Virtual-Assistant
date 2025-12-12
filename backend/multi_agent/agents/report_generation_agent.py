"""
Report Generation Agent

보고서 작성 및 생성 전문 에이전트
- 일일보고서 FSM 입력/빌드 (daily_fsm.py, daily_builder.py)
- 주간/월간 보고서 자동 생성 (weekly/monthly chain)
- HTML/PDF 생성 및 Canonical 변환
- 상태 기반 워크플로우형 Agent
"""

from typing import Any, Dict, Optional
from datetime import date
from sqlalchemy.orm import Session

from multi_agent.agents.report_base import ReportBaseAgent
from multi_agent.agents.report_main_router import ReportPromptRegistry
from app.domain.report.daily.daily_fsm import DailyReportFSM
from app.domain.report.daily.task_parser import TaskParser
from app.domain.report.daily.daily_builder import build_daily_report
from app.domain.report.daily.fsm_state import DailyFSMContext
from app.domain.report.daily.session_manager import get_session_manager
from app.domain.report.daily.main_tasks_store import get_main_tasks_store
from app.domain.report.daily.time_slots import generate_time_slots
from app.domain.report.weekly.chain import generate_weekly_report
from app.domain.report.monthly.chain import generate_monthly_report
from app.reporting.html_renderer import render_report_html
from app.llm.client import LLMClient
from app.domain.report.core.canonical_models import CanonicalReport
from app.domain.report.daily.repository import DailyReportRepository
from app.domain.report.weekly.repository import WeeklyReportRepository
from app.domain.report.monthly.repository import MonthlyReportRepository
from app.domain.report.weekly.schemas import WeeklyReportCreate
from app.domain.report.monthly.schemas import MonthlyReportCreate
from app.core.config import settings
from urllib.parse import quote


class ReportGenerationAgent(ReportBaseAgent):
    """보고서 작성 및 생성 에이전트"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None, prompt_registry=None):
        """초기화"""
        super().__init__(
            name="ReportGenerationAgent",
            description="일일/주간/월간 보고서 작성 및 생성을 도와주는 에이전트입니다. FSM 기반 대화형 일일보고서 작성과 주간/월간 보고서 자동 생성을 지원합니다.",
            llm_client=llm_client
        )
        self.prompt_registry = prompt_registry or ReportPromptRegistry
        
        # TaskParser 초기화
        self.task_parser = TaskParser(self.llm, prompt_registry=self.prompt_registry)
        
        # FSM 초기화
        self.fsm = DailyReportFSM(self.task_parser)

    def configure_prompts(self, prompt_registry):
        """Prompt registry 주입 (router에서 호출)."""
        self.prompt_registry = prompt_registry or ReportPromptRegistry
        if hasattr(self.task_parser, "prompt_registry"):
            self.task_parser.prompt_registry = self.prompt_registry
    
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        보고서 요청 처리 (일반적인 쿼리 기반 처리)
        
        Args:
            query: 사용자 질문
            context: 추가 컨텍스트
            
        Returns:
            처리 결과 문자열
        """
        if context and context.get("prompt_registry"):
            self.configure_prompts(context.get("prompt_registry"))

        # 일일보고서 작성 요청 감지
        query_lower = query.lower().strip()
        if ("일일" in query_lower or "daily" in query_lower) and \
           ("보고서" in query_lower or "report" in query_lower) and \
           ("작성" in query_lower or "입력" in query_lower or "write" in query_lower):
            return "일일보고서 입력 화면을 표시합니다. 업무를 입력하고 완료 버튼을 눌러주세요."

        # 일반적인 쿼리는 간단한 응답만 반환
        # 실제 작업은 직접 호출 메서드 사용
        return "보고서 작성을 도와드리겠습니다. 구체적인 작업을 요청해주세요."
    
    # ========================================
    # 직접 호출용 메서드 (API 엔드포인트용)
    # ========================================
    
    def start_daily_report(
        self,
        owner: str,
        target_date: date,
        time_ranges: Optional[list] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        일일보고서 FSM 시작
        
        Args:
            owner: 작성자 이름
            target_date: 대상 날짜
            time_ranges: 시간대 목록 (없으면 자동 생성)
            db: DB 세션 (선택)
            
        Returns:
            {
                "session_id": str,
                "question": str,
                "meta": dict
            }
        """
        # 시간대 생성
        if not time_ranges:
            time_ranges = generate_time_slots()
        
        # 저장소에서 main_tasks 불러오기
        store = get_main_tasks_store()
        main_tasks = store.get(owner=owner, target_date=target_date)
        
        if main_tasks is None:
            print(f"[WARNING] main_tasks가 저장되지 않음: {owner}, {target_date}")
            main_tasks = []
        
        # FSM 컨텍스트 생성
        context = DailyFSMContext(
            owner=owner,
            target_date=target_date,
            time_ranges=time_ranges,
            today_main_tasks=main_tasks,
            current_index=0,
            finished=False
        )
        
        # 세션 생성
        session_manager = get_session_manager()
        session_id = session_manager.create_session(context)
        
        # 첫 질문 가져오기
        result = self.fsm.start_session(context)
        
        # 세션 업데이트
        session_manager.update_session(session_id, result["state"])
        
        # 현재 시간대 가져오기
        current_time_range = time_ranges[result["current_index"]] if result["current_index"] < len(time_ranges) else ""
        
        return {
            "session_id": session_id,
            "question": result["question"],
            "meta": {
                "owner": owner,
                "date": target_date.isoformat(),
                "time_range": current_time_range,
                "current_index": result["current_index"],
                "total_ranges": result["total_ranges"]
            }
        }
    
    def answer_daily_question(
        self,
        session_id: str,
        answer: str,
        owner: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        일일보고서 FSM 답변 처리
        
        Args:
            session_id: 세션 ID
            answer: 사용자 답변
            owner: 작성자 이름
            db: DB 세션
            
        Returns:
            {
                "status": "in_progress" | "finished",
                "session_id": str,
                "question": Optional[str],
                "message": Optional[str],
                "report": Optional[CanonicalReport],
                "html_url": Optional[str],
                ...
            }
        """
        # 세션 조회
        session_manager = get_session_manager()
        context = session_manager.get_session(session_id)
        
        if not context:
            raise ValueError("세션을 찾을 수 없습니다")
        
        # 답변 처리
        result = self.fsm.process_answer(context, answer)
        
        # 세션 업데이트
        updated_context = result["state"]
        session_manager.update_session(session_id, updated_context)
        
        # 완료 여부 확인
        if result["finished"]:
            # 보고서 생성
            report = build_daily_report(
                owner=owner,
                target_date=updated_context.target_date,
                main_tasks=updated_context.today_main_tasks,
                time_tasks=updated_context.time_tasks,
                issues=updated_context.issues,
                plans=updated_context.plans,
                display_name=owner
            )
            
            # DB 저장
            REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
            existing_report = DailyReportRepository.get_by_owner_and_date(
                db, REPORT_OWNER, report.period_start
            )
            
            report_dict = report.model_dump(mode='json')
            
            if existing_report:
                # 병합 로직
                existing_json = existing_report.report_json.copy()
                existing_tasks = existing_json.get("tasks", [])
                new_tasks = report_dict.get("tasks", [])
                
                merged_tasks = existing_tasks.copy()
                existing_ids = {t.get("task_id") for t in existing_tasks if t.get("task_id")}
                
                for task in new_tasks:
                    if task.get("task_id") not in existing_ids:
                        merged_tasks.append(task)
                
                merged_json = {
                    **report_dict,
                    "tasks": merged_tasks,
                    "metadata": {
                        **report_dict.get("metadata", {}),
                        "status": "completed",
                        "merged": True
                    }
                }
                
                existing_report.report_json = merged_json
                db.commit()
                db.refresh(existing_report)
            else:
                # 새로 생성
                from app.domain.report.daily.schemas import DailyReportCreate
                report_dict["metadata"] = {
                    **report_dict.get("metadata", {}),
                    "status": "completed"
                }
                report_create = DailyReportCreate(
                    owner=REPORT_OWNER,
                    report_date=report.period_start,
                    report_json=report_dict
                )
                DailyReportRepository.create(db, report_create)
            
            # HTML 생성
            html_path = None
            html_url = None
            html_filename = None
            try:
                html_path = render_report_html(
                    report_type="daily",
                    data=report_dict,
                    output_filename=f"daily_report_{owner}_{report.period_start}.html",
                    display_name=owner
                )
                html_filename = html_path.name
                html_url = f"/static/reports/daily/{quote(html_filename)}"
            except Exception as html_error:
                print(f"HTML generation failed: {str(html_error)}")
            
            return {
                "status": "finished",
                "session_id": session_id,
                "question": None,
                "message": "일일보고서가 완료되었습니다.",
                "report": report,
                "html_url": html_url,
                "html_filename": html_filename,
                "meta": {
                    "owner": owner,
                    "date": updated_context.target_date.isoformat()
                }
            }
        else:
            # 다음 질문
            time_ranges = updated_context.time_ranges
            current_time_range = time_ranges[updated_context.current_index] if updated_context.current_index < len(time_ranges) else ""
            
            return {
                "status": "in_progress",
                "session_id": session_id,
                "question": result["question"],
                "message": None,
                "report": None,
                "html_url": None,
                "meta": {
                    "owner": owner,
                    "date": updated_context.target_date.isoformat(),
                    "time_range": current_time_range,
                    "current_index": updated_context.current_index,
                    "total_ranges": len(time_ranges)
                }
            }
    
    def generate_weekly_report(
        self,
        db: Session,
        owner: str,
        target_date: date,
        display_name: Optional[str] = None
    ) -> CanonicalReport:
        """
        주간보고서 생성
        
        Args:
            db: DB 세션
            owner: 작성자 이름 (호환성 유지용)
            target_date: 기준 날짜
            display_name: HTML 보고서에 표시할 이름
            
        Returns:
            CanonicalReport
        """
        if display_name is None:
            display_name = owner
        
        report = generate_weekly_report(
            db=db,
            owner=owner,
            target_date=target_date,
            display_name=display_name,
            prompt_registry=self.prompt_registry
        )
        
        return report
    
    def generate_monthly_report(
        self,
        db: Session,
        owner: str,
        year: int,
        month: int,
        display_name: Optional[str] = None
    ) -> CanonicalReport:
        """
        월간보고서 생성
        
        Args:
            db: DB 세션
            owner: 작성자 이름 (호환성 유지용)
            year: 연도
            month: 월
            display_name: HTML 보고서에 표시할 이름
            
        Returns:
            CanonicalReport
        """
        if display_name is None:
            display_name = owner
        
        target_date = date(year, month, 1)
        
        # KPI 계산 (카테고리 기반) - 일일보고서의 카테고리 필드에서 직접 집계
        from app.domain.report.monthly.kpi_calculator import calculate_monthly_kpi
        kpi_data = calculate_monthly_kpi(db=db, year=year, month=month)
        
        print(f"[INFO] 월간 KPI 계산 완료: new_contracts={kpi_data.get('new_contracts', 0)}, renewals={kpi_data.get('renewals', 0)}, consultations={kpi_data.get('consultations', 0)}")
        
        report = generate_monthly_report(
            db=db,
            owner=owner,
            target_date=target_date,
            kpi_data=kpi_data,  # 카테고리 기반으로 계산된 KPI 데이터 전달 (LLM은 analysis만 작성)
            display_name=display_name,
            prompt_registry=self.prompt_registry
        )
        
        return report
    
    def get_fsm(self) -> DailyReportFSM:
        """FSM 인스턴스 반환 (API에서 직접 사용)"""
        return self.fsm
    
    def get_task_parser(self) -> TaskParser:
        """TaskParser 인스턴스 반환"""
        return self.task_parser

