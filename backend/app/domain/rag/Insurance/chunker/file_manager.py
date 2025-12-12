from pathlib import Path
from typing import List, Dict, Any
import json

from .utils import ensure_dir

# Resolve to Insurance module directory (chunker/..)
BASE_DIR = Path(__file__).resolve().parents[1]
DOC_DIR = BASE_DIR / "documents"
PROCEEDS_DIR = DOC_DIR / "proceeds"


def resolve_input_path(pdfname: str) -> Path:
    return PROCEEDS_DIR / f"{pdfname}_extracted.json"


def resolve_output_path(pdfname: str) -> Path:
    ensure_dir(PROCEEDS_DIR)
    return PROCEEDS_DIR / f"chunks_{pdfname}.json"


def save_chunks(output_path: Path, json_data: List[Dict[str, Any]]) -> None:
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)