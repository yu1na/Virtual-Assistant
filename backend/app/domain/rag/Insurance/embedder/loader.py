from typing import List, Dict, Any
import json
from pathlib import Path


REQUIRED_KEYS = {"chunk_id", "content", "tokens", "source_pages"}


def load_chunks(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Chunk file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Chunk JSON must be a list of objects")
    valid = []
    for i, item in enumerate(data):
        if not REQUIRED_KEYS.issubset(item.keys()):
            raise ValueError(f"Chunk at index {i} missing required keys: {REQUIRED_KEYS}")
        valid.append(item)
    return valid