"""
Multi-Agent 시스템 설정
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class MultiAgentConfig(BaseSettings):
    """Multi-Agent 시스템 설정"""
    
    # OpenAI 설정
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    SUPERVISOR_MODEL: str = os.getenv("SUPERVISOR_MODEL", "gpt-4o")
    AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gpt-4o-mini")
    
    # Temperature 설정
    SUPERVISOR_TEMPERATURE: float = 0.3  # Supervisor는 더 결정적으로
    AGENT_TEMPERATURE: float = 0.7  # 에이전트는 더 창의적으로
    
    # 토큰 제한
    MAX_TOKENS: int = 2000
    
    # 세션 설정
    SESSION_TIMEOUT: int = 3600  # 1시간
    
    # LangSmith 추적 (선택)
    LANGSMITH_TRACING: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    LANGSMITH_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY")
    LANGSMITH_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "multi-agent-system")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 다른 환경 변수 무시 (Pydantic 2.x)


# 전역 설정 인스턴스
multi_agent_config = MultiAgentConfig()

