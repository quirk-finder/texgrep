from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
import warnings
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
MAX_PAGE_SIZE = 50
MAX_QUERY_LENGTH = 256
REGEX_TIMEOUT_SECONDS = 0.1
MAX_OFFSET = 5000


def parse_payload(payload: dict[str, Any]) -> SearchRequest:
    query = (payload.get("q") or "").strip()
    if not query:
        raise QueryValidationError("Query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise QueryValidationError("Query too long")

    mode: SearchMode = payload.get("mode", "literal")
    if mode not in ("literal", "regex"):
        raise QueryValidationError("Unknown mode")

    try:
        page = int(payload.get("page") or 1)
    except (TypeError, ValueError) as exc:
        raise QueryValidationError("Page must be an integer") from exc

    try:
        size = int(payload.get("size") or DEFAULT_PAGE_SIZE)
    except (TypeError, ValueError) as exc:
        raise QueryValidationError("Page size must be an integer") from exc
    if page < 1:
        raise QueryValidationError("Page must be >= 1")
    if size < 1:
        raise QueryValidationError("Invalid page size")
    size = min(size, MAX_PAGE_SIZE)

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

    cursor_raw = payload.get("cursor")
    cursor: str | None
    if cursor_raw is None:
        cursor = None
        if page * size > MAX_OFFSET:
            raise QueryValidationError("Page too deep")
    else:
        cursor = str(cursor_raw).strip()
        if cursor == "":
            cursor = None

    return SearchRequest(
        query=query,
        mode=mode,
        filters=normalized_filters,
        page=page,
        size=size,
        cursor=cursor,
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

        # unicode_escape で \w など未対応エスケープがあると DeprecationWarning が出るため抑制
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return codecs.decode(query, "unicode_escape")
    except Exception:  # pragma: no cover - best effort fallback
        return query


def decode_literal_query(query: str) -> str:
    return _decode_query(query)


def decode_regex_query(pattern: str) -> str:
    return _decode_query(pattern)
