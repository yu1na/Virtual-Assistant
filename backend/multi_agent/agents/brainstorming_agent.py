"""
Brainstorming Agent

브레인스토밍 및 창의적 아이디어 제안 에이전트
기존 BrainstormingService를 활용합니다.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent

# 브레인스토밍 에이전트 클래스
class BrainstormingAgent(BaseAgent):

    # 초기화 함수    
    def __init__(self):
        super().__init__(
            name="brainstorming",
            description="창의적인 아이디어 발상과 브레인스토밍 기법을 제안하는 에이전트입니다. "
                       "문제 해결, 아이디어 도출, 창의적 사고 방법 등을 안내합니다."
        )
        # Lazy loading: 실제 사용 시에만 BrainstormingService 로드
        self._brainstorming_service = None
    
    # @property: 메소드를 변수처럼 사용할 수 있게 해주는 기능
    @property
    def brainstorming_service(self):
        """BrainstormingService lazy loading"""
        if self._brainstorming_service is None:
            from app.domain.brainstorming.service import BrainstormingService
            self._brainstorming_service = BrainstormingService()
        return self._brainstorming_service
    
    # 브레인스토밍 진행하는 비동기 함수
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:

        try:
            # Supervisor가 이 에이전트를 선택했다는 것은
            # 사용자가 아이디어/브레인스토밍이 필요한 상황이라는 의미
            # RAG 검색 없이 바로 브레인스토밍 도구 사용을 제안
            
            print(f"[BrainstormingAgent] 쿼리: {query}")
            print(f"[BrainstormingAgent] 브레인스토밍 도구 제안 모드")
            
            # 사용자의 쿼리에서 주제 추출 (간단하게)
            # 예: "빵집 매출 증대 아이디어" -> "빵집 매출 증대"
            topic_hint = ""
            if "빵집" in query or "카페" in query or "가게" in query:
                topic_hint = "관련 "
            elif "마케팅" in query:
                topic_hint = "마케팅 "
            elif "프로젝트" in query or "기획" in query:
                topic_hint = "프로젝트 "
            
            # 간결한 제안 메시지 반환
            return f"SUGGESTION: 브레인스토밍 도구로 {topic_hint}아이디어를 함께 만들어볼까요? 🚀"
            
        except Exception as e:
            print(f"[BrainstormingAgent] 오류: {e}")
            return f"브레인스토밍 제안 중 오류가 발생했습니다: {str(e)}"
    
    # 브레인스토밍 에이전트 기능 목록 리턴
    def get_capabilities(self) -> list:
        
        return [
            "창의적 아이디어 제안",
            "브레인스토밍 기법 안내",
            "문제 해결 방법 제시",
            "협업 방법 제안",
            "혁신적 사고 촉진",
        ]

