"""
심리 상담 서비스
생성날짜: 2025.11.24
설명: RAG 기반 아들러 심리 상담 시스템 서비스 레이어
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

# councel 디렉토리를 Python 경로에 추가
COUNCEL_DIR = Path(__file__).parent.parent.parent.parent / "councel"
sys.path.insert(0, str(COUNCEL_DIR))

# RAG 심리 상담 시스템 메인코드 임포트
from sourcecode.rag_therapy import RAGTherapySystem

# 심리 상담 서비스 클래스(싱글톤 인스턴스)
class TherapyService:
    
    _instance: Optional['TherapyService'] = None # 심리 상담 서비스 인스턴스
    _rag_system: Optional[RAGTherapySystem] = None # RAG 심리 상담 시스템 인스턴스
    
    # 심리 상담 시스템 인스턴스 생성
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    # 시스템 초기화 함수
    def __init__(self):

        # RAG 심리 상담 시스템이 없으면 초기화
        if self._rag_system is None:
            # Vector DB 경로 설정
            base_dir = Path(__file__).parent.parent.parent.parent
            vector_db_dir = base_dir / "councel" / "vector_db"
            
            try:
                # RAG 상담 시스템 초기화
                self._rag_system = RAGTherapySystem(str(vector_db_dir))
            except Exception as e:
                print(f"RAG 심리 상담 시스템 초기화 실패: {e}")
                self._rag_system = None
    
    # 상담 시스템 사용 가능 여부 확인
    def is_available(self) -> bool:

        # RAG 심리 상담 시스템이 있으면 True, 없으면 False
        return self._rag_system is not None
    
    # 상담 응답 생성
    # 사용자의 입력을 받아 응답 생성 -> RAG 심리 상담 시스템의 chat 함수 호출
    async def chat(self, user_input: str, enable_scoring: bool = True, user_id: Optional[str] = None) -> Dict[str, Any]:

        # 상담 시스템 사용 가능 여부가 불가능하면 return 반환
        if not self.is_available():
            return {
                "answer": "죄송합니다. 심리 상담 시스템이 현재 사용 불가능합니다.",
                "used_chunks": [],
                "mode": "error",
                "continue_conversation": False,
                "scoring": None,
            }
        
        try:
            # RAG 시스템으로 상담 진행
            response = await self._rag_system.chat(user_input, user_id=user_id)
            return response
        except Exception as e:
            print(f"상담 처리 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return {
                "answer": f"죄송합니다. 상담 처리 중 오류가 발생했습니다: {str(e)}",
                "used_chunks": [],
                "mode": "error",
                "continue_conversation": True,
                "scoring": None,
            }
    
    # 사용자 세션 초기화
    def reset_session(self, user_id: Optional[str] = None) -> bool:
        """사용자 세션 초기화"""
        if not self.is_available():
            return False
        
        try:
            self._rag_system.reset_session(user_id=user_id)
            return True
        except Exception as e:
            print(f"세션 초기화 중 오류: {e}")
            return False

