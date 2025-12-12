"""
브레인스토밍 평가 모듈

LLM as a Judge 패턴을 사용하여 브레인스토밍 결과를 자동 평가합니다.

평가 차원:
1. RAG 활용도 (20%)
2. 답변 완성도 (20%)
3. 질문-답변 연관도 (20%)
4. 창의성 (20%)
5. 실용성 (20%)

Judge 모델: GPT-5
"""

from .judge import BrainstormingJudge
from .models import EvaluationScore, TestCaseResult
from .criteria import EVALUATION_CRITERIA, WEIGHTS

__all__ = [
    'BrainstormingJudge',
    'EvaluationScore',
    'TestCaseResult',
    'EVALUATION_CRITERIA',
    'WEIGHTS',
]

