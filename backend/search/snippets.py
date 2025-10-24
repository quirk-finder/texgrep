from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from .query import REGEX_TIMEOUT_SECONDS, decode_literal_query, decode_regex_query
from .types import SearchMode, SearchRequest


@dataclass(slots=True)
class MatchResult:
    start: int
    end: int
    line_number: int


def find_match(content: str, request: SearchRequest) -> MatchResult | None:
    if request.mode == "literal":
        needle = decode_literal_query(request.query)
        start = content.find(needle)
        if start == -1:
            return None
        end = start + len(needle)
    else:
        pattern_text = decode_regex_query(request.query)
        try:
            pattern = re.compile(pattern_text, flags=re.MULTILINE, timeout=REGEX_TIMEOUT_SECONDS)
        except TypeError:  # pragma: no cover - Python < 3.11 fallback
            pattern = re.compile(pattern_text, flags=re.MULTILINE)
        match = pattern.search(content)
        if not match:
            return None
        start, end = match.span()

    line_number = content.count("\n", 0, start) + 1
    return MatchResult(start=start, end=end, line_number=line_number)


def build_snippet(content: str, match: MatchResult, *, context_lines: int, mode: SearchMode, query: str) -> str:
    lines = content.splitlines()
    line_index = max(match.line_number - 1, 0)
    start_line = max(line_index - context_lines, 0)
    end_line = min(line_index + context_lines + 1, len(lines))

    snippet_lines = lines[start_line:end_line]
    snippet_text = "\n".join(snippet_lines)

    snippet_start_offset = _offset_for_line(lines, start_line)
    highlight_start = max(match.start - snippet_start_offset, 0)
    highlight_end = max(min(match.end - snippet_start_offset, len(snippet_text)), highlight_start)

    if highlight_start == highlight_end:
        highlight_spans: List[Tuple[int, int]] = []
    else:
        highlight_spans = _extend_highlight(snippet_text, query, mode, highlight_start, highlight_end)

    return _render_with_highlight(snippet_text, highlight_spans)


def _offset_for_line(lines: List[str], target_line: int) -> int:
    offset = 0
    for idx in range(target_line):
        offset += len(lines[idx]) + 1
    return offset


def _extend_highlight(snippet_text: str, query: str, mode: SearchMode, start: int, end: int) -> List[Tuple[int, int]]:
    if mode == "literal":
        return [(start, end)]
    pattern_text = decode_regex_query(query)
    pattern = re.compile(pattern_text, flags=re.MULTILINE)
    spans: List[Tuple[int, int]] = []
    for match in pattern.finditer(snippet_text):
        spans.append(match.span())
    if not spans:
        spans.append((start, end))
    return spans


def _render_with_highlight(snippet_text: str, spans: Iterable[Tuple[int, int]]) -> str:
    spans_list = sorted((start, end) for start, end in spans if end > start)
    if not spans_list:
        return html.escape(snippet_text)

    rendered: List[str] = []
    cursor = 0
    for start, end in spans_list:
        if start > cursor:
            rendered.append(html.escape(snippet_text[cursor:start]))
        rendered.append("<mark>")
        rendered.append(html.escape(snippet_text[start:end]))
        rendered.append("</mark>")
        cursor = end
    if cursor < len(snippet_text):
        rendered.append(html.escape(snippet_text[cursor:]))
    return "".join(rendered)
