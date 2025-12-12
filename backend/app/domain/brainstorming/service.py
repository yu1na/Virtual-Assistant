"""
브레인스토밍 서비스 로직

ChromaDB를 사용한 RAG 검색 서비스를 제공합니다.
"""
from pathlib import Path
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from app.core.config import settings


class BrainstormingService:
    """브레인스토밍 RAG 검색 서비스"""
    
    def __init__(self):
        # OpenAI 클라이언트 초기화
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        
        # ChromaDB 경로 설정 - 브레인스토밍 모듈 전용
        # 다른 팀원과 충돌하지 않도록 모듈 내부에 저장
        base_dir = Path(__file__).parent
        data_dir = base_dir / "data"
        self.persist_directory = str(data_dir / "chroma")
        
        # ChromaDB 클라이언트 초기화
        self.chroma_client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 브레인스토밍 컬렉션 가져오기
        self.collection_name = "brainstorming_techniques"
        try:
            self.collection = self.chroma_client.get_collection(
                name=self.collection_name
            )
        except Exception as e:
            raise RuntimeError(
                f"브레인스토밍 컬렉션을 찾을 수 없습니다. "
                f"먼저 chroma_loader.py를 실행하세요. Error: {e}"
            )
    
    def _embed_query(self, query: str) -> List[float]:
        """
        질문을 임베딩 벡터로 변환
        
        Args:
            query: 검색 질문
            
        Returns:
            임베딩 벡터
        """
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=query,
            encoding_format="float"
        )
        
        return response.data[0].embedding
    
    def search_techniques(
        self, 
        query: str, 
        n_results: int = 5,
        min_similarity: float = 0.0
    ) -> List[Dict]:
        """
        브레인스토밍 기법 검색
        
        Args:
            query: 검색 질문 (예: "팀 협업을 위한 방법", "창의적인 아이디어 도출")
            n_results: 반환할 결과 개수 (기본값: 5)
            min_similarity: 최소 유사도 (0~1, 기본값: 0.0)
            
        Returns:
            검색 결과 리스트
            [
                {
                    "chunk_id": "01",
                    "title": "마인드 매핑",
                    "content": "...",
                    "similarity": 0.85,
                    "metadata": {...}
                },
                ...
            ]
        """
        # 1. 질문을 벡터로 변환
        query_embedding = self._embed_query(query)
        
        # 2. ChromaDB에서 유사도 검색
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # 3. 결과 포맷팅
        formatted_results = []
        
        for idx in range(len(results['ids'][0])):
            distance = results['distances'][0][idx]
            similarity = 1 - distance  # 거리를 유사도로 변환
            
            # 최소 유사도 필터링
            if similarity < min_similarity:
                continue
            
            metadata = results['metadatas'][0][idx]
            document = results['documents'][0][idx]
            
            formatted_results.append({
                "chunk_id": metadata['chunk_id'],
                "title": metadata['title'],
                "content": document,
                "similarity": round(similarity, 4),
                "metadata": {
                    "word_count": metadata.get('word_count', 0),
                    "char_count": metadata.get('char_count', 0),
                    "source_file": metadata.get('source_file', ''),
                    "embedding_model": metadata.get('embedding_model', '')
                }
            })
        
        return formatted_results
    
    def generate_suggestions(
        self, 
        query: str,
        context_count: int = 3
    ) -> Dict:
        """
        RAG를 사용하여 브레인스토밍 제안 생성
        
        Args:
            query: 사용자 질문/상황
            context_count: 참고할 청크 개수
            
        Returns:
            {
                "query": "...",
                "suggestions": "GPT가 생성한 제안",
                "sources": [...] # 참고한 청크들
            }
        """
        # 1. 관련 청크 검색
        relevant_chunks = self.search_techniques(
            query=query,
            n_results=context_count,
            min_similarity=0.3
        )
        
        if not relevant_chunks:
            return {
                "query": query,
                "suggestions": "관련된 브레인스토밍 기법을 찾을 수 없습니다.",
                "sources": []
            }
        
        # 2. 컨텍스트 구성
        context_text = "\n\n".join([
            f"[{chunk['title']}]\n{chunk['content']}"
            for chunk in relevant_chunks
        ])
        
        # 3. GPT에게 질문
        prompt = f"""당신은 브레인스토밍 전문가입니다. 
아래의 브레인스토밍 기법들을 참고하여 사용자의 상황에 가장 적합한 방법을 추천해주세요.

<참고 자료>
{context_text}

<사용자 질문>
{query}

위 자료를 바탕으로:
1. 이 상황에 가장 적합한 브레인스토밍 기법 2-3가지를 추천하고
2. 각 기법을 어떻게 적용하면 좋을지 구체적으로 설명해주세요.
3. 실행 시 주의사항도 함께 알려주세요.

친근하고 실용적인 톤으로 답변해주세요."""

        response = self.openai_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "당신은 브레인스토밍과 창의적 사고 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS
        )
        
        suggestions = response.choices[0].message.content
        
        # 4. 결과 반환
        return {
            "query": query,
            "suggestions": suggestions,
            "sources": [
                {
                    "title": chunk['title'],
                    "chunk_id": chunk['chunk_id'],
                    "similarity": chunk['similarity']
                }
                for chunk in relevant_chunks
            ]
        }
    
    def get_technique_by_id(self, chunk_id: str) -> Optional[Dict]:
        """
        특정 청크 ID로 브레인스토밍 기법 조회
        
        Args:
            chunk_id: 청크 ID (예: "01", "02")
            
        Returns:
            청크 정보 또는 None
        """
        # ChromaDB에서 ID로 조회
        try:
            result = self.collection.get(
                ids=[f"chunk_{chunk_id}"],
                include=["documents", "metadatas"]
            )
            
            if not result['ids']:
                return None
            
            metadata = result['metadatas'][0]
            document = result['documents'][0]
            
            return {
                "chunk_id": metadata['chunk_id'],
                "title": metadata['title'],
                "content": document,
                "metadata": {
                    "word_count": metadata.get('word_count', 0),
                    "char_count": metadata.get('char_count', 0),
                    "source_file": metadata.get('source_file', ''),
                    "embedding_model": metadata.get('embedding_model', '')
                }
            }
        except:
            return None
    
    def list_all_techniques(self) -> List[Dict]:
        """
        모든 브레인스토밍 기법 목록 조회
        
        Returns:
            모든 청크의 요약 정보 리스트
        """
        result = self.collection.get(
            include=["metadatas"]
        )
        
        techniques = []
        for idx, chunk_id in enumerate(result['ids']):
            metadata = result['metadatas'][idx]
            techniques.append({
                "chunk_id": metadata['chunk_id'],
                "title": metadata['title'],
                "word_count": metadata.get('word_count', 0)
            })
        
        # chunk_id로 정렬
        techniques.sort(key=lambda x: x['chunk_id'])
        
        return techniques
