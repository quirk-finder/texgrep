from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

SnippetTextKind = Literal["text"]
SnippetMathKind = Literal["math"]


@dataclass(slots=True)
class TextSnippetBlock:
    kind: SnippetTextKind = "text"
    html: str = ""


@dataclass(slots=True)
class MathSnippetBlock:
    kind: SnippetMathKind = "math"
    tex: str = ""
    display: bool = False
    marked: bool = False


SnippetBlock = TextSnippetBlock | MathSnippetBlock

SearchMode = Literal["literal", "regex"]


@dataclass(slots=True)
class SearchRequest:
    query: str
    mode: SearchMode
    filters: dict[str, str | None]
    page: int
    size: int
    cursor: str | None = None


@dataclass(slots=True)
class SearchHit:
    file_id: str
    path: str
    line: int
    url: str = ""
    snippet: str | None = None
    blocks: list[SnippetBlock] | None = None


@dataclass(slots=True)
class SearchResponse:
    hits: list[SearchHit]
    total: int
    took_provider_ms: int
    page: int
    size: int
    next_cursor: str | None = None


@dataclass(slots=True)
class IndexDocument:
    file_id: str
    path: str
    url: str
    year: str | None
    source: str | None
    content: str
    commands: Iterable[str] | None = None
    line_offsets: list[int] | None = None
