"""
평가 모듈 데이터 모델 (Pydantic)
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class EvaluationScore(BaseModel):
    """개별 평가 점수"""
    
    rag_utilization: float = Field(..., ge=1, le=10, description="RAG 활용도 (1-10)")
    completeness: float = Field(..., ge=1, le=10, description="답변 완성도 (1-10)")
    relevance: float = Field(..., ge=1, le=10, description="질문-답변 연관도 (1-10)")
    creativity: float = Field(..., ge=1, le=10, description="창의성 (1-10)")
    practicality: float = Field(..., ge=1, le=10, description="실용성 (1-10)")
    
    reasoning: str = Field(..., description="평가 근거")
    
    def weighted_average(self, weights: Dict[str, float]) -> float:
        """가중 평균 계산"""
        total = (
            self.rag_utilization * weights["rag_utilization"] +
            self.completeness * weights["completeness"] +
            self.relevance * weights["relevance"] +
            self.creativity * weights["creativity"] +
            self.practicality * weights["practicality"]
        )
        return round(total, 2)


class TestCaseInput(BaseModel):
    """테스트 케이스 입력 데이터"""
    
    id: str = Field(..., description="테스트 케이스 ID")
    name: str = Field(..., description="테스트 케이스 이름")
    category: str = Field(..., description="카테고리")
    q1_purpose: str = Field(..., description="Q1: 목적")
    q3_associations: List[str] = Field(..., description="Q3: 자유 연상 단어")
    expected: Dict = Field(default_factory=dict, description="기대 결과")


class SingleRunResult(BaseModel):
    """단일 실행 결과"""
    
    run_number: int = Field(..., description="실행 번호 (1, 2, 3)")
    session_id: str = Field(..., description="세션 ID")
    
    # 생성된 결과
    ideas_text: str = Field(..., description="생성된 아이디어 전문")
    ideas_count: int = Field(..., description="생성된 아이디어 개수")
    
    # RAG 정보
    permanent_rag_docs: List[str] = Field(default_factory=list, description="사용된 Permanent RAG 문서")
    ephemeral_keywords: List[str] = Field(default_factory=list, description="추출된 Ephemeral RAG 키워드")
    
    # 평가 점수
    scores: EvaluationScore = Field(..., description="평가 점수")
    weighted_total: float = Field(..., description="가중 평균 점수")
    
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="실행 시각")


class TestCaseResult(BaseModel):
    """테스트 케이스 전체 결과 (3회 실행)"""
    
    test_case_id: str = Field(..., description="테스트 케이스 ID")
    test_case_name: str = Field(..., description="테스트 케이스 이름")
    
    # 3회 실행 결과
    runs: List[SingleRunResult] = Field(..., description="3회 실행 결과")
    
    # 평균 점수
    average_scores: Dict[str, float] = Field(..., description="평균 점수")
    average_weighted_total: float = Field(..., description="평균 가중 점수")
    
    # 표준편차 (일관성 측정)
    std_deviation: float = Field(..., description="표준편차 (낮을수록 일관성 높음)")
    
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="평가 시각")


class EvaluationSummary(BaseModel):
    """전체 평가 요약"""
    
    evaluation_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"), description="평가 날짜")
    test_cases: List[TestCaseResult] = Field(..., description="테스트 케이스 결과 목록")
    
    overall_average: float = Field(..., description="전체 평균 점수")
    
    model_info: Dict[str, str] = Field(default_factory=dict, description="모델 정보")

