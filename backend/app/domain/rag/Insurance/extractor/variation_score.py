"""
Variation Score 계산 모듈
페이지 복잡도를 측정해 OCR 필요 여부를 결정

OCR 판단 기준:
1. 텍스트만 충분히 추출된 페이지 (content > 100자): OCR 불필요
2. 이미지/그래픽이 많은 페이지: OCR 필요
3. 빈 페이지 또는 표지: OCR 불필요
"""

import fitz
from typing import Tuple, Optional


def calculate_variation_score(pymupdf_page: fitz.Page) -> float:
    """
    페이지의 variation score 계산
    - 이미지, 그래픽 요소의 다양성 측정 (텍스트 추출 품질과 독립적)
    
    반환값:
    - 0.0 ~ 1.0: 낮을수록 텍스트 중심, 높을수록 이미지/그래픽 중심
    """
    
    score = 0.0
    
    try:
        # 1. 이미지 개수 (가장 중요함)
        images = pymupdf_page.get_images()
        image_score = min(len(images) * 0.4, 0.6)  # 각 이미지마다 0.4, 최대 0.6
        
        # 2. 그래픽 요소 (선, 도형 등)
        drawing_elements = len(pymupdf_page.get_drawings())
        drawing_score = min(drawing_elements / 20, 0.3)  # 최대 0.3
        
        # 3. 텍스트 블록 (참고용, 복잡도만 측정)
        text_blocks = len(pymupdf_page.get_text("blocks"))
        text_score = min(text_blocks / 100, 0.1)  # 가중치 낮춤, 최대 0.1
        
        score = image_score + drawing_score + text_score
        score = min(score, 1.0)
        
    except Exception as e:
        return 0.5
    
    return score


def should_use_ocr(
    variation_score: float, 
    text_content_length: int,
    has_images: bool,
    threshold: float = 0.6
) -> bool:
    """
    OCR 필요 여부를 판단
    
    기준:
    1. 빈 페이지 (텍스트 < 10자) → OCR 불필요
    2. 의미있는 이미지가 있음 → OCR 필요 (도표, 마인드맵 등)
    3. 텍스트만 충분함 (> 200자) + 이미지 없음 → OCR 불필요
    4. 그 외 (텍스트 부족) → OCR 필요
    """
    # 1. 빈 페이지는 OCR 불필요
    if text_content_length < 10:
        return False
    
    # 2. 이미지가 있으면 OCR 필요 (큰 도표, 마인드맵 등)
    if has_images:
        return True
    
    # 3. 텍스트만 충분하면 OCR 불필요
    if text_content_length > 200:
        return False
    
    # 4. 그 외엔 OCR 필요 (텍스트 부족)
    return True
