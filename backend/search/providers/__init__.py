from __future__ import annotations

import os
from collections.abc import Callable

from ..types import SearchRequest, SearchResponse
from .opensearch import search as _opensearch
from .zoekt import search as _zoekt

SearchProvider = Callable[[SearchRequest], SearchResponse]


def get_provider_name(name: str | None = None) -> str:
    provider_name = (
        (name or os.environ.get("SEARCH_PROVIDER", "opensearch")).strip().lower()
    )
    if not provider_name:
        provider_name = "opensearch"
    return provider_name


def get_provider(name: str):
    if name == "opensearch":
        return _opensearch
    if name == "zoekt":
        return _zoekt
    raise ValueError(f"Unknown provider: {name}")
