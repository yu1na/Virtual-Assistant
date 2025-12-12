"""
Judge 클래스 - GPT-5를 사용한 평가
"""

import json
from openai import OpenAI
from typing import Dict, List, Optional
from dotenv import load_dotenv
import os

from .models import EvaluationScore
from .prompts import build_judge_prompt, JUDGE_SYSTEM_PROMPT

load_dotenv()


class BrainstormingJudge:
    """
    브레인스토밍 결과 평가자
    
    GPT-5를 사용하여 생성된 아이디어를 5가지 기준으로 평가합니다.
    """
    
    def __init__(
        self,
        model: str = "gpt-5",
        temperature: float = 1.0,
        api_key: Optional[str] = None
    ):
        """
        Args:
            model: OpenAI 모델명 (기본: gpt-5)
            temperature: 생성 온도 (GPT-5는 1.0만 지원)
            api_key: OpenAI API Key (None이면 환경변수에서 읽음)
        """
        self.model = model
        self.temperature = temperature  # GPT-5는 사용 안 함 (기본값 1.0)
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        
        print(f"✅ BrainstormingJudge 초기화 완료")
        print(f"   - Model: {self.model}")
        print(f"   - Temperature: {self.temperature} (GPT-5는 기본값만 지원)")
    
    def evaluate(
        self,
        question: str,
        answer: str,
        permanent_rag_docs: List[str],
        ephemeral_keywords: List[str]
    ) -> EvaluationScore:
        """
        브레인스토밍 결과 평가
        
        Args:
            question: 사용자 질문 (Q1 목적)
            answer: AI 답변 (생성된 아이디어 전문)
            permanent_rag_docs: Permanent RAG 문서 리스트
            ephemeral_keywords: Ephemeral RAG 키워드 리스트
        
        Returns:
            EvaluationScore: 평가 결과
        """
        
        # Judge 프롬프트 생성
        user_prompt = build_judge_prompt(
            question=question,
            answer=answer,
            permanent_rag_docs=permanent_rag_docs,
            ephemeral_keywords=ephemeral_keywords
        )
        
        # GPT-5 호출
        try:
            # GPT-5는 temperature 조정 불가 (기본값 1만 지원)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            # 응답 파싱
            content = response.choices[0].message.content
            scores_dict = json.loads(content)
            
            # Pydantic 모델로 변환
            score = EvaluationScore(**scores_dict)
            
            return score
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {e}")
            print(f"응답 내용: {content}")
            raise
        except Exception as e:
            print(f"❌ 평가 실패: {e}")
            raise
    
    def evaluate_batch(
        self,
        test_cases: List[Dict]
    ) -> List[EvaluationScore]:
        """
        여러 테스트 케이스 일괄 평가
        
        Args:
            test_cases: 평가할 테스트 케이스 리스트
        
        Returns:
            List[EvaluationScore]: 평가 결과 리스트
        """
        results = []
        
        for i, case in enumerate(test_cases):
            print(f"🔍 평가 중... ({i+1}/{len(test_cases)})")
            
            score = self.evaluate(
                question=case["question"],
                answer=case["answer"],
                permanent_rag_docs=case.get("permanent_rag_docs", []),
                ephemeral_keywords=case.get("ephemeral_keywords", [])
            )
            
            results.append(score)
        
        print(f"✅ 일괄 평가 완료: {len(results)}개")
        return results

