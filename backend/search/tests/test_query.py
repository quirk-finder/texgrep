from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from search.query import MAX_PAGE_SIZE, QueryValidationError, parse_payload


def test_parse_literal_query():
    request = parse_payload({"q": r"\\newcommand", "mode": "literal"})
    assert request.query == r"\\newcommand"
    assert request.mode == "literal"
    assert request.page == 1
    assert request.size == 20


def test_parse_rejects_empty_query():
    with pytest.raises(QueryValidationError):
        parse_payload({"q": "   "})


def test_parse_regex_validated():
    request = parse_payload({"q": r"\\\w+", "mode": "regex"})
    assert request.mode == "regex"


def test_parse_rejects_invalid_regex():
    with pytest.raises(QueryValidationError):
        parse_payload({"q": "[", "mode": "regex"})


def test_parse_rejects_non_integer_page():
    with pytest.raises(QueryValidationError, match="Page must be an integer"):
        parse_payload({"q": "foo", "page": "abc"})


def test_parse_rejects_non_integer_size():
    with pytest.raises(QueryValidationError, match="Page size must be an integer"):
        parse_payload({"q": "foo", "size": "abc"})


_filters_strategy = st.dictionaries(
    st.sampled_from(["year", "source", "other"]),
    st.one_of(st.text(max_size=8), st.integers(-5, 5), st.none()),
    max_size=3,
)


_payload_strategy = st.fixed_dictionaries(
    {
        "q": st.text(max_size=260),
        "mode": st.one_of(
            st.just("literal"), st.just("regex"), st.text(max_size=8), st.none()
        ),
        "page": st.one_of(st.integers(-5, 10), st.text(max_size=5), st.none()),
        "size": st.one_of(st.integers(-5, 60), st.text(max_size=5), st.none()),
        "filters": st.one_of(_filters_strategy, st.text(max_size=10), st.none()),
        "cursor": st.one_of(st.text(max_size=10), st.integers(-5, 20), st.none()),
    }
)


@given(_payload_strategy)
def test_parse_payload_handles_arbitrary_input(payload: dict[str, object | None]) -> None:
    normalized = {k: v for k, v in payload.items() if v is not None}
    try:
        request = parse_payload(normalized)
    except QueryValidationError:
        return

    assert request.query
    assert request.mode in {"literal", "regex"}
    assert request.page >= 1
    assert 1 <= request.size <= MAX_PAGE_SIZE
    assert set(request.filters.keys()).issubset({"year", "source"})
