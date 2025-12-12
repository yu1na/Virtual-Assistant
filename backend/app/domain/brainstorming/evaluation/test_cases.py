"""
테스트 케이스 정의
"""

from typing import List, Dict

# 테스트 케이스 001: 파티쉐 디저트 아이디어
TEST_CASE_001 = {
    "id": "tc001",
    "name": "파티쉐 디저트 아이디어",
    "category": "창업/제품 기획",
    
    # Q1: 목적
    "q1_purpose": "프랑스 파티쉐가 인스타그램에서 판매할 수 있는 시각적으로 매력적인 디저트 아이디어",
    
    # Q3: 자유 연상 단어들 (Ephemeral RAG)
    "q3_associations": [
        "디저트", "파티쉐", "인스타그램", "비주얼", "홈베이킹",
        "마카롱", "케이크", "타르트", "색감", "예쁜",
        "SNS", "사진", "주문제작", "시그니처", "차별화"
    ],
    
    # 기대 결과
    "expected": {
        "ideas_count_min": 2,  # 최소 2개 (API 코드상 2-3개)
        "has_swot": True,       # SWOT 분석 포함
    },
    
    # 참고: Before 개선 시 예상 점수 (참고용)
    "baseline_scores": {
        "rag_utilization": 4.0,
        "completeness": 8.0,
        "relevance": 9.0,
        "creativity": 3.0,
        "practicality": 8.0,
    }
}


# 테스트 케이스 002: 크리에이터 유튜브 기획
TEST_CASE_002 = {
    "id": "tc002",
    "name": "크리에이터 유튜브 브이로그 기획",
    "category": "콘텐츠 제작",
    
    # Q1: 목적
    "q1_purpose": "일상 브이로그를 찍는 1인 크리에이터가 구독자를 늘리고 차별화할 수 있는 유튜브 콘텐츠 아이디어",
    
    # Q3: 자유 연상 단어들 (Ephemeral RAG)
    "q3_associations": [
        "유튜브", "브이로그", "구독자", "콘텐츠", "영상편집",
        "썸네일", "알고리즘", "조회수", "일상", "크리에이터",
        "휴대폰촬영", "숏츠", "댓글", "소통", "채널성장"
    ],
    
    # 기대 결과
    "expected": {
        "ideas_count_min": 2,
        "has_swot": True,
    },
    
    # 참고: Before 개선 시 예상 점수 (참고용)
    "baseline_scores": {
        "rag_utilization": 4.0,
        "completeness": 8.0,
        "relevance": 9.0,
        "creativity": 3.0,
        "practicality": 8.0,
    }
}


# 테스트 케이스 003: 소규모 비즈니스 SNS 마케팅
TEST_CASE_003 = {
    "id": "tc003",
    "name": "소규모 로컬 카페 SNS 마케팅",
    "category": "마케팅/홍보",
    
    # Q1: 목적
    "q1_purpose": "동네에서 작은 카페를 운영하는 사장님이 저비용으로 SNS를 활용해 단골 고객을 늘릴 수 있는 마케팅 전략",
    
    # Q3: 자유 연상 단어들 (Ephemeral RAG)
    "q3_associations": [
        "카페", "SNS", "인스타그램", "마케팅", "홍보",
        "단골", "지역", "로컬", "소상공인", "사진",
        "이벤트", "쿠폰", "리뷰", "해시태그", "스토리"
    ],
    
    # 기대 결과
    "expected": {
        "ideas_count_min": 2,
        "has_swot": True,
    },
    
    # 참고: Before 개선 시 예상 점수 (참고용)
    "baseline_scores": {
        "rag_utilization": 4.0,
        "completeness": 8.0,
        "relevance": 9.0,
        "creativity": 3.0,
        "practicality": 8.0,
    }
}


# 모든 테스트 케이스 리스트
ALL_TEST_CASES: List[Dict] = [
    TEST_CASE_001,
    TEST_CASE_002,
    TEST_CASE_003,
]


def get_test_case_by_id(test_id: str) -> Dict:
    """
    ID로 테스트 케이스 조회
    
    Args:
        test_id: 테스트 케이스 ID (예: "tc001")
    
    Returns:
        Dict: 테스트 케이스
    
    Raises:
        ValueError: 해당 ID의 테스트 케이스가 없을 때
    """
    for case in ALL_TEST_CASES:
        if case["id"] == test_id:
            return case
    
    raise ValueError(f"테스트 케이스를 찾을 수 없습니다: {test_id}")


def list_test_cases() -> List[str]:
    """
    모든 테스트 케이스 ID 목록
    
    Returns:
        List[str]: 테스트 케이스 ID 리스트
    """
    return [case["id"] for case in ALL_TEST_CASES]

