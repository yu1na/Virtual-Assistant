"""
Today Plan Chain

LangChain 기반 오늘의 일정 플래닝 체인

Author: AI Assistant
Created: 2025-11-18
"""
from typing import Optional, List
from datetime import date

from app.llm.client import LLMClient
from app.domain.report.planner.tools import YesterdayReportTool
from app.domain.report.search.retriever import UnifiedRetriever, UnifiedSearchResult
from app.domain.report.planner.schemas import (
    TodayPlanRequest,
    TodayPlanResponse,
    TaskItem,
    TaskSource
)


class TodayPlanGenerator:
    """오늘의 일정 플래닝 생성기"""
    
    SYSTEM_PROMPT = None

    
    def __init__(
        self,
        retriever_tool: YesterdayReportTool,
        llm_client: LLMClient,
        vector_retriever: Optional[UnifiedRetriever] = None,
        prompt_registry=None
    ):
        """
        초기화
        
        Args:
            retriever_tool: 전날 보고서 검색 도구 (PostgreSQL)
            llm_client: LLM 클라이언트
            vector_retriever: VectorDB 검색기 (과거 업무 패턴 검색용, 선택적)
        """
        self.retriever_tool = retriever_tool
        self.llm_client = llm_client
        self.vector_retriever = vector_retriever
        if prompt_registry is None:
            from multi_agent.agents.report_main_router import ReportPromptRegistry

            prompt_registry = ReportPromptRegistry
        self.prompt_registry = prompt_registry
    
    async def generate(
        self,
        request: TodayPlanRequest
    ) -> TodayPlanResponse:
        """
        오늘의 일정 플래닝
        
        Args:
            request: 일정 생성 요청
            
        Returns:
            생성된 일정
        """
        # Step 1: 전날 보고서 가져오기
        # owner 필터링 제거: 단일 워크스페이스로 동작
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        yesterday_data = self.retriever_tool.get_yesterday_report(
            owner=REPORT_OWNER,  # 상수 owner 사용
            target_date=request.target_date
        )
        
        unresolved = yesterday_data["unresolved"]
        next_day_plan = yesterday_data["next_day_plan"]
        tasks = yesterday_data.get("tasks", [])
        found = yesterday_data["found"]
        
        print(f"[DEBUG] TodayPlanGenerator.generate (async): found={found}, unresolved={len(unresolved)}, next_day_plan={len(next_day_plan)}, tasks={len(tasks)}, search_date={yesterday_data.get('search_date')}")
        
        # Step 2: VectorDB에서 최근 업무 패턴 검색
        # 익일 업무 계획이 3개 이상이면 VectorDB 검색 건너뛰기 (익일 계획이 최우선)
        similar_tasks: List[UnifiedSearchResult] = []
        
        # 익일 업무 계획이 3개 미만일 때만 VectorDB 검색 수행
        should_search_vector = len(next_day_plan) < 3
        
        if should_search_vector and self.vector_retriever:
            try:
                from datetime import timedelta
                
                today = request.target_date
                period_end = today - timedelta(days=1)  # 어제까지
                
                # 날짜 필터 없이 검색 (owner만 필터링)
                # 결과를 날짜 기준으로 필터링하고 정렬하여 최신 데이터 우선 사용
                print(f"[INFO] 최근 업무 패턴 검색 (날짜 필터 없이, 검색 후 필터링)")
                
                # 다양한 검색 쿼리
                search_queries = [
                    f"{request.owner} 최근 업무",
                    f"{request.owner} 상담 고객",
                    f"{request.owner} 계약 처리",
                    f"{request.owner} 업무 진행",
                ]
                
                all_results = []
                
                for query in search_queries:
                    # 날짜 필터 없이 검색 (더 많은 결과 확보)
                    results = self.vector_retriever.search_daily(
                        query=query,
                        owner=None,  # owner 필터링 제거
                        n_results=20,  # 날짜 필터 없이 더 많은 결과 가져오기
                        chunk_types=["detail", "summary"]
                    )
                    all_results.extend(results)
                
                print(f"[INFO] 초기 검색 결과: {len(all_results)}개 발견")
                
                # 날짜 기준으로 필터링 및 정렬 (최신순)
                # 최근 30일 이내 데이터만 선택
                max_date = period_end
                min_date = max_date - timedelta(days=30)
                min_date_str = min_date.isoformat()
                max_date_str = max_date.isoformat()
                
                filtered_results = []
                for result in all_results:
                    result_date_str = result.metadata.get("date", "")
                    # 날짜 필터링: 최근 30일 이내만
                    if result_date_str and min_date_str <= result_date_str <= max_date_str:
                        filtered_results.append(result)
                
                print(f"[INFO] 날짜 필터링 후 ({min_date_str} ~ {max_date_str}): {len(filtered_results)}개")
                
                # 완료된 업무 필터링: 다음날에 완료된 업무는 제외
                from datetime import datetime
                incomplete_results = []
                for result in filtered_results:
                    result_date_str = result.metadata.get("date", "")
                    if not result_date_str:
                        incomplete_results.append(result)
                        continue
                    
                    try:
                        result_date = datetime.strptime(result_date_str, "%Y-%m-%d").date()
                        next_day = result_date + timedelta(days=1)
                        
                        # 다음날 업무 검색 (완료 여부 확인)
                        task_text = result.text
                        # 청크 타입이 detail인 경우 실제 업무 내용 추출
                        if "[일일_DETAIL]" in task_text:
                            # 시간 범위 제거하고 업무 내용만 추출
                            lines = task_text.split('\n')
                            task_content = " ".join([line.strip() for line in lines[1:] if line.strip()])
                        else:
                            task_content = task_text
                        
                        # 다음날 같은 업무가 있는지 확인
                        next_day_tasks = self.vector_retriever.search_daily(
                            query=task_content[:100],  # 업무 내용으로 검색
                            owner=None,  # owner 필터링 제거
                            single_date=next_day.isoformat(),
                            n_results=5,
                            chunk_types=["detail"]
                        )
                        
                        # 유사도가 높은 업무가 있으면 완료된 것으로 간주
                        is_completed = False
                        for next_task in next_day_tasks:
                            # 유사한 업무가 있으면 완료된 것으로 간주
                            if next_task.score > 0.7:  # 유사도 임계값
                                is_completed = True
                                break
                        
                        if not is_completed:
                            incomplete_results.append(result)
                    except Exception as e:
                        # 날짜 파싱 실패 시 포함
                        print(f"[WARNING] 날짜 파싱 실패 ({result_date_str}): {e}")
                        incomplete_results.append(result)
                
                print(f"[INFO] 완료된 업무 필터링 후: {len(incomplete_results)}개 (제외: {len(filtered_results) - len(incomplete_results)}개)")
                
                # 날짜 기준으로 정렬 (최신순)
                incomplete_results.sort(key=lambda x: (
                    x.metadata.get("date", ""),  # 날짜 기준 (최신순)
                    -x.score  # 동일 날짜면 유사도 높은 순
                ), reverse=True)
                
                # 중복 제거 및 최신 데이터 우선 선택
                seen_tasks = set()
                diverse_tasks = []
                
                for result in incomplete_results:
                    # 텍스트의 핵심 부분으로 중복 체크
                    text_key = result.text[:50].strip()
                    if text_key and text_key not in seen_tasks:
                        diverse_tasks.append(result)
                        seen_tasks.add(text_key)
                    
                    # 최대 15개까지만
                    if len(diverse_tasks) >= 15:
                        break
                
                similar_tasks = diverse_tasks
                
                # 결과 요약 출력
                if similar_tasks:
                    dates_found = sorted(set(r.metadata.get("date", "") for r in similar_tasks if r.metadata.get("date")), reverse=True)
                    oldest_date = dates_found[-1] if dates_found else "N/A"
                    newest_date = dates_found[0] if dates_found else "N/A"
                    
                    print(f"[INFO] 최근 업무 패턴 검색 완료:")
                    print(f"  ├─ 총 {len(similar_tasks)}개 업무 발견")
                    print(f"  ├─ 날짜 범위: {oldest_date} ~ {newest_date}")
                    print(f"  └─ 검색된 업무 예시 (최신순):")
                    for idx, task in enumerate(similar_tasks[:5], 1):
                        task_date = task.metadata.get("date", "N/A")
                        print(f"      [{idx}] {task_date}: {task.text[:60]}...")
                else:
                    print(f"[WARNING] 업무 패턴 검색 결과 없음 (필터링 범위: {min_date_str} ~ {max_date_str})")
                    
            except Exception as e:
                print(f"[WARNING] VectorDB 검색 실패: {e}")
                import traceback
                traceback.print_exc()
                similar_tasks = []
        else:
            if not should_search_vector:
                print(f"[INFO] 익일 업무 계획이 {len(next_day_plan)}개로 충분하여 VectorDB 검색 건너뜀 (익일 계획 최우선)")
            elif not self.vector_retriever:
                print(f"[WARNING] VectorDB 검색기 없음 - 최근 업무 패턴 검색 불가")
        
        # Step 3: LLM 프롬프트 구성
        user_prompt = self._build_user_prompt(
            today=request.target_date,
            owner=request.owner,
            unresolved=unresolved,
            next_day_plan=next_day_plan,
            similar_tasks=similar_tasks
        )
        
        # Step 4: LLM 호출 (JSON 응답)
        llm_response = await self.llm_client.acomplete_json(
            system_prompt=self.prompt_registry.plan_system(),
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        # Step 4: 응답 파싱 및 검증
        tasks = []
        for task_dict in llm_response.get("tasks", []):
            try:
                task = TaskItem(**task_dict)
                tasks.append(task)
            except Exception as e:
                print(f"[WARNING] Task parsing error: {e}")
                continue
        
        # 최소 3개 보장 (fallback)
        if len(tasks) < 3:
            print(f"[WARNING] LLM이 {len(tasks)}개만 생성 - 기본 업무 추가")
            
            # 부족한 개수만큼 기본 업무 추가
            default_tasks = [
                TaskItem(
                    title="기존 고객 관리 및 연락",
                    description="기존 고객들에게 연락하여 현황 확인 및 관계 유지",
                    priority="medium",
                    expected_time="1시간",
                    category="고객 상담"
                ),
                TaskItem(
                    title="고객 발굴 활동",
                    description="고객 명단 검토 및 상담 준비",
                    priority="medium",
                    expected_time="1시간",
                    category="영업"
                ),
                TaskItem(
                    title="상품 정보 학습 및 업데이트",
                    description="최신 상품 정보 확인 및 학습",
                    priority="low",
                    expected_time="30분",
                    category="학습"
                )
            ]
            
            # 부족한 만큼 추가
            needed = 3 - len(tasks)
            tasks.extend(default_tasks[:needed])
        
        summary = llm_response.get("summary", "오늘의 일정 플래닝입니다.")

        task_sources = self._track_task_sources(
            tasks=tasks,
            next_day_plan=next_day_plan,
            unresolved=unresolved,
            similar_tasks=similar_tasks
        )
        
        return TodayPlanResponse(
            tasks=tasks,
            summary=summary,
            source_date=yesterday_data["search_date"],
            owner=None,  # owner 필드 제거 (더 이상 사용하지 않음)
            target_date=str(request.target_date),
            task_sources=task_sources
        )
    
    def generate_sync(
        self,
        request: TodayPlanRequest
    ) -> TodayPlanResponse:
        """
        동기 버전: 오늘의 일정 플래닝
        
        Args:
            request: 일정 생성 요청
            
        Returns:
            생성된 일정
        """
        # Step 1: 전날 보고서 가져오기
        # owner 필터링 제거: 단일 워크스페이스로 동작
        from app.core.config import settings
        REPORT_OWNER = settings.REPORT_WORKSPACE_OWNER
        yesterday_data = self.retriever_tool.get_yesterday_report(
            owner=REPORT_OWNER,  # 상수 owner 사용
            target_date=request.target_date
        )
        
        unresolved = yesterday_data["unresolved"]
        next_day_plan = yesterday_data["next_day_plan"]
        tasks = yesterday_data.get("tasks", [])
        found = yesterday_data["found"]
        
        print(f"[DEBUG] TodayPlanGenerator.generate_sync: found={found}, unresolved={len(unresolved)}, next_day_plan={len(next_day_plan)}, tasks={len(tasks)}, search_date={yesterday_data.get('search_date')}")
        
        # Step 2: VectorDB에서 최근 업무 패턴 검색
        # 익일 업무 계획이 3개 이상이면 VectorDB 검색 건너뛰기 (익일 계획이 최우선)
        similar_tasks: List[UnifiedSearchResult] = []
        
        # 익일 업무 계획이 3개 미만일 때만 VectorDB 검색 수행
        should_search_vector = len(next_day_plan) < 3
        
        if should_search_vector and self.vector_retriever:
            try:
                from datetime import timedelta
                
                today = request.target_date
                period_end = today - timedelta(days=1)  # 어제까지
                
                # 날짜 필터 없이 검색 (owner만 필터링)
                # 결과를 날짜 기준으로 필터링하고 정렬하여 최신 데이터 우선 사용
                print(f"[INFO] 최근 업무 패턴 검색 (날짜 필터 없이, 검색 후 필터링)")
                
                # 다양한 검색 쿼리
                search_queries = [
                    f"{request.owner} 최근 업무",
                    f"{request.owner} 상담 고객",
                    f"{request.owner} 계약 처리",
                    f"{request.owner} 업무 진행",
                ]
                
                all_results = []
                for query in search_queries:
                    # 날짜 필터 없이 검색 (더 많은 결과 확보)
                    results = self.vector_retriever.search_daily(
                        query=query,
                        owner=None,  # owner 필터링 제거
                        n_results=20,  # 날짜 필터 없이 더 많은 결과 가져오기
                        chunk_types=["detail", "summary"]
                    )
                    all_results.extend(results)
                
                print(f"[INFO] 초기 검색 결과: {len(all_results)}개 발견")
                
                # 날짜 기준으로 필터링 및 정렬 (최신순)
                # 최근 30일 이내 데이터만 선택
                max_date = period_end
                min_date = max_date - timedelta(days=30)
                min_date_str = min_date.isoformat()
                max_date_str = max_date.isoformat()
                
                filtered_results = []
                for result in all_results:
                    result_date_str = result.metadata.get("date", "")
                    # 날짜 필터링: 최근 30일 이내만
                    if result_date_str and min_date_str <= result_date_str <= max_date_str:
                        filtered_results.append(result)
                
                print(f"[INFO] 날짜 필터링 후 ({min_date_str} ~ {max_date_str}): {len(filtered_results)}개")
                
                # 완료된 업무 필터링: 다음날에 완료된 업무는 제외
                from datetime import datetime
                incomplete_results = []
                for result in filtered_results:
                    result_date_str = result.metadata.get("date", "")
                    if not result_date_str:
                        incomplete_results.append(result)
                        continue
                    
                    try:
                        result_date = datetime.strptime(result_date_str, "%Y-%m-%d").date()
                        next_day = result_date + timedelta(days=1)
                        
                        # 다음날 업무 검색 (완료 여부 확인)
                        task_text = result.text
                        # 청크 타입이 detail인 경우 실제 업무 내용 추출
                        if "[일일_DETAIL]" in task_text:
                            # 시간 범위 제거하고 업무 내용만 추출
                            lines = task_text.split('\n')
                            task_content = " ".join([line.strip() for line in lines[1:] if line.strip()])
                        else:
                            task_content = task_text
                        
                        # 다음날 같은 업무가 있는지 확인
                        next_day_tasks = self.vector_retriever.search_daily(
                            query=task_content[:100],  # 업무 내용으로 검색
                            owner=None,  # owner 필터링 제거
                            single_date=next_day.isoformat(),
                            n_results=5,
                            chunk_types=["detail"]
                        )
                        
                        # 유사도가 높은 업무가 있으면 완료된 것으로 간주
                        is_completed = False
                        for next_task in next_day_tasks:
                            # 유사한 업무가 있으면 완료된 것으로 간주
                            if next_task.score > 0.7:  # 유사도 임계값
                                is_completed = True
                                break
                        
                        if not is_completed:
                            incomplete_results.append(result)
                    except Exception as e:
                        # 날짜 파싱 실패 시 포함
                        print(f"[WARNING] 날짜 파싱 실패 ({result_date_str}): {e}")
                        incomplete_results.append(result)
                
                print(f"[INFO] 완료된 업무 필터링 후: {len(incomplete_results)}개 (제외: {len(filtered_results) - len(incomplete_results)}개)")
                
                # 날짜 기준으로 정렬 (최신순)
                incomplete_results.sort(key=lambda x: (
                    x.metadata.get("date", ""),  # 날짜 기준 (최신순)
                    -x.score  # 동일 날짜면 유사도 높은 순
                ), reverse=True)
                
                # 중복 제거 및 최신 데이터 우선 선택
                seen_tasks = set()
                diverse_tasks = []
                
                for result in incomplete_results:
                    # 텍스트의 핵심 부분으로 중복 체크
                    text_key = result.text[:50].strip()
                    if text_key and text_key not in seen_tasks:
                        diverse_tasks.append(result)
                        seen_tasks.add(text_key)
                    
                    # 최대 20개까지만
                    if len(diverse_tasks) >= 20:
                        break
                
                similar_tasks = diverse_tasks
                
                # 결과 요약 출력
                if similar_tasks:
                    dates_found = sorted(set(r.metadata.get("date", "") for r in similar_tasks if r.metadata.get("date")), reverse=True)
                    oldest_date = dates_found[-1] if dates_found else "N/A"
                    newest_date = dates_found[0] if dates_found else "N/A"
                    
                    print(f"[INFO] 최근 업무 패턴 검색 완료:")
                    print(f"  ├─ 총 {len(similar_tasks)}개 업무 발견")
                    print(f"  ├─ 날짜 범위: {oldest_date} ~ {newest_date}")
                    print(f"  └─ 검색된 업무 예시 (최신순):")
                    for idx, task in enumerate(similar_tasks[:5], 1):
                        task_date = task.metadata.get("date", "N/A")
                        print(f"      [{idx}] {task_date}: {task.text[:60]}...")
                else:
                    print(f"[WARNING] 업무 패턴 검색 결과 없음 (필터링 범위: {min_date_str} ~ {max_date_str})")
                    
            except Exception as e:
                print(f"[WARNING] VectorDB 검색 실패: {e}")
                import traceback
                traceback.print_exc()
                similar_tasks = []
        else:
            if not should_search_vector:
                print(f"[INFO] 익일 업무 계획이 {len(next_day_plan)}개로 충분하여 VectorDB 검색 건너뜀 (익일 계획 최우선)")
            elif not self.vector_retriever:
                print(f"[WARNING] VectorDB 검색기 없음 - 최근 업무 패턴 검색 불가")
        
        # Step 3: LLM 프롬프트 구성
        user_prompt = self._build_user_prompt(
            today=request.target_date,
            owner=request.owner,
            unresolved=unresolved,
            next_day_plan=next_day_plan,
            tasks=tasks,
            similar_tasks=similar_tasks
        )
        
        # Step 4: LLM 호출 (JSON 응답) - 동기
        llm_response = self.llm_client.complete_json(
            system_prompt=self.prompt_registry.plan_system(),
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        # Step 5: 응답 파싱 및 검증
        tasks = []
        for task_dict in llm_response.get("tasks", []):
            try:
                task = TaskItem(**task_dict)
                tasks.append(task)
            except Exception as e:
                print(f"[WARNING] Task parsing error: {e}")
                continue
        
        # 최소 3개 보장 (fallback)
        if len(tasks) < 3:
            print(f"[WARNING] LLM이 {len(tasks)}개만 생성 - 기본 업무 추가")
            
            # 부족한 개수만큼 기본 업무 추가
            default_tasks = [
                TaskItem(
                    title="기존 고객 관리 및 연락",
                    description="기존 고객들에게 연락하여 현황 확인 및 관계 유지",
                    priority="medium",
                    expected_time="1시간",
                    category="고객 상담"
                ),
                TaskItem(
                    title="고객 발굴 활동",
                    description="고객 명단 검토 및 상담 준비",
                    priority="medium",
                    expected_time="1시간",
                    category="영업"
                ),
                TaskItem(
                    title="상품 정보 학습 및 업데이트",
                    description="최신 상품 정보 확인 및 학습",
                    priority="low",
                    expected_time="30분",
                    category="학습"
                )
            ]
            
            # 부족한 만큼 추가
            needed = 3 - len(tasks)
            tasks.extend(default_tasks[:needed])
        
        summary = llm_response.get("summary", "오늘의 일정 플래닝입니다.")
        
        # 업무 출처 추적
        task_sources = self._track_task_sources(
            tasks=tasks,
            next_day_plan=next_day_plan,
            unresolved=unresolved,
            similar_tasks=similar_tasks
        )
        
        return TodayPlanResponse(
            tasks=tasks,
            summary=summary,
            source_date=yesterday_data["search_date"],
            owner=None,  # owner 필드 제거 (더 이상 사용하지 않음)
            target_date=str(request.target_date),
            task_sources=task_sources
        )
    
    def _build_user_prompt(
        self,
        today: date,
        owner: str,
        unresolved: list,
        next_day_plan: list,
        tasks: list = None,
        similar_tasks: List[UnifiedSearchResult] = None
    ) -> str:
        """LLM 사용자 프롬프트 구성 (데이터만 조립)."""
        unresolved_text = "\\n".join([f"- {item}" for item in unresolved]) if unresolved else "없음"
        next_day_plan_text = "\\n".join([f"- {item}" for item in next_day_plan]) if next_day_plan else "없음"
        tasks_text = "\\n".join([f"- {item}" for item in (tasks or [])]) if tasks else "없음"

        similar_tasks_text = "없음"
        if similar_tasks:
            task_patterns = []
            for result in similar_tasks[:15]:
                if result.chunk_type in ["detail", "summary"]:
                    task_date = result.metadata.get("date", "N/A")
                    task_patterns.append(f"- [{task_date}] {result.text}")
            if task_patterns:
                similar_tasks_text = "\\n".join(task_patterns)

        return self.prompt_registry.plan_user(
            today=today,
            owner=owner,
            tasks_text=tasks_text,
            next_day_plan_text=next_day_plan_text,
            unresolved_text=unresolved_text,
            similar_tasks_text=similar_tasks_text,
        )

    def _track_task_sources(
        self,
        tasks: List[TaskItem],
        next_day_plan: list,
        unresolved: list,
        similar_tasks: List[UnifiedSearchResult]
    ) -> List[TaskSource]:
        """
        업무 출처 추적
        
        Args:
            tasks: 생성된 업무 목록
            next_day_plan: 전날 익일 계획
            unresolved: 전날 미종결 업무
            similar_tasks: ChromaDB에서 가져온 유사 업무
            
        Returns:
            각 업무의 출처 정보
        """
        task_sources = []
        
        for idx, task in enumerate(tasks):
            task_text = f"{task.title} {task.description}".lower()
            source_type = None
            source_description = None
            
            # 1순위: 익일 업무 계획 확인
            for plan in next_day_plan:
                if plan.lower() in task_text or task_text in plan.lower():
                    source_type = "yesterday_plan"
                    source_description = "전날 계획한 익일 업무 계획"
                    break
            
            # 2순위: 미종결 업무 확인
            if not source_type:
                for unresolved_item in unresolved:
                    if unresolved_item.lower() in task_text or task_text in unresolved_item.lower():
                        source_type = "yesterday_unresolved"
                        source_description = "전날 미종결 업무"
                        break
            
            # 3순위: ChromaDB 추천 업무 확인
            if not source_type and similar_tasks:
                for similar_task in similar_tasks:
                    similar_text = similar_task.text.lower()
                    # 간단한 키워드 매칭
                    task_keywords = set(task_text.split())
                    similar_keywords = set(similar_text.split())
                    if len(task_keywords & similar_keywords) >= 2:  # 최소 2개 키워드 일치
                        source_type = "chromadb_recommendation"
                        source_description = "맞춤형 추천 업무(ChromaDB 접근)"
                        break
            
            # 출처를 찾지 못한 경우 기본값
            if not source_type:
                source_type = "chromadb_recommendation"
                source_description = "맞춤형 추천 업무(ChromaDB 접근)"
            
            task_sources.append(TaskSource(
                source_type=source_type,
                source_description=source_description,
                task_index=idx
            ))
        
        return task_sources

