from __future__ import annotations

from ..backends import OpenSearchBackend
from ..types import SearchRequest, SearchResponse

_backend = OpenSearchBackend()


def search(request: SearchRequest) -> SearchResponse:
    return _backend.search(request)
