from typing import Dict
from typing import Dict

from .utils import get_logger
from .text_extractors import extract_text_pymupdf, extract_text_plumber, merge_texts
from .table_parser import parse_table_to_markdown

logger = get_logger(__name__)


def process_page(pymupdf_page, plumber_page, api_key: str | None) -> Dict:
    """Process a page with robust error handling and text-only mode.
    - Avoid any rendering/vision to prevent PyMuPDF color errors
    - Gracefully skip problematic extract paths
    """
    content = ""
    # Try fast PyMuPDF text
    try:
        content = extract_text_pymupdf(pymupdf_page) or ""
    except Exception as e:
        logger.warning(f"PyMuPDF text extraction failed: {e}")
        content = ""

    # Complement with pdfplumber text
    try:
        plumber_text = extract_text_plumber(plumber_page) or ""
        content = merge_texts(content, plumber_text)
    except Exception as e:
        logger.info(f"pdfplumber text fallback skipped: {e}")

    # Tables via pdfplumber only; wrap errors
    tables_md = []
    try:
        tables_raw = plumber_page.extract_tables() or []
        tables_md = [parse_table_to_markdown(t) for t in tables_raw if t]
    except Exception as e:
        logger.info(f"table parse skipped: {e}")

    has_tables = len(tables_md) > 0

    # Force mode to text to avoid OCR/image rendering that may hang
    mode = "text"

    return {
        "mode": mode,
        "content": content,
        "has_tables": has_tables,
        "tables_markdown": tables_md,
    }
