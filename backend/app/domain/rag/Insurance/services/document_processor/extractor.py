"""
PDF 추출 서비스

레거시 `extractor/` 폴더의 PDF 추출 로직을 통합하여
서비스 레이어용으로 정리한 구현입니다.
"""
import base64
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

import fitz
import numpy as np
import pdfplumber
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ...core.config import config
from ...core.utils import get_logger

logger = get_logger(__name__)

# Constants
DPI_FOR_VISION = 120
DPI_FOR_ANALYSIS = 50
MIN_IMAGE_VARIANCE = 200  # 낮춤: 도표/차트가 있는 페이지 포함하기 위해
MIN_IMAGE_AREA_RATIO = 0.10  # 사용 안 함 (bbox 계산 신뢰도 낮음)
VISION_TEXT_THRESHOLD = 300  # 텍스트 길이가 이 값보다 짧으면 Vision 사용 고려

# OCR 실패 지표
OCR_FAILURE_INDICATORS = [
    "sorry", "unable", "cannot", "can't", "failed",
    "죄송", "불가능", "처리할 수 없"
]

# 프롬프트
VISION_OCR_PROMPT = """다음 이미지를 Markdown 형식으로 변환하세요.
- 표는 Markdown 테이블로 변환
- 제목은 ##, ### 등으로 표시
- 단락은 줄바꿈으로 구분"""

LLM_MERGE_PROMPT_TEMPLATE = """두 개의 텍스트를 병합하여 하나의 일관된 문서로 만드세요.

[PDF 텍스트]
{raw_text}

[Vision OCR 결과]
{vision_result}

병합 규칙:
1. 중복 제거
2. 표와 이미지 정보는 Vision OCR 우선
3. 일반 텍스트는 PDF 텍스트 우선
4. Markdown 형식 유지"""


# 데이터 모델
@dataclass
class BBox:
    """테이블/이미지 경계 상자"""
    x0: float
    y0: float
    x1: float
    y1: float
    
    def to_dict(self) -> dict:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass
class PageAnalysis:
    """페이지 분석 결과 (Vision/LLM 호출 없음)"""
    page_num: int
    raw_text: str
    has_tables: bool
    has_images: bool
    table_bboxes: List[BBox]
    image_bboxes: List[BBox]
    variance: Optional[float] = None
    image_area_ratio: Optional[float] = None
    meaningful_image: Optional[bool] = None
    tables_data: List[List[List[str]]] = field(default_factory=list)
    
    def is_empty(self) -> bool:
        return not self.raw_text.strip() and not self.has_tables and not self.has_images


@dataclass
class PageResult:
    """최종 페이지 처리 결과 (Vision/LLM 포함)"""
    page: int
    mode: Literal["empty", "text", "vision", "vision-fallback", "error"]
    content: str
    has_tables: bool
    has_images: bool
    table_bboxes: List[BBox]
    image_bboxes: List[BBox]
    
    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "mode": self.mode,
            "content": self.content,
            "has_tables": self.has_tables,
            "has_images": self.has_images,
            "table_bboxes": [bbox.to_dict() for bbox in self.table_bboxes],
            "image_bboxes": [bbox.to_dict() for bbox in self.image_bboxes]
        }


