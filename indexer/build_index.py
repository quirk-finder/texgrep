from __future__ import annotations

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
        documents.append(
            IndexDocument(
                file_id=sample.file_id,
                path=str(sample.path),
                url=sample.url,
                year=sample.year,
                source=sample.source,
                content=processed.content,
                commands=processed.commands,
                line_offsets=processed.line_offsets,
            )
        )
    return documents
