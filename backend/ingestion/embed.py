from __future__ import annotations

import os
from typing import List, Optional

from openai import OpenAI

DEFAULT_BATCH = 100
EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 3072


class EmbeddingService:
    """Shared embedding service (OpenAI only for reports)."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, dimension: Optional[int] = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for embeddings")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model or EMBED_MODEL
        self.dimension = dimension or EMBED_DIM

    def embed_text(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            encoding_format="float",
        )
        return response.data[0].embedding

    def embed_texts(self, texts: List[str], batch_size: int = DEFAULT_BATCH) -> List[List[float]]:
        embeddings: List[List[float]] = []
        total = len(texts)

        for i in range(0, total, batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
                encoding_format="float",
            )
            embeddings.extend([item.embedding for item in response.data])

        return embeddings


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(api_key: Optional[str] = None, model: Optional[str] = None, dimension: Optional[int] = None) -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(api_key=api_key, model=model, dimension=dimension)
    return _embedding_service


def embed_text(text: str, api_key: Optional[str] = None, model: Optional[str] = None, dimension: Optional[int] = None) -> List[float]:
    return get_embedding_service(api_key=api_key, model=model, dimension=dimension).embed_text(text)


def embed_texts(
    texts: List[str],
    api_key: Optional[str] = None,
    batch_size: int = DEFAULT_BATCH,
    model: Optional[str] = None,
    dimension: Optional[int] = None,
) -> List[List[float]]:
    return get_embedding_service(api_key=api_key, model=model, dimension=dimension).embed_texts(texts, batch_size=batch_size)
