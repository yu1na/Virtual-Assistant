from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from chromadb import Collection

from ingestion.embed import get_embedding_service

from app.domain.report.core.chunker import (
    ALLOWED_CHUNK_TYPES,
    ChunkValidationError,
    validate_metadata,
)
from app.domain.report.search.retriever import UnifiedSearchResult


@dataclass
class SearchKeywords:
    chunk_types: List[str]
    single_date: Optional[str] = None
    date_range: Optional[Dict[str, date]] = None


class QueryAnalyzer:
    """Lightweight keyword analyzer to guide filters."""

    @staticmethod
    def _parse_date_string(raw: str) -> Optional[date]:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _month_range_from_token(token: str) -> Optional[Dict[str, date]]:
        parsed = None
        for fmt in ("%Y-%m", "%Y/%m", "%Y.%m"):
            try:
                parsed = datetime.strptime(token.strip(), fmt)
                break
            except ValueError:
                continue
        if not parsed:
            return None

        year, month = parsed.year, parsed.month
        _, last_day = calendar.monthrange(year, month)
        return {"start": date(year, month, 1), "end": date(year, month, last_day)}

    @staticmethod
    def _week_range_from_anchor(anchor: date) -> Dict[str, date]:
        week_start = anchor - timedelta(days=anchor.weekday())
        week_end = week_start + timedelta(days=6)
        return {"start": week_start, "end": week_end}

    @staticmethod
    def _extract_relative_date_range(lower: str, reference: date) -> Optional[Dict[str, date]]:
        if "today" in lower:
            return {"start": reference, "end": reference}
        if "yesterday" in lower:
            day = reference - timedelta(days=1)
            return {"start": day, "end": day}

        match = re.search(r"last\s+(\d+)\s+days", lower)
        if match:
            days = max(int(match.group(1)), 1)
            start = reference - timedelta(days=days - 1)
            return {"start": start, "end": reference}

        if "this week" in lower:
            return QueryAnalyzer._week_range_from_anchor(reference)
        if "last week" in lower or "past week" in lower:
            anchor = reference - timedelta(days=7)
            return QueryAnalyzer._week_range_from_anchor(anchor)

        if "this month" in lower:
            _, last_day = calendar.monthrange(reference.year, reference.month)
            return {
                "start": date(reference.year, reference.month, 1),
                "end": date(reference.year, reference.month, last_day),
            }
        if "last month" in lower or "past month" in lower:
            year, month = reference.year, reference.month - 1
            if month == 0:
                year -= 1
                month = 12
            _, last_day = calendar.monthrange(year, month)
            return {"start": date(year, month, 1), "end": date(year, month, last_day)}

        return None

    @staticmethod
    def _parse_absolute_korean_dates(query: str, reference_date: date) -> tuple[Optional[str], Optional[Dict[str, date]]]:
        """
        한국어 절대 날짜 파싱
        
        Returns:
            (single_date: Optional[str], date_range: Optional[Dict[str, date]])
            - single_date: "YYYY-MM-DD" 형식 문자열 (단일 날짜인 경우)
            - date_range: {"start": date, "end": date} (월 범위인 경우)
        """
        # 1) YYYY년 MM월 DD일 → single_date
        full_date_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", query)
        if full_date_match:
            try:
                year = int(full_date_match.group(1))
                month = int(full_date_match.group(2))
                day = int(full_date_match.group(3))
                parsed_date = date(year, month, day)
                return (parsed_date.strftime("%Y-%m-%d"), None)
            except ValueError:
                pass
        
        # 2) YYYY년 MM월 → month range
        year_month_match = re.search(r"(\d{4})년\s*(\d{1,2})월", query)
        if year_month_match:
            try:
                year = int(year_month_match.group(1))
                month = int(year_month_match.group(2))
                _, last_day = calendar.monthrange(year, month)
                return (None, {
                    "start": date(year, month, 1),
                    "end": date(year, month, last_day)
                })
            except ValueError:
                pass
        
        # 3) MM월 DD일 → reference_date의 연도 사용
        month_day_match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", query)
        if month_day_match:
            try:
                month = int(month_day_match.group(1))
                day = int(month_day_match.group(2))
                year = reference_date.year
                parsed_date = date(year, month, day)
                return (parsed_date.strftime("%Y-%m-%d"), None)
            except ValueError:
                pass
        
        return (None, None)

    @staticmethod
    def _extract_date_range(query: str, base_date: Optional[date] = None) -> Optional[Dict[str, date]]:
        reference = base_date or date.today()
        lower = query.lower()

        # 절대 날짜를 먼저 파싱 (한국어 형식 우선)
        single_date, korean_date_range = QueryAnalyzer._parse_absolute_korean_dates(query, reference)
        if korean_date_range:
            return korean_date_range
        if single_date:
            parsed_date = datetime.strptime(single_date, "%Y-%m-%d").date()
            return {"start": parsed_date, "end": parsed_date}

        # ISO 형식 날짜 파싱 (YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD)
        explicit_dates = [
            QueryAnalyzer._parse_date_string(match)
            for match in re.findall(r"\b(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b", query)
        ]
        explicit_dates = [d for d in explicit_dates if d]
        if len(explicit_dates) >= 2:
            start, end = explicit_dates[0], explicit_dates[1]
            if start > end:
                start, end = end, start
            return {"start": start, "end": end}
        if len(explicit_dates) == 1:
            return {"start": explicit_dates[0], "end": explicit_dates[0]}

        # 상대 날짜 파싱 (절대 날짜가 없을 때만)
        relative = QueryAnalyzer._extract_relative_date_range(lower, reference)
        if relative:
            return relative

        week_anchor = re.search(
            r"week\s+(?:of|starting|beginning)?\s*(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
            lower,
        )
        if week_anchor:
            anchor_date = QueryAnalyzer._parse_date_string(week_anchor.group(1))
            if anchor_date:
                return QueryAnalyzer._week_range_from_anchor(anchor_date)

        month_ranges = []
        for token in re.findall(r"\b(\d{4}[-/.]\d{1,2})(?![-/.]\d)\b", query):
            month_range = QueryAnalyzer._month_range_from_token(token)
            if month_range:
                month_ranges.append(month_range)
        if month_ranges:
            start = month_ranges[0]["start"]
            end = month_ranges[-1]["end"]
            if start > end:
                start, end = end, start
            return {"start": start, "end": end}

        return None

    @staticmethod
    def extract_keywords(query: str, base_date: Optional[date] = None) -> SearchKeywords:
        lower = query.lower()
        chunk_types: List[str] = []
        
        # 날짜 범위 추출 (_extract_date_range에서 한국어 날짜도 처리)
        date_range = QueryAnalyzer._extract_date_range(query, base_date)
        single_date = None
        
        # 단일 날짜인 경우 single_date 설정
        if date_range and date_range["start"] == date_range["end"]:
            single_date = date_range["start"].strftime("%Y-%m-%d")

        if any(word in lower for word in ["계획", "plan", "익일"]):
            chunk_types.append("plan")
        if any(word in lower for word in ["미종결", "pending", "이슈", "issue"]):
            chunk_types.append("pending")
        if any(word in lower for word in ["요약", "summary"]):
            chunk_types.append("summary")
        if any(word in lower for word in ["todo", "할 일", "진행 업무"]):
            chunk_types.append("todo")
        if not chunk_types:
            chunk_types = ["detail", "todo", "pending", "plan", "summary"]

        return SearchKeywords(chunk_types=chunk_types, single_date=single_date, date_range=date_range)


