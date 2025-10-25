from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Iterable, List, Literal, Sequence, Tuple

from .query import (
    REGEX_TIMEOUT_SECONDS,
    decode_literal_query,
    decode_regex_query,
)
from .types import MathSnippetBlock, SearchMode, SearchRequest, SnippetBlock, TextSnippetBlock

MATH_ENVIRONMENTS: set[str] = {
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "multline",
    "multline*",
    "flalign",
    "flalign*",
}

VERBATIM_ENVIRONMENTS: set[str] = {
    "verbatim",
    "lstlisting",
    "minted",
    "filecontents",
}


@dataclass(slots=True)
class MatchResult:
    start: int
    end: int
    line_number: int


@dataclass(slots=True)
class Segment:
    kind: Literal["text", "math"]
    start: int
    end: int
    prefix_len: int = 0
    suffix_len: int = 0
    display: bool = False


@dataclass(slots=True)
class SnippetResult:
    snippet: str
    blocks: List[SnippetBlock]


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


def build_snippet(
    content: str,
    match: MatchResult,
    *,
    context_lines: int,
    mode: SearchMode,
    query: str,
) -> SnippetResult:
    segments = _split_into_segments(content)
    lines = content.splitlines()
    line_index = max(match.line_number - 1, 0)
    start_line = max(line_index - context_lines, 0)
    end_line = min(line_index + context_lines + 1, len(lines))

    snippet_start_offset = _offset_for_line(lines, start_line)
    snippet_end_offset = _offset_for_line(lines, end_line)
    if end_line >= len(lines):
        snippet_end_offset = len(content)

    snippet_start_offset, snippet_end_offset = _extend_to_full_segments(
        snippet_start_offset, snippet_end_offset, segments
    )

    snippet_text = content[snippet_start_offset:snippet_end_offset]

    highlight_spans = _compute_highlight_spans(snippet_text, mode, query)
    if not highlight_spans:
        fallback_start = max(match.start - snippet_start_offset, 0)
        fallback_end = max(
            min(match.end - snippet_start_offset, len(snippet_text)),
            fallback_start,
        )
        if fallback_end > fallback_start:
            highlight_spans = [(fallback_start, fallback_end)]

    legacy_snippet = _render_with_highlight(snippet_text, highlight_spans)

    blocks = _build_blocks(
        content,
        snippet_start_offset,
        snippet_end_offset,
        segments,
        highlight_spans,
    )

    return SnippetResult(snippet=legacy_snippet, blocks=blocks)


def _offset_for_line(lines: List[str], target_line: int) -> int:
    offset = 0
    for idx in range(min(target_line, len(lines))):
        offset += len(lines[idx]) + 1
    return offset


def _compute_highlight_spans(snippet_text: str, mode: SearchMode, query: str) -> List[Tuple[int, int]]:
    if not snippet_text:
        return []
    if mode == "literal":
        needle = decode_literal_query(query)
        if not needle:
            return []
        spans: List[Tuple[int, int]] = []
        start = 0
        while True:
            idx = snippet_text.find(needle, start)
            if idx == -1:
                break
            spans.append((idx, idx + len(needle)))
            start = idx + len(needle)
        return spans
    pattern_text = decode_regex_query(query)
    try:
        pattern = re.compile(pattern_text, flags=re.MULTILINE, timeout=REGEX_TIMEOUT_SECONDS)
    except TypeError:  # pragma: no cover - Python < 3.11 fallback
        pattern = re.compile(pattern_text, flags=re.MULTILINE)
    spans = []
    for match in pattern.finditer(snippet_text):
        start, end = match.span()
        if end > start:
            spans.append((start, end))
    return spans


