from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb import Collection

from app.domain.report.core.chunker import ChunkValidationError, validate_metadata

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHROMA_PERSIST_DIR = BASE_DIR / "Data" / "ChromaDB" / "report"
COLLECTION_NAME = "reports"


class ReportVectorStore:
    """ChromaDB wrapper for the report collection."""

    def __init__(self) -> None:
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        self._collection: Optional[Collection] = None

    def get_collection(self) -> Collection:
        if self._collection is None:
            try:
                self._collection = self.client.get_collection(name=COLLECTION_NAME)
            except Exception:
                self._collection = self.client.create_collection(
                    name=COLLECTION_NAME,
                    metadata={
                        "description": "Daily report collection",
                        "embedding_model": "text-embedding-3-large",
                        "embedding_dim": 3072,
                    },
                )
        return self._collection

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ChunkValidationError("Chunks and embeddings length mismatch")

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            metadata = validate_metadata(dict(chunk["metadata"]))
            ids.append(chunk["id"])
            documents.append(chunk["text"])
            metadatas.append(metadata)

        collection = self.get_collection()
        collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


_report_vector_store: Optional[ReportVectorStore] = None


def get_report_vector_store() -> ReportVectorStore:
    global _report_vector_store
    if _report_vector_store is None:
        _report_vector_store = ReportVectorStore()
    return _report_vector_store
