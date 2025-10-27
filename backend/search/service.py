from __future__ import annotations

from typing import Protocol

from .backends import InMemorySearchBackend, OpenSearchBackend, SearchBackendProtocol
from .types import IndexDocument, SearchRequest, SearchResponse


class SearchService:
    def __init__(self, backend: SearchBackendProtocol | None = None) -> None:
        self.backend = backend or OpenSearchBackend()

    def search(self, request: SearchRequest) -> SearchResponse:
        return self.backend.search(request)

    def index_documents(self, documents: list[IndexDocument]) -> None:
        self.backend.index_documents(documents)

    def ensure_index(self) -> None:
        self.backend.create_index()

    def reset_index(self) -> None:
        self.backend.delete_index()
        self.backend.create_index()


class SearchServiceFactory(Protocol):
    def __call__(self) -> SearchService: ...


def get_search_service() -> SearchService:
    return SearchService()


def get_inmemory_service() -> SearchService:
    return SearchService(InMemorySearchBackend())
