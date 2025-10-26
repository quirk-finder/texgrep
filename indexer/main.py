from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

from .pipeline import IndexRecord, collect_records, ensure_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build search indexes for TeX sources")
    parser.add_argument("--input", required=True, type=Path, help="Path to the corpus root")
    parser.add_argument(
        "--provider",
        required=True,
        choices=["opensearch", "zoekt"],
        help="Index provider to target",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional limit on files")
    parser.add_argument(
        "--corpus",
        type=str,
        default=None,
        help="Corpus identifier (defaults to the input directory name)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = ensure_root(args.input)
    records = collect_records(root, limit=args.limit)

    if not records:
        print("No .tex files discovered; nothing to do")
        return

    if args.provider == "opensearch":
        index_with_opensearch(records)
    else:
        corpus = args.corpus or root.name
        index_with_zoekt(records, corpus=corpus, root=root)


def index_with_opensearch(records: Iterable[IndexRecord]) -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "texgrep.settings")
    import django
    django.setup()

    from backend.search.service import SearchService
    from backend.search.types import IndexDocument

    documents: List[IndexDocument] = []
    for record in records:
        # ★ 先頭のバックスラッシュを剥がす（\iiint → iiint）
        raw_cmds = list(record.commands or [])
        normalized_cmds = [(c[1:] if c.startswith("\\") else c) for c in raw_cmds]

        documents.append(
            IndexDocument(
                file_id=record.file_id,
                path=record.path,
                url=record.url or "",
                year=record.year,
                source=record.source or "samples",
                content=record.content,
                commands=normalized_cmds,   # ★ ここを差し替え
                line_offsets=record.line_offsets,
            )
        )

    service = SearchService()
    service.reset_index()
    service.index_documents(documents)


def index_with_zoekt(records: Iterable[IndexRecord], *, corpus: str, root: Path) -> None:
    zoekt_index = shutil.which("zoekt-index")
    if not zoekt_index:
        raise RuntimeError("zoekt-index executable not found in PATH")

    base_dir = Path("/data/repos") / corpus
    base_dir.mkdir(parents=True, exist_ok=True)

    try:
        path_key = root.resolve().relative_to(root.resolve().parent).as_posix()
    except ValueError:
        path_key = root.resolve().name

    repo_dir = base_dir / path_key
    repo_dir.mkdir(parents=True, exist_ok=True)

    for record in records:
        target = repo_dir / record.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(record.content, encoding="utf-8")

    _ensure_git_repo(repo_dir)
    _git(repo_dir, ["add", "--all"])
    status = _git(repo_dir, ["status", "--porcelain"], capture_output=True)
    if status.strip():
        _git(repo_dir, ["commit", "-m", "Update index"], check=False)

    subprocess.run([zoekt_index, "-incremental", str(repo_dir)], check=True)


def _ensure_git_repo(path: Path) -> None:
    if (path / ".git").exists():
        return
    _git(path, ["init"])
    _git(path, ["config", "user.email", "indexer@example.com"])
    _git(path, ["config", "user.name", "TexGrep Indexer"])


def _git(path: Path, args: List[str], capture_output: bool = False, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=path,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
    )
    if capture_output:
        output = result.stdout or ""
        return output
    return ""


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
