from __future__ import annotations

from pathlib import Path

import pytest

from indexer.build_index import _preprocess, build_index
from indexer.fetch_samples import SampleFile
from indexer.preprocess import PreprocessedFile


class StubService:
    def __init__(self) -> None:
        self.reset_called = 0
        self.indexed: list = []

    def reset_index(self) -> None:
        self.reset_called += 1

    def index_documents(self, documents):  # type: ignore[no-untyped-def]
        self.indexed = list(documents)


def test_build_index_passes_limit_to_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service = StubService()

    sample_path = tmp_path / "sample.tex"
    sample_path.write_text("\\begin{document}\\alpha\\end{document}", encoding="utf-8")
    sample = SampleFile(
        file_id="samples:1",
        path=sample_path,
        url="https://example.com/sample.tex",
        year="2023",
        source="samples",
    )

    captured: dict[str, int | None] = {}

    def _fake_fetch(workspace, limit=None):  # type: ignore[no-untyped-def]
        captured["limit"] = limit
        return [sample]

    monkeypatch.setattr("indexer.build_index.fetch_samples", _fake_fetch)

    documents = build_index(service, source="samples", limit=1)

    assert captured.get("limit") == 1
    assert service.reset_called == 1
    assert service.indexed
    assert documents[0].commands


def test_preprocess_fallback_extracts_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "fallback.tex"
    sample_path.write_text("ignored", encoding="utf-8")
    sample = SampleFile(
        file_id="samples:fallback",
        path=sample_path,
        url="http://example.com/fallback.tex",
        year=None,
        source="samples",
    )

    preprocessed = PreprocessedFile(
        path=sample_path,
        content="Contains \\Gamma and \\Delta",
        commands=[],
        line_offsets=[1],
    )

    monkeypatch.setattr("indexer.build_index.preprocess_file", lambda path: preprocessed)

    documents = _preprocess([sample])
    assert sorted(documents[0].commands) == ["Delta", "Gamma"]


def test_build_index_rejects_unknown_source(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StubService()

    with pytest.raises(ValueError):
        build_index(service, source="unknown")


def test_build_index_arxiv_not_implemented(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StubService()

    with pytest.raises(NotImplementedError):
        build_index(service, source="arxiv")
