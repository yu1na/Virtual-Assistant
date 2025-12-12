"""
Therapy Agent

심리 상담 에이전트
기존 TherapyService를 활용합니다.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent

# 심리 상담 에이전트 클래스
class TherapyAgent(BaseAgent):

    # 초기화 함수
    def __init__(self):
        super().__init__(
            name="therapy",
            description="심리 상담과 정신 건강 지원을 제공하는 에이전트입니다. "
                       "아들러 개인심리학 기반으로 상담과 조언을 제공합니다. "
                       "감정적 지원, 스트레스 관리, 대인관계 조언 등이 필요할 때 사용합니다."
        )
        # Lazy loading: 실제 사용 시에만 TherapyService 로드
        self._therapy_service = None
    
    # property: 메소드를 변수처럼 사용할 수 있게 해주는 기능
    @property
    def therapy_service(self):
        """TherapyService lazy loading"""
        if self._therapy_service is None:
            from app.domain.therapy.service import TherapyService
            self._therapy_service = TherapyService()
        return self._therapy_service
    
    # 심리 상담 처리 비동기 함수
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:

        try:
            # 상담 시스템 사용 가능 여부 확인
            if not self.therapy_service.is_available():
                return "죄송합니다. 심리 상담 시스템이 현재 사용 불가능합니다. 잠시 후 다시 시도해주세요."
            
            # 컨텍스트에서 enable_scoring 추출 (기본값: True)
            enable_scoring = True
            if context and "enable_scoring" in context:
                enable_scoring = context["enable_scoring"]
            
            # TherapyService를 통해 상담 진행
            response = await self.therapy_service.chat(
                user_input=query,
                enable_scoring=enable_scoring
            )
            
            # 응답 구성
            answer = response.get("answer", "상담 응답을 생성할 수 없습니다.")
            
            # 모드 정보 추가 (디버깅용, 선택적)
            mode = response.get("mode", "unknown")
            if mode != "normal":
                # 필요시 모드 정보를 답변에 포함할 수 있음
                pass
            
            return answer
            
        except Exception as e:
            return f"심리 상담 처리 중 오류가 발생했습니다: {str(e)}"
    
    # 에이전트 기능 목록
    def get_capabilities(self) -> list:

        return [
            "심리 상담",
            "감정적 지원",
            "스트레스 관리 조언",
            "대인관계 조언",
            "정신 건강 지원",
            "아들러 개인심리학 기반 상담",
        ]

