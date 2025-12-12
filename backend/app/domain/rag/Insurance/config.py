"""
Insurance RAG 전용 설정 파일

HR RAG와 완전히 분리된 독립적인 설정입니다.
"""

from pathlib import Path
from typing import Optional
from app.core.config import settings


class InsuranceRAGConfig:
    """Insurance RAG 시스템 설정 (HR과 완전히 분리)"""
    
    def __init__(self):
        # 기존 core/config.py의 settings 재사용
        self._settings = settings
        
        # 디렉토리 생성
        self.ensure_directories()
    
    # ========================================
    # 기존 설정 재사용 (core/config.py)
    # ========================================
    
    @property
    def OPENAI_API_KEY(self) -> str:
        """OpenAI API Key (기존 설정 사용)"""
        return self._settings.OPENAI_API_KEY
    
    @property
    def OPENAI_MODEL(self) -> str:
        """OpenAI LLM 모델 (기존 설정 사용)"""
        return self._settings.LLM_MODEL
    
    @property
    def OPENAI_VISION_MODEL(self) -> str:
        """OpenAI Vision 모델"""
        return "gpt-4o"  # Vision은 gpt-4o 사용
    
    @property
    def OPENAI_TEMPERATURE(self) -> float:
        """LLM Temperature (기존 설정 사용)"""
        return self._settings.LLM_TEMPERATURE
    
    @property
    def OPENAI_MAX_TOKENS(self) -> int:
        """LLM Max Tokens (기존 설정 사용)"""
        return self._settings.LLM_MAX_TOKENS
    
    @property
    def OPENAI_EMBEDDING_MODEL(self) -> str:
        """Embedding 모델"""
        return "text-embedding-3-large"
    
    @property
    def CHROMA_PERSIST_DIRECTORY(self) -> str:
        """ChromaDB 저장 경로 (Insurance 전용)"""
        # Insurance 전용 ChromaDB 경로 (모듈 독립성)
        from pathlib import Path
        insurance_dir = Path(__file__).parent / "chroma_db"
        return str(insurance_dir.absolute())
    
    @property
    def CHROMA_COLLECTION_NAME(self) -> str:
        """ChromaDB 컬렉션명 (Insurance 전용, HR과 분리)"""
        return "insurance_documents"
    
    # ========================================
    # Insurance 전용 디렉토리
    # ========================================
    
    @property
    def INS_ROOT(self) -> Path:
        """Insurance 루트 디렉토리"""
        # Insurance 모듈 기준 상대 경로
        return Path(__file__).parent / "internal_insurance"
    
    @property
    def UPLOAD_DIR(self) -> Path:
        """업로드 디렉토리 (Insurance 전용)"""
        return self.INS_ROOT / "uploads"
    
    @property
    def PROCESSED_DIR(self) -> Path:
        """처리된 파일 디렉토리 (Insurance 전용)"""
        return self.INS_ROOT / "processed"
    
    # ========================================
    # RAG 전용 설정
    # ========================================
    
    # OpenAI 임베딩 모델 (text-embedding-3-large)
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 3072
    
    # 번역용 모델 (GPT-4o-mini)
    TRANSLATION_MODEL: str = "gpt-4o-mini"
    
    # 청크 설정 (문자 기반 - 하위 호환성)
    RAG_CHUNK_SIZE: int = 400
    RAG_CHUNK_OVERLAP: int = 50
    RAG_MIN_CHUNK_SIZE: int = 300
    RAG_MAX_CHUNK_SIZE: int = 500
    
    # 청크 설정 (토큰 기반 - 새 청킹 시스템)
    RAG_CHUNK_TOKENS: int = 384
    RAG_CHUNK_OVERLAP_TOKENS: int = 80
    
    # 검색 설정
    RAG_TOP_K: int = 3
    RAG_MAX_TOP_K: int = 4
    RAG_MIN_SIMILARITY_THRESHOLD: float = 0.25  # 최소 threshold
    RAG_MAX_SIMILARITY_THRESHOLD: float = 0.375  # 최대 threshold (min의 1.5배)
    # 동적 threshold는 항상 활성화: 검색 결과에 따라 min~max 범위 내에서 자동 조정
    # OpenAI 임베딩은 cosine similarity 사용 (0~1 범위, 높을수록 유사)
    
    # LangSmith 설정
    @property
    def LANGSMITH_API_KEY(self) -> Optional[str]:
        """LangSmith API Key (core settings에서 읽기)"""
        return self._settings.LANGSMITH_API_KEY if self._settings.LANGSMITH_API_KEY else None
    
    @property
    def LANGSMITH_PROJECT(self) -> str:
        """LangSmith 프로젝트명"""
        return self._settings.LANGSMITH_PROJECT
    
    @property
    def LANGSMITH_TRACING(self) -> bool:
        """LangSmith 추적 활성화 여부"""
        return self._settings.LANGSMITH_TRACING.lower() == "true"
    
    # PDF 처리 설정
    MAX_IMAGE_SIZE: tuple = (1024, 1024)
    IMAGE_DPI: int = 150
    
    # 표 감지 설정
    TABLE_MIN_ROWS: int = 2
    TABLE_MIN_COLS: int = 2
    
    def ensure_directories(self):
        """필요한 디렉토리 생성"""
        self.INS_ROOT.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        Path(self.CHROMA_PERSIST_DIRECTORY).mkdir(parents=True, exist_ok=True)


# 싱글톤 인스턴스
insurance_config = InsuranceRAGConfig()
