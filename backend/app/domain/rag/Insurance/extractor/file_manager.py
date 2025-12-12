from pathlib import Path
from typing import List, Any
import json

from .utils import ensure_dir

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "documents"
PROCEEDS_DIR = DOCS_DIR / "proceeds"
OUTPUT_DIR = BASE_DIR / "documents" / "proceeds"


def resolve_input_pdfs() -> List[Path]:
    pdfs: List[Path] = []
    for p in [DOCS_DIR, PROCEEDS_DIR]:
        if p.exists():
            pdfs.extend(sorted(p.glob("**/*.pdf")))
    return pdfs


def resolve_output_path(pdf_filename: str) -> Path:
    ensure_dir(OUTPUT_DIR)
    stem = Path(pdf_filename).stem
    return OUTPUT_DIR / f"{stem}_extracted.json"


def save_json(output_path: Path, data: Any) -> None:
    ensure_dir(output_path.parent)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
