from __future__ import annotations

from pathlib import Path

from indexer.preprocess import _compute_line_offsets, preprocess_file


def test_preprocess_file_extracts_commands_and_offsets(tmp_path: Path) -> None:
    path = tmp_path / "sample.tex"
    content = (
        "% comment should be removed\r\n"
        "\\alpha\r\n"
        "\r\n"
        "\t\\beta% inline comment\r\n"
        "text line\r\n"
    )
    path.write_bytes(content.encode("utf-8"))

    processed = preprocess_file(path)

    assert processed.commands == ["\\alpha", "\\beta"]
    assert processed.content.splitlines() == [
        "",
        "\\alpha",
        "",
        "\t\\beta",
        "text line",
    ]
    assert processed.line_offsets == [1, 2, 3, 4, 5]


def test_compute_line_offsets_handles_insertions() -> None:
    original = ["one", "two"]
    processed = ["inserted", "one", "two"]
    offsets = _compute_line_offsets(original, processed)
    assert offsets == [1, 1, 2]
