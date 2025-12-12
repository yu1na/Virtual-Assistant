"""
Insurance RAG Agent

보험 상품, 청구 절차, 보험금 규정 등에 대한 질문을 처리하는 에이전트입니다.
RAG(Retrieval Augmented Generation)를 통해 보험 매뉴얼 문서에서 정보를 검색하고 답변합니다.
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage

# ============================================================================
# 설정
# ============================================================================

class InsuranceRAGConfig:
    """Insurance RAG 에이전트 설정"""
    
    # API 설정
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    MODEL = "gpt-4o-mini"
    TEMPERATURE = 0.3
    MAX_TOKENS = 1024
    
    # RAG 설정
    CHROMA_DB_PATH = "backend/app/domain/rag/Insurance/chroma_db"
    COLLECTION_NAME = "insurance_manual"
    TOP_K = 5
    
    # 프롬프트 설정
    SYSTEM_PROMPT = """당신은 보험 전문가입니다.

당신의 역할:
1. 사용자의 보험 관련 질문을 이해합니다.
2. 제공된 보험 매뉴얼 문서에서 관련 정보를 찾습니다.
3. 정확하고 명확한 답변을 제공합니다.
4. 문서에 없는 내용은 "문서에서 확인할 수 없습니다"라고 명시합니다.

중요한 규칙:
- 항상 문서 기반의 정보만 제공하세요.
- 추측이나 일반적인 지식으로 답변하지 마세요.
- 복잡한 답변은 단계별로 설명하세요.
- 사용자의 질문에 직접 답변하세요.
"""


# ============================================================================
# Insurance RAG Agent 클래스
# ============================================================================

class InsuranceRAGAgent:
    """보험 RAG 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        self.config = InsuranceRAGConfig()
        self.llm = ChatOpenAI(
            model=self.config.MODEL,
            temperature=self.config.TEMPERATURE,
            max_tokens=self.config.MAX_TOKENS,
            api_key=self.config.OPENAI_API_KEY
        )
        self.retriever = self._initialize_retriever()
    
    def _initialize_retriever(self):
        """ChromaDB 검색기 초기화"""
        try:
            import chromadb
            
            # ChromaDB 클라이언트 초기화
            client = chromadb.PersistentClient(path=self.config.CHROMA_DB_PATH)
            collection = client.get_collection(self.config.COLLECTION_NAME)
            
            return collection
        except Exception as e:
            print(f"[ERROR] ChromaDB 초기화 실패: {e}")
            return None
    
    def _retrieve_context(self, query: str) -> str:
        """쿼리와 유사한 문서 검색"""
        if not self.retriever:
            return "검색 서비스를 이용할 수 없습니다."
        
        try:
            # 쿼리 임베딩 생성
            from openai import OpenAI
            client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            
            response = client.embeddings.create(
                input=query[:8000],
                model="text-embedding-3-small"
            )
            query_embedding = response.data[0].embedding
            
            # 유사한 문서 검색
            results = self.retriever.query(
                query_embeddings=[query_embedding],
                n_results=self.config.TOP_K
            )
            
            # 검색 결과를 컨텍스트로 변환
            if results and results['documents']:
                documents = results['documents'][0]
                context = "\n\n".join([
                    f"[문서 {i+1}]\n{doc}" 
                    for i, doc in enumerate(documents)
                ])
                return context
            else:
                return "관련 문서를 찾을 수 없습니다."
                
        except Exception as e:
            print(f"[ERROR] 문서 검색 실패: {e}")
            return f"검색 중 오류 발생: {str(e)[:100]}"
    
    async def process(self, query: str) -> Dict[str, Any]:
        """
        사용자 질문을 처리합니다.
        
        Args:
            query: 사용자 질문
            
        Returns:
            응답 결과 (answer, source_documents 포함)
        """
        try:
            # 1. 관련 문서 검색
            context = self._retrieve_context(query)
            
            # 2. 프롬프트 구성
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.config.SYSTEM_PROMPT),
                ("user", """다음 보험 매뉴얼 문서를 참고하여 질문에 답변해주세요.

[참고 문서]
{context}

[질문]
{question}

[답변]""")
            ])
            
            # 3. 프롬프트에 값 채우기
            formatted_prompt = prompt.format_messages(
                context=context,
                question=query
            )
            
            # 4. LLM으로 답변 생성
            response = await self.llm.ainvoke(formatted_prompt)
            answer = response.content if response.content else "답변을 생성할 수 없습니다."
            
            # 5. 결과 반환
            return {
                "answer": answer,
                "query": query,
                "source_documents": context[:500] + "..." if len(context) > 500 else context,
                "success": True
            }
            
        except Exception as e:
            print(f"[ERROR] 처리 중 오류: {e}")
            return {
                "answer": f"질문 처리 중 오류가 발생했습니다: {str(e)[:100]}",
                "query": query,
                "source_documents": "",
                "success": False,
                "error": str(e)
            }
    
    def process_sync(self, query: str) -> Dict[str, Any]:
        """
        동기 버전: 사용자 질문을 처리합니다.
        
        Args:
            query: 사용자 질문
            
        Returns:
            응답 결과 (answer, source_documents 포함)
        """
        try:
            # 1. 관련 문서 검색
            context = self._retrieve_context(query)
            
            # 2. 프롬프트 구성
            prompt = ChatPromptTemplate.from_messages([
                ("system", self.config.SYSTEM_PROMPT),
                ("user", """다음 보험 매뉴얼 문서를 참고하여 질문에 답변해주세요.

[참고 문서]
{context}

[질문]
{question}

[답변]""")
            ])
            
            # 3. 프롬프트에 값 채우기
            formatted_prompt = prompt.format_messages(
                context=context,
                question=query
            )
            
            # 4. LLM으로 답변 생성
            response = self.llm.invoke(formatted_prompt)
            answer = response.content if response.content else "답변을 생성할 수 없습니다."
            
            # 5. 결과 반환
            return {
                "answer": answer,
                "query": query,
                "source_documents": context[:500] + "..." if len(context) > 500 else context,
                "success": True
            }
            
        except Exception as e:
            print(f"[ERROR] 처리 중 오류: {e}")
            return {
                "answer": f"질문 처리 중 오류가 발생했습니다: {str(e)[:100]}",
                "query": query,
                "source_documents": "",
                "success": False,
                "error": str(e)
            }


# ============================================================================
# 에이전트 인스턴스 생성
# ============================================================================

async def create_insurance_tool():
    """Insurance RAG Tool 생성"""
    agent = InsuranceRAGAgent()
    
    async def insurance_query(query: str) -> str:
        """
        보험 관련 질문 처리
        
        Args:
            query: 사용자 질문
            
        Returns:
            답변 문자열
        """
        result = await agent.process(query)
        return result["answer"]
    
    return insurance_query


def create_insurance_tool_sync():
    """Insurance RAG Tool 생성 (동기 버전)"""
    agent = InsuranceRAGAgent()
    
    def insurance_query(query: str) -> str:
        """
        보험 관련 질문 처리
        
        Args:
            query: 사용자 질문
            
        Returns:
            답변 문자열
        """
        result = agent.process_sync(query)
        return result["answer"]
    
    return insurance_query
