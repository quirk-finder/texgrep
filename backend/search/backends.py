from __future__ import annotations

import time
from typing import Iterable, List, Sequence

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from opensearchpy import OpenSearch, helpers

from . import opensearch_client
from .snippets import build_snippet, find_match
from .types import IndexDocument, SearchHit, SearchRequest, SearchResponse


class SearchBackendProtocol:
    def search(self, request: SearchRequest) -> SearchResponse:
        raise NotImplementedError

    def index_documents(self, documents: Iterable[IndexDocument]) -> None:
        raise NotImplementedError

    def delete_index(self) -> None:
        raise NotImplementedError

    def create_index(self) -> None:
        raise NotImplementedError


class OpenSearchBackend(SearchBackendProtocol):
    def __init__(self, client: OpenSearch | None = None, index_name: str | None = None) -> None:
        self.client = client or opensearch_client.create_client()
        self.index_name = index_name or settings.OPENSEARCH_INDEX

    def create_index(self) -> None:
        if self.client.indices.exists(index=self.index_name):
            return
        self.client.indices.create(index=self.index_name, body=get_index_definition())

    def delete_index(self) -> None:
        if self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)

    def index_documents(self, documents: Iterable[IndexDocument]) -> None:
        actions = (
            {
                "_op_type": "index",
                "_index": self.index_name,
                "_id": doc.file_id,
                "file_id": doc.file_id,
                "path": doc.path,
                "url": doc.url,
                "year": doc.year,
                "source": doc.source,
                "content": doc.content,
                "commands": list(doc.commands or []),
            }
            for doc in documents
        )
        helpers.bulk(self.client, actions)

    def search(self, request: SearchRequest) -> SearchResponse:
        query = opensearch_client.build_search_body(request)
        start = (request.page - 1) * request.size
        response = self.client.search(
            index=self.index_name,
            body=query,
            from_=start,
            size=request.size,
        )
        hits = _process_hits(response.get("hits", {}).get("hits", []), request)
        total = int(response.get("hits", {}).get("total", {}).get("value", 0))
        took_ms = int(response.get("took", 0))
        return SearchResponse(hits=hits, total=total, took_ms=took_ms)


class InMemorySearchBackend(SearchBackendProtocol):
    def __init__(self) -> None:
        self._documents: dict[str, IndexDocument] = {}

    def create_index(self) -> None:  # pragma: no cover - nothing to do
        self._documents.clear()

    def delete_index(self) -> None:  # pragma: no cover - nothing to do
        self._documents.clear()

    def index_documents(self, documents: Iterable[IndexDocument]) -> None:
        for doc in documents:
            self._documents[doc.file_id] = doc

    def search(self, request: SearchRequest) -> SearchResponse:
        start_time = time.monotonic()
        matches: List[SearchHit] = []
        for doc in self._documents.values():
            if not _filters_match(request, doc):
                continue
            match = find_match(doc.content, request)
            if not match:
                continue
            snippet = build_snippet(
                doc.content,
                match,
                context_lines=_snippet_lines(),
                mode=request.mode,
                query=request.query,
            )
            matches.append(
                SearchHit(
                    file_id=doc.file_id,
                    path=doc.path,
                    line=match.line_number,
                    snippet=snippet.snippet,
                    url=doc.url,
                    blocks=snippet.blocks,
                )
            )
        matches.sort(key=lambda hit: hit.path)
        start = (request.page - 1) * request.size
        end = start + request.size
        slice_hits = matches[start:end]
        took_ms = int((time.monotonic() - start_time) * 1000)
        return SearchResponse(hits=slice_hits, total=len(matches), took_ms=took_ms)


def _process_hits(raw_hits: Sequence[dict], request: SearchRequest) -> List[SearchHit]:
    results: List[SearchHit] = []
    for raw in raw_hits:
        source = raw.get("_source", {})
        content = source.get("content", "")
        match = find_match(content, request)
        if not match:
            continue
        snippet = build_snippet(
            content,
            match,
            context_lines=_snippet_lines(),
            mode=request.mode,
            query=request.query,
        )
        results.append(
            SearchHit(
                file_id=source.get("file_id", raw.get("_id", "")),
                path=source.get("path", ""),
                line=match.line_number,
                snippet=snippet.snippet,
                url=source.get("url", ""),
                blocks=snippet.blocks,
            )
        )
    return results


def _index_definition() -> dict:
    return {
        "settings": {
            "index": {
                # ngram/edge_ngram の (max_gram - min_gram) 許容差
                "max_ngram_diff": 20
            },
            "analysis": {
                "tokenizer": {
                    "tex_tokenizer": {
                        "type": "pattern",
                        "pattern": r"\s+",
                    }
                },
                "filter": {
                    "command_edge": {
                        "type": "edge_ngram",
                        "min_gram": 1,
                        "max_gram": 15,
                    },
                    "tex_ngram": {
                        "type": "ngram",
                        "min_gram": 2,
                        "max_gram": 15,
                    },
                },
                "analyzer": {
                    "tex_analyzer": {
                        "type": "custom",
                        "tokenizer": "tex_tokenizer",
                        "filter": [],
                    },
                    "command_prefix": {
                        "type": "custom",
                        "tokenizer": "keyword",
                        "filter": ["command_edge"],
                    },
                    "tex_ngram_analyzer": {
                        "type": "custom",
                        "tokenizer": "tex_tokenizer",
                        "filter": ["tex_ngram"],
                    },
                },
            }
        },
        "mappings": {
            "properties": {
                "file_id": {"type": "keyword"},
                "path": {"type": "keyword"},
                "url": {"type": "keyword"},
                "year": {"type": "keyword"},
                "source": {"type": "keyword"},
                "commands": {
                    "type": "keyword",
                    "fields": {
                        "prefix": {
                            "type": "text",
                            "analyzer": "command_prefix",
                        }
                    },
                },
                "content": {
                    "type": "text",
                    "analyzer": "tex_analyzer",
                    "search_analyzer": "tex_analyzer",
                    "term_vector": "with_positions_offsets",
                    "fields": {
                        "ngram": {
                            "type": "text",
                            "analyzer": "tex_ngram_analyzer",
                        }
                    },
                },
            }
        },
    }


def _filters_match(request: SearchRequest, doc: IndexDocument) -> bool:
    year = doc.year or ""
    source = doc.source or ""
    if request.filters.get("year") and request.filters["year"] != year:
        return False
    if request.filters.get("source") and request.filters["source"] != source:
        return False
    return True


def get_index_definition() -> dict:
    return _index_definition()


def _snippet_lines() -> int:
    try:
        return settings.SEARCH_CONFIG["snippet_lines"]
    except (ImproperlyConfigured, AttributeError, KeyError):  # pragma: no cover - fallback for tests
        return 8
