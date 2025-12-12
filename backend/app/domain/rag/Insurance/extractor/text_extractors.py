from typing import Tuple
import pdfplumber
import fitz

from .utils import clean_text


def extract_text_pymupdf(page: fitz.Page) -> str:
    try:
        return clean_text(page.get_text("text") or "")
    except Exception:
        return ""


def extract_text_plumber(pl_page: pdfplumber.page.Page) -> str:
    try:
        return clean_text(pl_page.extract_text() or "")
    except Exception:
        return ""


def merge_texts(pymupdf_text: str, plumber_text: str) -> str:
    if not pymupdf_text and not plumber_text:
        return ""
    if pymupdf_text and not plumber_text:
        return pymupdf_text
    if plumber_text and not pymupdf_text:
        return plumber_text
    # Prefer longer, then append unique parts
    if len(pymupdf_text) >= len(plumber_text):
        base, extra = pymupdf_text, plumber_text
    else:
        base, extra = plumber_text, pymupdf_text
    if extra in base:
        return base
    return (base + " \n" + extra).strip()
