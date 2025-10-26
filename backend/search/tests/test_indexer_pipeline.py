from __future__ import annotations

from pathlib import Path

from search.query import parse_payload
from search.service import get_inmemory_service

from indexer.pipeline import collect_records


def test_commands_are_searchable(tmp_path: Path) -> None:
    sample = tmp_path / "example.tex"
    sample.write_text(
        "\\documentclass{article}\n"
        "\\newcommand{\\triple}{\\iiint}\n"
        "\\begin{document}\n"
        "The operator $\\triple$ expands to $\\iiint$.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    records = collect_records(tmp_path)
    assert len(records) == 1
    record = records[0]
    assert "\\triple" in record.commands
    assert "\\iiint" in record.commands

    service = get_inmemory_service()
    from backend.search.types import IndexDocument

    service.index_documents(
        [
            IndexDocument(
                file_id=record.file_id,
                path=record.path,
                url=record.url or "",
                year=record.year,
                source=record.source,
                content=record.content,
                commands=record.commands,
                line_offsets=record.line_offsets,
            )
        ]
    )

    response = service.search(parse_payload({"q": r"\\triple", "mode": "literal"}))
    assert response.total == 1
    assert response.hits[0].line == 2

    response_double = service.search(parse_payload({"q": r"\\iiint", "mode": "literal"}))
    assert response_double.total == 1
    assert any("\\iiint" in hit.snippet for hit in response_double.hits)