class PDFExtractor:
    """
    프로덕션급 PDF 추출 서비스
    
    PDF 텍스트 추출, 테이블 감지, 이미지 분석,
    Vision API 통합 및 폴백 전략을 처리합니다.
    """
    
    def __init__(self, openai_client: Optional[OpenAI] = None):
        """
        추출기 초기화
        
        Args:
            openai_client: Vision API용 OpenAI 클라이언트 (선택사항)
        """
        self.client = openai_client or OpenAI(api_key=config.openai_api_key)
    
    # ===== 저수준 유틸리티 =====
    
    @staticmethod
    def _page_to_jpeg_data_url(page: fitz.Page, dpi: int = DPI_FOR_VISION) -> str:
        """PDF 페이지를 JPEG base64 데이터 URL로 변환"""
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("jpeg")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"
    
    @staticmethod
    def _page_to_gray_array(page: fitz.Page, dpi: int = DPI_FOR_ANALYSIS) -> np.ndarray:
        """페이지를 그레이스케일 numpy 배열로 변환"""
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8)
        img_array = img_array.reshape((pix.height, pix.width, pix.n))
        return np.mean(img_array, axis=2).astype(np.uint8)
    
    @staticmethod
    def _detect_tables(pdfplumber_page: pdfplumber.page.Page) -> Tuple[List[List[List[str]]], List[BBox]]:
        """페이지에서 테이블 감지 (빈 테이블 필터링 포함)"""
        try:
            tables_data = pdfplumber_page.extract_tables() or []
            detected_tables = pdfplumber_page.find_tables() or []
            
            # 실제 내용이 있는 테이블만 필터링
            valid_tables = []
            valid_bboxes = []
            
            for table, table_obj in zip(tables_data, detected_tables):
                # 빈 테이블 체크: 최소 2행 이상 + 실제 내용이 있는 셀 존재
                if table and len(table) >= 2:
                    has_content = False
                    content_cells = 0
                    
                    for row in table:
                        if row:
                            for cell in row:
                                if cell and str(cell).strip():
                                    content_cells += 1
                                    if content_cells >= 3:  # 최소 3개 이상의 내용 있는 셀
                                        has_content = True
                                        break
                        if has_content:
                            break
                    
                    if has_content:
                        valid_tables.append(table)
                        valid_bboxes.append(
                            BBox(x0=table_obj.bbox[0], y0=table_obj.bbox[1], 
                                 x1=table_obj.bbox[2], y1=table_obj.bbox[3])
                        )
            
            return valid_tables, valid_bboxes
        except Exception as e:
            logger.warning(f"Table detection failed: {e}")
            return [], []
    
    @staticmethod
    def _detect_images(page: fitz.Page) -> List[BBox]:
        """페이지에서 이미지 감지"""
        try:
            image_bboxes = []
            for img in page.get_images():
                xref = img[0]
                for rect in page.get_image_rects(xref):
                    image_bboxes.append(BBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1))
            return image_bboxes
        except Exception as e:
            logger.warning(f"Image detection failed: {e}")
            return []
    
    @staticmethod
    def _calculate_image_variance(page: fitz.Page) -> float:
        """의미 있는 이미지 감지를 위한 그레이스케일 분산 계산"""
        try:
            gray = PDFExtractor._page_to_gray_array(page, DPI_FOR_ANALYSIS)
            return float(gray.var())
        except Exception as e:
            logger.warning(f"Variance calculation failed: {e}")
            return float('inf')
    
    @staticmethod
    def _calculate_image_area_ratio(page: fitz.Page, image_bboxes: List[BBox]) -> float:
        """이미지 면적 비율 계산 (전체 이미지 면적 / 페이지 면적)"""
        if not image_bboxes:
            return 0.0
        try:
            page_rect = page.rect
            page_area = page_rect.width * page_rect.height
            if page_area == 0:
                return 0.0
            total_image_area = sum((bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0) for bbox in image_bboxes)
            return total_image_area / page_area
        except Exception:
            return 0.0
    
    @staticmethod
    def _tables_to_markdown(tables: List[List[List[str]]]) -> str:
        """테이블을 Markdown 형식으로 변환"""
        md_list = []
        for table in tables:
            if not table:
                continue
            table = [[cell if cell is not None else "" for cell in row] for row in table]
            if not table:
                continue
            md = "| " + " | ".join(table[0]) + " |\n"
            md += "| " + " | ".join("---" for _ in table[0]) + " |\n"
            for row in table[1:]:
                md += "| " + " | ".join(row) + " |\n"
            md_list.append(md)
        return "\n\n".join(md_list)
    
    # ===== Vision/LLM 통합 =====
    
    @staticmethod
    def _is_vision_failure(text: str) -> bool:
        """Vision OCR 실패 여부 확인"""
        if not text or len(text.strip()) < 10:
            return True
        text_lower = text.lower().strip()
        return any(indicator in text_lower for indicator in OCR_FAILURE_INDICATORS)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _vision_ocr(self, jpeg_data_url: str) -> str:
        """OCR을 위해 Vision API 호출 (재시도 포함)"""
        resp = self.client.chat.completions.create(
            model=config.llm_model,
            temperature=0,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": jpeg_data_url}}
                ]
            }]
        )
        result = resp.choices[0].message.content or ""
        logger.debug(f"Vision OCR: {len(result)} chars")
        return result
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def _merge_with_llm(self, raw_text: str, vision_result: str) -> str:
        """LLM을 사용하여 원본 텍스트와 Vision OCR 결과 병합"""
        prompt = LLM_MERGE_PROMPT_TEMPLATE.format(raw_text=raw_text, vision_result=vision_result)
        resp = self.client.chat.completions.create(
            model=config.llm_model,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        result = resp.choices[0].message.content or ""
        logger.debug(f"LLM merge: {len(result)} chars")
        return result
    
    # ===== 고수준 API =====
    
    def analyze_page(
        self,
        page: fitz.Page,
        pdfplumber_page: pdfplumber.page.Page,
        page_num: int
    ) -> PageAnalysis:
        """
        페이지 분석 (Vision/LLM 호출 없음)
        
        페이지에서 텍스트, 테이블, 이미지를 감지합니다.
        """
        # 원본 텍스트 추출
        try:
            raw_text = page.get_text("text") or ""
        except Exception as e:
            logger.warning(f"Page {page_num} text extraction failed: {e}")
            raw_text = ""
        
        # 테이블 감지
        tables_data, table_bboxes = self._detect_tables(pdfplumber_page)
        has_tables = len(tables_data) > 0
        
        # 이미지 감지
        image_bboxes = self._detect_images(page)
        has_images = len(image_bboxes) > 0
        
        # 이미지 메트릭 계산
        variance = None
        image_area_ratio = None
        meaningful_image = None
        if has_images:
            variance = self._calculate_image_variance(page)
            image_area_ratio = self._calculate_image_area_ratio(page, image_bboxes)
            # variance만으로 판단 (area_ratio는 bbox 계산 문제로 신뢰도 낮음)
            # 많은 이미지 요소가 있지만 bbox 면적이 제대로 계산되지 않는 경우가 많음
            meaningful_image = variance >= MIN_IMAGE_VARIANCE if variance is not None else False
        
        return PageAnalysis(
            page_num=page_num,
            raw_text=raw_text,
            has_tables=has_tables,
            has_images=has_images,
            table_bboxes=table_bboxes,
            image_bboxes=image_bboxes,
            variance=variance,
            image_area_ratio=image_area_ratio,
            meaningful_image=meaningful_image,
            tables_data=tables_data if has_tables else []
        )
    
    def process_page(self, page: fitz.Page, analysis: PageAnalysis) -> PageResult:
        """
        페이지 처리 - 컨텐츠 타입별 최적 도구 사용 (선택적 병합 전략)
        
        처리 규칙:
        1. 빈 페이지 → "empty" 모드
        2. 품질 좋은 테이블 → pdfplumber만 (구조화된 데이터)
        3. 복잡한 페이지 (차트/도표) → Vision OCR + 선택적 LLM 병합
           조건: 이미지 있음 AND (텍스트<300자 OR variance>1500)
           병합: 텍스트>50자이면 LLM 병합, 아니면 Vision만
        4. 텍스트 위주 → raw_text만
        
        폴백: Vision 실패시 raw_text 사용
        """
        # 빈 페이지
        if analysis.is_empty():
            return PageResult(
                page=analysis.page_num,
                mode="empty",
                content="",
                has_tables=False,
                has_images=False,
                table_bboxes=[],
                image_bboxes=[]
            )
        
        content = ""
        mode: Literal["text", "vision", "vision-fallback", "error"] = "text"
        
        # 우선순위 1: 품질 좋은 테이블 → pdfplumber만 사용
        if analysis.has_tables:
            mode = "text"  # pdfplumber 사용이므로 text 모드
            tables_md = self._tables_to_markdown(analysis.tables_data)
            content = analysis.raw_text + "\n\n" + tables_md if analysis.raw_text.strip() else tables_md
        
        # 우선순위 2: 복잡한 페이지 (차트/도표) → Vision OCR + raw_text 하이브리드
        elif analysis.has_images:
            text_length = len(analysis.raw_text.strip())
            variance = analysis.variance or 0.0
            
            # 텍스트가 적거나(<VISION_TEXT_THRESHOLD) variance가 매우 높으면(>1500) Vision 처리
            run_vision = (text_length < VISION_TEXT_THRESHOLD or variance > 1500)
            
            if run_vision:
                mode = "vision"
                try:
                    jpeg_data_url = self._page_to_jpeg_data_url(page)
                    vision_markdown = self._vision_ocr(jpeg_data_url)
                    
                    if self._is_vision_failure(vision_markdown):
                        mode = "vision-fallback"
                        content = analysis.raw_text or ""
                    else:
                        # 선택적 병합: 텍스트가 충분하면 LLM 병합, 아니면 Vision만
                        if text_length > 50:
                            # LLM 병합으로 문맥 통합 (품질 우선)
                            content = self._merge_with_llm(analysis.raw_text, vision_markdown)
                        else:
                            # 텍스트가 거의 없으면 Vision 결과만 (비용 절감)
                            content = vision_markdown
                except Exception as e:
                    logger.error(f"Page {analysis.page_num} Vision OCR failed: {e}")
                    mode = "vision-fallback"
                    content = analysis.raw_text or ""
            else:
                mode = "text"
                content = analysis.raw_text
        
        # 우선순위 3: 텍스트 위주 → raw_text만 사용
        else:
            mode = "text"
            content = analysis.raw_text
        
        return PageResult(
            page=analysis.page_num,
            mode=mode,
            content=content,
            has_tables=analysis.has_tables,
            has_images=analysis.has_images,
            table_bboxes=analysis.table_bboxes,
            image_bboxes=analysis.image_bboxes
        )
    
    def extract_pdf(self, pdf_path: str, use_vision: bool = True) -> List[PageResult]:
        """
        전체 PDF 문서 추출
        
        Args:
            pdf_path: PDF 파일 경로
            use_vision: Vision API 사용 여부 (기본값: True)
            
        Returns:
            각 페이지의 PageResult 리스트
        """
        results = []
        
        # 통계 추적
        stats = {
            "text": 0,           # 텍스트만
            "vision": 0,         # Vision OCR (이미지)
            "vision-fallback": 0,  # Vision OCR (테이블)
            "empty": 0,          # 빈 페이지
            "error": 0           # 에러
        }
        
        with fitz.open(pdf_path) as pdf_doc, pdfplumber.open(pdf_path) as plumber_doc:
            total_pages = len(pdf_doc)
            logger.info(f"PDF 추출 시작: {pdf_path} ({total_pages}페이지, vision={use_vision})")
            
            for page_num, (pymupdf_page, plumber_page) in enumerate(zip(pdf_doc, plumber_doc.pages), start=1):
                # 페이지 분석
                analysis = self.analyze_page(pymupdf_page, plumber_page, page_num)
                
                # 페이지 처리
                if use_vision:
                    result = self.process_page(pymupdf_page, analysis)
                else:
                    # 텍스트 전용 모드
                    result = PageResult(
                        page=page_num,
                        mode="text",
                        content=analysis.raw_text,
                        has_tables=analysis.has_tables,
                        has_images=analysis.has_images,
                        table_bboxes=analysis.table_bboxes,
                        image_bboxes=analysis.image_bboxes
                    )
                
                results.append(result)
                stats[result.mode] += 1
        
        # 통계 출력
        logger.info(f"=== PDF 추출 완료: {total_pages}페이지 ===")
        logger.info(f"📄 텍스트만: {stats['text']}페이지 ({stats['text']/total_pages*100:.1f}%)")
        logger.info(f"🖼️  Vision(이미지): {stats['vision']}페이지 ({stats['vision']/total_pages*100:.1f}%)")
        logger.info(f"📊 Vision(테이블): {stats['vision-fallback']}페이지 ({stats['vision-fallback']/total_pages*100:.1f}%)")
        logger.info(f"⚪ 빈 페이지: {stats['empty']}페이지 ({stats['empty']/total_pages*100:.1f}%)")
        if stats['error'] > 0:
            logger.warning(f"❌ 에러: {stats['error']}페이지 ({stats['error']/total_pages*100:.1f}%)")
        
        return results
