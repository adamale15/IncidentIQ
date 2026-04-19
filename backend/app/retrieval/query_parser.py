"""
Lightweight query parsing, metadata extraction, and routing heuristics.
"""
import calendar
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional


SERVICE_ALIASES = {
    "auth": "auth-service",
    "auth-service": "auth-service",
    "payment": "payment-service",
    "payments": "payment-service",
    "payment-service": "payment-service",
    "cart": "cart-service",
    "cart-service": "cart-service",
    "search": "search-service",
    "search-service": "search-service",
    "notification": "notification-service",
    "notification-service": "notification-service",
    "api gateway": "api-gateway",
    "gateway": "api-gateway",
    "api-gateway": "api-gateway",
    "database": "database",
    "db": "database",
    "cache": "cache",
    "redis": "cache",
}


class QueryParser:
    """Extract metadata filters, classify query type, and rewrite retrieval text."""

    def parse(self, question: str) -> Dict[str, Any]:
        normalized = question.strip()
        lowered = normalized.lower()

        service = self._extract_service(lowered)
        severity = self._extract_severity(lowered)
        date_range = self._extract_date_range(lowered)
        query_type = self._classify_query(lowered)
        rewritten_query = self._rewrite_query(
            question=normalized,
            service=service,
            severity=severity,
            date_range=date_range,
            query_type=query_type,
        )

        filters: Dict[str, Any] = {}
        if service:
            filters["service"] = service
        if severity:
            filters["severity"] = severity
        if date_range:
            filters["date_range"] = date_range

        return {
            "original_query": normalized,
            "rewritten_query": rewritten_query,
            "query_type": query_type,
            "filters": filters,
            "service": service,
            "severity": severity,
            "date_range": date_range,
        }

    def _extract_service(self, lowered: str) -> Optional[str]:
        for alias, canonical in SERVICE_ALIASES.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", lowered):
                return canonical
        return None

    def _extract_severity(self, lowered: str) -> Optional[str]:
        match = re.search(r"\b(p[0-3])\b", lowered)
        return match.group(1).upper() if match else None

    def _extract_date_range(self, lowered: str) -> Optional[Dict[str, str]]:
        today = date.today()

        if "last week" in lowered:
            start = today - timedelta(days=7)
            return {"start": start.isoformat(), "end": today.isoformat()}

        if "last month" in lowered:
            start = today - timedelta(days=30)
            return {"start": start.isoformat(), "end": today.isoformat()}

        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
            lowered,
        )
        if month_match:
            month_name = month_match.group(1)
            month_index = list(calendar.month_name).index(month_name.capitalize())
            year_match = re.search(r"\b(20\d{2})\b", lowered)
            year = int(year_match.group(1)) if year_match else today.year
            last_day = calendar.monthrange(year, month_index)[1]
            return {
                "start": date(year, month_index, 1).isoformat(),
                "end": date(year, month_index, last_day).isoformat(),
            }

        explicit_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", lowered)
        if explicit_match:
            parsed = explicit_match.group(1)
            return {"start": parsed, "end": parsed}

        return None

    def _classify_query(self, lowered: str) -> str:
        if any(token in lowered for token in ["compare", "difference", "versus", " vs "]):
            return "comparison"
        if any(token in lowered for token in ["timeline", "walk me through", "start to resolution", "chronological"]):
            return "timeline"
        if any(token in lowered for token in ["runbook", "restart", "steps", "how do i"]):
            return "simple_lookup"
        if any(token in lowered for token in ["why", "cause", "root cause", "what caused"]):
            return "causal_reasoning"
        return "simple_lookup"

    def _rewrite_query(
        self,
        question: str,
        service: Optional[str],
        severity: Optional[str],
        date_range: Optional[Dict[str, str]],
        query_type: str,
    ) -> str:
        parts = [question]

        if service:
            parts.append(service)
        if severity:
            parts.append(severity)
        if date_range:
            parts.append(date_range["start"])
            if date_range["end"] != date_range["start"]:
                parts.append(date_range["end"])

        if query_type == "causal_reasoning":
            parts.append("root cause resolution failure incident")
        elif query_type == "timeline":
            parts.append("timeline chronology incident resolution")
        elif query_type == "comparison":
            parts.append("compare incidents similarities differences")
        else:
            parts.append("direct answer runbook steps")

        return " ".join(parts)
