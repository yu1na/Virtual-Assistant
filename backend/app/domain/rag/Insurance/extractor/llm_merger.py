"""
LLM Text Merger - Merge PyMuPDF + Vision OCR results using GPT-4

Intelligently combines:
1. Original PyMuPDF extracted text
2. Vision OCR detected text

Uses GPT-4 to select/merge the best version for optimal quality.
"""

import os
from typing import Tuple
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

from .utils import get_logger

logger = get_logger(__name__)


class LLMMerger:
    """
    Merge text extraction results using LLM intelligence.
    
    Handles:
    - Comparing original vs OCR text quality
    - Selecting the better version
    - Merging complementary parts
    - Preserving formatting
    """
    
    def __init__(self):
        """Initialize LLM merger with OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.logger = logger
    
    def merge_texts(self, original_text: str, ocr_text: str, has_images: bool) -> Tuple[str, bool]:
        """
        Use LLM to intelligently merge original and OCR text.
        
        Args:
            original_text: Text from PyMuPDF extraction
            ocr_text: Text from Vision OCR
            has_images: Whether page contains meaningful images
            
        Returns:
            Tuple of (merged_text, was_merged)
        """
        
        # Quick checks - if one is clearly better, use it
        orig_len = len(original_text.strip())
        ocr_len = len(ocr_text.strip())
        
        # If both are empty, return original
        if orig_len == 0 and ocr_len == 0:
            return original_text, False
        
        # If only one has content, use it
        if orig_len == 0:
            return ocr_text, True
        if ocr_len == 0:
            return original_text, False
        
        # If they're very similar, no need for LLM
        if original_text.strip() == ocr_text.strip():
            return original_text, False
        
        # Both have significant content - use LLM to merge
        try:
            return self._llm_merge(original_text, ocr_text, has_images)
        except Exception as e:
            self.logger.warning(f"LLM merge failed: {e}, using original text")
            return original_text, False
    
    def _llm_merge(self, original_text: str, ocr_text: str, has_images: bool) -> Tuple[str, bool]:
        """
        Call GPT-4 to intelligently merge texts.
        
        Args:
            original_text: PyMuPDF text
            ocr_text: Vision OCR text
            has_images: Whether page has images
            
        Returns:
            Tuple of (merged_text, was_merged)
        """
        
        prompt = f"""당신은 텍스트 추출 품질 전문가입니다.

두 가지 방법으로 추출한 PDF 페이지 텍스트가 있습니다:
1. 원본 텍스트 (PyMuPDF 자동 추출)
2. OCR 텍스트 (Vision AI로 이미지 인식)

당신의 역할: 두 텍스트를 분석하고 최고 품질의 결과물을 만들기

지침:
- 원본이 좋으면 원본 사용 (깨지지 않음, 포맷 유지)
- OCR이 좋으면 OCR 사용 (이미지에서 텍스트 더 잘 인식)
- 둘 다 좋으면 병합 (원본의 구조 + OCR의 누락된 부분)
- 개선되지 않으면 원본 유지

페이지 특성: 이미지 포함 = {has_images}

---
원본 텍스트:
{original_text[:2000]}

---
OCR 텍스트:
{ocr_text[:2000]}

---
최종 결과물을 반환하세요. 설명은 필요 없고 오직 최고 품질의 텍스트만 출력하세요."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=4000,
                temperature=0,  # Deterministic
            )
            
            merged = response.choices[0].message.content.strip()
            
            self.logger.debug(f"LLM merge: orig={len(original_text)}, ocr={len(ocr_text)}, merged={len(merged)}")
            return merged, True
            
        except Exception as e:
            self.logger.warning(f"LLM merge failed: {e}")
            return original_text, False
