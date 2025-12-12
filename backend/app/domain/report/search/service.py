from __future__ import annotations

from typing import Any, Dict, Optional

from .intent_router import IntentRouter, QueryIntent
from .retriever import UnifiedRetriever


class UnifiedSearchService:
    """Glue code between the intent router and the retriever."""

    def __init__(self, retriever: UnifiedRetriever, router: IntentRouter) -> None:
        self.retriever = retriever
        self.router = router

    async def search(self, query: str, user: Optional[str] = None, n_results: int = 5) -> Dict[str, Any]:
        return self._search(query=query, user=user, n_results=n_results)

    def search_sync(self, query: str, user: Optional[str] = None, n_results: int = 5) -> Dict[str, Any]:
        return self._search(query=query, user=user, n_results=n_results)

    def _search(self, query: str, user: Optional[str], n_results: int) -> Dict[str, Any]:
        intent_result: QueryIntent = self.router.route(query)
        chunk_types = intent_result.filters.get("chunk_types") if intent_result.filters else None

        results = self.retriever.search_daily(
            query=query,
            owner=user,
            n_results=n_results,
            chunk_types=chunk_types,
        )

        return {
            "query": query,
            "intent": intent_result.intent,
            "reason": intent_result.reason,
            "filters": intent_result.filters,
            "results": results,
            "count": len(results),
        }
