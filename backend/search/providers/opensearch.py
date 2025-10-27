from __future__ import annotations

from ..backends import OpenSearchBackend
from ..types import SearchRequest, SearchResponse

_backend: OpenSearchBackend | None = None


def _get_backend() -> OpenSearchBackend:
    global _backend
    if _backend is None:
        _backend = OpenSearchBackend()
    return _backend


def search(request: SearchRequest) -> SearchResponse:
    return _get_backend().search(request)
