from __future__ import annotations

from indexer.build_index import build_index

from search.query import parse_payload
from search.service import get_inmemory_service


def test_ingest_and_search_samples():
    service = get_inmemory_service()
    documents = build_index(service, source="samples", limit=3)
    assert documents

    request = parse_payload({"q": r"\\newcommand", "mode": "literal"})
    response = service.search(request)
    assert response.total >= 1
    assert any("<mark>\\newcommand" in hit.snippet for hit in response.hits)
    assert any(
        hit.blocks
        and any(
            "<mark>\\newcommand" in getattr(block, "html", "")
            for block in hit.blocks
            if block.kind == "text"
        )
        for hit in response.hits
    )