class HybridSearcher:
    """Simple hybrid search that applies metadata filters then vector search."""

    def __init__(self, collection: Collection) -> None:
        self.collection = collection
        self.embedding_service = get_embedding_service(model="text-embedding-3-large", dimension=3072)

    def _build_date_list(self, start: date, end: date) -> List[str]:
        dates = []
        current = start
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return dates

    def _build_where(
        self,
        keywords: SearchKeywords,
        owner: Optional[str],
        normalized_date_range: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        conditions: List[Dict[str, Any]] = [{"report_type": "daily"}]

        if keywords.chunk_types:
            valid = [ctype for ctype in keywords.chunk_types if ctype in ALLOWED_CHUNK_TYPES]
            if valid:
                conditions.append({"chunk_type": {"$in": valid}})

        # owner 필터링 제거: 단일 워크스페이스로 동작
        # if owner:
        #     conditions.append({"owner": owner})

        if normalized_date_range:
            # ChromaDB는 하나의 연산자만 허용하므로 날짜 리스트를 생성하여 $in 사용
            start_date = datetime.strptime(normalized_date_range["start"], "%Y-%m-%d").date()
            end_date = datetime.strptime(normalized_date_range["end"], "%Y-%m-%d").date()
            date_list = self._build_date_list(start_date, end_date)
            if date_list:
                conditions.append({"date": {"$in": date_list}})
        elif keywords.single_date:
            conditions.append({"date": keywords.single_date})

        return {"$and": conditions} if len(conditions) > 1 else conditions[0]

    def _normalize_date_range(self, date_range: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        if not date_range:
            return None

        start_date = self._parse_to_date(date_range.get("start"))
        end_date = self._parse_to_date(date_range.get("end"))
        if not start_date or not end_date:
            return None

        if start_date > end_date:
            start_date, end_date = end_date, start_date

        return {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")}

    def _parse_to_date(self, value: Any) -> Optional[date]:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
                try:
                    return datetime.strptime(value.strip(), fmt).date()
                except ValueError:
                    continue
        return None

    def search(
        self,
        query: str,
        keywords: SearchKeywords,
        owner: Optional[str] = None,
        base_date_range: Optional[Dict[str, date]] = None,
        top_k: int = 5,
    ) -> List[UnifiedSearchResult]:
        # single_date가 있으면 우선적으로 date_range로 변환
        effective_date_range: Optional[Dict[str, Any]] = None
        if keywords.single_date:
            # single_date를 date 객체로 변환
            try:
                single_date_obj = datetime.strptime(keywords.single_date, "%Y-%m-%d").date()
                effective_date_range = {"start": single_date_obj, "end": single_date_obj}
            except ValueError:
                pass
        
        # single_date가 없으면 date_range 또는 base_date_range 사용
        if not effective_date_range:
            effective_date_range = keywords.date_range or base_date_range
        
        normalized_date_range = self._normalize_date_range(effective_date_range)

        where_filter = self._build_where(keywords, owner, normalized_date_range)
        query_embedding = self.embedding_service.embed_text(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter if where_filter else None,
        )

        search_results: List[UnifiedSearchResult] = []
        if not results or not results.get("ids"):
            return search_results

        ids = results["ids"][0]
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for i in range(len(ids)):
            metadata = metadatas[i] or {}
            try:
                metadata = validate_metadata(metadata)
            except ChunkValidationError:
                continue

            if metadata.get("chunk_type") not in ALLOWED_CHUNK_TYPES:
                continue
            if metadata.get("report_type") != "daily":
                continue
            if normalized_date_range:
                meta_date = metadata.get("date", "")
                if not meta_date or not (
                    normalized_date_range["start"] <= meta_date <= normalized_date_range["end"]
                ):
                    continue

            score = 1.0 / (1.0 + distances[i])
            search_results.append(
                UnifiedSearchResult(
                    chunk_id=ids[i],
                    doc_id=metadata.get("doc_id", ""),
                    doc_type=metadata.get("report_type", "daily"),
                    chunk_type=metadata.get("chunk_type", ""),
                    text=documents[i],
                    score=score,
                    metadata=metadata,
                )
            )

        # Return best matches first
        search_results.sort(key=lambda r: -r.score)
        return search_results[:top_k]
