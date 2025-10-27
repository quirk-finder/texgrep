from __future__ import annotations

import sys
import types
from typing import Any, cast

from django.core.cache import cache
from django.http import JsonResponse
from django.test import Client, override_settings
from django.urls import path

from search.ratelimit import ratelimit


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
