from __future__ import annotations

from search.query import parse_payload
from search.snippets import build_snippet, find_match


def test_build_snippet_literal_highlights():
    content = "\\newcommand{\\R}{\\mathbb{R}}\nSome text."
    request = parse_payload({"q": r"\\newcommand", "mode": "literal"})
    match = find_match(content, request)
    assert match is not None
    snippet = build_snippet(content, match, context_lines=2, mode=request.mode, query=request.query)
    assert "<mark>\\newcommand" in snippet
    assert "Some text" in snippet
    assert match.line_number == 1


def test_build_snippet_regex_highlights_multiple():
    content = "\\tikzpicture\n\\tikzstyle{my style}"
    request = parse_payload({"q": r"\\\\tikz\\w+", "mode": "regex"})
    match = find_match(content, request)
    assert match is not None
    snippet = build_snippet(content, match, context_lines=1, mode=request.mode, query=request.query)
    assert snippet.count("<mark>") >= 1
