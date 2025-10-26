from __future__ import annotations

import pytest

from search.providers import get_provider
from search.providers import zoekt
from search.query import decode_literal_query
from search.types import SearchRequest


def test_zoekt_provider_returns_snippet_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    content = "\n".join([
        r"\begin{equation}",
        r"a \\xrightarrow{n} b",
        r"\end{equation}",
    ])
    zoekt_response = {
        "FileMatches": [
            {
                "Repository": "samples",
                "FileName": "foo.tex",
                "Checksum": "abc123",
                "URL": "https://example.com/foo.tex",
                "Content": content,
                "LineMatches": [
                    {"LineNumber": 2, "Line": r"a \\xrightarrow{n} b"},
                ],
            }
        ],
        "Stats": {"Duration": 0.012, "MatchCount": 1},
    }
    post_call: dict = {}

    def fake_post(url: str, payload: dict, *, timeout: float = zoekt.DEFAULT_TIMEOUT) -> dict:
        post_call["url"] = url
        post_call["payload"] = payload
        return zoekt_response

    monkeypatch.setenv("ZOEKT_URL", "http://zoekt.test:6070/")
    monkeypatch.setattr(zoekt, "_http_post", fake_post)
    monkeypatch.setattr(zoekt, "_http_get", lambda *a, **k: content)

    request = SearchRequest(query=r"\\xrightarrow", mode="literal", filters={}, page=1, size=5)
    response = zoekt.search(request)

    assert post_call["url"] == "http://zoekt.test:6070/api/search"
    assert post_call["payload"]["query"]["pattern"] == decode_literal_query(request.query)

    assert response.total == 1
    assert response.took_provider_ms == 12
    assert response.hits
    hit = response.hits[0]
    assert hit.blocks is not None
    math_blocks = [block for block in hit.blocks if getattr(block, "kind", "") == "math"]
    assert math_blocks, "expected math snippet blocks"
    assert "\\class{mjx-hl}{\\xrightarrow{n}}" in math_blocks[0].tex
    assert "<mark>\\xrightarrow" in (hit.snippet or "")


def test_zoekt_provider_falls_back_when_stats_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    content = "\n".join([
        r"\begin{equation}",
        r"a \\xrightarrow{n} b",
        r"\end{equation}",
    ])
    zoekt_response = {
        "FileMatches": [
            {
                "Repository": "samples",
                "FileName": "foo.tex",
                "URL": "https://example.com/foo.tex",
                "LineMatches": [
                    {"LineNumber": 2, "Line": r"a \\xrightarrow{n} b"},
                ],
            }
        ]
    }

    post_calls: list[dict] = []
    get_calls: list[dict] = []

    def fake_post(url: str, payload: dict, *, timeout: float = zoekt.DEFAULT_TIMEOUT) -> dict:
        post_calls.append({"url": url, "payload": payload})
        return zoekt_response

    def fake_get(url: str, params: dict, *, timeout: float = zoekt.DEFAULT_TIMEOUT) -> str:
        get_calls.append({"url": url, "params": params})
        return content

    class FakeTime:
        def __init__(self) -> None:
            self._calls = 0

        def monotonic(self) -> float:
            if self._calls == 0:
                self._calls += 1
                return 10.0
            self._calls += 1
            return 10.250

    fake_time = FakeTime()

    monkeypatch.setenv("ZOEKT_URL", "http://zoekt.test:6070")
    monkeypatch.setattr(zoekt, "_http_post", fake_post)
    monkeypatch.setattr(zoekt, "_http_get", fake_get)
    monkeypatch.setattr(zoekt, "time", fake_time)

    request = SearchRequest(query=r"\\xrightarrow", mode="literal", filters={}, page=2, size=5)
    response = zoekt.search(request)

    assert response.total == 1
    assert response.took_provider_ms == 250
    assert post_calls[0]["payload"]["offset"] == 5
    assert get_calls == [
        {
            "url": "http://zoekt.test:6070/api/file",
            "params": {"Repository": "samples", "File": "foo.tex"},
        }
    ]

    hit = response.hits[0]
    assert hit.file_id == "samples:foo.tex"
    assert hit.blocks is not None
    assert any(getattr(block, "kind", "") == "math" for block in hit.blocks or [])

    provider = get_provider("zoekt")
    assert provider is zoekt.search
