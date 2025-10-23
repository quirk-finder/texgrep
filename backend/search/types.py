from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Literal, Optional

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
    snippet: str
    url: str


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
