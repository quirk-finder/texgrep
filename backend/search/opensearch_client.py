from __future__ import annotations

import re
from typing import Iterable, List

from django.conf import settings
from opensearchpy import OpenSearch

from .query import decode_literal_query, decode_regex_query
from .types import SearchRequest

_SAFE_META_CHARS = set("[](){}|")
_UNSAFE_QUANTIFIER = re.compile(r"(?<!\\)[+?*]")


def create_client() -> OpenSearch:
    """Create a configured OpenSearch client instance."""
    return OpenSearch(hosts=[settings.OPENSEARCH_HOST], verify_certs=False)


def build_search_body(request: SearchRequest) -> dict:
    """Build the OpenSearch query body for a search request."""
    if request.mode == "literal":
        must_clause = _literal_clause(request.query)
    else:
        must_clause = _regex_clause(request.query)

    filters = _build_filters(request.filters)
    bool_query: dict[str, Iterable[dict]] = {
        "must": [must_clause],
        "filter": filters,
    }
    return {
        "query": {"bool": bool_query},
        "highlight": _highlight_definition(),
    }


def _literal_clause(query: str) -> dict:
    literal = decode_literal_query(query)
    should = [
        {"match_phrase": {"content": {"query": literal}}},            # 本文そのまま
        {"term": {"commands": literal}},                              # 完全一致（例: "\iiint"）
        {"match": {"commands.prefix": {"query": literal, "operator": "and"}}},  # 先頭一致
    ]
    return {"bool": {"should": should, "minimum_should_match": 1}}


def _regex_clause(pattern: str) -> dict:
    decoded = decode_regex_query(pattern)
    if is_safe_regex(decoded):
        return {"regexp": {"content": {"value": decoded}}}
    return _ngram_clause(decoded)


def is_safe_regex(pattern: str) -> bool:
    if len(pattern) > 64:
        return False
    if pattern.startswith(".*") or pattern.endswith(".*"):
        return False
    if any(char in pattern for char in _SAFE_META_CHARS):
        return False
    if _UNSAFE_QUANTIFIER.search(pattern):
        return False
    return True


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


def _build_filters(filters: dict[str, str | None]) -> List[dict]:
    clauses: List[dict] = []
    for key, value in filters.items():
        if value:
            clauses.append({"term": {key: value}})
    return clauses


def _collect_ngrams(pattern: str) -> List[str]:
    literal = _strip_regex_syntax(pattern)
    grams: List[str] = []
    for token in literal.split():
        if not token:
            continue
        if len(token) <= 2:
            grams.append(token)
            continue
        max_len = min(len(token), 15)
        for size in range(2, max_len + 1):
            for start in range(0, len(token) - size + 1):
                grams.append(token[start : start + size])
    seen = set()
    unique: List[str] = []
    for gram in grams:
        if gram not in seen:
            seen.add(gram)
            unique.append(gram)
        if len(unique) >= 20:
            break
    return unique


def _strip_regex_syntax(pattern: str) -> str:
    result: List[str] = []
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
