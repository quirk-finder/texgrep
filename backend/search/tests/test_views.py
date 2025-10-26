from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import django
import pytest
from rest_framework.test import APIClient

import search.views as views
from search.types import SearchRequest, SearchResponse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "texgrep.settings")
django.setup()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


def _install_perf_counter(monkeypatch: pytest.MonkeyPatch, values: list[float]) -> None:
    state = {"values": list(values)}

    def _perf_counter() -> float:
        if state["values"]:
            return state["values"].pop(0)
        return values[-1]

    monkeypatch.setattr(views.time, "perf_counter", _perf_counter)


def _install_provider(
    monkeypatch: pytest.MonkeyPatch,
    provider_fn: Callable[[SearchRequest], SearchResponse],
    provider_name: str = "opensearch",
) -> None:
    monkeypatch.setattr(views, "get_provider", lambda name=None: provider_fn)
    monkeypatch.setattr(views, "get_provider_name", lambda: provider_name)


def test_literal_search_records_end_to_end_duration(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_provider(request: SearchRequest) -> SearchResponse:
        captured["request"] = request
        return SearchResponse(
            hits=[],
            total=0,
            took_provider_ms=12,
            page=request.page,
            size=request.size,
        )

    _install_provider(monkeypatch, fake_provider, provider_name="opensearch")
    _install_perf_counter(monkeypatch, [1.0, 1.2])

    response = api_client.post("/api/search", {"q": "foo", "mode": "literal"}, format="json")

    assert response.status_code == 200
    data = response.json()
    assert 190 <= data["took_end_to_end_ms"] <= 210
    assert data["took_provider_ms"] == 12
    assert captured["request"].mode == "literal"


def test_regex_search_rejected_for_non_zoekt(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _should_not_run(request: SearchRequest) -> SearchResponse:  # pragma: no cover - guard
        raise AssertionError("provider should not be called")

    _install_provider(monkeypatch, _should_not_run, provider_name="opensearch")

    response = api_client.post(
        "/api/search",
        {"q": "foo", "mode": "regex"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["message"] == "regex is only supported with Zoekt"


def test_size_clamped_to_maximum(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def fake_provider(request: SearchRequest) -> SearchResponse:
        seen["request"] = request
        return SearchResponse(hits=[], total=0, took_provider_ms=1, page=request.page, size=request.size)

    _install_provider(monkeypatch, fake_provider, provider_name="opensearch")
    _install_perf_counter(monkeypatch, [5.0, 5.1])

    response = api_client.post(
        "/api/search",
        {"q": "foo", "mode": "literal", "size": 500},
        format="json",
    )

    assert response.status_code == 200
    assert seen["request"].size == 50
    assert response.json()["size"] == 50


def test_page_must_be_at_least_one(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_provider(
        monkeypatch,
        lambda request: SearchResponse(
            hits=[], total=0, took_provider_ms=1, page=request.page, size=request.size
        ),
    )

    response = api_client.post(
        "/api/search",
        {"q": "foo", "mode": "literal", "page": 0},
        format="json",
    )

    assert response.status_code == 400


def test_reindex_limit_must_be_numeric(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _ShouldNotRun:
        def delay(self, **kwargs: Any) -> None:  # pragma: no cover - guard
            raise AssertionError("reindex_task.delay should not be called")

    monkeypatch.setattr(views, "reindex_task", _ShouldNotRun())

    response = api_client.post(
        "/api/reindex",
        {"source": "samples", "limit": "not-a-number"},
def test_page_must_be_an_integer(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _should_not_run(request: SearchRequest) -> SearchResponse:  # pragma: no cover - guard
        raise AssertionError("provider should not be called")

    _install_provider(monkeypatch, _should_not_run, provider_name="opensearch")

    response = api_client.post(
        "/api/search",
        {"q": "foo", "mode": "literal", "page": "abc"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "limit must be a non-negative integer"


def test_reindex_limit_must_not_be_negative(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _ShouldNotRun:
        def delay(self, **kwargs: Any) -> None:  # pragma: no cover - guard
            raise AssertionError("reindex_task.delay should not be called")

    monkeypatch.setattr(views, "reindex_task", _ShouldNotRun())

    response = api_client.post(
        "/api/reindex",
        {"source": "samples", "limit": -5},


def test_size_string_zero_is_rejected(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _should_not_run(request: SearchRequest) -> SearchResponse:  # pragma: no cover - guard
        raise AssertionError("provider should not be called")

    _install_provider(monkeypatch, _should_not_run, provider_name="opensearch")

    response = api_client.post(
        "/api/search",
        {"q": "foo", "mode": "literal", "size": "0"},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "limit must be a non-negative integer"