def _build_blocks(
    content: str,
    snippet_start: int,
    snippet_end: int,
    segments: Sequence[Segment],
    highlight_spans: Sequence[Tuple[int, int]],
) -> List[SnippetBlock]:
    blocks: List[SnippetBlock] = []
    for segment in segments:
        if segment.end <= snippet_start or segment.start >= snippet_end:
            continue
        block_start = max(segment.start, snippet_start)
        block_end = min(segment.end, snippet_end)
        block_text = content[block_start:block_end]
        block_offset = block_start - snippet_start
        if segment.kind == "text":
            spans = _relative_spans(block_offset, len(block_text), highlight_spans)
            html_content = _render_with_highlight(block_text, spans)
            html_content = html_content.replace("\n", "<br />")
            blocks.append(TextSnippetBlock(html=html_content))
        else:
            prefix_len = max(segment.prefix_len - max(block_start - segment.start, 0), 0)
            suffix_len = max(segment.suffix_len - max(segment.end - block_end, 0), 0)
            math_content = block_text[prefix_len:len(block_text) - suffix_len or None]
            spans = _relative_spans(
                block_offset + prefix_len,
                len(math_content),
                highlight_spans,
            )
            rendered_tex = _render_math_with_highlight(math_content, spans)
            blocks.append(
                MathSnippetBlock(
                    tex=rendered_tex,
                    display=segment.display,
                    marked=bool(spans),
                )
            )
    return blocks


