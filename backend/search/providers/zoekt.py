from __future__ import annotations

import json
import os
import time
from typing import List, Sequence
from urllib import parse, request as urllib_request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ..query import decode_literal_query
from ..snippets import MatchResult, build_snippet, find_match
from ..types import SearchHit, SearchRequest, SearchResponse

ZOEKT_URL_ENV = "ZOEKT_URL"
DEFAULT_ZOEKT_URL = "http://zoekt:6070"
DEFAULT_TIMEOUT = 2.0


def search(request: SearchRequest) -> SearchResponse:
    base_url = os.environ.get(ZOEKT_URL_ENV, DEFAULT_ZOEKT_URL).rstrip("/")
    search_url = f"{base_url}/api/search"
    start = time.monotonic()

    offset = _resolve_offset(request)
    payload = _build_query_payload(request, offset)
    data = _http_post(search_url, payload)
    stats = data.get("Stats", {}) or {}
    file_matches: Sequence[dict] = data.get("FileMatches", []) or []
    hits = _process_file_matches(base_url, file_matches, request)

    took_ms = _extract_duration(stats, data, start)
    total = _extract_total(stats, len(hits))
    next_cursor = _build_next_cursor(offset, request.size, total)
    page = request.page if request.cursor is None else max(offset // request.size + 1, 1)
    return SearchResponse(
        hits=hits,
        total=total,
        took_provider_ms=took_ms,
        page=page,
        size=request.size,
        next_cursor=next_cursor,
    )


def _build_query_payload(request: SearchRequest, offset: int) -> dict:
    literal = decode_literal_query(request.query)
    size = request.size
    query: dict[str, object] = {
        "query": {
            "type": "substring",
            "pattern": literal,
            "caseSensitive": True,
        },
        "num": size,
        "offset": offset,
    }
    # Zoekt does not yet support structured filters in this integration; they can be
    # layered in via Repo/Branch constraints later.
    return query


def _process_file_matches(
    base_url: str,
    matches: Sequence[dict],
    request: SearchRequest,
) -> List[SearchHit]:
    results: List[SearchHit] = []
    for file_match in matches:
        content = _extract_content(base_url, file_match)
        if content is None:
            continue
        path = file_match.get("FileName", "") or ""
        repository = file_match.get("Repository", "") or ""
        checksum = file_match.get("Checksum")
        file_id = checksum or f"{repository}:{path}" if repository else path
        url = file_match.get("URL", "") or ""
        line_matches = file_match.get("LineMatches", []) or []
        for raw_line in line_matches:
            line_number = int(raw_line.get("LineNumber", 0) or 0)
            preview = raw_line.get("Line", "") or ""
            match = _build_match(content, line_number, preview, request)
            if match is None:
                continue
            snippet = build_snippet(
                content,
                match,
                context_lines=_snippet_lines(),
                mode=request.mode,
                query=request.query,
            )
            results.append(
                SearchHit(
                    file_id=file_id,
                    path=path,
                    line=match.line_number,
                    snippet=snippet.snippet,
                    url=url,
                    blocks=snippet.blocks,
                )
            )
    return results


def _extract_content(base_url: str, file_match: dict) -> str | None:
    content = file_match.get("Content")
    if isinstance(content, str):
        return content
    repository = file_match.get("Repository")
    path = file_match.get("FileName")
    if not repository or not path:
        return None
    return _http_get(
        f"{base_url}/api/file",
        params={"Repository": repository, "File": path},
    )


def _build_match(
    content: str,
    line_number: int,
    preview: str,
    request: SearchRequest,
) -> MatchResult | None:
    if not content:
        return None
    if line_number <= 0:
        return find_match(content, request)

    needle = decode_literal_query(request.query)
    if not needle:
        return find_match(content, request)

    idx = preview.find(needle)
    if idx == -1:
        match = find_match(content, request)
        return match

    lines = content.splitlines()
    start_offset = _offset_for_line(lines, line_number - 1)
    start = start_offset + idx
    end = start + len(needle)
    return MatchResult(start=start, end=end, line_number=line_number)


def _offset_for_line(lines: Sequence[str], line_index: int) -> int:
    offset = 0
    for idx in range(min(line_index, len(lines))):
        offset += len(lines[idx]) + 1
    return offset


def _snippet_lines() -> int:
    try:
        return settings.SEARCH_CONFIG["snippet_lines"]
    except (ImproperlyConfigured, AttributeError, KeyError):  # pragma: no cover - fallback for tests
        return 8


def _extract_duration(stats: dict, data: dict, start: float) -> int:
    duration = stats.get("Duration") or data.get("Duration")
    if duration is not None:
        try:
            return int(float(duration) * 1000)
        except (TypeError, ValueError):  # pragma: no cover - defensive fallback
            pass
    return int((time.monotonic() - start) * 1000)


def _extract_total(stats: dict, fallback: int) -> int:
    total = stats.get("MatchCount") or stats.get("FileCount")
    try:
        return int(total)
    except (TypeError, ValueError):  # pragma: no cover - fallback when stats missing
        return fallback


def _http_post(url: str, payload: dict, *, timeout: float = DEFAULT_TIMEOUT) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request_obj = urllib_request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(request_obj, timeout=timeout) as response:
        body = response.read()
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def _http_get(url: str, params: dict[str, str], *, timeout: float = DEFAULT_TIMEOUT) -> str:
    query = parse.urlencode(params)
    target = f"{url}?{query}" if query else url
    with urllib_request.urlopen(target, timeout=timeout) as response:
        body = response.read()
    return body.decode("utf-8")


def _resolve_offset(request: SearchRequest) -> int:
    if request.cursor:
        try:
            return max(int(request.cursor), 0)
        except (TypeError, ValueError):
            return 0
    return max((request.page - 1) * request.size, 0)


def _build_next_cursor(offset: int, size: int, total: int) -> str | None:
    next_offset = offset + size
    if next_offset >= total:
        return None
    return str(next_offset)
