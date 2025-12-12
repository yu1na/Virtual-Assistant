from typing import List
from pathlib import Path

from .file_manager import resolve_chunks_path, resolve_all_chunks, parse_pdfname_from_chunks
from .loader import load_chunks
from .embed_model import get_embedding
from .chroma_client import init_db, get_collection, insert_chunk
from .config import EMBED_VERSION
from .utils import get_logger

logger = get_logger(__name__)


def _run_one(path: Path) -> Path:
    pdfname = parse_pdfname_from_chunks(path)
    chunks = load_chunks(path)
    client = init_db()
    collection = get_collection(client)
    count = 0
    for ch in chunks:
        try:
            emb = get_embedding(ch["content"])
        except Exception as e:
            logger.warning(f"Embedding failed for {ch['chunk_id']}: {e}")
            continue
        # Chroma metadata requires primitive types; convert lists to strings
        pages = ch.get("source_pages", [])
        pages_str = ",".join(str(p) for p in pages) if isinstance(pages, list) else str(pages)
        metadata = {
            "source_pages": pages_str,
            "raw_tokens": int(ch.get("tokens", 0)),
            "pdf_name": str(pdfname),
            "embed_version": str(EMBED_VERSION),
        }
        try:
            insert_chunk(collection, ch["chunk_id"], ch["content"], emb, metadata)
            count += 1
        except Exception as e:
            logger.error(f"Insert failed for {ch['chunk_id']}: {e}")
    logger.info(f"Embedded {count} chunks for {pdfname}")
    return path


def run_for_file(pdfname: str) -> Path:
    path = resolve_chunks_path(pdfname)
    if not path.exists():
        raise FileNotFoundError(f"Chunks JSON not found: {path}")
    return _run_one(path)


def run_for_all() -> List[Path]:
    paths = resolve_all_chunks()
    if not paths:
        logger.info("No chunk files found in proceeds.")
        return []
    outs: List[Path] = []
    for p in paths:
        outs.append(_run_one(p))
    return outs