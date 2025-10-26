from __future__ import annotations

import os
from typing import Callable

from django.core.exceptions import ImproperlyConfigured

from ..types import SearchRequest, SearchResponse

SearchProvider = Callable[[SearchRequest], SearchResponse]


def get_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.environ.get("SEARCH_PROVIDER", "opensearch")).strip().lower()
    if not provider_name:
        provider_name = "opensearch"

    if provider_name == "opensearch":
        from .opensearch import search as search_impl

        return search_impl
    if provider_name == "zoekt":
        from .zoekt import search as search_impl

        return search_impl

    raise ImproperlyConfigured(f"Unknown search provider: {provider_name}")
