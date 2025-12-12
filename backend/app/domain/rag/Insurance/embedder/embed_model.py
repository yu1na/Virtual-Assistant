from typing import List
import os
import numpy as np

from .config import EMBED_MODEL
from .utils import get_logger

logger = get_logger(__name__)


def _local_embed(text: str) -> List[float]:
    # Local deterministic embedding: hash to pseudo-vector
    dim = 1536
    h = 0
    for ch in text:
        h = (h * 131 + ord(ch)) % (1 << 32)
    np.random.seed(h % (2**32 - 1))
    v = np.random.rand(dim).astype(np.float32)
    v = v / (np.linalg.norm(v) + 1e-8)
    return v.tolist()


def get_embedding(text: str) -> List[float]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Fallback
        return _local_embed(text)
    # If OpenAI client is available, wire real embedding here.
    # To keep module standalone without external deps, use local for now.
    logger.info("OPENAI_API_KEY present but client wiring not implemented; using local embedding.")
    return _local_embed(text)