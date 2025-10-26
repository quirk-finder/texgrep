from __future__ import annotations

import re
from collections.abc import Iterable

from django.conf import settings
from opensearchpy import OpenSearch

from .query import decode_literal_query, decode_regex_query
from .types import SearchRequest

_SAFE_META_CHARS = set("[](){}|")
_UNSAFE_QUANTIFIER = re.compile(r"(?<!\\)[+?*]")
SAFE_REGEX_MAX_LEN = 64
MIN_TOKEN_LEN = 2
MAX_UNIQUE_GRAMS = 20


def create_client() -> OpenSearch:
    """Create a configured OpenSearch client instance."""
    return OpenSearch(hosts=[settings.OPENSEARCH_HOST], verify_certs=False)


def build_search_body(request: SearchRequest) -> dict[str, object]:
    """Build the OpenSearch query body for a search request."""
    must_clause = (
        _literal_clause(request.query)
        if request.mode == "literal"
        else _regex_clause(request.query)
    )

    filters = _build_filters(request.filters)  # list[dict[str, object]]
    bool_query: dict[str, Iterable[dict]] = {
        "must": [must_clause],
        "filter": filters,
    }
    return {
        "query": {"bool": bool_query},
        "highlight": _highlight_definition(),
    }


def _literal_clause(query: str) -> dict[str, object]:
    literal = decode_literal_query(query)
    # commands 用は先頭の \ を除いた正規化形を使う
    norm = literal[1:] if literal.startswith("\\") else literal

    # 本文は「そのまま」と「\ の有無を反転した形」の両方で should
    should: list[dict[str, object]] = [
        {"match_phrase": {"content": {"query": literal}}}
    ]
    alt = ("\\" + norm) if not literal.startswith("\\") else norm
    if alt != literal:
        should.append({"match_phrase": {"content": {"query": alt}}})

    # commands（完全一致 / 先頭一致）
    should.extend(
        [
            {"term": {"commands": norm}},
            {"match": {"commands.prefix": {"query": norm, "operator": "and"}}},
        ]
    )
    return {"bool": {"should": should, "minimum_should_match": 1}}


def _regex_clause(pattern: str) -> dict:
    decoded = decode_regex_query(pattern)
    if is_safe_regex(decoded):
        return {"regexp": {"content": {"value": decoded}}}
    return _ngram_clause(decoded)


def is_safe_regex(pattern: str) -> bool:
    if len(pattern) > SAFE_REGEX_MAX_LEN:
        return False
    if pattern.startswith(".*") or pattern.endswith(".*"):
        return False
    if any(char in pattern for char in _SAFE_META_CHARS):
        return False
    return not _UNSAFE_QUANTIFIER.search(pattern)


def _ngram_clause(pattern: str) -> dict:
    grams = _collect_ngrams(pattern)
    if not grams:
        return {"match_all": {}}
    must_terms = [{"term": {"content.ngram": gram}} for gram in grams]
    return {"bool": {"must": must_terms}}


def _highlight_definition() -> dict:
    return {
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"],
        "fields": {
            "content": {
                "type": "fvh",
                "number_of_fragments": 0,
            }
        },
    }


def _build_filters(filters: dict[str, str | None]) -> list[dict[str, object]]:
    clauses: list[dict] = []
    for key, value in filters.items():
        if value:
            clauses.append({"term": {key: value}})
    return clauses


def _collect_ngrams(pattern: str) -> list[str]:
    literal = _strip_regex_syntax(pattern)
    grams: list[str] = []
    for token in literal.split():
        if not token:
            continue
        if len(token) <= MIN_TOKEN_LEN:
            grams.append(token)
            continue
        max_len = min(len(token), 15)
        for size in range(2, max_len + 1):
            for start in range(0, len(token) - size + 1):
                grams.append(token[start : start + size])
    seen = set()
    unique: list[str] = []
    for gram in grams:
        if gram not in seen:
            seen.add(gram)
            unique.append(gram)
        if len(unique) >= MAX_UNIQUE_GRAMS:
            break
    return unique


def _strip_regex_syntax(pattern: str) -> str:
    result: list[str] = []
    escape = False
    for char in pattern:
        if escape:
            result.append(char)
            escape = False
            continue
        if char == "\\":
            result.append("\\")
            escape = True
            continue
        if char in ".*+?[](){}|":
            result.append(" ")
        else:
            result.append(char)
    cleaned = "".join(result)
    return " ".join(cleaned.split())
