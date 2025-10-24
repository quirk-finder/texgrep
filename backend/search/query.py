from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .types import SearchMode, SearchRequest


class QueryValidationError(ValueError):
    """Raised when the incoming search query is invalid."""


@dataclass(slots=True)
class RawSearchPayload:
    q: str
    mode: SearchMode
    filters: dict[str, str | None]
    page: int
    size: int


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_QUERY_LENGTH = 256
REGEX_TIMEOUT_SECONDS = 0.1


def parse_payload(payload: dict[str, Any]) -> SearchRequest:
    query = (payload.get("q") or "").strip()
    if not query:
        raise QueryValidationError("Query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise QueryValidationError("Query too long")

    mode: SearchMode = payload.get("mode", "literal")
    if mode not in ("literal", "regex"):
        raise QueryValidationError("Unknown mode")

    page = int(payload.get("page") or 1)
    size = int(payload.get("size") or DEFAULT_PAGE_SIZE)
    if page < 1:
        raise QueryValidationError("Page must be >= 1")
    if size < 1 or size > MAX_PAGE_SIZE:
        raise QueryValidationError("Invalid page size")

    filters = payload.get("filters") or {}
    if not isinstance(filters, dict):
        raise QueryValidationError("Filters must be an object")
    normalized_filters = {}
    for key in ("year", "source"):
        value = filters.get(key)
        if value is None:
            normalized_filters[key] = None
        else:
            normalized_filters[key] = str(value)

    if mode == "regex":
        validate_regex(query)

    return SearchRequest(
        query=query,
        mode=mode,
        filters=normalized_filters,
        page=page,
        size=size,
    )


def validate_regex(pattern: str) -> None:
    try:
        compiled_pattern = _decode_query(pattern)
        try:
            re.compile(compiled_pattern, flags=re.MULTILINE, timeout=REGEX_TIMEOUT_SECONDS)
        except TypeError:
            re.compile(compiled_pattern, flags=re.MULTILINE)
    except TimeoutError as exc:  # pragma: no cover - requires catastrophic input
        raise QueryValidationError("Regex pattern timed out during validation") from exc
    except re.error as exc:
        raise QueryValidationError(f"Invalid regex: {exc}") from exc


def _decode_query(query: str) -> str:
    try:
        import codecs

        return codecs.decode(query, "unicode_escape")
    except Exception:  # pragma: no cover - best effort fallback
        return query


def decode_literal_query(query: str) -> str:
    return _decode_query(query)


def decode_regex_query(pattern: str) -> str:
    return _decode_query(pattern)
