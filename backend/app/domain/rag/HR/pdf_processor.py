"""
PDF 처리 모듈

PyMuPDF와 pdfplumber를 조합하여 PDF에서 텍스트, 표, 이미지를 추출합니다.
"""

import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import io
import base64
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from .config import rag_config
from .schemas import (
    ProcessedDocument,
    ProcessedContent,
    ContentType,
    DocumentMetadata,
    TableData
)
from .utils import get_logger

logger = get_logger(__name__)


class PDFProcessor:
    """PDF 문서 처리기"""
    
    def __init__(self):
        self.config = rag_config
    
    def save_chunks_with_embeddings(self, doc: ProcessedDocument, chunks: List[Any]):
        """
        청크와 임베딩을 함께 저장
        
        Args:
            doc: 처리된 문서
            chunks: DocumentChunk 리스트 (임베딩 포함)
        """
        chunks_data = []
        for chunk in chunks:
            chunk_dict = {
                "text": chunk.text,
                "metadata": chunk.metadata.model_dump(),
                "embedding": chunk.embedding if hasattr(chunk, 'embedding') else None
            }
            
            # 번역 텍스트 추가
            if chunk.metadata.translated_text:
                chunk_dict["translated_text"] = chunk.metadata.translated_text
            
            chunks_data.append(chunk_dict)
        
        # 문서와 함께 저장
        self._save_processed_document(doc, chunks_with_embeddings=chunks_data)
        
    def process_pdf(self, pdf_path: str) -> ProcessedDocument:
        """
        PDF 파일을 처리하여 텍스트, 표, 이미지를 추출합니다.
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            ProcessedDocument: 처리된 문서 객체
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        logger.info(f"PDF 처리 시작: {pdf_path}")
        
        contents: List[ProcessedContent] = []
        
        # PyMuPDF로 문서 열기
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # pdfplumber로도 열기 (표 추출용)
        with pdfplumber.open(pdf_path) as pdf:
            for page_num in range(total_pages):
                logger.info(f"페이지 {page_num + 1}/{total_pages} 처리 중...")
                
                # PyMuPDF 페이지
                fitz_page = doc[page_num]
                # pdfplumber 페이지
                plumber_page = pdf.pages[page_num]
                
                # 1. 표 추출 (pdfplumber 사용)
                tables = self._extract_tables(plumber_page, page_num)
                contents.extend(tables)
                
                # 2. 이미지/차트 추출 (PyMuPDF 사용)
                images = self._extract_images(fitz_page, page_num, pdf_path.stem)
                contents.extend(images)
                
                # 3. 텍스트 추출 (PyMuPDF 사용)
                text_content = self._extract_text(fitz_page, page_num, pdf_path.stem)
                if text_content:
                    contents.append(text_content)
        
        doc.close()
        
        processed_doc = ProcessedDocument(
            filename=pdf_path.name,
            total_pages=total_pages,
            contents=contents,
            file_path=str(pdf_path)
        )
        
        # 처리 결과를 JSON으로 저장
        self._save_processed_document(processed_doc)
        
        logger.info(f"PDF 처리 완료: {len(contents)}개 컨텐츠 추출")
        return processed_doc
    
    def _extract_text(
        self, 
        page: fitz.Page, 
        page_num: int, 
        filename: str
    ) -> Optional[ProcessedContent]:
        """페이지에서 텍스트 추출"""
        text = page.get_text()
        
        if not text or len(text.strip()) < 10:
            return None
        
        metadata = DocumentMetadata(
            filename=filename,
            page_number=page_num + 1,
            content_type=ContentType.TEXT
        )
        
        return ProcessedContent(
            content_type=ContentType.TEXT,
            text=text.strip(),
            metadata=metadata
        )
    
    def _extract_tables(
        self, 
        page: Any, 
        page_num: int
    ) -> List[ProcessedContent]:
        """페이지에서 표 추출"""
        tables_content = []
        
        try:
            tables = page.extract_tables()
            
            if not tables:
                return []
            
            for table_idx, table in enumerate(tables):
                if not table or len(table) < self.config.TABLE_MIN_ROWS:
                    continue
                
                # 표를 JSON 구조로 변환
                headers = table[0] if table else []
                rows = table[1:] if len(table) > 1 else []
                
                # 빈 행 제거
                rows = [row for row in rows if any(cell for cell in row if cell)]
                
                if len(rows) < 1:
                    continue
                
                table_data = TableData(
                    headers=[str(h) if h else "" for h in headers],
                    rows=[[str(cell) if cell else "" for cell in row] for row in rows]
                )
                
                # 표를 마크다운 텍스트로 변환
                markdown_table = self._table_to_markdown(table_data)
                
                metadata = DocumentMetadata(
                    filename="",
                    page_number=page_num + 1,
                    content_type=ContentType.TABLE
                )
                
                content = ProcessedContent(
                    content_type=ContentType.TABLE,
                    text=markdown_table,
                    metadata=metadata,
                    table_data=table_data
                )
                
                tables_content.append(content)
                logger.info(f"표 추출: 페이지 {page_num + 1}, 표 {table_idx + 1}")
                
        except Exception as e:
            logger.warning(f"표 추출 중 오류 (페이지 {page_num + 1}): {e}")
        
        return tables_content
    
    def _table_to_markdown(self, table_data: TableData) -> str:
        """표 데이터를 마크다운 형식으로 변환"""
        lines = []
        
        # 헤더
        if table_data.headers:
            lines.append("| " + " | ".join(table_data.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(table_data.headers)) + " |")
        
        # 행
        for row in table_data.rows:
            lines.append("| " + " | ".join(row) + " |")
        
        return "\n".join(lines)
    
    def _extract_images(
        self, 
        page: fitz.Page, 
        page_num: int, 
        filename: str
    ) -> List[ProcessedContent]:
        """페이지에서 이미지 추출 및 GPT-4 Vision으로 설명 생성"""
        images_content = []
        
        try:
            image_list = page.get_images()
            
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = page.parent.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # 이미지를 PIL Image로 변환
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # 이미지 크기 조정
                    if image.size[0] > self.config.MAX_IMAGE_SIZE[0] or \
                       image.size[1] > self.config.MAX_IMAGE_SIZE[1]:
                        image.thumbnail(self.config.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
                    
                    # GPT-4 Vision으로 이미지 설명 생성
                    description = self._describe_image_with_gpt4(image)
                    
                    metadata = DocumentMetadata(
                        filename=filename,
                        page_number=page_num + 1,
                        content_type=ContentType.IMAGE
                    )
                    
                    content = ProcessedContent(
                        content_type=ContentType.IMAGE,
                        text=description,
                        metadata=metadata
                    )
                    
                    images_content.append(content)
                    logger.info(f"이미지 처리 완료: 페이지 {page_num + 1}, 이미지 {img_idx + 1}")
                    
                except Exception as e:
                    logger.warning(f"이미지 추출 중 오류 (페이지 {page_num + 1}, 이미지 {img_idx + 1}): {e}")
                    
        except Exception as e:
            logger.warning(f"이미지 리스트 가져오기 오류 (페이지 {page_num + 1}): {e}")
        
        return images_content
    
    def _describe_image_with_gpt4(self, image: Image.Image) -> str:
        """GPT-4 Vision API를 사용하여 이미지 설명 생성"""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.config.OPENAI_API_KEY)
            
            # 이미지를 base64로 인코딩
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            response = client.chat.completions.create(
                model=self.config.OPENAI_VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "이 이미지를 상세히 설명해주세요. 특히 차트, 그래프, 다이어그램인 경우 데이터와 트렌드를 설명해주세요. 한국어로 답변해주세요."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            description = response.choices[0].message.content
            return f"[이미지 설명]\n{description}"
            
        except Exception as e:
            logger.error(f"GPT-4 Vision API 호출 오류: {e}")
            return "[이미지 설명을 생성할 수 없습니다]"
    
    def process_text(self, text_path: str) -> ProcessedDocument:
        """
        텍스트 파일(TXT, MD)을 처리합니다.
        
        Args:
            text_path: 텍스트 파일 경로
            
        Returns:
            ProcessedDocument: 처리된 문서 객체
        """
        text_path = Path(text_path)
        if not text_path.exists():
            raise FileNotFoundError(f"텍스트 파일을 찾을 수 없습니다: {text_path}")
        
        logger.info(f"텍스트 파일 처리 시작: {text_path}")
        
        # 파일 읽기
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # UTF-8로 읽을 수 없으면 다른 인코딩 시도
            with open(text_path, 'r', encoding='cp949') as f:
                content = f.read()
        
        if not content or len(content.strip()) < 10:
            raise ValueError(f"텍스트 파일이 비어있거나 너무 짧습니다: {text_path}")
        
        # 텍스트를 ProcessedContent로 변환
        metadata = DocumentMetadata(
            filename=text_path.name,
            page_number=1,
            content_type=ContentType.TEXT,
            total_pages=1
        )
        
        processed_content = ProcessedContent(
            content_type=ContentType.TEXT,
            text=content.strip(),
            metadata=metadata
        )
        
        processed_doc = ProcessedDocument(
            filename=text_path.name,
            total_pages=1,
            contents=[processed_content],
            file_path=str(text_path)
        )
        
        # 처리 결과를 JSON으로 저장
        self._save_processed_document(processed_doc)
        
        logger.info(f"텍스트 파일 처리 완료: {len(content)} 문자")
        return processed_doc
    
    def _save_processed_document(self, doc: ProcessedDocument, chunks_with_embeddings: Optional[List[Dict]] = None):
        """
        처리된 문서를 JSON 파일로 저장 (임베딩 포함)
        
        Args:
            doc: 처리된 문서
            chunks_with_embeddings: 임베딩이 포함된 청크 리스트
        """
        try:
            output_path = self.config.PROCESSED_DIR / f"{Path(doc.filename).stem}.json"
            
            # file_path를 internal_docs 경로로 정규화
            doc_dict = doc.model_dump()
            if doc_dict.get('file_path'):
                # data 경로를 internal_docs로 변경
                file_path = doc_dict['file_path']
                if 'data' in file_path and 'internal_docs' not in file_path:
                    file_path = file_path.replace('data', 'internal_docs')
                    doc_dict['file_path'] = file_path
            
            # 임베딩 정보 추가
            if chunks_with_embeddings:
                doc_dict['chunks_with_embeddings'] = chunks_with_embeddings
                logger.info(f"임베딩 포함하여 저장: {len(chunks_with_embeddings)}개 청크")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(doc_dict, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"처리된 문서 저장: {output_path}")
            
        except Exception as e:
            logger.error(f"문서 저장 중 오류: {e}")
    
    @staticmethod
    def update_existing_json_paths(processed_dir: Path):
        """
        기존 처리된 JSON 파일들의 file_path를 data에서 internal_docs로 업데이트
        
        Args:
            processed_dir: 처리된 JSON 파일들이 있는 디렉토리
        """
        if not processed_dir.exists():
            logger.warning(f"디렉토리가 존재하지 않습니다: {processed_dir}")
            return
        
        json_files = list(processed_dir.glob("*.json"))
        updated_count = 0
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # file_path 업데이트
                if 'file_path' in data and 'data' in data['file_path']:
                    old_path = data['file_path']
                    new_path = old_path.replace('data', 'internal_docs')
                    data['file_path'] = new_path
                    
                    # 파일 저장
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                    
                    updated_count += 1
                    logger.info(f"업데이트 완료: {json_file.name}")
                    
            except Exception as e:
                logger.error(f"JSON 파일 업데이트 중 오류 ({json_file.name}): {e}")
        
        logger.info(f"총 {updated_count}개 JSON 파일 업데이트 완료")
        return updated_count

