from __future__ import annotations

from search.serializers import SearchResponseSerializer
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
