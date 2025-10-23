from __future__ import annotations

import pytest

from search.query import QueryValidationError, parse_payload


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
