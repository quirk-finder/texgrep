from __future__ import annotations

import pytest

from search.providers import get_provider, get_provider_name


def test_get_provider_name_prefers_explicit_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "zoekt")
    assert get_provider_name(" OpenSearch ") == "opensearch"


def test_get_provider_name_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    monkeypatch.setenv("SEARCH_PROVIDER", "ZoEkt")
    assert get_provider_name() == "zoekt"


def test_get_provider_name_defaults_to_opensearch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "  ")
    assert get_provider_name(None) == "opensearch"


def test_get_provider_returns_known_callables() -> None:
    assert callable(get_provider("opensearch"))
    assert callable(get_provider("zoekt"))


def test_get_provider_raises_for_unknown_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    with pytest.raises(ValueError):
        get_provider("unknown")
