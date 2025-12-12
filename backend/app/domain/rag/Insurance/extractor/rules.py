from typing import Tuple

from .config import config


def is_empty_page(raw_text: str) -> bool:
    return not raw_text or not raw_text.strip()


def detect_table(tables_md_len: int) -> bool:
    return tables_md_len >= config.TABLE_MIN_ROWS


def should_use_vision_ocr(raw_text_len: int, variance: float) -> bool:
    return raw_text_len <= config.MIN_TEXT_FOR_OCR and variance >= config.HIGH_VARIANCE_THRESHOLD


def get_text_mode(raw_text_len: int, tables_detected: bool, variance: float) -> str:
    if raw_text_len == 0 and not tables_detected:
        return "empty"
    if tables_detected:
        return "table"
    if should_use_vision_ocr(raw_text_len, variance):
        return "vision"
    return "text"
