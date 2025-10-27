from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest
from indexer.fetch_samples import SampleFile

import search.service as service_mod
from search import tasks
from search.backends import SearchBackendProtocol
from search.query import decode_literal_query, parse_payload
from search.service import SearchService
from search.types import IndexDocument, SearchHit, SearchRequest, SearchResponse


@dataclass
class RecordingOpenSearchBackend(SearchBackendProtocol):
    documents: list[IndexDocument]

    def __init__(self) -> None:
        self.documents = []
        self._created = 0
        self._deleted = 0

    def create_index(self) -> None:
        self._created += 1

    def delete_index(self) -> None:
        self._deleted += 1
        self.documents.clear()

    def index_documents(self, documents: Iterable[IndexDocument]) -> None:
        self.documents = list(documents)

    def search(self, request: SearchRequest) -> SearchResponse:
        if request.mode == "literal":
            literal = decode_literal_query(request.query)
            norm = literal.lstrip("\\")
        else:
            norm = request.query
        hits: list[SearchHit] = []
        for doc in self.documents:
            commands = list(doc.commands or [])
            if norm in commands:
                hits.append(
                    SearchHit(
                        file_id=doc.file_id,
                        path=doc.path,
                        line=1,
                        url=doc.url,
                        snippet=doc.content,
                    )
        )
        return SearchResponse(
            hits=hits,
            total=len(hits),
            took_provider_ms=1,
            page=request.page,
            size=request.size,
            next_cursor=None,
        )


def _configure_reindex_service(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[RecordingOpenSearchBackend, SearchService]:
    backend = RecordingOpenSearchBackend()
    service = SearchService(backend=backend)

    monkeypatch.setattr(service_mod.SearchService, "reset_index", lambda self: None)
    monkeypatch.setattr(tasks, "get_search_service", lambda: service)

    try:
        import search.tasks as tasks_alias

        monkeypatch.setattr(tasks_alias, "get_search_service", lambda: service)
    except ImportError:
        pass

    return backend, service


def test_reindex_task_makes_literal_commands_searchable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    backend, service = _configure_reindex_service(monkeypatch)

    sample_path = tmp_path / "example.tex"
    sample_path.write_text(
        "\\documentclass{article}\n"
        "\\newcommand{\\triple}{\\iiint}\n"
        "\\begin{document}\n"
        "The operator $\\triple$ expands to $\\iiint$.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    sample = SampleFile(
        file_id="samples:example",
        path=sample_path,
        url="https://example.com/samples/example.tex",
        year="2024",
        source="samples",
    )
    monkeypatch.setattr(
        "indexer.build_index.fetch_samples", lambda workspace, limit=None: [sample]
    )

    # reindex_task の呼び出し先もモジュール経由に変更
    result = tasks.reindex_task()
    assert result == {"count": 1}

    assert backend.documents
    commands = list(backend.documents[0].commands or [])
    assert "triple" in commands
    assert all(not c.startswith("\\") for c in commands)

    response = service.search(
        parse_payload({"q": r"\\triple", "mode": "literal", "page": 1, "size": 5})
    )
    assert response.total == 1


def test_reindex_task_respects_limit_argument(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    backend, _ = _configure_reindex_service(monkeypatch)

    sample_path = tmp_path / "limited.tex"
    sample_path.write_text("\\begin{document}Limit test\\end{document}", encoding="utf-8")
    sample = SampleFile(
        file_id="samples:limited",
        path=sample_path,
        url="https://example.com/samples/limited.tex",
        year="2024",
        source="samples",
    )

    captured: dict[str, int | None] = {}

    def _fake_fetch(workspace, limit=None):  # type: ignore[no-untyped-def]
        captured["limit"] = limit
        return [sample]

    monkeypatch.setattr("indexer.build_index.fetch_samples", _fake_fetch)

    result = tasks.reindex_task(limit=1)
    assert result == {"count": 1}
    assert captured.get("limit") == 1
    assert backend.documents
