"""
Base Agent 클래스

모든 전문 에이전트의 기본 클래스
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# 모든 에이전트의 기본 클래스
# 이 클래스 안에 있는 함수들을 다른 에이전트에서 상속받아 구현
class BaseAgent(ABC):
    
    # 초기화 함수
    def __init__(self, name: str, description: str):

        self.name = name # 에이전트 이름
        self.description = description # 에이전트 설명
    
    # 질문 처리를 하는 비동기 함수(추상 메서드)
    # @abstractmethod: 추상 메서드를 만드는 파이썬 데코레이터(@ << 이게 데코레이터 어노테이션 X)
    @abstractmethod
    async def process(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        
        # 상속받은 클래스는 여기 안에 처리를 하는 코드 작성
        # 부모 클래스에서는 패스
        pass
    
    # 에이전트 이름 반환
    def get_name(self) -> str:
        return self.name
    
    # 에이전트 설명 반환
    def get_description(self) -> str:
        return self.description
    
    # 에이전트 기능 목록 반환
    def get_capabilities(self) -> list:

        # 상속받은 클래스는 여기 안에 기능을 넣으면 됨
        return []
    
    # 에이전트 정보 반환
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"

