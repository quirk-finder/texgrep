from __future__ import annotations

import sys
import types
import itertools
from typing import Any, cast

from django.core.cache import cache
from django.http import JsonResponse
from django.test import Client, override_settings
from django.urls import path

from search.ratelimit import ratelimit


_module_counter = itertools.count()


def test_ratelimit_blocks_after_threshold() -> None:
    cache.clear()
    client = Client()

    @ratelimit(key="ip", rate="1/m", block=True)
    def limited_view(request):  # type: ignore[no-untyped-def]
        return JsonResponse({"status": "ok"})

    module_name = "search.tests._tmp_ratelimit_urls"
    urlconf = types.ModuleType(module_name)
    cast(Any, urlconf).urlpatterns = [path("limited/", limited_view)]  # ここだけ Any に
    sys.modules[module_name] = urlconf

    try:
        with override_settings(ROOT_URLCONF=module_name):
            first = client.get("/limited/", REMOTE_ADDR="127.0.0.1")
            assert first.status_code == 200
            assert first.json() == {"status": "ok"}

            second = client.get("/limited/", REMOTE_ADDR="127.0.0.1")
            assert second.status_code == 429
            assert second.json() == {"detail": "Too many requests"}
    finally:
        sys.modules.pop(module_name, None)
        cache.clear()


def _register_view(view):  # type: ignore[no-untyped-def]
    module_name = f"search.tests._tmp_ratelimit_urls_{next(_module_counter)}"
    urlconf = types.ModuleType(module_name)
    cast(Any, urlconf).urlpatterns = [path("limited/", view)]
    sys.modules[module_name] = urlconf
    return module_name


def test_ratelimit_non_blocking_sets_limited_flag() -> None:
    cache.clear()
    client = Client()

    @ratelimit(key="ip", rate="1/m", block=False)
    def limited_view(request):  # type: ignore[no-untyped-def]
        limited = getattr(request, "limited", False)
        return JsonResponse({"limited": limited})

    module_name = _register_view(limited_view)

    try:
        with override_settings(ROOT_URLCONF=module_name):
            first = client.get("/limited/", REMOTE_ADDR="127.0.0.1")
            assert first.status_code == 200
            assert first.json() == {"limited": False}

            second = client.get("/limited/", REMOTE_ADDR="127.0.0.1")
            assert second.status_code == 200
            assert second.json() == {"limited": True}
    finally:
        sys.modules.pop(module_name, None)
        cache.clear()


def test_ratelimit_prefers_forwarded_header_over_remote_addr() -> None:
    cache.clear()
    client = Client()

    @ratelimit(key="ip-or-header:X-Forwarded-For", rate="1/m", block=True)
    def limited_view(request):  # type: ignore[no-untyped-def]
        return JsonResponse({"status": "ok"})

    module_name = _register_view(limited_view)

    try:
        with override_settings(ROOT_URLCONF=module_name):
            first = client.get(
                "/limited/",
                REMOTE_ADDR="10.0.0.1",
                HTTP_X_FORWARDED_FOR="203.0.113.1",
            )
            assert first.status_code == 200

            second = client.get(
                "/limited/",
                REMOTE_ADDR="10.0.0.2",
                HTTP_X_FORWARDED_FOR="203.0.113.1",
            )
            assert second.status_code == 429
    finally:
        sys.modules.pop(module_name, None)
        cache.clear()


def test_ratelimit_falls_back_to_ip_when_header_missing() -> None:
    cache.clear()
    client = Client()

    @ratelimit(key="ip-or-header:X-Forwarded-For", rate="1/m", block=True)
    def limited_view(request):  # type: ignore[no-untyped-def]
        return JsonResponse({"status": "ok"})

    module_name = _register_view(limited_view)

    try:
        with override_settings(ROOT_URLCONF=module_name):
            first = client.get("/limited/", REMOTE_ADDR="10.0.0.3")
            assert first.status_code == 200

            second = client.get("/limited/", REMOTE_ADDR="10.0.0.3")
            assert second.status_code == 429
    finally:
        sys.modules.pop(module_name, None)
        cache.clear()
