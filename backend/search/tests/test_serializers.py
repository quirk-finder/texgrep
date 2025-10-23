from __future__ import annotations

from search.serializers import SearchResponseSerializer
from search.types import SearchHit, SearchResponse


def test_search_response_serializer_roundtrip():
    response = SearchResponse(
        hits=[SearchHit(file_id="1", path="file.tex", line=10, snippet="snippet", url="http://example.com")],
        total=1,
        took_ms=5,
    )
    payload = SearchResponseSerializer.from_response(response)
    assert payload["total"] == 1
    assert payload["hits"][0]["path"] == "file.tex"
