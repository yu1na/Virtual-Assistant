from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractorConfig:
    MIN_TEXT_FOR_OCR: int = 1500
    DPI_FOR_VISION: int = 220
    HIGH_VARIANCE_THRESHOLD: float = 1500.0
    TABLE_MIN_ROWS: int = 1
    VISION_MODEL: str = "gpt-4o-mini"


config = ExtractorConfig()
