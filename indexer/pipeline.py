from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional
from typing import Union
from .preprocess import preprocess_file

StrPath = Union[str, Path]


@dataclass(slots=True)
class IndexRecord:
    file_id: str
    path: str
    url: Optional[str]
    year: Optional[str]
    source: Optional[str]
    commands: List[str]
    content: str
    line_offsets: List[int]


def load_metadata(path: Path) -> Dict[str, dict]:
    metadata_path = path / "metadata.jsonl"
    if not metadata_path.exists():
        return {}

    metadata: Dict[str, dict] = {}
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            file_id = data.pop("file_id", None)
            if not file_id:
                continue
            metadata[file_id] = data
    return metadata


def discover_tex_files(root: Path) -> List[Path]:
    return sorted(root.rglob("*.tex"))


def iter_records(root: Path, *, limit: int | None = None) -> Iterator[IndexRecord]:
    metadata = load_metadata(root)
    tex_files = discover_tex_files(root)
    files_iter = tex_files if limit is None else tex_files[:limit]
    for path in files_iter:
        relative_path = path.relative_to(root).as_posix()
        meta = metadata.get(relative_path, {})
        processed = preprocess_file(path)
        commands = processed.commands
        record = IndexRecord(
            file_id=relative_path,
            path=relative_path,
            url=meta.get("url"),
            year=meta.get("year"),
            source=meta.get("source"),
            commands=commands,
            content=processed.content,
            line_offsets=processed.line_offsets,
        )
        yield record


def collect_records(root: Path, *, limit: int | None = None) -> List[IndexRecord]:
    return list(iter_records(root, limit=limit))


def ensure_root(path: StrPath) -> Path:
    path = Path(path)  # ★ ここで Path 化
    root = path.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Input directory '{path}' does not exist")
    if not root.is_dir():
        raise NotADirectoryError(f"Input path '{path}' is not a directory")
    return root
