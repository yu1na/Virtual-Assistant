"""
세션 관리 모듈

동시성을 고려한 임시 세션(Ephemeral Session) 생성, 조회, 삭제를 관리합니다.
- 세션별 독립적 Lock (병렬 처리 가능)
- Atomic 연산 보장
- Java의 ConcurrentHashMap 수준의 동시성 처리
"""

import uuid
import threading
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional
import shutil

# Import 경로 처리 (FastAPI vs 직접 실행)
try:
    from app.domain.common.base_session_manager import BaseSessionManager
except ImportError:
    import sys
    project_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(project_root))
    from app.domain.common.base_session_manager import BaseSessionManager


class BrainstormingSessionData:
    """브레인스토밍 세션 데이터"""
    
    def __init__(self, session_id: str, session_dir: Path):
        self.id = session_id
        self.created_at = datetime.now().isoformat()
        self.directory = str(session_dir)
        self.q1_purpose = None
        self.q2_warmup = None
        self.q3_associations = []
        self.ideas = []
        # 2024-11-30: chroma_collection 제거 (Ephemeral RAG → JSON 기반)
        self.ephemeral_rag_initialized = False


class SessionManager(BaseSessionManager[BrainstormingSessionData]):
    """
    세션 관리자 클래스
    
    - UUID 기반 세션 ID 생성
    - 세션별 독립적 Lock (병렬 처리)
    - 세션별 데이터 디렉토리 관리
    """
    
    _instance = None
    _init_lock = None
    
    def __new__(cls):
        """싱글톤 패턴: 전역에서 하나의 SessionManager만 존재"""
        if cls._init_lock is None:
            cls._init_lock = threading.Lock()
        
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """초기화 (싱글톤이므로 한 번만 실행됨)"""
        if not hasattr(self, '_initialized'):
            super().__init__()
            
            # 현재 파일의 디렉토리 기준으로 경로 설정
            current_file = Path(__file__).resolve()
            self.module_dir = current_file.parent
            self.ephemeral_dir = self.module_dir / "data" / "ephemeral"
            
            # ephemeral 디렉토리 생성
            self.ephemeral_dir.mkdir(parents=True, exist_ok=True)
            
            # 비동기 환경용 Lock
            self._async_locks = {}  # {session_id: asyncio.Lock}
            self._async_locks_lock = threading.Lock()  # async locks 딕셔너리용 Lock
            
            self._initialized = True
            print(f"✅ SessionManager 초기화 완료")
            print(f"   - Ephemeral 디렉토리: {self.ephemeral_dir}")
    
    def _get_async_lock(self, session_id: str) -> asyncio.Lock:
        """세션별 비동기 Lock 가져오기 (Lazy 생성)"""
        with self._async_locks_lock:
            if session_id not in self._async_locks:
                self._async_locks[session_id] = asyncio.Lock()
            return self._async_locks[session_id]
    
    def create_session(self) -> str:
        """
        새로운 세션 생성 (동기 환경용, Thread-safe)
        
        Returns:
            str: 생성된 세션 ID (UUID)
        """
        session_id = str(uuid.uuid4())
        session_dir = self.ephemeral_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Atomic get-or-create
        session_data = self._safe_get_or_create(
            session_id,
            lambda: BrainstormingSessionData(session_id, session_dir)
        )
        
        print(f"✅ 세션 생성: {session_id}")
        return session_id
    
    async def create_session_async(self) -> str:
        """
        새로운 세션 생성 (비동기 환경용)
        
        Returns:
            str: 생성된 세션 ID (UUID)
        """
        session_id = str(uuid.uuid4())
        session_dir = self.ephemeral_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 비동기 Lock 사용
        async_lock = self._get_async_lock(session_id)
        async with async_lock:
            # Atomic get-or-create
            session_data = self._safe_get_or_create(
                session_id,
                lambda: BrainstormingSessionData(session_id, session_dir)
            )
        
        print(f"✅ 세션 생성 (async): {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """
        세션 정보 조회 (동기 환경용, Thread-safe)
        
        Args:
            session_id: 세션 ID
            
        Returns:
            dict | None: 세션 정보 또는 None
        """
        session_data = self._safe_get(session_id)
        
        if session_data is None:
            return None
        
        # dict 형태로 변환
        return {
            'id': session_data.id,
            'created_at': session_data.created_at,
            'directory': session_data.directory,
            'q1_purpose': session_data.q1_purpose,
            'q2_warmup': session_data.q2_warmup,
            'q3_associations': session_data.q3_associations.copy(),
            'ideas': session_data.ideas.copy(),
            'ephemeral_rag_initialized': session_data.ephemeral_rag_initialized
        }
    
    async def get_session_async(self, session_id: str) -> Optional[dict]:
        """
        세션 정보 조회 (비동기 환경용)
        
        Args:
            session_id: 세션 ID
            
        Returns:
            dict | None: 세션 정보 또는 None
        """
        async_lock = self._get_async_lock(session_id)
        async with async_lock:
            return self.get_session(session_id)
    
    def update_session(self, session_id: str, updates: dict) -> bool:
        """
        세션 정보 업데이트 (동기 환경용, Thread-safe)
        
        Args:
            session_id: 세션 ID
            updates: 업데이트할 필드 딕셔너리
            
        Returns:
            bool: 성공 여부
        """
        def _update(session_data: BrainstormingSessionData):
            for key, value in updates.items():
                if hasattr(session_data, key):
                    setattr(session_data, key, value)
        
        return self._safe_update(session_id, _update)
    
    async def update_session_async(self, session_id: str, updates: dict) -> bool:
        """
        세션 정보 업데이트 (비동기 환경용)
        
        Args:
            session_id: 세션 ID
            updates: 업데이트할 필드 딕셔너리
            
        Returns:
            bool: 성공 여부
        """
        async_lock = self._get_async_lock(session_id)
        async with async_lock:
            return self.update_session(session_id, updates)
    
    def delete_session(self, session_id: str):
        """
        세션 삭제 (동기 환경용, Thread-safe)
        
        Args:
            session_id: 세션 ID
        """
        # 세션 데이터 가져오기
        session_data = self._safe_get(session_id)
        
        if session_data:
            # 디렉토리 삭제
            try:
                session_dir = Path(session_data.directory)
                if session_dir.exists():
                    shutil.rmtree(session_dir)
                    print(f"✅ 세션 디렉토리 삭제: {session_dir}")
            except Exception as e:
                print(f"⚠️  세션 디렉토리 삭제 실패: {e}")
        
        # 세션 데이터 삭제
        deleted = self._safe_delete(session_id)
        
        # 비동기 Lock도 정리
        with self._async_locks_lock:
            if session_id in self._async_locks:
                del self._async_locks[session_id]
        
        if deleted:
            print(f"✅ 세션 삭제 완료: {session_id}")
        else:
            print(f"⚠️  세션을 찾을 수 없음: {session_id}")
    
    async def delete_session_async(self, session_id: str):
        """
        세션 삭제 (비동기 환경용)
        
        Args:
            session_id: 세션 ID
        """
        async_lock = self._get_async_lock(session_id)
        async with async_lock:
            self.delete_session(session_id)
    
    def list_sessions(self) -> list:
        """
        모든 세션 ID 목록 조회
        
        Returns:
            list: 세션 ID 리스트
        """
        return self._safe_list_sessions()
    
    def session_exists(self, session_id: str) -> bool:
        """
        세션 존재 여부 확인
        
        Args:
            session_id: 세션 ID
            
        Returns:
            bool: 존재 여부
        """
        return self._safe_exists(session_id)
