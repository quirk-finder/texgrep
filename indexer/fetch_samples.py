from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

SAMPLE_DATA_DIR = Path(__file__).resolve().parent / "sample_corpus"


@dataclass(slots=True)
class SampleFile:
    file_id: str
    path: Path
    url: str
    year: str | None
    source: str


def fetch_samples(target_dir: Path, *, limit: int | None = None) -> List[SampleFile]:
    target_dir.mkdir(parents=True, exist_ok=True)
    samples: List[SampleFile] = []
    available = sorted(SAMPLE_DATA_DIR.glob("*.tex"))
    if limit:
        available = available[:limit]
    for path in available:
        destination = target_dir / path.name
        shutil.copy(path, destination)
        samples.append(
            SampleFile(
                file_id=_hash_id("samples", path.name),
                path=destination,
                url=f"https://example.com/samples/{path.name}",
                year=None,
                source="samples",
            )
        )
    return samples


def _hash_id(prefix: str, name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"
