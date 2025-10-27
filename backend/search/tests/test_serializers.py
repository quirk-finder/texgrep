from __future__ import annotations

import pytest
from rest_framework import serializers as drf_serializers

from search.query import QueryValidationError
from search.serializers import (
    SearchRequestSerializer,
    SearchResponseSerializer,
    SnippetBlockSerializer,
)
from search.types import SearchHit, SearchResponse, TextSnippetBlock


def test_search_response_serializer_roundtrip():
    response = SearchResponse(
        hits=[
            SearchHit(
                file_id="1",
                path="file.tex",
                line=10,
                snippet="snippet",
                url="http://example.com",
                blocks=[TextSnippetBlock(html="Example <mark>hit</mark>")],
            )
        ],
        total=1,
        took_provider_ms=5,
        page=1,
        size=20,
    )
    payload = SearchResponseSerializer.from_response(response, took_end_to_end_ms=7)
    assert payload["total"] == 1
    assert payload["hits"][0]["path"] == "file.tex"
    assert payload["hits"][0]["blocks"][0]["html"] == "Example <mark>hit</mark>"
    assert payload["took_provider_ms"] == 5
    assert payload["took_end_to_end_ms"] == 7


def test_snippet_block_serializer_requires_math_tex() -> None:
    serializer = SnippetBlockSerializer(data={"kind": "math", "html": "<p>ignored</p>"})

    with pytest.raises(drf_serializers.ValidationError) as exc:
        serializer.is_valid(raise_exception=True)

    assert "Math block must include tex content" in str(exc.value)


def test_search_request_serializer_wraps_query_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_parse_payload(_attrs):
        raise QueryValidationError("bad query")

    monkeypatch.setattr(
        "search.serializers.parse_payload", fake_parse_payload
    )

    serializer = SearchRequestSerializer(data={"q": "x", "mode": "literal"})

    with pytest.raises(drf_serializers.ValidationError) as exc:
        serializer.is_valid(raise_exception=True)

    assert "bad query" in str(exc.value)
