from pathlib import Path
from typing import List

# Resolve to Insurance module directory (embedder/..)
BASE_DIR = Path(__file__).resolve().parents[1]
PROCEEDS_DIR = BASE_DIR / "documents" / "proceeds"


def resolve_chunks_path(pdfname: str) -> Path:
    return PROCEEDS_DIR / f"chunks_{pdfname}.json"


def resolve_all_chunks() -> List[Path]:
    if not PROCEEDS_DIR.exists():
        return []
    return sorted(PROCEEDS_DIR.glob("chunks_*.json"))


def parse_pdfname_from_chunks(path: Path) -> str:
    name = path.stem
    if name.startswith("chunks_"):
        return name.replace("chunks_", "")
    return name