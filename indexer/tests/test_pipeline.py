from __future__ import annotations

import json
from pathlib import Path

from indexer.pipeline import collect_records, iter_records


def test_collect_records_from_empty_directory(tmp_path: Path) -> None:
    records = collect_records(tmp_path)
    assert records == []


def test_iter_records_uses_metadata_and_limit(tmp_path: Path) -> None:
    nested = tmp_path / "subdir"
    nested.mkdir()
    first = nested / "first.tex"
    second = nested / "second.tex"
    first.write_text("\\begin{document}\\alpha\\end{document}", encoding="utf-8")
    second.write_text("\\begin{document}\\beta\\end{document}", encoding="utf-8")

    metadata = tmp_path / "metadata.jsonl"
    metadata_lines = [
        {
            "file_id": "subdir/first.tex",
            "url": "https://example.com/first",
            "year": "2023",
            "source": "custom",
        },
        {"url": "missing id"},
    ]
    metadata.write_text(
        "\n".join(json.dumps(entry) for entry in metadata_lines) + "\n",
        encoding="utf-8",
    )

    records = list(iter_records(tmp_path, limit=1))
    assert len(records) == 1
    record = records[0]
    assert record.path == "subdir/first.tex"
    assert record.url == "https://example.com/first"
    assert record.year == "2023"
    assert record.source == "custom"
    assert "\\alpha" in record.commands
