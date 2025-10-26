from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

from django.core.cache import cache
from django.http import JsonResponse

_PERIOD_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
}


def ratelimit(key: str, rate: str, block: bool = False) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    limit, window = _parse_rate(rate)

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            identifier = _resolve_identifier(request, key)
            if not identifier:
                return view_func(request, *args, **kwargs)

            cache_key = _cache_key(identifier, key, window)
            added = cache.add(cache_key, 1, timeout=window)
            if added:
                return view_func(request, *args, **kwargs)

            try:
                current = cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, timeout=window)
                current = 1

            if current > limit:
                if block:
                    return JsonResponse({"detail": "Too many requests"}, status=429)
                request.limited = True  # type: ignore[attr-defined]
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def _parse_rate(rate: str) -> tuple[int, int]:
    try:
        count_str, period_str = rate.split("/", 1)
        count = int(count_str)
        window = _PERIOD_SECONDS[period_str[0].lower()]
    except (ValueError, KeyError, IndexError) as exc:  # pragma: no cover - guard
        raise ValueError(f"Invalid rate: {rate}") from exc
    return count, window


def _resolve_identifier(request, key: str) -> str | None:
    if key.startswith("ip-or-header:"):
        header_name = key.split(":", 1)[1]
        header_value = _get_header(request, header_name)
        return header_value or _get_ip(request)
    if key == "ip":
        return _get_ip(request)
    if key.startswith("header:"):
        header_name = key.split(":", 1)[1]
        return _get_header(request, header_name)
    return None


def _get_ip(request) -> str | None:
    return request.META.get("REMOTE_ADDR")


def _get_header(request, header_name: str) -> str | None:
    meta_key = "HTTP_" + header_name.replace("-", "_").upper()
    value = request.META.get(meta_key)
    if not value:
        return None
    return value.split(",")[0].strip()


def _cache_key(identifier: str, key: str, window: int) -> str:
    bucket = int(time.time() // window)
    return f"ratelimit:{key}:{identifier}:{bucket}"
