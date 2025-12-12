"""
Document processing service
"""
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from .models import InsuranceDocument, Chunk, DocumentType
from ..config import insurance_config
from .exceptions import DocumentProcessingException


class DocumentProcessor:
    """
    간단한 문서 처리 서비스
    
    현재는 기본 기능만 제공하며, 필요시 확장 가능
    """
    
    def __init__(self):
        """문서 처리기 초기화"""
        pass

    
    def process_pdf(
        self,
        pdf_path: str,
        resume: bool = False
    ) -> List[InsuranceDocument]:
        """
        PDF 파일 전체 처리 (로드 + 청킹)
        
        현재는 구현되지 않음 - 필요시 구현 필요
        """
        raise NotImplementedError("PDF processing not implemented yet")
    
    def process_document(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        doc_id: str = None
    ) -> List[InsuranceDocument]:
        """
        단일 문서 처리 (청킹)
        
        현재는 구현되지 않음 - 필요시 구현 필요
        """
        raise NotImplementedError("Document processing not implemented yet")
    
    def process_documents_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[InsuranceDocument]:
        """
        여러 문서 배치 처리
        
        현재는 구현되지 않음 - 필요시 구현 필요
        """
        raise NotImplementedError("Batch processing not implemented yet")

    
    def get_info(self) -> Dict[str, Any]:
        """
        현재 프로세서 정보 반환
        
        Returns:
            프로세서 정보
        """
        return {
            "document_processor": "DocumentProcessor",
            "status": "initialized"
        }

    
    @staticmethod
    def extract_keywords(text: str, min_length: int = 2) -> List[str]:
        """
        텍스트에서 핵심 키워드 추출
        
        Args:
            text: 텍스트
            min_length: 최소 키워드 길이
            
        Returns:
            키워드 리스트
        """
        # 한글, 영문, 숫자만 남기고 토큰화
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        tokens = text.split()
        
        # 불용어 제거
        stopwords = {
            '은', '는', '이', '가', '을', '를', '의', '에', '와', '과', '도', 
            '으로', '로', '입니다', '있습니다', '합니다', '한다', '된다', '이다', 
            '것', '수', '등', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 
            'on', 'at', 'to', 'for', 'of', 'with'
        }
        
        keywords = [
            token for token in tokens 
            if len(token) >= min_length and token.lower() not in stopwords
        ]
        
        return list(set(keywords))  # 중복 제거
