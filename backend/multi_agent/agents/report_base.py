"""
Report Base Agent Class

모든 보고서 관련 에이전트의 기본 클래스
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.llm.client import LLMClient


class ReportBaseAgent(ABC):
    """모든 보고서 에이전트의 기본 클래스"""
    
    def __init__(
        self,
        name: str,
        description: str,
        llm_client: Optional[LLMClient] = None
    ):
        """
        초기화
        
        Args:
            name: 에이전트 이름
            description: 에이전트 설명
            llm_client: LLM 클라이언트 (None이면 기본 생성)
        """
        self.name = name
        self.description = description
        
        # LLM 클라이언트
        if llm_client is None:
            self.llm = LLMClient(
                model="gpt-4o",
                temperature=0.7,
                max_tokens=2000
            )
        else:
            self.llm = llm_client
    
    @abstractmethod
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        사용자 쿼리 처리
        
        Args:
            query: 사용자 질문
            context: 추가 컨텍스트 정보
            
        Returns:
            에이전트 응답
        """
        pass
    
    def get_info(self) -> Dict[str, str]:
        """
        에이전트 정보 반환
        
        Returns:
            에이전트 정보 딕셔너리
        """
        return {
            "name": self.name,
            "description": self.description
        }

