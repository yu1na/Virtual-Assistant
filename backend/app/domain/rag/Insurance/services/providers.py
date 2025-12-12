"""
간단한 Provider 클래스들 (infrastructure 디렉토리 불필요)
"""
from typing import List
from openai import OpenAI
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from ..config import insurance_config
from .models import InsuranceDocument


# ============================================
# Embedding Provider
# ============================================

class SimpleEmbeddingProvider:
    """간단한 OpenAI 임베딩 제공자"""
    
    def __init__(self, model: str = None, dimensions: int = None):
        self.model = model or insurance_config.EMBEDDING_MODEL
        self.dimensions = dimensions or insurance_config.EMBEDDING_DIMENSION
        self.client = OpenAI(api_key=insurance_config.OPENAI_API_KEY)
    
    def embed_text(self, text: str) -> List[float]:
        """텍스트를 임베딩 벡터로 변환"""
        response = self.client.embeddings.create(
            input=text,
            model=self.model,
            dimensions=self.dimensions
        )
        return response.data[0].embedding
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트를 한 번에 임베딩 (배치 처리)"""
        response = self.client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=self.dimensions
        )
        return [item.embedding for item in response.data]
    
    def get_model_name(self) -> str:
        return self.model
    
    def get_embedding_dimension(self) -> int:
        return self.dimensions


# ============================================
# Vector Store
# ============================================

class SimpleVectorStore:
    """간단한 ChromaDB 벡터 스토어"""
    
    def __init__(self, collection_name: str, persist_directory: str, embedding_function):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # 디버깅 로그
        print(f"\n[INSURANCE VECTOR STORE] Initializing...")
        print(f"  Path: {persist_directory}")
        print(f"  Collection: {collection_name}")
        
        # ChromaDB 설정 (로더와 동일하게)
        from chromadb.config import Settings as ChromaSettings
        
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.embedding_function = embedding_function
        
        # 컬렉션 가져오기 또는 생성 (임베딩 함수 없이)
        try:
            self.collection = self.client.get_collection(
                name=collection_name
            )
            doc_count = self.collection.count()
            print(f"  ✅ Loaded existing collection: {doc_count} documents")
        except Exception as e:
            print(f"  ⚠️ Collection not found, creating new: {e}")
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"  ✅ Created new collection")
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: dict = None
    ) -> tuple[List[InsuranceDocument], List[float]]:
        """벡터 검색"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata
        )
        
        documents = []
        scores = []
        
        if results['documents'] and results['documents'][0]:
            for i, doc_content in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                doc_id = results['ids'][0][i] if results['ids'] else None
                
                documents.append(InsuranceDocument(
                    content=doc_content,
                    metadata=metadata,
                    doc_id=doc_id
                ))
                
                # ChromaDB는 squared L2 distance를 반환 (낮을수록 유사)
                # distance 값을 그대로 사용하되, 낮을수록 좋은 score로 사용
                # 또는 간단한 변환: similarity = 1 / (1 + distance)
                distance = results['distances'][0][i] if results['distances'] else 0.0
                
                # Distance를 similarity-like score로 변환
                # distance가 0에 가까울수록 1에 가까워짐
                # distance가 클수록 0에 가까워짐
                similarity = 1.0 / (1.0 + distance)
                scores.append(similarity)
        
        return documents, scores
    
    def get_collection_info(self) -> dict:
        """컬렉션 정보 반환"""
        count = self.collection.count()
        return {
            "name": self.collection_name,
            "count": count,
            "persist_directory": self.persist_directory
        }


# ============================================
# LLM Provider
# ============================================

class SimpleLLMProvider:
    """간단한 OpenAI LLM 제공자"""
    
    def __init__(
        self,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None
    ):
        self.model = model or insurance_config.OPENAI_MODEL
        self.temperature = temperature if temperature is not None else insurance_config.OPENAI_TEMPERATURE
        self.max_tokens = max_tokens or insurance_config.OPENAI_MAX_TOKENS
        self.client = OpenAI(api_key=insurance_config.OPENAI_API_KEY)
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None
    ) -> str:
        """텍스트 생성"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=self.max_tokens
        )
        
        return response.choices[0].message.content
    
    def get_model_name(self) -> str:
        return self.model
