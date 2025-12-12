"""
Chatbot Agent

일반 대화 처리 에이전트
기존 ChatService를 활용합니다.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent

# 일반 챗봇 대화 처리 에이전트 클래스
class ChatbotAgent(BaseAgent):

    # 초기화 함수
    def __init__(self):
        super().__init__(
            name="chatbot",
            description="일반적인 대화와 질문에 답변하는 에이전트입니다. "
                       "인사, 잡담, 일상적인 질문 등을 처리합니다."
        )
        # Lazy loading: 실제 사용 시에만 ChatService 로드
        self._chat_service = None
    
    # @property: 메소드를 변수처럼 사용할 수 있게 해주는 기능
    @property
    def chat_service(self):
        """ChatService lazy loading"""
        if self._chat_service is None:
            from app.domain.chatbot.service import ChatService
            self._chat_service = ChatService()
        return self._chat_service
    
    # 일반 대화 처리 기능을 하는 비동기 함수
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:

        try:
            # 컨텍스트에서 세션 ID 추출
            session_id = None
            user_id = None
            
            if context:
                session_id = context.get("session_id")
                user_id = context.get("user_id")
            
            # 세션이 없으면 새로 생성
            if not session_id:
                session_id = self.chat_service.create_session(user_id=user_id)
            
            # ChatService를 통해 메시지 처리
            response = await self.chat_service.process_message(
                session_id=session_id,
                user_message=query,
                user_id=user_id,
                temperature=0.7
            )
            
            return response
            
        except Exception as e:
            return f"챗봇 처리 중 오류가 발생했습니다: {str(e)}"
    
    # 기능 목록 리턴해주는 함수
    def get_capabilities(self) -> list:

        return [
            "일반 대화",
            "인사 및 잡담",
            "간단한 질문 답변",
            "대화 히스토리 유지",
        ]

