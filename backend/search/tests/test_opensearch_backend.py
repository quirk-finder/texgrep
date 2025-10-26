from __future__ import annotations

from dataclasses import dataclass

from search.backends import OpenSearchBackend, get_index_definition
from search.query import decode_literal_query, parse_payload


class FakeIndices:
    def exists(self, index: str) -> bool:  # pragma: no cover - not used in tests
        return False

    def close(self, index: str) -> None:  # pragma: no cover - helper stub
        raise NotImplementedError


@dataclass
class FakeClient:
    indices: FakeIndices

    def __post_init__(self) -> None:
        self.last_body: dict | None = None

    def search(self, *, index: str, body: dict, from_: int, size: int) -> dict:
        self.last_body = body
        return {
            "hits": {
                "hits": [
                    {
                        "_id": "doc-1",
                        "_source": {
                            "file_id": "doc-1",
                            "path": "sections/example.tex",
                            "url": "http://example.test/doc-1",
                            "content": "First line\n\\iiint_{a}^{b} f(x) dx\nThird line",
                        },
                    }
                ],
                "total": {"value": 1},
            },
            "took": 12,
        }


def test_index_definition_preserves_backslash_and_command_prefix() -> None:
    definition = get_index_definition()
    analysis = definition["settings"]["analysis"]
    tokenizer = analysis["tokenizer"]["tex_tokenizer"]
    assert tokenizer["pattern"] == "\\s+"

    command_edge = analysis["filter"]["command_edge"]
    assert command_edge == {"type": "edge_ngram", "min_gram": 1, "max_gram": 15}

    content = definition["mappings"]["properties"]["content"]
    assert content["term_vector"] == "with_positions_offsets"
    assert "ngram" in content["fields"]

    assert "line_offsets" in definition["mappings"]["properties"]


def test_literal_search_preserves_backslash_and_highlighting() -> None:
    client = FakeClient(indices=FakeIndices())
    backend = OpenSearchBackend(client=client, index_name="tex")
    request = parse_payload({"q": r"\\iiint", "mode": "literal", "page": 1, "size": 5})

    response = backend.search(request)

    assert client.last_body is not None
    must_clause = client.last_body["query"]["bool"]["must"][0]
    should_clauses = must_clause["bool"]["should"]
    phrase_clause = next(item for item in should_clauses if "match_phrase" in item)
    assert phrase_clause["match_phrase"]["content"]["query"] == decode_literal_query(request.query)
    highlight = client.last_body["highlight"]["fields"]["content"]
    assert highlight["type"] == "fvh"

    assert response.total == 1
    hit = response.hits[0]
    assert hit.line == 2
    assert "<mark>\\iiint</mark>_{a}^{b}" in hit.snippet
    assert "Third line" in hit.snippet
    assert hit.blocks is not None
    assert any(
        "<mark>\\iiint" in getattr(block, "html", "")
        for block in hit.blocks
        if block.kind == "text"
    )
