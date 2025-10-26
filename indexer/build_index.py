from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Iterable, List

from search.service import SearchService
from search.types import IndexDocument

from .fetch_samples import SampleFile, fetch_samples
from .preprocess import preprocess_file


def build_index(service: SearchService, *, source: str, limit: int | None = None) -> List[IndexDocument]:
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        if source == "samples":
            fetched = fetch_samples(workspace, limit=limit)
        elif source == "arxiv":
            raise NotImplementedError("ArXiv ingestion is not implemented in the MVP")
        else:
            raise ValueError(f"Unknown source '{source}'")

        documents = _preprocess(fetched)
        service.reset_index()
        service.index_documents(documents)
        return documents


def _preprocess(samples: Iterable[SampleFile]) -> List[IndexDocument]:
    documents: List[IndexDocument] = []
    for sample in samples:
        processed = preprocess_file(sample.path)
        cmds = list(processed.commands or [])
        if not cmds:
            cmds = sorted(set(re.findall(r'\\([A-Za-z]+)', processed.content)))
        documents.append(
            IndexDocument(
                file_id=sample.file_id,
                path=str(sample.path),
                url=sample.url,
                year=sample.year,
                source=sample.source,
                content=processed.content,
                commands=cmds,
                line_offsets=processed.line_offsets,
            )
        )
    return documents
