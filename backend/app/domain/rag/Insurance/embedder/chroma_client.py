from typing import Dict, Any, List
from pathlib import Path
import time

from chromadb import PersistentClient

from .config import CHROMA_PATH
from .utils import ensure_dir, get_logger

logger = get_logger(__name__)


def init_db() -> PersistentClient:
    path = Path(CHROMA_PATH)
    ensure_dir(path)
    client = PersistentClient(path=str(path))
    return client


def get_collection(client: PersistentClient):
    return client.get_or_create_collection(
        name="insurance_manual",
        metadata={"hnsw:space": "cosine"}
    )


def insert_chunk(collection, chunk_id: str, document: str, embedding: List[float], metadata: Dict[str, Any]) -> None:
    try:
        collection.add(ids=[chunk_id], documents=[document], embeddings=[embedding], metadatas=[metadata])
    except Exception as e:
        logger.warning(f"Insert failed once for {chunk_id}: {e}. Retrying...")
        time.sleep(0.2)
        collection.add(ids=[chunk_id], documents=[document], embeddings=[embedding], metadatas=[metadata])