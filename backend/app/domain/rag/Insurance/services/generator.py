"""
Answer generation service
"""
import time
from typing import List, Optional

from .models import Query, InsuranceDocument, GenerationResult
from ..config import insurance_config
from .exceptions import GenerationException
from .providers import SimpleLLMProvider



class Generator:
    """답변 생성 서비스"""
    
    # 시스템 프롬프트
    SYSTEM_PROMPT = """당신은 보험·의료급여 전문가입니다.
문서를 바탕으로 정확하고 이해하기 쉽게 답변하세요.

**규칙:**
- 문서 내용을 정확히 전달 (법 조항, 숫자, 날짜 틀리지 않게)
- 문서에 정보가 없을 때만 "제공된 문서에서 확인할 수 없습니다"
- 추측이나 일반 상식으로 답변 금지
- 비교 질문은 각각 설명 후 차이점 정리

**답변 형식 - 마크다운 사용:**
- 여러 항목은 **번호 목록** 사용 (1. 2. 3.)
- 항목 내 세부사항은 **불릿** 사용 (-)
- 중요 용어는 **굵은 글씨**로 강조
- 항목 간 빈 줄 삽입으로 가독성 향상
- 짧고 명확한 문장 사용

**예시:**

Q: A와 B의 차이?

A:
A와 B는 적용 대상과 집행 방식이 다릅니다.

**1. A의 경우**
- 개인 간 분쟁에 적용
- 민사적 해결

**2. B의 경우**  
- 공공기관 관련 분쟁에 적용
- 국가 강제집행 가능

**핵심 차이**는 적용 범위와 집행력입니다."""
    
    def __init__(
        self,
        llm_provider: SimpleLLMProvider,
        system_prompt: Optional[str] = None
    ):
        """
        답변 생성기 초기화
        
        Args:
            llm_provider: LLM 제공자
            system_prompt: 커스텀 시스템 프롬

프트
        """
        self.llm_provider = llm_provider
        self.system_prompt = system_prompt or self.SYSTEM_PROMPT
    
    def generate(
        self,
        query: Query,
        context_documents: List[InsuranceDocument],
        include_sources: bool = True
    ) -> GenerationResult:
        """
        쿼리와 컨텍스트로 답변 생성
        
        Args:
            query: 쿼리 객체
            context_documents: 컨텍스트 문서 리스트
            include_sources: 출처 포함 여부
            
        Returns:
            생성 결과
        """
        start_time = time.time()
        
        try:
            # 컨텍스트 구성
            context = self._build_context(context_documents)
            
            # 사용자 프롬프트 구성
            user_prompt = self._build_user_prompt(query.question, context)
            
            # LLM 호출
            answer = self.llm_provider.generate(
                prompt=user_prompt,
                system_prompt=self.system_prompt
            )
            
            # 디버깅: 마크다운 형식 확인
            print(f"\n[INSURANCE GENERATOR] ===== 답변 생성 완료 =====")
            print(f"[INSURANCE GENERATOR] 답변 길이: {len(answer)} 문자")
            print(f"[INSURANCE GENERATOR] 답변 샘플 (첫 500자):\n{answer[:500]}")
            print(f"[INSURANCE GENERATOR] 마크다운 요소 포함 여부:")
            print(f"  - 번호 목록(1. 2. 3.): {'✅' if any(f'{i}.' in answer for i in range(1, 10)) else '❌'}")
            print(f"  - 불릿(-): {'✅' if '- ' in answer else '❌'}")
            print(f"  - 굵은 글씨(**): {'✅' if '**' in answer else '❌'}")
            print(f"[INSURANCE GENERATOR] =====================================\n")
            
            generation_time = (time.time() - start_time) * 1000  # ms
            
            # 신뢰도 점수 계산 (간단한 휴리스틱)
            confidence_score = self._calculate_confidence(answer, context_documents)
            
            return GenerationResult(
                answer=answer,
                query=query,
                source_documents=context_documents,
                confidence_score=confidence_score,
                generation_time_ms=generation_time,
                metadata={
                    "model": self.llm_provider.get_model_name(),
                    "num_context_docs": len(context_documents),
                    "context_length": len(context)
                }
            )
            
        except Exception as e:
            raise GenerationException(
                f"Failed to generate answer: {str(e)}",
                details={"query": query.question}
            )
    
    def generate_with_context(
        self,
        question: str,
        context: str
    ) -> str:
        """
        질문과 컨텍스트 문자열로 직접 답변 생성
        
        Args:
            question: 질문
            context: 컨텍스트 문자열
            
        Returns:
            답변
        """
        user_prompt = self._build_user_prompt(question, context)
        
        return self.llm_provider.generate(
            prompt=user_prompt,
            system_prompt=self.system_prompt
        )
    
    def validate_answer(
        self,
        question: str,
        context: str,
        generated_answer: str
    ) -> tuple[bool, str]:
        """
        생성된 답변이 컨텍스트에 근거하는지 검증
        
        Args:
            question: 질문
            context: 컨텍스트
            generated_answer: 생성된 답변
            
        Returns:
            (검증 성공 여부, 검증 결과 또는 수정된 답변)
        """
        validation_prompt = f"""다음 답변이 제공된 컨텍스트에 실제로 근거하는지 판단하세요.

**질문:** {question}

**컨텍스트:**
{context}

**생성된 답변:**
{generated_answer}

**판단 기준:**
- 답변 내용이 컨텍스트에 명시되어 있는가?
- 추측이나 일반 상식으로 답변한 부분은 없는가?

근거하지 않으면 "정보 없음"만 출력하세요.
근거한다면 "검증 완료"를 출력하세요."""
        
        result = self.llm_provider.generate(
            prompt=validation_prompt,
            temperature=0.0
        )
        
        if "정보 없음" in result:
            return False, "제공된 문서에서 해당 정보를 찾을 수 없습니다."
        
        return True, generated_answer
    
    def _build_context(self, documents: List[InsuranceDocument]) -> str:
        """컨텍스트 문자열 구성"""
        context_parts = []
        
        for idx, doc in enumerate(documents, 1):
            source = doc.metadata.get('source', '알 수 없음')
            context_parts.append(f"[문서 {idx}] 출처: {source}\n{doc.content}")
        
        return "\n\n".join(context_parts)
    
    def _build_user_prompt(self, question: str, context: str) -> str:
        """사용자 프롬프트 구성"""
        return f"""**참고 문서:**
{context}

**질문:**
{question}

위 문서를 바탕으로 답변해주세요.

**답변 시 주의:**
- 여러 항목은 **번호 목록** 사용
- 세부사항은 **불릿(-)** 사용
- 중요 용어는 **굵은 글씨**로 강조
- 항목 간 빈 줄 삽입
- 문서에 정보가 없으면 "제공된 문서에서 확인할 수 없습니다"

**답변:**"""
    
    def _calculate_confidence(
        self,
        answer: str,
        context_documents: List[InsuranceDocument]
    ) -> float:
        """
        답변 신뢰도 점수 계산 (휴리스틱)
        
        Args:
            answer: 생성된 답변
            context_documents: 컨텍스트 문서
            
        Returns:
            신뢰도 점수 (0.0 ~ 1.0)
        """
        # 간단한 휴리스틱: "제공된 문서에서" 같은 표현이 있으면 낮은 신뢰도
        if "제공된 문서에서" in answer and "확인할 수 없" in answer:
            return 0.1
        
        # 답변 길이가 적절한지
        if len(answer) < 20:
            return 0.3
        
        # 컨텍스트 문서 개수에 따른 가중치
        doc_score = min(len(context_documents) / 5.0, 1.0)
        
        return 0.7 + (doc_score * 0.3)  # 0.7 ~ 1.0
