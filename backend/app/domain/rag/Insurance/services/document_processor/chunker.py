"""
텍스트 청킹 서비스

레거시 chunker/ 폴더의 청킹 로직을 통합하여
서비스 레이어용으로 정리한 구현입니다.
"""
import re
import tiktoken
from typing import List

from ...core.config import config
from ...core.utils import get_logger

logger = get_logger(__name__)

# 상수
MIN_CHUNK_LENGTH = 10
TIKTOKEN_ENCODING = "cl100k_base"

# OCR 실패 지표
OCR_FAILURE_INDICATORS = [
    "sorry", "unable", "cannot", "can't", "failed",
    "죄송", "불가능", "처리할 수 없"
]


class TextChunker:
    """
    프로덕션급 텍스트 청킹 서비스
    
    테이블 보존, OCR 실패 필터링, 문단 인식 분할을 포함한
    토큰 기반 청킹을 처리합니다.
    """
    
    def __init__(
        self,
        max_tokens: int = 500,
        overlap_tokens: int = 80,
        encoding: str = TIKTOKEN_ENCODING
    ):
        """
        청커 초기화
        
        Args:
            max_tokens: 청크당 최대 토큰 수 (기본값: 500)
            overlap_tokens: 청크 간 오버랩 (기본값: 80)
            encoding: tiktoken 인코딩 이름 (기본값: cl100k_base)
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.encoding = encoding
        self._encoder = None
    
    @property
    def encoder(self) -> tiktoken.Encoding:
        """tiktoken 인코더 지연 로드"""
        if self._encoder is None:
            try:
                self._encoder = tiktoken.get_encoding(self.encoding)
                logger.debug(f"tiktoken encoder loaded: {self.encoding}")
            except Exception as e:
                logger.error(f"tiktoken encoder failed: {e}")
                raise
        return self._encoder
    
    # ===== 필터링 =====
    
    @staticmethod
    def is_ocr_failure_message(text: str) -> bool:
        """텍스트가 OCR 실패 메시지인지 확인"""
        if not text:
            return False
        text_lower = text.lower().strip()
        return any(indicator in text_lower for indicator in OCR_FAILURE_INDICATORS)
    
    @staticmethod
    def filter_chunk(chunk_text: str) -> bool:
        """
        청크가 유효한지 확인
        
        제거 조건:
        - 길이 < MIN_CHUNK_LENGTH
        - OCR 실패 메시지
        - 공백/특수문자만 포함
        - "표", "그림", "페이지 N" 같은 단편 패턴
        
        유지 조건:
        - "제 1 장", "제 2 절" 같은 구조 정보
        
        Returns:
            유효하면 True, 제거해야 하면 False
        """
        if not chunk_text:
            return False
        
        chunk_text = chunk_text.strip()
        
        # 최소 길이
        if len(chunk_text) < MIN_CHUNK_LENGTH:
            return False
        
        # 공백만 포함
        if chunk_text.isspace():
            return False
        
        # 특수문자만 포함 (한글/영문/숫자 없음)
        if not re.search(r'[가-힣a-zA-Z0-9]', chunk_text):
            return False
        
        # OCR 실패 메시지
        if TextChunker.is_ocr_failure_message(chunk_text):
            return False
        
        # 단편 패턴 (제거 대상)
        fragment_patterns = [
            r'^표\s*$',
            r'^그림\s*$',
            r'^페이지\s*\d+\s*$',
            r'^\d+\s*페이지\s*$',
        ]
        
        for pattern in fragment_patterns:
            if re.match(pattern, chunk_text, re.IGNORECASE):
                return False
        
        return True
    
    # ===== 문단 분할 =====
    
    @staticmethod
    def is_table_paragraph(para: str) -> bool:
        """
        문단이 Markdown 테이블인지 확인
        
        테이블 패턴:
        - |로 시작하는 줄 (2줄 이상)
        - |---|--- 구분자 패턴 포함
        """
        lines = para.split('\n')
        pipe_lines = [line for line in lines if line.strip().startswith('|')]
        has_separator = any(re.search(r'\|[\s-]+\|', line) for line in lines)
        return len(pipe_lines) >= 2 and has_separator
    
    @staticmethod
    def pre_split_paragraphs(text: str) -> List[str]:
        """
        텍스트를 문단으로 분할 (청킹 전 전처리)
        
        규칙:
        1. 이중 줄바꿈 (\\n\\n+)으로 기본 분할
        2. 제목 패턴 (# 접두사)
        3. 테이블 패턴 (| 접두사) - 여러 문단의 테이블 병합
        4. 불릿 패턴 (-, •, * 접두사)
        
        Returns:
            문단 텍스트 리스트
        """
        if not text or not text.strip():
            return []
        
        # 이중 줄바꿈으로 기본 분할
        paragraphs = re.split(r'\n\n+', text)
        
        result = []
        i = 0
        while i < len(paragraphs):
            para = paragraphs[i].strip()
            if not para:
                i += 1
                continue
            
            # 제목 패턴
            if re.match(r'^#+\s+', para):
                result.append(para)
                i += 1
                continue
            
            # 테이블 패턴: 여러 문단의 테이블 병합
            if TextChunker.is_table_paragraph(para):
                table_parts = [para]
                j = i + 1
                while j < len(paragraphs):
                    next_para = paragraphs[j].strip()
                    if next_para and TextChunker.is_table_paragraph(next_para):
                        table_parts.append(next_para)
                        j += 1
                    else:
                        break
                result.append('\n\n'.join(table_parts))
                i = j
                continue
            
            # 불릿 패턴
            if re.match(r'^[-•*]\s+', para):
                result.append(para)
                i += 1
                continue
            
            # 일반 문단
            result.append(para)
            i += 1
        
        return result
    
    # ===== 토큰 기반 청킹 =====
    
    def tokenize(self, text: str) -> List[int]:
        """텍스트 토큰화"""
        if not text:
            return []
        try:
            return self.encoder.encode(text)
        except Exception as e:
            logger.warning(f"Tokenization failed, using whitespace fallback: {e}")
            return text.split()
    
    def detokenize(self, token_ids: List[int]) -> str:
        """토큰 ID 역토큰화"""
        if not token_ids:
            return ""
        try:
            return self.encoder.decode(token_ids)
        except Exception as e:
            logger.warning(f"Detokenization failed: {e}")
            return ""
    
    def token_chunk(self, text: str) -> List[str]:
        """
        오버랩을 포함하여 토큰 단위로 텍스트 청킹
        
        Args:
            text: 입력 텍스트
            
        Returns:
            텍스트 청크 리스트
        """
        if not text or not text.strip():
            return []
        
        tokens = self.tokenize(text)
        
        if len(tokens) <= self.max_tokens:
            return [text.strip()]
        
        step = max(self.max_tokens - self.overlap_tokens, 1)
        chunks = []
        
        for start in range(0, len(tokens), step):
            end = min(start + self.max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.detokenize(chunk_tokens)
            chunks.append(chunk_text)
            
            if end >= len(tokens):
                break
        
        return chunks
    
    # ===== 고수준 API =====
    
    def chunk(self, text: str, filter_invalid: bool = True) -> List[str]:
        """
        문단 인식 분할과 필터링을 포함한 텍스트 청킹
        
        Args:
            text: 입력 텍스트
            filter_invalid: 유효하지 않은 청크 필터링 여부 (기본값: True)
            
        Returns:
            유효한 텍스트 청크 리스트
        """
        if not text or not text.strip():
            return []
        
        # 단계 1: 문단으로 사전 분할
        paragraphs = self.pre_split_paragraphs(text)
        
        # 단계 2: 각 문단을 토큰으로 청킹
        all_chunks = []
        for para in paragraphs:
            para_chunks = self.token_chunk(para)
            all_chunks.extend(para_chunks)
        
        # 단계 3: 유효하지 않은 청크 필터링
        if filter_invalid:
            all_chunks = [chunk for chunk in all_chunks if self.filter_chunk(chunk)]
        
        return all_chunks
    
    def chunk_document(
        self,
        content: str,
        metadata: dict = None,
        filter_invalid: bool = True
    ) -> List[dict]:
        """
        문서를 청킹하고 메타데이터와 함께 반환
        
        Args:
            content: 문서 내용
            metadata: 문서 메타데이터 (선택사항)
            filter_invalid: 유효하지 않은 청크 필터링 여부
            
        Returns:
            텍스트와 메타데이터가 포함된 청크 딕셔너리 리스트
        """
        chunks = self.chunk(content, filter_invalid=filter_invalid)
        
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_data = {
                "text": chunk_text,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            if metadata:
                chunk_data["metadata"] = metadata.copy()
            result.append(chunk_data)
        
        return result
