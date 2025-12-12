"""Insurance RAG Services Layer"""

# 간소화된 버전 - core 디렉토리 불필요
from .models import Query, InsuranceDocument, GenerationResult, RetrievalResult
from .exceptions import InsuranceRAGException, RetrievalException, GenerationException
from .providers import SimpleEmbeddingProvider, SimpleVectorStore, SimpleLLMProvider
from .retriever import Retriever
from .hybrid_retriever import HybridRetriever
from .generator import Generator

# DocumentProcessor는 폴더 이름 충돌로 인해 직접 import하지 않음
# 필요시: from app.domain.rag.Insurance.services.document_processor import DocumentProcessor

try:
    from .rag_pipeline import RAGPipeline
except Exception:
    RAGPipeline = None

__all__ = [
    "Query",
    "InsuranceDocument", 
    "GenerationResult",
    "RetrievalResult",
    "InsuranceRAGException",
    "RetrievalException",
    "GenerationException",
    "SimpleEmbeddingProvider",
    "SimpleVectorStore",
    "SimpleLLMProvider",
    "Retriever",
    "HybridRetriever",
    "Generator",
    "RAGPipeline",
]
