"""
문서 변환 모듈

LangChain을 사용하여 문서를 마크다운 형식으로 변환하고 시맨틱 단위로 청킹합니다.
"""

from typing import List
import uuid
try:
    from langchain_core.documents import Document as LangChainDocument
except ImportError:
    # 구버전 호환성
    from langchain.schema import Document as LangChainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken

from .config import rag_config
from .schemas import (
    ProcessedDocument,
    ProcessedContent,
    DocumentChunk,
    ChunkMetadata,
    ContentType
)
from .utils import get_logger

logger = get_logger(__name__)


class DocumentConverter:
    """문서 변환 및 청킹 처리기"""
    
    def __init__(self):
        self.config = rag_config
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
        # LangChain 텍스트 분할기 설정 - 텍스트용
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.RAG_TEXT_CHUNK_SIZE,
            chunk_overlap=self.config.RAG_TEXT_CHUNK_OVERLAP,
            length_function=self._token_length,
            separators=["\n\n", "\n", ". ", " ", ""],
            is_separator_regex=False
        )
        
        # LangChain 텍스트 분할기 설정 - 표/그래프/이미지용
        self.visual_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.RAG_VISUAL_CHUNK_SIZE,
            chunk_overlap=self.config.RAG_VISUAL_CHUNK_OVERLAP,
            length_function=self._token_length,
            separators=["\n\n", "\n", ". ", " ", ""],
            is_separator_regex=False
        )
    
    def _token_length(self, text: str) -> int:
        """텍스트의 토큰 길이 계산"""
        return len(self.encoding.encode(text))
    
    def convert_to_markdown(self, content: ProcessedContent) -> str:
        """
        컨텐츠를 마크다운 형식으로 변환
        
        Args:
            content: 처리된 컨텐츠
            
        Returns:
            str: 마크다운 형식의 텍스트
        """
        markdown_parts = []
        
        # 메타데이터 헤더
        markdown_parts.append(f"## 페이지 {content.metadata.page_number}")
        markdown_parts.append(f"**타입**: {content.content_type}")
        markdown_parts.append("")
        
        # 컨텐츠 타입별 처리
        if content.content_type == ContentType.TABLE:
            markdown_parts.append("### 표")
            markdown_parts.append(content.text)
            
        elif content.content_type == ContentType.IMAGE:
            markdown_parts.append("### 이미지/차트")
            markdown_parts.append(content.text)
            
        else:  # TEXT
            markdown_parts.append(content.text)
        
        markdown_parts.append("")
        markdown_parts.append("---")
        markdown_parts.append("")
        
        return "\n".join(markdown_parts)
    
    def create_chunks(
        self, 
        processed_doc: ProcessedDocument
    ) -> List[DocumentChunk]:
        """
        처리된 문서를 청크로 분할
        
        Args:
            processed_doc: 처리된 문서
            
        Returns:
            List[DocumentChunk]: 문서 청크 리스트
        """
        logger.info(f"문서 청킹 시작: {processed_doc.filename}")
        
        chunks: List[DocumentChunk] = []
        document_id = processed_doc.filename
        
        for content in processed_doc.contents:
            # 마크다운 변환
            markdown_text = self.convert_to_markdown(content)
            
            # 토큰 길이 확인
            token_length = self._token_length(markdown_text)
            
            # 컨텐츠 타입에 따라 다른 splitter와 설정 사용
            is_visual = content.content_type in [ContentType.TABLE, ContentType.IMAGE]
            splitter = self.visual_splitter if is_visual else self.text_splitter
            max_chunk_size = self.config.RAG_VISUAL_MAX_CHUNK_SIZE if is_visual else self.config.RAG_TEXT_MAX_CHUNK_SIZE
            min_chunk_size = self.config.RAG_VISUAL_MIN_CHUNK_SIZE if is_visual else self.config.RAG_TEXT_MIN_CHUNK_SIZE
            
            logger.info(f"청킹 타입: {'표/그래프/이미지' if is_visual else '텍스트'}, "
                       f"크기: {token_length} 토큰, "
                       f"최대: {max_chunk_size}, 최소: {min_chunk_size}")
            
            # 청크 크기보다 작으면 분할하지 않음
            if token_length <= max_chunk_size:
                # UUID 기반 청크 ID 생성
                chunk_id = str(uuid.uuid4())
                
                metadata = ChunkMetadata(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    filename=processed_doc.filename,
                    page_number=content.metadata.page_number,
                    content_type=content.content_type,
                    chunk_index=0,
                    total_chunks=1
                )
                
                chunk = DocumentChunk(
                    text=markdown_text,
                    metadata=metadata
                )
                chunks.append(chunk)
                
            else:
                # LangChain Document 객체 생성
                langchain_doc = LangChainDocument(
                    page_content=markdown_text,
                    metadata={
                        "filename": processed_doc.filename,
                        "page_number": content.metadata.page_number,
                        "content_type": content.content_type,
                        "document_id": document_id
                    }
                )
                
                # 컨텐츠 타입에 따라 적절한 Splitter로 분할
                split_docs = splitter.split_documents([langchain_doc])
                
                for idx, split_doc in enumerate(split_docs):
                    # 최소 청크 크기 확인
                    if self._token_length(split_doc.page_content) < min_chunk_size:
                        continue
                    
                    # UUID 기반 청크 ID 생성
                    chunk_id = str(uuid.uuid4())
                    
                    metadata = ChunkMetadata(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        filename=processed_doc.filename,
                        page_number=content.metadata.page_number,
                        content_type=content.content_type,
                        chunk_index=idx,
                        total_chunks=len(split_docs)
                    )
                    
                    chunk = DocumentChunk(
                        text=split_doc.page_content,
                        metadata=metadata
                    )
                    chunks.append(chunk)
        
        logger.info(f"청킹 완료: {len(chunks)}개 청크 생성")
        return chunks
    
    def validate_chunks(self, chunks: List[DocumentChunk]) -> bool:
        """
        청크의 유효성 검증
        
        Args:
            chunks: 검증할 청크 리스트
            
        Returns:
            bool: 유효성 여부
        """
        if not chunks:
            logger.warning("청크가 비어있습니다")
            return False
        
        for chunk in chunks:
            token_length = self._token_length(chunk.text)
            is_visual = chunk.metadata.content_type in [ContentType.TABLE, ContentType.IMAGE]
            min_size = self.config.RAG_VISUAL_MIN_CHUNK_SIZE if is_visual else self.config.RAG_TEXT_MIN_CHUNK_SIZE
            max_size = self.config.RAG_VISUAL_MAX_CHUNK_SIZE if is_visual else self.config.RAG_TEXT_MAX_CHUNK_SIZE
            
            if token_length < min_size:
                logger.warning(
                    f"청크가 너무 작습니다: {chunk.metadata.chunk_id} "
                    f"({token_length} 토큰, 최소: {min_size})"
                )
                
            if token_length > max_size * 1.5:
                logger.warning(
                    f"청크가 너무 큽니다: {chunk.metadata.chunk_id} "
                    f"({token_length} 토큰, 최대: {max_size})"
                )
        
        return True

