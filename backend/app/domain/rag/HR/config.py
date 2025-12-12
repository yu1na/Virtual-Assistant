"""
RAG 전용 설정 파일

기존 core/config.py의 설정을 재사용하고 RAG 전용 설정만 추가합니다.
"""

from pathlib import Path
from typing import Optional
from app.core.config import settings


class RAGConfig:
    """RAG 시스템 설정 (기존 설정 재사용)"""
    
    def __init__(self):
        # 기존 core/config.py의 settings 재사용
        self._settings = settings
        
        # 디렉토리 생성
        self.ensure_directories()
    
    # ========================================
    # 경로 설정 (절대 경로로 고정하여 오류 방지)
    # ========================================
    
    @property
    def BASE_DIR(self) -> Path:
        """backend 폴더의 절대 경로를 반환합니다."""
        # 현재 파일 위치: backend/app/domain/rag/HR/config.py
        # .parents[4] -> backend 폴더
        return Path(__file__).resolve().parents[4]

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
    def CHROMA_PERSIST_DIRECTORY(self) -> str:
        """ChromaDB 저장 경로 (절대 경로 고정)"""
        # 실행 위치에 상관없이 항상 backend/chroma_db를 바라보게 함
        return str(self.BASE_DIR / "chroma_db")
    
    @property
    def CHROMA_COLLECTION_NAME(self) -> str:
        """ChromaDB 컬렉션명 (RAG 전용)"""
        # 기존 로그와 일치시키기 위해 이름 변경
        return "hr_documents"
    
    @property
    def UPLOAD_DIR(self) -> Path:
        """업로드 디렉토리 (절대 경로)"""
        return self.BASE_DIR / "internal_docs" / "uploads"
    
    @property
    def DATA_DIR(self) -> Path:
        """데이터 디렉토리 (절대 경로)"""
        return self.BASE_DIR / "internal_docs"
    
    @property
    def PROCESSED_DIR(self) -> Path:
        """처리된 파일 디렉토리 (절대 경로)"""
        return self.BASE_DIR / "internal_docs" / "processed"
    
    # ========================================
    # RAG 전용 설정
    # ========================================
    
    # OpenAI 임베딩 모델 (text-embedding-3-large)
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 3072
    
    # 번역용 모델 (GPT-4o-mini)
    TRANSLATION_MODEL: str = "gpt-4o-mini"
    
    # 청크 설정 - 텍스트용
    RAG_TEXT_CHUNK_SIZE: int = 400
    RAG_TEXT_CHUNK_OVERLAP: int = 50
    RAG_TEXT_MIN_CHUNK_SIZE: int = 300
    RAG_TEXT_MAX_CHUNK_SIZE: int = 500
    
    # 청크 설정 - 표/그래프/이미지용
    RAG_VISUAL_CHUNK_SIZE: int = 750
    RAG_VISUAL_CHUNK_OVERLAP: int = 100
    RAG_VISUAL_MIN_CHUNK_SIZE: int = 600
    RAG_VISUAL_MAX_CHUNK_SIZE: int = 900
    
    # 하이브리드 검색 설정 (벡터 + BM25)
    USE_HYBRID_SEARCH: bool = True
    VECTOR_WEIGHT: float = 0.8  # 벡터 검색 가중치 
    BM25_WEIGHT: float = 0.2    # BM25 검색 가중치 
    
    # 검색 설정
    RAG_TOP_K: int = 5
    RAG_MAX_TOP_K: int = 8
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
        return str(self._settings.LANGSMITH_TRACING).lower() == "true"
    
    # PDF 처리 설정
    MAX_IMAGE_SIZE: tuple = (1024, 1024)
    IMAGE_DPI: int = 150
    
    # 표 감지 설정
    TABLE_MIN_ROWS: int = 2
    TABLE_MIN_COLS: int = 2
    
    def ensure_directories(self):
        """필요한 디렉토리 생성"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        Path(self.CHROMA_PERSIST_DIRECTORY).mkdir(parents=True, exist_ok=True)


# 싱글톤 인스턴스
rag_config = RAGConfig()