from typing import List, Dict, Any
import json
from pathlib import Path


def load_pages(extracted_json_path: Path) -> List[Dict[str, Any]]:
    with extracted_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    pages = data.get("pages", [])
    return pages