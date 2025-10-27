import pytest

from backend.search.opensearch_client import _literal_clause, build_search_body, is_safe_regex
from backend.search.types import SearchRequest


@pytest.mark.parametrize(
    "query, expected_norm, expected_alt",
    [
        (r"\\alpha", "alpha", "\\alpha"),
        ("foo", "foo", r"\foo"),
    ],
)
def test_literal_clause_should_variants(query, expected_norm, expected_alt):
    # Arrange
    # Act
    clause = _literal_clause(query)

    # Assert
    should_queries = [
        item["match_phrase"]["content"]["query"]
        for item in clause["bool"]["should"]
        if "match_phrase" in item
    ]
    assert expected_norm in should_queries  # normalized form used for commands search
    assert expected_alt in should_queries  # alternate with leading backslash toggled


@pytest.mark.parametrize(
    "pattern, expected",
    [
        ("abc", True),
        ("a+", False),  # unsafe quantifier should be rejected
        ("a" * 65, False),  # overly long patterns are rejected early
        (".*abc", False),  # leading wildcard rejected
        ("abc.*", False),  # trailing wildcard rejected
        ("a|b", False),  # alternation rejected
        ("[ab]", False),  # character class rejected
    ],
)
def test_is_safe_regex_variants(pattern, expected):
    # Arrange / Act
    result = is_safe_regex(pattern)

    # Assert
    assert result is expected


def test_literal_clause_includes_command_terms():
    clause = _literal_clause(r"\\gamma")

    should = clause["bool"]["should"]

    term_clause = next(item for item in should if "term" in item)
    assert term_clause == {"term": {"commands": "gamma"}}

    prefix_clause = next(item for item in should if "match" in item)
    assert prefix_clause == {
        "match": {"commands.prefix": {"query": "gamma", "operator": "and"}}
    }


def test_build_search_body_constructs_literal_should_clause():
    # Arrange
    request = SearchRequest(
        query="foo",
        mode="literal",
        filters={"year": "2023"},
        page=1,
        size=5,
    )

    # Act
    body = build_search_body(request)

    # Assert
    must_clause = body["query"]["bool"]["must"][0]
    should_clause = must_clause["bool"]["should"]
    should_queries = {
        item["match_phrase"]["content"]["query"]
        for item in should_clause
        if "match_phrase" in item
    }
    assert should_queries == {"foo", r"\foo"}  # literal and escaped variant searched
    assert body["query"]["bool"]["filter"] == [{"term": {"year": "2023"}}]


def test_build_search_body_uses_ngram_clause_for_unsafe_regex():
    request = SearchRequest(
        query="a" * 70,
        mode="regex",
        filters={"source": "samples"},
        page=1,
        size=5,
    )

    body = build_search_body(request)

    must_clause = body["query"]["bool"]["must"][0]
    assert "bool" in must_clause
    assert must_clause["bool"]["must"]

    highlight = body["highlight"]
    assert highlight["pre_tags"] == ["<mark>"]
    assert highlight["post_tags"] == ["</mark>"]
    assert highlight["fields"]["content"] == {
        "type": "fvh",
        "number_of_fragments": 0,
    }

    filters = body["query"]["bool"]["filter"]
    assert filters == [{"term": {"source": "samples"}}]


def test_build_search_body_filters_out_empty_values():
    request = SearchRequest(
        query="literal",
        mode="literal",
        filters={"source": "samples", "year": None},
        page=1,
        size=5,
    )

    body = build_search_body(request)

    filters = body["query"]["bool"]["filter"]
    assert filters == [{"term": {"source": "samples"}}]


def test_build_search_body_ngram_fallback_for_meta_regex():
    request = SearchRequest(
        query="a|b",
        mode="regex",
        filters={},
        page=1,
        size=5,
    )

    body = build_search_body(request)

    must_clause = body["query"]["bool"]["must"][0]
    terms = must_clause["bool"]["must"]
    assert {"term": {"content.ngram": "a"}} in terms
    assert {"term": {"content.ngram": "b"}} in terms

    highlight = body["highlight"]
    assert highlight["fields"]["content"]["type"] == "fvh"
    assert highlight["fields"]["content"]["number_of_fragments"] == 0

