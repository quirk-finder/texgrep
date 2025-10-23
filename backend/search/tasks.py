from __future__ import annotations

import structlog
from celery import shared_task

from indexer.build_index import build_index

from .service import get_search_service

logger = structlog.get_logger(__name__)


@shared_task(name="search.tasks.reindex_task")
def reindex_task(*, source: str = "samples", limit: int | None = None) -> dict:
    service = get_search_service()
    logger.info("reindex.start", source=source, limit=limit)
    documents = build_index(service, source=source, limit=limit)
    logger.info("reindex.complete", count=len(documents))
    return {"count": len(documents)}
