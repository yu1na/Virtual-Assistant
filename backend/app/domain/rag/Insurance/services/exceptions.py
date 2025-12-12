"""
Insurance RAG 예외 클래스 (core 디렉토리 불필요)
"""


class InsuranceRAGException(Exception):
    """Insurance RAG 기본 예외"""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class RetrievalException(InsuranceRAGException):
    """검색 관련 예외"""
    pass


class GenerationException(InsuranceRAGException):
    """답변 생성 관련 예외"""
    pass


class DocumentProcessingException(InsuranceRAGException):
    """문서 처리 관련 예외"""
    pass
