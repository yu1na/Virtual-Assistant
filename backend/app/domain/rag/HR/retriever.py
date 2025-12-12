"""
RAG 검색 모듈 (LangChain 기반)

LangChain 체인과 LangSmith를 사용하여 RAG 시스템을 구현합니다.
"""

from typing import List, Optional, Dict, Any
import time
import os
import json
import datetime

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_openai import ChatOpenAI

# LangSmith 설정
from langsmith import traceable

from .config import rag_config
from .vector_store import VectorStore
from .schemas import QueryRequest, QueryResponse, RetrievedChunk
from .utils import get_logger
from .evaluator import RAGEvaluator

logger = get_logger(__name__)


class RAGRetriever:
    """RAG 기반 검색 및 답변 생성 (LangChain 체인 사용)"""
    
    def __init__(self, collection_name: Optional[str] = None):
        self.config = rag_config
        self.vector_store = VectorStore(collection_name)
        
        # LangSmith 설정
        if self.config.LANGSMITH_TRACING and self.config.LANGSMITH_API_KEY:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.config.LANGSMITH_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = self.config.LANGSMITH_PROJECT
            logger.info(f"LangSmith 추적 활성화: {self.config.LANGSMITH_PROJECT}")
        
        # Lazy loading: LLM을 실제 사용 시에만 로드
        self._llm = None
        self._rag_chain = None
        self._evaluator = None
        
        logger.info("RAGRetriever 초기화 완료 (LLM lazy loading)")

    @property
    def evaluator(self):
        """Evaluator lazy loading"""
        if self._evaluator is None:
            self._evaluator = RAGEvaluator()
        return self._evaluator
    
    @property
    def llm(self):
        """LLM lazy loading"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.config.OPENAI_MODEL,
                temperature=self.config.OPENAI_TEMPERATURE,
                max_tokens=self.config.OPENAI_MAX_TOKENS,
                api_key=self.config.OPENAI_API_KEY
            )
            logger.info(f"LLM 로드 완료: {self.config.OPENAI_MODEL}")
        return self._llm
    
    @property
    def prompt_template(self):
        """프롬프트 템플릿"""
        return ChatPromptTemplate.from_messages([
            ("system", """당신은 문서 내용을 기반으로 정확하게 답변하는 AI 어시스턴트입니다.

다음 규칙을 엄격히 준수하여 답변하세요:

1. **답변 원칙**:
   - 제공된 문서(Context)에 있는 내용만으로 답변하세요.
   - **사용자가 묻는 정보가 문서에 명확히 없더라도, 문맥상 유추할 수 있거나 관련된 내용이 있다면 이를 찾아서 설명해 주세요.**
   - 아예 관련 내용이 없을 때만 "죄송합니다. 관련 정보를 문서에서 찾을 수 없습니다."라고 답변하세요.

2. **Markdown 필수**: 가독성을 위해 Markdown을 적극 활용하세요.
   - **모든 목록(글머리 기호)과 소제목(`###`) 앞뒤에는 반드시 줄바꿈 문자를 두 번 사용하여 빈 줄을 만드세요.**
   - 핵심 내용은 **볼드체**로 강조합니다.

3. **간결성**: 불필요한 서론을 빼고 핵심만 간결하게 답변하세요.
4. **언어**: 한국어로 답변하세요."""),
            ("user", """다음 문서들을 참고하여 질문에 답변해주세요.

{context}

질문: {query}

