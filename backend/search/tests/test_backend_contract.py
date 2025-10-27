from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest

from search.backends import OpenSearchBackend
from search.providers import zoekt
from search.types import SearchRequest, SearchResponse


class _FakeIndices:
    def exists(self, index: str) -> bool:  # pragma: no cover - protocol stub
        return True

    def create(self, index: str, body: dict[str, Any]) -> None:  # pragma: no cover
        raise AssertionError("index creation not expected in tests")

    def delete(self, index: str) -> None:  # pragma: no cover
        raise AssertionError("index deletion not expected in tests")


class _FakeOpenSearchClient:
    def __init__(self) -> None:
        self.indices = _FakeIndices()
        self.last_body: dict[str, Any] | None = None
        self.last_size: int | None = None
        self._hits: list[dict[str, Any]] = [
            {
                "_id": "doc-1",
                "_source": {
                    "file_id": "doc-1",
                    "path": "foo.tex",
                    "url": "https://example.test/foo.tex",
                    "content": "alpha line\\nmore content a|b pattern",
                    "line_offsets": [1, 2, 3],
                },
            },
            {
                "_id": "doc-2",
                "_source": {
                    "file_id": "doc-2",
                    "path": "bar.tex",
                    "url": "https://example.test/bar.tex",
                    "content": "second alpha line",
                    "line_offsets": [1, 2, 3],
                },
            },
        ]

    def search(
        self,
        *,
        index: str,
        body: dict[str, Any],
        from_: int,
        size: int,
        request_timeout: float | None = None,
    ) -> dict[str, Any]:
        self.last_body = body
        self.last_size = size
        return {
            "hits": {"hits": list(self._hits), "total": {"value": len(self._hits)}},
            "took": 7,
        }


@dataclass
class BackendCase:
    name: str
    search: Callable[[SearchRequest], SearchResponse]
    capture: dict[str, Any]


@pytest.fixture(params=["opensearch", "zoekt"])
def backend_case(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> BackendCase:
    if request.param == "opensearch":
        client = _FakeOpenSearchClient()
        backend = OpenSearchBackend(client=client, index_name="tex")
        return BackendCase(
            name="opensearch",
            search=backend.search,
            capture={"client": client},
        )

    payloads: list[dict[str, Any]] = []

    def fake_post(
        url: str, payload: dict[str, Any], *, timeout: float = zoekt.DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        payloads.append(payload)
        pattern = str(payload.get("query", {}).get("pattern", ""))
        if pattern == "\\alpha":
            content = "prefix \\alpha suffix"
        else:
            content = "a|b expression in content"
        return {
            "FileMatches": [
                {
                    "Repository": "samples",
                    "FileName": "foo.tex",
                    "Checksum": "abc123",
                    "URL": "https://example.test/foo.tex",
                    "Content": content,
                    "LineMatches": [
                        {"LineNumber": 1, "Line": content},
                    ],
                }
            ],
            "Stats": {"Duration": 0.01, "MatchCount": 1},
        }

    monkeypatch.setattr(zoekt, "_http_post", fake_post)
    monkeypatch.setattr(zoekt, "_http_get", lambda *args, **kwargs: "")

    return BackendCase(
        name="zoekt",
        search=zoekt.search,
        capture={"payloads": payloads},
    )


def test_literal_query_handles_backslash_variants(backend_case: BackendCase) -> None:
    request = SearchRequest(
        query=r"\\alpha",
        mode="literal",
        filters={},
        page=1,
        size=3,
    )

    response = backend_case.search(request)

    assert response.hits
    snippet = response.hits[0].snippet or ""
    assert "alpha" in snippet

    if backend_case.name == "opensearch":
        client = backend_case.capture["client"]
        body = client.last_body or {}
        should = body["query"]["bool"]["must"][0]["bool"]["should"]
        queries = {
            item["match_phrase"]["content"]["query"]
            for item in should
            if "match_phrase" in item
        }
        assert "\\alpha" in queries
        assert "alpha" in queries
    else:
        payloads = backend_case.capture["payloads"]
        assert any(p["query"]["pattern"] == "\\alpha" for p in payloads)


def test_regex_unsafe_query_fallback_behaviour(backend_case: BackendCase) -> None:
    request = SearchRequest(
        query="a|b",
        mode="regex",
        filters={},
        page=1,
        size=2,
    )

    response = backend_case.search(request)

    assert response.hits
    if backend_case.name == "opensearch":
        client = backend_case.capture["client"]
        body = client.last_body or {}
        clause = body["query"]["bool"]["must"][0]
        assert "bool" in clause
        terms = clause["bool"].get("must", [])
        assert any(
            term.get("term", {}).get("content.ngram") in {"a", "b"}
            for term in terms
        )
        assert client.last_size == request.size
    else:
        payloads = backend_case.capture["payloads"]
        assert any(p["query"]["pattern"] == "a|b" for p in payloads)
