"""
Vision OCR Handler - OpenAI GPT-4 Vision API Integration

Performs OCR on PDF pages that contain images or insufficient text.
Uses GPT-4 Vision for superior text recognition and understanding.
Merges OCR results with existing text extraction.
"""

import base64
import io
import os
import fitz
from typing import Optional
from openai import OpenAI

from .utils import get_logger

logger = get_logger(__name__)


class VisionOCRHandler:
    """
    Handle Vision API calls for OCR using GPT-4 Vision.
    
    Responsibilities:
    - Extract page images as PNG
    - Call OpenAI GPT-4 Vision API
    - Parse OCR results
    - Merge with existing text content
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Vision OCR Handler.
        
        Args:
            api_key: OpenAI API key or None to use OPENAI_API_KEY env var
        """
        # Use provided key or get from environment
        key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=key)
        self.logger = logger
        self.model = "gpt-4o"  # Use GPT-4o for best vision quality
    
    def extract_page_image(self, pymupdf_page) -> Optional[str]:
        """
        Extract page as base64 PNG image.
        
        Args:
            pymupdf_page: PyMuPDF page object
            
        Returns:
            Base64 encoded PNG string or None if extraction fails
        """
        try:
            # Render page to PNG image
            pix = pymupdf_page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for quality
            png_bytes = pix.tobytes("png")
            
            # Encode to base64
            b64_image = base64.b64encode(png_bytes).decode("utf-8")
            return b64_image
            
        except Exception as e:
            self.logger.warning(f"Failed to extract page image: {e}")
            return None
    
    def call_vision_api(self, base64_image: str) -> str:
        """
        Call OpenAI GPT-4 Vision API for text detection.
        
        Args:
            base64_image: Base64 encoded PNG image
            
        Returns:
            Detected text from image
        """
        try:
            # Call GPT-4 Vision API with optimized prompt
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4o for best vision quality
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """이 PDF 페이지 이미지에서 모든 텍스트를 정확하고 완전하게 추출해주세요.

요구사항:
1. 모든 텍스트를 빠짐없이 추출
2. 원본 형식과 레이아웃 유지 (줄바꿈, 들여쓰기 포함)
3. 표나 목록이 있으면 구조 그대로 유지
4. 그림이나 이미지 설명은 [이미지: ...] 형식으로 표시
5. 읽기 어려운 부분은 최선을 다해 추측해 표시

추출한 텍스트만 반환하세요. 설명이나 마크다운 포맷은 불필요합니다."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4000,
            )
            
            # Extract text from response
            detected_text = response.choices[0].message.content
            
            self.logger.debug(f"Vision API returned {len(detected_text)} characters")
            return detected_text
            
        except Exception as e:
            self.logger.warning(f"Vision API call failed: {e}")
            return ""
    
    def merge_content(self, original_text: str, ocr_text: str, has_images: bool) -> str:
        """
        Merge PyMuPDF extracted text with Vision OCR result.
        
        Strategy:
        - If original_text is good (>200 chars): mostly use original, append OCR if different
        - If original_text is poor (<200 chars): use OCR as primary
        - If has_images: prioritize OCR (better for image-heavy pages)
        
        Args:
            original_text: Text extracted by PyMuPDF
            ocr_text: Text detected by Vision API
            has_images: Whether page contains meaningful images
            
        Returns:
            Merged content as string
        """
        try:
            original_len = len(original_text.strip())
            ocr_len = len(ocr_text.strip())
            
            # Strategy 1: Page has images - OCR might be more accurate
            if has_images:
                if ocr_len > original_len * 0.8:  # OCR got most of the text
                    # Use OCR as primary, append any unique original text
                    merged = ocr_text
                    if original_text and original_text not in ocr_text:
                        merged += f"\n\n[Original text extraction]:\n{original_text}"
                    return merged
            
            # Strategy 2: Original text is good (>200 chars)
            if original_len >= 200:
                # Original is sufficient, append OCR only if it adds significant content
                if ocr_len > original_len * 1.1:
                    return f"{original_text}\n\n[Additional OCR content]:\n{ocr_text}"
                return original_text
            
            # Strategy 3: Original text is poor (<200 chars)
            if ocr_len > 0:
                # Use OCR as primary
                if original_text:
                    return f"{ocr_text}\n\n[Original extraction]:\n{original_text}"
                return ocr_text
            
            # Strategy 4: Both are poor - return original
            return original_text
            
        except Exception as e:
            self.logger.warning(f"Merge failed: {e}")
            return original_text
    
    def process_page_with_ocr(
        self,
        pymupdf_page,
        original_text: str,
        has_images: bool
    ) -> tuple[str, bool]:
        """
        Process page with Vision OCR if needed.
        
        Args:
            pymupdf_page: PyMuPDF page object
            original_text: Already extracted text
            has_images: Whether page has meaningful images
            
        Returns:
            Tuple of (merged_content, ocr_was_performed)
        """
        try:
            # Step 1: Extract page as image
            base64_image = self.extract_page_image(pymupdf_page)
            if not base64_image:
                self.logger.debug("Could not extract page image, skipping OCR")
                return original_text, False
            
            # Step 2: Call Vision API
            ocr_text = self.call_vision_api(base64_image)
            if not ocr_text:
                self.logger.debug("Vision API returned no text")
                return original_text, False
            
            # Step 3: Merge results
            merged = self.merge_content(original_text, ocr_text, has_images)
            
            self.logger.debug(f"OCR processed: original={len(original_text)}, ocr={len(ocr_text)}, merged={len(merged)}")
            return merged, True
            
        except Exception as e:
            self.logger.warning(f"OCR processing failed: {e}")
            return original_text, False
