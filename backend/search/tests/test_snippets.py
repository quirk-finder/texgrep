from __future__ import annotations

from search.query import parse_payload
from search.snippets import build_snippet, find_match
from search.types import MathSnippetBlock, TextSnippetBlock


def test_build_snippet_literal_highlights():
    content = "\\newcommand{\\R}{\\mathbb{R}}\nSome text."
    request = parse_payload({"q": r"\\newcommand", "mode": "literal"})
    match = find_match(content, request)
    assert match is not None
    result = build_snippet(
        content, match, context_lines=2, mode=request.mode, query=request.query
    )
    assert "<mark>\\newcommand" in result.snippet
    assert "Some text" in result.snippet
    assert any(
        isinstance(block, TextSnippetBlock) and "<mark>\\newcommand" in block.html
        for block in result.blocks
    )
    assert match.line_number == 1


def test_build_snippet_regex_highlights_multiple():
    content = "\\tikzpicture\n\\tikzstyle{my style}"
    request = parse_payload({"q": r"\\\\tikz\\w+", "mode": "regex"})
    match = find_match(content, request)
    assert match is not None
    result = build_snippet(
        content, match, context_lines=1, mode=request.mode, query=request.query
    )
    assert result.snippet.count("<mark>") >= 1
    assert any(
        isinstance(block, TextSnippetBlock) and block.html.count("<mark>") >= 1
        for block in result.blocks
    )


def test_build_snippet_math_blocks_highlight_inside_math():
    content = "Inline $\\sum_{i=1}^{n} a_i$ example"
    request = parse_payload({"q": "\\\\sum", "mode": "literal"})
    match = find_match(content, request)
    assert match is not None
    result = build_snippet(
        content, match, context_lines=0, mode=request.mode, query=request.query
    )
    math_blocks = [
        block for block in result.blocks if isinstance(block, MathSnippetBlock)
    ]
    assert len(math_blocks) == 1
    math_block = math_blocks[0]
    assert math_block.marked is True
    assert "\\class{mjx-hl}{\\sum" in math_block.tex