def _relative_spans(
    block_offset: int,
    block_length: int,
    highlight_spans: Sequence[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    block_end = block_offset + block_length
    results: List[Tuple[int, int]] = []
    for start, end in highlight_spans:
        local_start = max(start, block_offset)
        local_end = min(end, block_end)
        if local_end > local_start:
            results.append((local_start - block_offset, local_end - block_offset))
    return results


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


def _render_math_with_highlight(tex: str, spans: Iterable[Tuple[int, int]]) -> str:
    spans_list = sorted((start, end) for start, end in spans if end > start)
    if not spans_list:
        return tex
    rendered: List[str] = []
    cursor = 0
    for start, end in spans_list:
        if start > cursor:
            rendered.append(tex[cursor:start])
        rendered.append(r"\class{mjx-hl}{")
        rendered.append(tex[start:end])
        rendered.append("}")
        cursor = end
    if cursor < len(tex):
        rendered.append(tex[cursor:])
    return "".join(rendered)


def _split_into_segments(content: str) -> List[Segment]:
    segments: List[Segment] = []
    length = len(content)
    pos = 0
    text_start = 0

    while pos < length:
        if content.startswith("\\verb", pos):
            verb_end = _extract_verb(content, pos)
            if verb_end is not None:
                if text_start < pos:
                    segments.append(Segment("text", text_start, pos))
                segments.append(Segment("text", pos, verb_end))
                pos = verb_end
                text_start = pos
                continue

        if content.startswith("\\begin{", pos):
            env_name, env_end = _read_environment_name(content, pos + len("\\begin{"))
            if env_name:
                env_close = _find_environment_end(content, env_name, env_end)
                if env_close is not None:
                    if env_name in VERBATIM_ENVIRONMENTS:
                        if text_start < pos:
                            segments.append(Segment("text", text_start, pos))
                        segments.append(Segment("text", pos, env_close))
                        pos = env_close
                        text_start = pos
                        continue
                    if env_name in MATH_ENVIRONMENTS:
                        if text_start < pos:
                            segments.append(Segment("text", text_start, pos))
                        segments.append(
                            Segment(
                                "math",
                                start=pos,
                                end=env_close,
                                prefix_len=0,
                                suffix_len=0,
                                display=True,
                            )
                        )
                        pos = env_close
                        text_start = pos
                        continue

        if content.startswith("\\[", pos):
            closing = _find_math_delimiter(content, pos, "\\[", "\\]")
            if closing is not None:
                if text_start < pos:
                    segments.append(Segment("text", text_start, pos))
                segments.append(
                    Segment(
                        "math",
                        start=pos,
                        end=closing,
                        prefix_len=2,
                        suffix_len=2,
                        display=True,
                    )
                )
                pos = closing
                text_start = pos
                continue

        if content.startswith("\\(", pos):
            closing = _find_math_delimiter(content, pos, "\\(", "\\)")
            if closing is not None:
                if text_start < pos:
                    segments.append(Segment("text", text_start, pos))
                segments.append(
                    Segment(
                        "math",
                        start=pos,
                        end=closing,
                        prefix_len=2,
                        suffix_len=2,
                        display=False,
                    )
                )
                pos = closing
                text_start = pos
                continue

        if content.startswith("$$", pos) and not _is_escaped(content, pos):
            closing = _find_double_dollar(content, pos)
            if closing is not None:
                if text_start < pos:
                    segments.append(Segment("text", text_start, pos))
                segments.append(
                    Segment(
                        "math",
                        start=pos,
                        end=closing,
                        prefix_len=2,
                        suffix_len=2,
                        display=True,
                    )
                )
                pos = closing
                text_start = pos
                continue

        if content[pos] == "$" and not _is_escaped(content, pos):
            closing = _find_single_dollar(content, pos)
            if closing is not None:
                if text_start < pos:
                    segments.append(Segment("text", text_start, pos))
                segments.append(
                    Segment(
                        "math",
                        start=pos,
                        end=closing,
                        prefix_len=1,
                        suffix_len=1,
                        display=False,
                    )
                )
                pos = closing
                text_start = pos
                continue

        pos += 1

    if text_start < length:
        segments.append(Segment("text", text_start, length))

    return segments


def _extend_to_full_segments(
    snippet_start: int, snippet_end: int, segments: Sequence[Segment]
) -> Tuple[int, int]:
    extended_start = snippet_start
    extended_end = snippet_end
    for segment in segments:
        if segment.kind == "math" and segment.end > snippet_start and segment.start < snippet_end:
            extended_start = min(extended_start, segment.start)
            extended_end = max(extended_end, segment.end)
    return extended_start, max(extended_end, extended_start)


def _read_environment_name(text: str, start: int) -> Tuple[str | None, int]:
    end = text.find("}", start)
    if end == -1:
        return None, start
    name = text[start:end].strip()
    if not name:
        return None, start
    return name, end + 1


def _find_environment_end(text: str, name: str, pos: int) -> int | None:
    pattern = re.compile(r"\\(begin|end)\{" + re.escape(name) + r"\}")
    depth = 1
    while True:
        match = pattern.search(text, pos)
        if not match:
            return None
        if match.group(1) == "begin":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return match.end()
        pos = match.end()


def _find_math_delimiter(text: str, start: int, opening: str, closing: str) -> int | None:
    pos = start + len(opening)
    while True:
        idx = text.find(closing, pos)
        if idx == -1:
            return None
        if not _is_escaped(text, idx):
            return idx + len(closing)
        pos = idx + len(closing)


def _find_double_dollar(text: str, start: int) -> int | None:
    pos = start + 2
    while True:
        idx = text.find("$$", pos)
        if idx == -1:
            return None
        if not _is_escaped(text, idx):
            return idx + 2
        pos = idx + 2


def _find_single_dollar(text: str, start: int) -> int | None:
    pos = start + 1
    while True:
        idx = text.find("$", pos)
        if idx == -1:
            return None
        if not _is_escaped(text, idx):
            return idx + 1
        pos = idx + 1


def _extract_verb(text: str, start: int) -> int | None:
    pos = start + len("\\verb")
    if pos < len(text) and text[pos] == "*":
        pos += 1
    if pos >= len(text):
        return None
    delimiter = text[pos]
    if delimiter == "\n":
        return None
    pos += 1
    end = text.find(delimiter, pos)
    if end == -1:
        return None
    return end + 1


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    i = index - 1
    while i >= 0 and text[i] == "\\":
        backslashes += 1
        i -= 1
    return backslashes % 2 == 1
