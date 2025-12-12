from typing import List, Dict, Any
from pathlib import Path

from .page_loader import load_pages
from .text_normalizer import normalize_pages
from .semantic_segmentation import create_segments
from .embedding_refiner import refine_segments
from .sliding_window import create_chunks
from .file_manager import resolve_input_path, resolve_output_path, save_chunks, PROCEEDS_DIR
from .utils import get_logger

logger = get_logger(__name__)


def run_for_file(pdfname: str) -> Path:
    input_path = resolve_input_path(pdfname)
    if not input_path.exists():
        raise FileNotFoundError(f"Extractor output not found: {input_path}")
    pages = load_pages(input_path)
    normalized_pages = normalize_pages(pages)
    sem_segments = create_segments(normalized_pages)
    refined_segments = refine_segments(sem_segments)
    final_chunks = create_chunks(refined_segments)
    out_path = resolve_output_path(pdfname)
    save_chunks(out_path, final_chunks)
    logger.info(f"Chunks saved: {out_path} (count={len(final_chunks)})")
    return out_path


def run_for_all() -> List[Path]:
    if not PROCEEDS_DIR.exists():
        logger.info(f"No proceeds directory; nothing to chunk. Checked: {PROCEEDS_DIR}")
        return []
    outputs: List[Path] = []
    files = list(PROCEEDS_DIR.glob("*_extracted.json"))
    if not files:
        logger.info(f"No extracted JSON found in: {PROCEEDS_DIR}")
        return []
    for f in files:
        pdfname = f.stem.replace("_extracted", "")
        out = run_for_file(pdfname)
        outputs.append(out)
    return outputs