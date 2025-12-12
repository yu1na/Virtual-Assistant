from pathlib import Path

EMBED_MODEL = "text-embedding-3-large"
EMBED_VERSION = "v1"
# Resolve Chroma path relative to the Insurance module to avoid CWD issues
CHROMA_PATH = str(Path(__file__).resolve().parents[1] / "chroma_db")