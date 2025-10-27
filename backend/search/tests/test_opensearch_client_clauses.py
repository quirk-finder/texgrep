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
    ],
)
def test_is_safe_regex_variants(pattern, expected):
    # Arrange / Act
    result = is_safe_regex(pattern)

    # Assert
    assert result is expected


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

