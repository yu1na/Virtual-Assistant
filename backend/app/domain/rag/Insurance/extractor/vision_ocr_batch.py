"""
Vision OCR Batch Processor with LLM Merging

Performs Vision OCR on previously extracted pages in batches.
- Read existing extraction JSON
- Process only pages marked with use_ocr=True
- Extract tables with pdfplumber
- Use LLM to intelligently merge PyMuPDF + OCR results
- Save updated file
"""

import json
import fitz
import pdfplumber
import os
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from .vision_ocr_handler import VisionOCRHandler
from .llm_merger import LLMMerger
from .table_parser import parse_table_to_markdown
from .utils import get_logger

logger = get_logger(__name__)


class VisionOCRBatchProcessor:
    """
    Process Vision OCR on pages marked for OCR in batches.
    
    Workflow:
    1. Load extracted JSON
    2. Identify pages needing OCR (use_ocr=True)
    3. Process in parallel with Vision API
    4. Use LLM to intelligently merge PyMuPDF + OCR results
    5. Save updated file
    """
    
    def __init__(self, max_workers: int = 2, use_llm_merge: bool = True):
        """
        Initialize batch processor.
        
        Args:
            max_workers: Number of parallel Vision API calls (default 2 to avoid rate limiting)
            use_llm_merge: Whether to use LLM to merge text results (default True)
        """
        self.handler = VisionOCRHandler()
        self.merger = LLMMerger() if use_llm_merge else None
        self.max_workers = max_workers
        self.use_llm_merge = use_llm_merge
        self.logger = logger
    
    def load_extraction(self, json_path: str) -> Dict:
        """Load previously extracted data"""
        try:
            with open(json_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load extraction: {e}")
            return None
    
    def process_page_ocr(self, pdf_path: str, page_data: Dict) -> Dict:
        """
        Process single page with Vision OCR and LLM merging.
        
        Args:
            pdf_path: Path to PDF file
            page_data: Page dict from extraction
            
        Returns:
            Updated page dict with ocr_performed and merged content
        """
        try:
            page_num = page_data['page'] - 1  # Convert to 0-indexed
            original_text = page_data['content']
            has_images = page_data.get('has_images', False)
            
            # Open PDF and get page
            doc = fitz.open(pdf_path)
            pymupdf_page = doc[page_num]
            
            # Step 1: Perform Vision OCR
            ocr_text, ocr_performed = self.handler.process_page_with_ocr(
                pymupdf_page,
                original_text,
                has_images
            )
            
            doc.close()
            
            # Step 2: Use LLM to intelligently merge if OCR was performed
            if ocr_performed and self.use_llm_merge and self.merger:
                try:
                    merged_text, was_merged = self.merger.merge_texts(
                        original_text,
                        ocr_text,
                        has_images
                    )
                    
                    if was_merged:
                        page_data['content'] = merged_text
                        page_data['ocr_performed'] = True
                        page_data['llm_merged'] = True
                        self.logger.info(f"✅ Page {page_data['page']}: Vision OCR + LLM merged")
                    else:
                        page_data['content'] = ocr_text
                        page_data['ocr_performed'] = True
                        page_data['llm_merged'] = False
                        self.logger.info(f"✅ Page {page_data['page']}: Vision OCR completed (no merge needed)")
                        
                except Exception as e:
                    self.logger.warning(f"⚠️  Page {page_data['page']}: LLM merge failed, using OCR result: {e}")
                    page_data['content'] = ocr_text
                    page_data['ocr_performed'] = True
                    page_data['llm_merged'] = False
            else:
                page_data['ocr_performed'] = ocr_performed
                page_data['llm_merged'] = False
                if ocr_performed:
                    page_data['content'] = ocr_text
                    self.logger.info(f"✅ Page {page_data['page']}: Vision OCR completed")
                else:
                    self.logger.warning(f"⚠️  Page {page_data['page']}: OCR failed, keeping original")
            
            return page_data
            
        except Exception as e:
            self.logger.error(f"❌ Page {page_data['page']}: {e}")
            page_data['ocr_performed'] = False
            page_data['llm_merged'] = False
            return page_data
    
    def process_batch(self, pdf_path: str, json_path: str) -> bool:
        """
        Process all pages marked for OCR in batches.
        
        Args:
            pdf_path: Path to PDF file
            json_path: Path to extraction JSON
            
        Returns:
            True if successful
        """
        try:
            # Load existing extraction
            data = self.load_extraction(json_path)
            if not data:
                return False
            
            # Find pages needing OCR
            ocr_pages = [p for p in data['pages'] if p.get('use_ocr', False) and not p.get('ocr_performed', False)]
            
            if not ocr_pages:
                self.logger.info("✅ No pages need OCR processing")
                return True
            
            self.logger.info(f"🔄 Processing {len(ocr_pages)} pages with Vision OCR...")
            self.logger.info(f"⚠️  Rate limit: max {self.max_workers} parallel requests")
            
            # Process in parallel with progress bar
            processed_pages = {}
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(self.process_page_ocr, pdf_path, page): page['page']
                    for page in ocr_pages
                }
                
                # Collect results as they complete with progress bar
                with tqdm(total=len(futures), desc="Vision OCR Progress", unit="pages") as pbar:
                    for future in as_completed(futures):
                        try:
                            updated_page = future.result()
                            processed_pages[updated_page['page']] = updated_page
                            pbar.update(1)
                        except Exception as e:
                            page_num = futures[future]
                            self.logger.error(f"Failed to process page {page_num}: {e}")
                            pbar.update(1)

            # Update original data with processed pages
            for i, page in enumerate(data['pages']):
                if page['page'] in processed_pages:
                    data['pages'][i] = processed_pages[page['page']]
            
            # Save updated extraction
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Statistics
            performed = sum(1 for p in data['pages'] if p.get('ocr_performed', False))
            self.logger.info(f"\n✅ Vision OCR batch complete!")
            self.logger.info(f"   OCR performed: {performed}/{len(ocr_pages)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")
            return False
