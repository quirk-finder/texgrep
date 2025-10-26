from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Literal, Optional


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


@dataclass(slots=True)
class SearchHit:
    file_id: str
    path: str
    line: int
    url: str
    snippet: Optional[str] = None
    blocks: Optional[List[SnippetBlock]] = None


@dataclass(slots=True)
class SearchResponse:
    hits: List[SearchHit]
    total: int
    took_ms: int


@dataclass(slots=True)
class IndexDocument:
    file_id: str
    path: str
    url: str
    year: Optional[str]
    source: Optional[str]
    content: str
    commands: Optional[Iterable[str]] = None
    line_offsets: Optional[List[int]] = None
