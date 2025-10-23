from __future__ import annotations

import re

import pytest

from search import query
from search.query import QueryValidationError


def test_validate_regex_timeout(monkeypatch):
    def fake_compile(pattern, flags=0, timeout=None):  # type: ignore[override]
        raise TimeoutError

    monkeypatch.setattr(re, "compile", fake_compile)
    with pytest.raises(QueryValidationError) as exc:
        query.validate_regex(r"a+")
    assert "timed out" in str(exc.value)