답변:""")
        ])
    
    @property
    def rag_chain(self):
        """RAG 체인 lazy loading"""
        if self._rag_chain is None:
            self._rag_chain = self._build_rag_chain()
            logger.info("RAG 체인 구성 완료")
        return self._rag_chain
    
    def _build_rag_chain(self):
        """LangChain 파이프 연산자(|)를 사용하여 RAG 체인 구성"""
        
        # 1. 컨텍스트 검색 및 동적 threshold 필터링
        @traceable(name="retrieve_and_filter")
        def retrieve_and_filter(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """문서 검색 및 동적 threshold 기반 필터링 (후보군 확대 + 키워드 부스팅 + 최소 보장)"""
            query = inputs["query"]
            top_k = inputs.get("top_k", self.config.RAG_TOP_K)
            
            logger.info(f"문서 검색 중: '{query}' (Top-{top_k})")
            
            # 1단계: 넉넉하게 많이 가져오기 (fetch_k=20)
            fetch_k = 20
            results = self.vector_store.search(query, fetch_k)
            
            # 결과 변환
            candidates = []
            all_similarities = []
            
            # 검색 결과 확인
            if not results:
                logger.warning("검색 결과가 없습니다.")
            elif not results.get('documents') or not results['documents']:
                logger.warning("검색 결과 문서가 없습니다.")
            elif not results['documents'][0]:
                logger.warning("검색 결과 문서 리스트가 비어있습니다.")
            else:
                doc_list = results['documents'][0]
                similarity_list = results.get('distances', [[]])[0] if results.get('distances') else []
                meta_list = results.get('metadatas', [[]])[0] if results.get('metadatas') else []
                
                logger.info(f"후보군 검색 결과: {len(doc_list)}개 문서, {len(similarity_list)}개 유사도 점수")
                
                # 모든 후보군 수집
                for i in range(len(doc_list)):
                    if i < len(similarity_list):
                        similarity_score = float(similarity_list[i])
                    else:
                        similarity_score = 0.0
                    
                    all_similarities.append(similarity_score)
                    
                    metadata = meta_list[i] if i < len(meta_list) else {}
                    chunk = RetrievedChunk(
                        text=doc_list[i],
                        metadata=metadata,
                        score=similarity_score
                    )
                    candidates.append(chunk)
            
            # 2단계: 키워드 점수 계산 및 부스팅
            def apply_keyword_boosting(chunks: List[RetrievedChunk], query_text: str) -> List[RetrievedChunk]:
                """키워드 매칭 점수를 추가하여 부스팅"""
                query_words = set(query_text.lower().split())
                scored_candidates = []
                
                for chunk in chunks:
                    keyword_score = 0.0
                    chunk_text_lower = chunk.text.lower()
                    
                    # 키워드 매칭 점수 계산 (2글자 이상인 단어만 체크)
                    for word in query_words:
                        if len(word) > 2 and word in chunk_text_lower:
                            keyword_score += 0.02  # 키워드당 +0.02 부스팅
                    
                    # 부스팅된 점수로 새 청크 생성
                    boosted_score = chunk.score + keyword_score
                    boosted_chunk = RetrievedChunk(
                        text=chunk.text,
                        metadata=chunk.metadata,
                        score=boosted_score
                    )
                    scored_candidates.append(boosted_chunk)
                    
                    if keyword_score > 0:
                        logger.debug(f"키워드 부스팅: {chunk.metadata.get('filename', 'Unknown')} "
                                   f"(기본: {chunk.score:.4f}, 부스팅: +{keyword_score:.4f}, 최종: {boosted_score:.4f})")
                
                return scored_candidates
            
            scored_candidates = apply_keyword_boosting(candidates, query)
            
            # 점수 순으로 정렬
            scored_candidates.sort(key=lambda x: x.score, reverse=True)
            
            # 3단계: 동적 threshold 계산
            if all_similarities:
                # 최고 점수와 평균 점수 계산
                max_similarity = max(all_similarities)
                avg_similarity = sum(all_similarities) / len(all_similarities)
                
                # 동적 threshold: 최고 점수와 평균의 중간값, min~max 범위 내로 제한
                dynamic_threshold = (max_similarity + avg_similarity) / 2
                dynamic_threshold = max(
                    self.config.RAG_MIN_SIMILARITY_THRESHOLD,
                    min(dynamic_threshold, self.config.RAG_MAX_SIMILARITY_THRESHOLD)
                )
                
                logger.info(f"동적 threshold 계산: max={max_similarity:.4f}, avg={avg_similarity:.4f}, "
                           f"threshold={dynamic_threshold:.4f} (범위: {self.config.RAG_MIN_SIMILARITY_THRESHOLD}~{self.config.RAG_MAX_SIMILARITY_THRESHOLD})")
            else:
                dynamic_threshold = self.config.RAG_MIN_SIMILARITY_THRESHOLD
                logger.warning(f"유사도 없음, 기본 threshold 사용: {dynamic_threshold}")
            
            # 4단계: Threshold 적용 (단, 최소 3개는 보장)
            final_results = []
            for chunk in scored_candidates:
                if chunk.score > dynamic_threshold:
                    final_results.append(chunk)
                    logger.debug(f"  ✓ Threshold 통과: {chunk.metadata.get('filename', 'Unknown')}, "
                               f"페이지: {chunk.metadata.get('page_number', '?')}, "
                               f"점수: {chunk.score:.4f} > {dynamic_threshold:.4f}")
            
            # 안전장치: Threshold를 넘은 게 너무 적으면, 점수 높은 순으로 최소 3개 채우기
            min_guaranteed = 3
            if len(final_results) < min_guaranteed:
                logger.warning(f"Threshold 통과 청크가 {len(final_results)}개로 부족합니다. "
                             f"점수 높은 순으로 최소 {min_guaranteed}개 보장합니다.")
                final_results = scored_candidates[:min_guaranteed]
                logger.info(f"최소 보장 적용: {len(final_results)}개 청크 선택")
            
            logger.info(f"Threshold 필터링 결과: {len(final_results)}개 청크 (후보군 {len(candidates)}개 중)")
            
            # 5단계: 같은 페이지의 청크들을 묶어서 합치기
            from collections import defaultdict
            page_groups = defaultdict(list)
            
            for chunk in final_results:
                filename = chunk.metadata.get('filename', 'Unknown')
                page_num = chunk.metadata.get('page_number', 0)
                key = (filename, page_num)
                
                chunk_index = chunk.metadata.get('chunk_index', 0)
                
                page_groups[key].append({
                    'chunk': chunk,
                    'score': chunk.score,
                    'chunk_index': chunk_index
                })
            
            # 각 페이지 그룹 내에서 chunk_index 순서로 정렬
            merged_chunks = []
            for (filename, page_num), group_chunks in page_groups.items():
                # chunk_index 순서로 정렬
                group_chunks.sort(key=lambda x: x['chunk_index'])
                
                # 같은 페이지의 텍스트 청크들을 합치기
                merged_text_parts = []
                max_score = max(g['score'] for g in group_chunks)
                
                for gc in group_chunks:
                    merged_text_parts.append(gc['chunk'].text)
                
                merged_text = "\n".join(merged_text_parts)
                
                # 첫 번째 청크의 메타데이터를 사용하되, 점수는 그룹 내 최고 점수 사용
                first_chunk = group_chunks[0]['chunk']
                merged_chunk = RetrievedChunk(
                    text=merged_text,
                    metadata=first_chunk.metadata,
                    score=max_score
                )
                
                merged_chunks.append({
                    'chunk': merged_chunk,
                    'score': max_score
                })
            
            # 점수로 정렬 (높은 순)
            merged_chunks.sort(key=lambda x: x['score'], reverse=True)
            
            # 6단계: 그 중에서 Top-5 자르기
            final_chunks = [mc['chunk'] for mc in merged_chunks[:top_k]]
            
            logger.info(f"최종 선택: {len(final_chunks)}개 페이지 그룹 "
                      f"(후보군 {len(candidates)}개 → Threshold 통과 {len(final_results)}개 → "
                      f"병합 {len(merged_chunks)}개 → Top-{top_k} {len(final_chunks)}개)")
            
            # 컨텍스트 구성
            context_parts = []
            for i, chunk in enumerate(final_chunks, 1):
                context_parts.append(f"[문서 {i}]")
                context_parts.append(f"파일: {chunk.metadata.get('filename', 'Unknown')}")
                context_parts.append(f"페이지: {chunk.metadata.get('page_number', 'Unknown')}")
                context_parts.append(f"내용:\n{chunk.text}")
                context_parts.append("")
            
            context = "\n".join(context_parts) if context_parts else "관련 문서를 찾을 수 없습니다."
            
            return {
                "query": query,
                "context": context,
                "retrieved_chunks": final_chunks,
                "top_k": top_k,
                "dynamic_threshold": dynamic_threshold
            }
        
        # 2. 답변 생성
        @traceable(name="generate_answer")
        def generate_answer(inputs: Dict[str, Any]) -> Dict[str, Any]:
            """LLM을 사용하여 답변 생성"""
            query = inputs["query"]
            context = inputs["context"]
            retrieved_chunks = inputs["retrieved_chunks"]
            
            if not retrieved_chunks:
                logger.warning("검색된 청크가 없음 - 기본 메시지 반환")
                return {
                    **inputs,
                    "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다."
                }
            
            # LangChain 체인 실행: prompt | llm | parser
            answer = (
                self.prompt_template 
                | self.llm 
                | StrOutputParser()
            ).invoke({
                "query": query,
                "context": context
            })
            
            return {
                **inputs,
                "answer": answer
            }
        
        # LangChain 체인 구성 (파이프 연산자 사용)
        chain = (
            RunnablePassthrough()
            | RunnableLambda(retrieve_and_filter)
            | RunnableLambda(generate_answer)
        )
        
        return chain
    
    @traceable(
        name="rag_query_full",
        metadata={
            "component": "RAG System",
            "version": "1.0"
        }
    )
    def query(self, request: QueryRequest) -> QueryResponse:
        """
        질의응답 전체 프로세스 (검색 필요 여부에 따라 RAG 또는 LLM 단독 사용)
        
        Args:
            request: 질의응답 요청
            
        Returns:
            QueryResponse: 질의응답 응답
        """
        start_time = time.time()
        
        try:
            # 문서 검색 필요: RAG 실행
            logger.info(f"문서 검색 필요: '{request.query}' -> RAG 실행")
            
            # LangChain 체인 실행 (동적 threshold는 자동 계산)
            result = self.rag_chain.invoke({
                "query": request.query,
                "top_k": request.top_k or self.config.RAG_TOP_K
            })
            
            answer = result["answer"]
            retrieved_chunks = result["retrieved_chunks"]
            
            # 검색 결과가 없을 때: Small talk 사용하지 않고 "정보 없음" 메시지
            if not retrieved_chunks:
                logger.warning(f"검색 결과 없음: '{request.query}' -> 정보 부족 메시지 반환")
                answer = "죄송합니다. 질문하신 내용과 관련된 문서를 찾을 수 없습니다. 다른 질문을 해주시거나, 더 구체적으로 질문해주세요."
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            # LangSmith에 메타데이터 전달을 위해 dict로 변환
            response = QueryResponse(
                query=request.query,
                answer=answer,
                retrieved_chunks=retrieved_chunks,
                processing_time=processing_time,
                model_used=self.config.OPENAI_MODEL
            )
            
            # 실시간 평가 수행 (터미널 출력용)
            # 실시간 평가 수행 (터미널 출력용) - 비활성화 (속도 개선 및 토큰 절약)
            # try:
            #     print("\n" + "="*50)
            #     print("🔍 실시간 RAG 답변 평가 수행 중...")
            #     # Ground Truth 조회 (평가용으로만 사용)
            #     ground_truth = self.evaluator.lookup_ground_truth(request.query)
                
            #     eval_result = self.evaluator.evaluate_single(
            #         question=request.query,
            #         answer=answer,
            #         context="\n".join([chunk.text for chunk in retrieved_chunks]),
            #         ground_truth=ground_truth
            #     )
            #     print(f"  - 정확성 (Faithfulness): {eval_result.get('faithfulness_score')}점")
            #     print(f"  - 완전성 (Completeness): {eval_result.get('completeness_score')}점")
            #     print(f"  - 연관성 (Answer Relevancy): {eval_result.get('answer_relevancy_score')}점")
            #     print(f"  - 정밀도 (Context Precision): {eval_result.get('context_precision_score')}점")
            #     print(f"  - 일치도 (Answer Correctness): {eval_result.get('answer_correctness_score')}점")
                
            #     # 결과 JSON 저장
            #     try:
            #         timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    
            #         # 절대 경로 계산: backend/data/HR_RAG/HR_RAG_result
            #         current_dir = os.path.dirname(os.path.abspath(__file__))
            #         # backend/app/domain/rag/HR -> ... -> backend
            #         backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
            #         result_dir = os.path.join(backend_dir, "data", "HR_RAG", "HR_RAG_result")
                    
            #         os.makedirs(result_dir, exist_ok=True)
                    
            #         result_file = os.path.join(result_dir, f"evaluation_{timestamp}.json")
                    
            #         # 저장할 데이터 구성
            #         save_data = {
            #             "timestamp": timestamp,
            #             "query": request.query,
            #             "answer": answer,
            #             "retrieved_chunks": [
            #                 {
            #                     "filename": chunk.metadata.get("filename", "Unknown"),
            #                     "page": chunk.metadata.get("page_number", "?"),
            #                     "score": chunk.score,
            #                     "text": chunk.text
            #                 } for chunk in retrieved_chunks
            #             ],
            #             "ground_truth": ground_truth,
            #             "evaluation": eval_result
            #         }
                    
            #         with open(result_file, 'w', encoding='utf-8') as f:
            #             json.dump(save_data, f, ensure_ascii=False, indent=4)
                        
            #         logger.info(f"평가 결과 저장 완료: {result_file}")
            #         print(f"  - 결과 파일 저장: {result_file}")
                    
            #     except Exception as save_e:
            #         logger.error(f"평가 결과 저장 실패: {save_e}")
            #         print(f"  - 결과 파일 저장 실패: {save_e}")

            #     print("="*50 + "\n")
                    
            # except Exception as eval_e:
            #     logger.warning(f"실시간 평가 중 오류 발생: {eval_e}")
            #     print(f"❌ 실시간 평가 중 오류 발생: {eval_e}")
            #     print("="*50 + "\n")
            
            # LangSmith 메타데이터 로깅
            from langsmith import traceable
            from langsmith.run_helpers import get_current_run_tree
            
            try:
                run_tree = get_current_run_tree()
                if run_tree:
                    run_tree.extra = {
                        "retrieved_chunks_count": len(retrieved_chunks),
                        "chunks": [
                            {
                                "filename": chunk.metadata.get("filename", "Unknown"),
                                "page_number": chunk.metadata.get("page_number", 0),
                                "score": chunk.score
                            }
                            for chunk in retrieved_chunks
                        ],
                        "processing_time": processing_time,
                        "model": self.config.OPENAI_MODEL
                    }
            except Exception as e:
                logger.warning(f"LangSmith 메타데이터 추가 실패: {e}")
            
            return response
            
        except Exception as e:
            logger.exception("질의응답 처리 중 오류")
            processing_time = time.time() - start_time
            
            return QueryResponse(
                query=request.query,
                answer=f"질의응답 처리 중 오류가 발생했습니다: {str(e)}",
                retrieved_chunks=[],
                processing_time=processing_time,
                model_used=self.config.OPENAI_MODEL
            )
    
