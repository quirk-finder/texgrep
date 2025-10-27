from __future__ import annotations

from pathlib import Path

import subprocess

import pytest

from indexer import preprocess
from indexer.preprocess import _compute_line_offsets, _maybe_latexpand, preprocess_file


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


def test_maybe_latexpand_skips_when_tool_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "doc.tex"
    content = "\\alpha"
    path.write_text(content, encoding="utf-8")

    monkeypatch.setattr(preprocess.shutil, "which", lambda _name: None)

    expanded = _maybe_latexpand(path)
    assert expanded == content


def test_maybe_latexpand_falls_back_on_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "doc.tex"
    content = "\\beta"
    path.write_text(content, encoding="utf-8")

    monkeypatch.setattr(preprocess.shutil, "which", lambda _name: "/usr/bin/latexpand")

    def _raise(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "latexpand")

    monkeypatch.setattr(preprocess.subprocess, "run", _raise)

    expanded = _maybe_latexpand(path)
    assert expanded == content
