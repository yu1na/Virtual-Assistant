"""
Context Management Module

ContextVars를 사용하여 비동기 요청 간의 컨텍스트(세션 ID, 사용자 정보 등)를 안전하게 관리합니다.
"""

from contextvars import ContextVar
from typing import Dict, Any, Optional

# 세션 컨텍스트 (세션 ID)
session_context: ContextVar[Optional[str]] = ContextVar("session_context", default=None)

# 사용자 컨텍스트 (사용자 ID 및 추가 정보)
user_context: ContextVar[Dict[str, Any]] = ContextVar("user_context", default={})

def get_session_id() -> Optional[str]:
    """현재 컨텍스트의 세션 ID를 반환합니다."""
    return session_context.get()

def get_user_context() -> Dict[str, Any]:
    """현재 컨텍스트의 사용자 정보를 반환합니다."""
    return user_context.get()

def reset_context():
    """컨텍스트를 초기화합니다."""
    session_context.set(None)
    user_context.set({})
