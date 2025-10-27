from __future__ import annotations

import time
from collections.abc import Iterable, Sequence

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from opensearchpy import OpenSearch, helpers

from . import opensearch_client
from .snippets import build_snippet, find_match
from .types import IndexDocument, SearchHit, SearchRequest, SearchResponse

PROVIDER_REQUEST_TIMEOUT = 2


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
    def __init__(
        self, client: OpenSearch | None = None, index_name: str | None = None
    ) -> None:
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
                "line_offsets": list(doc.line_offsets or []),
            }
            for doc in documents
        )
        helpers.bulk(self.client, actions)

    def search(self, request: SearchRequest) -> SearchResponse:
        query = opensearch_client.build_search_body(request)
        offset = _resolve_offset(request)
        response = self.client.search(
            index=self.index_name,
            body=query,
            from_=offset,
            size=request.size,
            request_timeout=PROVIDER_REQUEST_TIMEOUT,
        )
        hits = _process_hits(response.get("hits", {}).get("hits", []), request)
        if len(hits) > request.size:
            hits = hits[: request.size]
        total = int(response.get("hits", {}).get("total", {}).get("value", 0))
        took_ms = int(response.get("took", 0))
        next_cursor = _build_next_cursor(offset, request.size, total)
        page = (
            request.page
            if request.cursor is None
            else max(offset // request.size + 1, 1)
        )
        return SearchResponse(
            hits=hits,
            total=total,
            took_provider_ms=took_ms,
            page=page,
            size=request.size,
            next_cursor=next_cursor,
        )


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
        matches: list[SearchHit] = []
        for doc in self._documents.values():
            if not _filters_match(request, doc):
                continue
            match = find_match(doc.content, request)
            if match is None:
                continue
            snippet = build_snippet(
                doc.content,
                match,
                context_lines=_snippet_lines(),
                mode=request.mode,
                query=request.query,
            )
            line_number = _resolve_line_number(doc.line_offsets, match.line_number)
            matches.append(
                SearchHit(
                    file_id=doc.file_id,
                    path=doc.path,
                    line=line_number,
                    snippet=snippet.snippet,
                    url=doc.url,
                    blocks=snippet.blocks,
                )
            )
        matches.sort(key=lambda hit: hit.path)
        offset = _resolve_offset(request)
        start = offset
        end = start + request.size
        slice_hits = matches[start:end]
        took_ms = int((time.monotonic() - start_time) * 1000)
        next_cursor = _build_next_cursor(offset, request.size, len(matches))
        page = (
            request.page
            if request.cursor is None
            else max(offset // request.size + 1, 1)
        )
        return SearchResponse(
            hits=slice_hits,
            total=len(matches),
            took_provider_ms=took_ms,
            page=page,
            size=request.size,
            next_cursor=next_cursor,
        )


def _process_hits(
    raw_hits: Sequence[dict[str, object]], request: SearchRequest
) -> list[SearchHit]:
    results: list[SearchHit] = []
    for raw in raw_hits:
        source = raw.get("_source", {}) or {}
        content = source.get("content", "")
        match = find_match(content, request)
        # 1st fallback: \ の有無を反転して再トライ（literal のときだけ）
        if match is None and request.mode == "literal":
            alt_q = (
                request.query[1:]
                if request.query.startswith("\\")
                else "\\" + request.query
            )
            alt_req = SearchRequest(
                query=alt_q,
                mode=request.mode,
                page=request.page,
                size=request.size,
                filters=request.filters,
            )
            match = find_match(content, alt_req)

        # 2nd fallback: それでも見つからなければ結果は捨てず、素朴スニペットを返す
        if match is not None:
            snippet_obj = build_snippet(
                content,
                match,
                context_lines=_snippet_lines(),
                mode=request.mode,
                query=request.query,
            )
            snippet_text = snippet_obj.snippet
            blocks = snippet_obj.blocks
            match_line = match.line_number
        else:
            # 先頭から数行をスニペットとして返す（見た目が途切れないように）
            lines = content.splitlines()
            head = lines[: max(1, _snippet_lines())]
            snippet_text = "\n".join(head)
            blocks = []
            match_line = 1  # 先頭行扱い

        line_offsets = source.get("line_offsets")
        line_number = _resolve_line_number(line_offsets, match_line)
        results.append(
            SearchHit(
                file_id=source.get("file_id", raw.get("_id", "")),
                path=source.get("path", ""),
                line=line_number,
                snippet=snippet_text,
                url=source.get("url", ""),
                blocks=blocks,
            )
        )
    return results


def _index_definition() -> dict[str, object]:
    return {
        "settings": {
            "index": {"max_ngram_diff": 20},
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
                    # ★ LaTeX コマンド抽出（\\iiint → iiint を増殖）
                    "tex_command_capture": {
                        "type": "pattern_capture",
                        "preserve_original": True,
                        "patterns": [r"\\\\([A-Za-z]+\\*?)"],  # \iiint, \foo*
                    },
                },
                "analyzer": {
                    # ★ 本文用。whitespace 分割＋小文字化＋コマンド抽出
                    "tex_analyzer": {
                        "type": "custom",
                        "tokenizer": "tex_tokenizer",
                        "filter": ["lowercase", "tex_command_capture"],
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
            },
        },
        "mappings": {
            "properties": {
                "file_id": {"type": "keyword"},
                "path": {"type": "keyword"},
                "url": {"type": "keyword"},
                "year": {"type": "keyword"},
                "source": {"type": "keyword"},
                "commands": {
                    "type": "keyword",  # ← ここは keyword のままでOK（後述の正規化で合わせる）
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
    return not (request.filters.get("source") and request.filters["source"] != source)


def get_index_definition() -> dict[str, object]:
    definition = _index_definition()
    definition["mappings"]["properties"]["line_offsets"] = {"type": "integer"}
    return definition


def _resolve_line_number(line_offsets: Iterable[int] | None, match_line: int) -> int:
    if not line_offsets:
        return match_line
    offsets_list = list(line_offsets)
    index = match_line - 1
    if 0 <= index < len(offsets_list):
        mapped = offsets_list[index]
        if isinstance(mapped, int) and mapped > 0:
            return mapped
    return match_line


def _snippet_lines() -> int:
    try:
        return settings.SEARCH_CONFIG["snippet_lines"]
    except (
        ImproperlyConfigured,
        AttributeError,
        KeyError,
    ):  # pragma: no cover - fallback for tests
        return 8


def _resolve_offset(request: SearchRequest) -> int:
    if request.cursor:
        try:
            offset = int(request.cursor)
        except (TypeError, ValueError):
            offset = 0
        return max(offset, 0)
    return max((request.page - 1) * request.size, 0)


def _build_next_cursor(offset: int, size: int, total: int) -> str | None:
    next_offset = offset + size
    if next_offset >= total:
        return None
    return str(next_offset)
