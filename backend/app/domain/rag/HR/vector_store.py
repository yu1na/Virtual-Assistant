"""
벡터 저장소 모듈

OpenAI text-embedding-3-large를 사용한 임베딩 생성 및 ChromaDB 직접 사용
한국어 → 영어 번역 후 임베딩 생성
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import uuid
import json
from pathlib import Path
import numpy as np

from .config import rag_config
from .schemas import DocumentChunk, ProcessedDocument
from .utils import get_logger

logger = get_logger(__name__)


class VectorStore:
    """벡터 저장소 관리 (ChromaDB 직접 사용)"""
    
    def __init__(self, collection_name: Optional[str] = None):
        self.config = rag_config
        self.collection_name = collection_name or self.config.CHROMA_COLLECTION_NAME
        
        # Lazy loading: 모델을 실제 사용 시에만 로드
        self._openai_client = None
        self._translation_client = None
        
        # ChromaDB 클라이언트 설정
        chroma_settings = Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
        
        # ChromaDB 클라이언트 초기화
        try:
            self.client = chromadb.PersistentClient(
                path=self.config.CHROMA_PERSIST_DIRECTORY,
                settings=chroma_settings
            )
        except ValueError as e:
            # 이미 다른 설정으로 인스턴스가 존재하는 경우
            logger.warning(f"기존 ChromaDB 인스턴스 감지: {e}")
            # 같은 설정으로 재시도
            try:
                self.client = chromadb.PersistentClient(
                    path=self.config.CHROMA_PERSIST_DIRECTORY,
                    settings=chroma_settings
                )
            except Exception as e2:
                logger.error(f"ChromaDB 클라이언트 초기화 실패: {e2}")
                raise
        
        # 컬렉션 가져오기 또는 생성
        self.collection = self._get_or_create_collection()
        
        logger.info(f"벡터 저장소 초기화 완료: {self.collection_name}")
    
    @property
    def openai_client(self):
        """OpenAI 클라이언트 lazy loading"""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            logger.info(f"OpenAI 임베딩 클라이언트 로드 완료: {self.config.EMBEDDING_MODEL}")
        return self._openai_client
    
    @property
    def translation_client(self):
        """번역용 OpenAI 클라이언트 lazy loading"""
        if self._translation_client is None:
            from openai import OpenAI
            self._translation_client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            logger.info(f"번역 클라이언트 로드 완료: {self.config.TRANSLATION_MODEL}")
        return self._translation_client
    
    def _get_or_create_collection(self):
        """컬렉션 가져오기 또는 생성"""
        try:
            collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"기존 컬렉션 로드: {self.collection_name}")
            
            # Cosine distance는 collection metadata에 직접 저장되지 않음.
            # 따라서 Settings(distance="cosine") 로 지정했는지만 확인하면 됨.
            logger.info("컬렉션 로드 완료 (metric은 Client Settings에 따름)")
        
        except:
            try:
                collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "RAG 문서 임베딩"}
                    # distance_function 제거 (지원하지 않음)
                )
                logger.info(f"새 컬렉션 생성: {self.collection_name} (metric: cosine via Settings)")
            except Exception as e:
                logger.error(f"컬렉션 생성 실패: {e}")
                raise
        
        return collection
    
    def translate_to_english(self, korean_text: str) -> str:
        """
        한국어 텍스트를 영어로 번역 (GPT-4o-mini 사용)
        
        Args:
            korean_text: 번역할 한국어 텍스트
            
        Returns:
            str: 영어 번역 텍스트
        """
        try:
            response = self.translation_client.chat.completions.create(
                model=self.config.TRANSLATION_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional translator. Translate Korean text to English accurately. Only return the translated text, nothing else."
                    },
                    {
                        "role": "user",
                        "content": f"Translate this Korean text to English:\n\n{korean_text}"
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            translated_text = response.choices[0].message.content.strip()
            logger.debug(f"번역 완료: {len(korean_text)} chars -> {len(translated_text)} chars")
            return translated_text
            
        except Exception as e:
            logger.error(f"번역 중 오류: {e}")
            # 번역 실패 시 원본 텍스트 반환
            return korean_text
    
    def embed_text(self, text: str, translate: bool = True) -> List[float]:
        """
        텍스트를 벡터로 임베딩 (한→영 번역 후 임베딩)
        
        Args:
            text: 임베딩할 텍스트
            translate: 한→영 번역 여부
            
        Returns:
            List[float]: 임베딩 벡터
        """
        # 한국어 텍스트를 영어로 번역
        if translate:
            text_to_embed = self.translate_to_english(text)
        else:
            text_to_embed = text
        
        try:
            response = self.openai_client.embeddings.create(
                model=self.config.EMBEDDING_MODEL,
                input=text_to_embed
            )
            embedding = response.data[0].embedding
            logger.debug(f"임베딩 생성 완료: 차원 {len(embedding)}")
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류: {e}")
            raise
    
    def embed_texts(self, texts: List[str], translate: bool = True) -> List[List[float]]:
        """
        여러 텍스트를 벡터로 임베딩 (한→영 번역 후 임베딩)
        
        Args:
            texts: 임베딩할 텍스트 리스트
            translate: 한→영 번역 여부
            
        Returns:
            List[List[float]]: 임베딩 벡터 리스트
        """
        # 한국어 텍스트들을 영어로 번역
        if translate:
            logger.info(f"{len(texts)}개 텍스트 번역 중...")
            texts_to_embed = [self.translate_to_english(text) for text in texts]
        else:
            texts_to_embed = texts
        
        try:
            logger.info(f"{len(texts_to_embed)}개 텍스트 임베딩 중...")
            response = self.openai_client.embeddings.create(
                model=self.config.EMBEDDING_MODEL,
                input=texts_to_embed
            )
            embeddings = [data.embedding for data in response.data]
            logger.info(f"임베딩 완료: {len(embeddings)}개 벡터 생성 (차원: {len(embeddings[0])})")
            return embeddings
            
        except Exception as e:
            logger.error(f"배치 임베딩 생성 중 오류: {e}")
            raise
    
    def check_existing_embeddings(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        기존 임베딩 존재 여부 확인 및 로드
        
        Args:
            document_id: 문서 ID
            
        Returns:
            Dict: 기존 임베딩 정보 (없으면 None)
        """
        try:
            # JSON 파일에서 기존 임베딩 확인
            json_path = self.config.PROCESSED_DIR / f"{Path(document_id).stem}.json"
            
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 임베딩이 포함되어 있는지 확인
                if data.get('chunks_with_embeddings'):
                    logger.info(f"기존 임베딩 발견: {document_id}")
                    return data
            
            return None
            
        except Exception as e:
            logger.warning(f"기존 임베딩 확인 중 오류: {e}")
            return None
    
    def add_chunks(self, chunks: List[DocumentChunk], reuse_embeddings: bool = True) -> int:
        """
        청크를 벡터 저장소에 추가 (임베딩 재사용 지원)
        
        Args:
            chunks: 추가할 청크 리스트
            reuse_embeddings: 기존 임베딩 재사용 여부
            
        Returns:
            int: 추가된 청크 수
        """
        if not chunks:
            logger.warning("추가할 청크가 없습니다")
            return 0
        
        # 기존 임베딩 확인
        existing_data = None
        if reuse_embeddings and chunks:
            document_id = chunks[0].metadata.document_id
            existing_data = self.check_existing_embeddings(document_id)
        
        # 텍스트와 메타데이터 준비
        texts = []
        translated_texts = []
        metadatas = []
        ids = []
        embeddings = []
        
        for idx, chunk in enumerate(chunks):
            # 고유 ID 생성
            chunk_id = chunk.metadata.chunk_id or str(uuid.uuid4())
            ids.append(chunk_id)
            
            texts.append(chunk.text)
            
            # 기존 임베딩 재사용
            if existing_data and existing_data.get('chunks_with_embeddings'):
                existing_chunks = existing_data['chunks_with_embeddings']
                if idx < len(existing_chunks) and existing_chunks[idx].get('embedding'):
                    embeddings.append(existing_chunks[idx]['embedding'])
                    translated_texts.append(existing_chunks[idx].get('translated_text', ''))
                    logger.debug(f"청크 {idx} 임베딩 재사용")
                else:
                    embeddings.append(None)
                    translated_texts.append(None)
            else:
                embeddings.append(None)
                translated_texts.append(None)
            
            # 메타데이터 (ChromaDB는 문자열, 숫자, 불리언만 지원)
            metadata = {
                "document_id": chunk.metadata.document_id,
                "filename": chunk.metadata.filename,
                "page_number": chunk.metadata.page_number,
                "content_type": chunk.metadata.content_type,
                "chunk_index": chunk.metadata.chunk_index,
            }
            
            if chunk.metadata.total_chunks:
                metadata["total_chunks"] = chunk.metadata.total_chunks
            
            # 원본/번역 텍스트 저장 (검색 시 활용)
            if chunk.metadata.original_text:
                metadata["original_text"] = chunk.metadata.original_text[:500]  # 길이 제한
            if chunk.metadata.translated_text:
                metadata["translated_text"] = chunk.metadata.translated_text[:500]  # 길이 제한
            
            metadatas.append(metadata)
        
        # 새로 임베딩 생성이 필요한 청크만 처리
        new_embedding_indices = [i for i, emb in enumerate(embeddings) if emb is None]
        
        if new_embedding_indices:
            logger.info(f"{len(new_embedding_indices)}개 청크 새로 임베딩 중...")
            new_texts = [texts[i] for i in new_embedding_indices]
            new_embeddings = self.embed_texts(new_texts, translate=True)
            
            # 새 임베딩과 번역 텍스트를 리스트에 삽입
            for idx, emb_idx in enumerate(new_embedding_indices):
                embeddings[emb_idx] = new_embeddings[idx]
        else:
            logger.info(f"모든 청크 임베딩 재사용: {len(chunks)}개")
        
        # 모든 청크 객체에 임베딩 저장 (JSON 저장용)
        for i, chunk in enumerate(chunks):
            if embeddings[i]:
                chunk.embedding = embeddings[i]
                logger.debug(f"청크 {i}에 임베딩 저장 완료 (차원: {len(embeddings[i])})")
        
        # ChromaDB에 추가
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        logger.info(f"{len(chunks)}개 청크를 벡터 저장소에 추가 완료")
        return len(chunks)
    
    def add_document(self, processed_doc: ProcessedDocument, chunks: List[DocumentChunk]) -> int:
        """
        처리된 문서와 청크를 벡터 저장소에 추가
        
        Args:
            processed_doc: 처리된 문서
            chunks: 문서 청크 리스트
            
        Returns:
            int: 추가된 청크 수
        """
        logger.info(f"문서 추가 중: {processed_doc.filename}")
        return self.add_chunks(chunks)
    
    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        두 벡터 간의 cosine similarity 직접 계산
        
        Args:
            vec1: 첫 번째 벡터
            vec2: 두 번째 벡터
            
        Returns:
            float: Cosine similarity (0~1, 높을수록 유사)
        """
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        # Cosine similarity = dot(A, B) / (||A|| * ||B||)
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # 0~1 범위로 정규화 (cosine similarity는 -1~1 범위지만 OpenAI 임베딩은 항상 양수)
        similarity = max(0.0, min(1.0, similarity))
        
        return float(similarity)
    
    def search(
        self, 
        query: str, 
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        쿼리로 유사한 청크 검색 (쿼리도 한→영 번역 후 검색)
        Internal cosine similarity 직접 계산
        
        Args:
            query: 검색 쿼리 (한국어)
            top_k: 반환할 결과 수
            
        Returns:
            Dict: 검색 결과 (기존 형식 유지, distances는 similarity score)
        """
        if top_k is None:
            top_k = self.config.RAG_TOP_K
        
        # 저장된 문서가 있는지 확인
        doc_count = self.collection.count()
        if doc_count == 0:
            logger.warning("저장된 문서가 없습니다.")
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
        
        # 쿼리 임베딩 (한→영 번역 후)
        try:
            logger.info(f"쿼리 번역 및 임베딩 생성 중: '{query}'")
            query_embedding = self.embed_text(query, translate=True)
            logger.debug(f"쿼리 임베딩 생성 완료 (차원: {len(query_embedding)})")
        except Exception as e:
            logger.error(f"쿼리 임베딩 생성 실패: {e}")
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
        
        # ChromaDB에서 임베딩 포함하여 검색 (include=['embeddings'])
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, doc_count),  # top_k만큼만 검색 (retriever에서 fetch_k로 조절)
                include=['documents', 'metadatas', 'embeddings']  # 임베딩 포함
            )
            logger.debug(f"ChromaDB 검색 결과: {len(results.get('ids', [[]])[0]) if results.get('ids') else 0}개")
        except Exception as e:
            logger.error(f"ChromaDB 검색 실패: {e}")
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
        
        # 결과 처리 및 internal similarity 계산
        documents = []
        metadatas = []
        similarities = []
        
        if results and results.get('documents') and results['documents']:
            doc_list = results['documents'][0] if results['documents'][0] else []
            embeddings_list = results.get('embeddings', [[]])[0] if results.get('embeddings') else []
            
            for i in range(len(doc_list)):
                # 문서와 메타데이터 추가
                documents.append(doc_list[i])
                
                if results.get('metadatas') and results['metadatas'][0] and i < len(results['metadatas'][0]):
                    metadatas.append(results['metadatas'][0][i])
                else:
                    metadatas.append({})
                
                # Internal cosine similarity 직접 계산
                # [수정됨] embeddings_list가 None이 아니고 길이가 충분한지 확인
                if embeddings_list is not None and len(embeddings_list) > i:
                    doc_embedding = embeddings_list[i]
                    similarity = self.calculate_cosine_similarity(query_embedding, doc_embedding)
                    similarities.append(similarity)
                    logger.debug(f"문서 {i+1} cosine similarity: {similarity:.4f}")
                else:
                    similarities.append(0.0)
        
        logger.info(f"검색 완료: {len(documents)}개 결과 반환 (internal similarity 계산)")
        
        return {
            "documents": [documents],
            "metadatas": [metadatas],
            "distances": [similarities]  # similarities로 변경
        }
    
    def delete_document(self, document_id: str) -> bool:
        """
        문서 ID로 모든 관련 청크 삭제
        
        Args:
            document_id: 문서 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            # 해당 문서의 모든 청크 찾기
            results = self.collection.get(
                where={"document_id": document_id}
            )
            
            if results and results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"문서 삭제 완료: {document_id} ({len(results['ids'])}개 청크)")
                return True
            else:
                logger.warning(f"삭제할 문서를 찾을 수 없습니다: {document_id}")
                return False
                
        except Exception as e:
            logger.error(f"문서 삭제 중 오류: {e}")
            return False
    
    def count_documents(self) -> int:
        """저장된 총 청크 수 반환"""
        return self.collection.count()
    
    def reset_collection(self):
        """컬렉션 초기화 (모든 데이터 삭제)"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            logger.info(f"컬렉션 초기화 완료: {self.collection_name}")
        except Exception as e:
            logger.error(f"컬렉션 초기화 중 오류: {e}")
            raise